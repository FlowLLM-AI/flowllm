import asyncio
import datetime
import json
import time
from typing import List, Dict

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message, Role
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class ReactLLMOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self, llm: str = "qwen3_30b_instruct", save_answer: bool = True, **kwargs):
        super().__init__(llm=llm, save_answer=save_answer, **kwargs)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "query_llm",
            "description": "use this query to query an LLM",
            "input_schema": {
                "query": {
                    "type": "string",
                    "description": "search keyword",
                    "required": True
                }
            },
            "output_schema": {
                "react_llm_result": {
                    "type": "string",
                    "description": "react llm result",
                }
            }
        })

    async def async_execute(self):
        query: str = self.input_dict["query"]

        max_steps: int = int(self.op_params.get("max_steps", 10))
        from flowllm.op.search import DashscopeSearchOp

        tools: List[BaseAsyncToolOp] = [DashscopeSearchOp()]
        tool_dict: Dict[str, BaseAsyncToolOp] = {x.tool_call.name: x for x in tools}
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

            op_list: List[BaseAsyncToolOp] = []
            for j, tool_call in enumerate(assistant_message.tool_calls):
                logger.info(f"submit step={i} tool_calls.name={tool_call.name} argument_dict={tool_call.argument_dict}")

                if tool_call.name not in tool_dict:
                    logger.warning(f"step={i} no tool_call.name={tool_call.name}")
                    continue

                op_copy = tool_dict[tool_call.name].copy()
                op_list.append(op_copy)
                self.submit_async_task(op_copy.async_call, context=self.context.copy(**tool_call.argument_dict))
                time.sleep(1)

            await self.join_async_task()

            for j, op in enumerate(op_list):
                logger.info(f"submit step.index={i}.{j} tool_result={op.output}")
                tool_result = str(op.output)
                tool_message = Message(role=Role.TOOL, content=tool_result, tool_call_id=op.tool_call.id)
                messages.append(tool_message)

        self.set_result(messages[-1].content)
        self.context.response.messages = messages

async def main():
    from flowllm.app import FlowLLMApp
    async with FlowLLMApp(load_default_config=True):
        context = FlowContext(query="茅台和五粮现在股价多少？")

        op = ReactLLMOp()
        result = await op.async_call(context=context)
        print(result)
        print(op.output)


if __name__ == "__main__":
    asyncio.run(main())
