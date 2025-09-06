import asyncio
import datetime
import json
import time
from typing import List, Dict

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op import BaseToolOp
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.message import Message, Role
from flowllm.schema.tool_call import ToolCall


@C.register_op(name="react_llm_op")
class ReactLLMOp(BaseToolOp):
    file_path: str = __file__

    def __init__(self, llm="qwen3_30b_instruct", **kwargs):
        super().__init__(llm=llm, **kwargs)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "query_llm",
            "description": "use this query to query an LLM",
            "input_schema": {
                "query": {
                    "type": "str",
                    "description": "search keyword",
                    "required": True
                }
            }
        })

    async def async_execute(self):
        query: str = self.context.query

        max_steps: int = int(self.op_params.get("max_steps", 10))
        from flowllm.op import BaseToolOp
        from flowllm.op.search import DashscopeSearchOp

        tools: List[BaseToolOp] = [DashscopeSearchOp(save_answer=True)]
        tool_dict: Dict[str, BaseToolOp] = {x.tool_call.name: x for x in tools}
        for name, tool_call in tool_dict.items():
            logger.info(f"name={name} "
                        f"tool_call={json.dumps(tool_call.tool_call.simple_input_dump(), ensure_ascii=False)}")

        now_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_prompt = self.prompt_format(prompt_name="role_prompt",
                                         time=now_time,
                                         tools=",".join(list(tool_dict.keys())),
                                         query=query)
        messages: List[Message] = [Message(role=Role.USER, content=user_prompt)]
        logger.info(f"step.0 user_prompt={user_prompt}")

        for i in range(max_steps):
            assistant_message: Message = await self.llm.achat(messages, tools=[x.tool_call for x in tools])
            messages.append(assistant_message)
            logger.info(f"assistant.round{i}.reasoning_content={assistant_message.reasoning_content}\n"
                        f"content={assistant_message.content}\n"
                        f"tool.size={len(assistant_message.tool_calls)}")

            if not assistant_message.tool_calls:
                break

            for j, tool_call in enumerate(assistant_message.tool_calls):
                logger.info(f"submit step={i} tool_calls.name={tool_call.name} argument_dict={tool_call.argument_dict}")

                if tool_call.name not in tool_dict:
                    logger.warning(f"step={i} no tool_call.name={tool_call.name}")
                    continue

                self.submit_async_task(tool_dict[tool_call.name].copy().async_call,
                                       context=self.context.copy(**tool_call.argument_dict))
                time.sleep(1)

            task_results = await self.join_async_task()

            for j, tool_result in enumerate(task_results):
                tool_call = assistant_message.tool_calls[j]
                logger.info(f"submit step.index={i}.{j} tool_result={tool_result}")
                if isinstance(tool_result, FlowResponse):
                    tool_result = tool_result.answer
                else:
                    tool_result = str(tool_result)
                tool_message = Message(role=Role.TOOL, content=tool_result, tool_call_id=tool_call.id)
                messages.append(tool_message)

        self.context.response.messages = messages
        self.context.response.answer = messages[-1].content


async def main():
    C.set_service_config().init_by_service_config()
    context = FlowContext(query="茅台和五粮现在股价多少？")

    op = ReactLLMOp()
    result = await op.async_call(context=context)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
