import datetime
import json
import time
from typing import List, Dict

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_llm_op import BaseLLMOp
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.message import Message, Role


@C.register_op()
class ReactV2Op(BaseLLMOp):
    file_path: str = __file__

    def execute(self):
        query: str = self.context.query

        max_steps: int = int(self.op_params.get("max_steps", 10))
        from flowllm.flow.base_tool_flow import BaseToolFlow
        from flowllm.flow.gallery import DashscopeSearchToolFlow, CodeToolFlow

        tools: List[BaseToolFlow] = [DashscopeSearchToolFlow(), CodeToolFlow()]

        """
        NOTE : x.tool_call.name != x.name
        `x.tool_call.name` is tool's namex.name is flow's name(unique service name)
        """
        tool_dict: Dict[str, BaseToolFlow] = {x.tool_call.name: x for x in tools}
        for name, tool_call in tool_dict.items():
            logger.info(f"name={name} "
                        f"tool_call={json.dumps(tool_call.tool_call.simple_input_dump(), ensure_ascii=False)}")

        now_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        has_terminate_tool = False

        user_prompt = self.prompt_format(prompt_name="role_prompt",
                                         time=now_time,
                                         tools=",".join(list(tool_dict.keys())),
                                         query=query)
        messages: List[Message] = [Message(role=Role.USER, content=user_prompt)]
        logger.info(f"step.0 user_prompt={user_prompt}")

        for i in range(max_steps):
            assistant_message: Message = self.llm.chat(messages, tools=[x.tool_call for x in tools])
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

                self.submit_task(tool_dict[tool_call.name].__call__, **tool_call.argument_dict)
                time.sleep(1)

            for i, (tool_result, tool_call) in enumerate(zip(self.join_task(), assistant_message.tool_calls)):
                logger.info(f"submit step={i} tool_calls.name={tool_call.name} tool_result={tool_result}")
                if isinstance(tool_result, FlowResponse):
                    tool_result = tool_result.answer
                else:
                    tool_result = str(tool_result)
                tool_message = Message(role=Role.TOOL, content=tool_result, tool_call_id=tool_call.id)
                messages.append(tool_message)

        # Store results in context instead of response
        self.context.response.messages = messages
        self.context.response.answer = messages[-1].content


if __name__ == "__main__":
    C.set_default_service_config().init_by_service_config()
    context = FlowContext(query="茅台和五粮现在股价多少？")

    op = ReactV2Op()
    op(context=context)
