import datetime
import time
from typing import List, Dict

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_llm_op import BaseLLMOp
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.message import Message, Role


@C.register_op()
class ReactV1Op(BaseLLMOp):
    file_path: str = __file__

    def execute(self):
        query: str = self.context.query

        max_steps: int = int(self.op_params.get("max_steps", 10))
        from flowllm.flow.base_tool_flow import BaseToolFlow
        from flowllm.flow.gallery import DashscopeSearchToolFlow, CodeToolFlow, TerminateToolFlow

        tools: List[BaseToolFlow] = [DashscopeSearchToolFlow(), CodeToolFlow(), TerminateToolFlow()]

        """
        NOTE : x.tool_call.name != x.name
        `x.tool_call.name` is tool's namex.name is flow's name(unique service name)
        """
        tool_dict: Dict[str, BaseToolFlow] = {x.tool_call.name: x for x in tools}
        now_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        has_terminate_tool = False

        user_prompt = self.prompt_format(prompt_name="role_prompt",
                                         time=now_time,
                                         tools=",".join(list(tool_dict.keys())),
                                         query=query)
        messages: List[Message] = [Message(role=Role.USER, content=user_prompt)]
        logger.info(f"step.0 user_prompt={user_prompt}")

        for i in range(max_steps):
            if has_terminate_tool:
                assistant_message: Message = self.llm.chat(messages)
            else:
                assistant_message: Message = self.llm.chat(messages, tools=[x.tool_call for x in tools])

            messages.append(assistant_message)
            logger.info(f"assistant.{i}.reasoning_content={assistant_message.reasoning_content}\n"
                        f"content={assistant_message.content}\n"
                        f"tool.size={len(assistant_message.tool_calls)}")

            if has_terminate_tool:
                break

            for tool in assistant_message.tool_calls:
                if tool.name == "terminate":
                    has_terminate_tool = True
                    logger.info(f"step={i} find terminate tool, break.")
                    break

            if not has_terminate_tool and not assistant_message.tool_calls:
                logger.warning(f"【bugfix】step={i} no tools, break.")
                has_terminate_tool = True

            for j, tool_call in enumerate(assistant_message.tool_calls):
                logger.info(f"submit step={i} tool_calls.name={tool_call.name} argument_dict={tool_call.argument_dict}")

                if tool_call.name not in tool_dict:
                    logger.warning(f"step={i} no tool_call.name={tool_call.name}")
                    continue

                self.submit_task(tool_dict[tool_call.name].__call__, **tool_call.argument_dict)
                time.sleep(1)

            if not has_terminate_tool:
                user_content_list = []
                for tool_result, tool_call in zip(self.join_task(), assistant_message.tool_calls):
                    logger.info(f"submit step={i} tool_calls.name={tool_call.name} tool_result={tool_result}")
                    if isinstance(tool_result, FlowResponse):
                        tool_result = tool_result.answer
                    else:
                        tool_result = str(tool_result)
                    user_content_list.append(f"<tool_response>\n{tool_result}\n</tool_response>")
                user_content_list.append(self.prompt_format(prompt_name="next_prompt"))
                assistant_message.tool_calls.clear()
                messages.append(Message(role=Role.USER, content="\n".join(user_content_list)))

            else:
                assistant_message.tool_calls.clear()
                query = self.prompt_format(prompt_name="final_prompt", query=query)
                messages.append(Message(role=Role.USER, content=query))

        # Store results in context instead of response
        self.context.response.messages = messages
        self.context.response.answer = messages[-1].content


if __name__ == "__main__":
    C.set_default_service_config().init_by_service_config()
    context = FlowContext(query="茅台和五粮现在股价多少？")

    op = ReactV1Op()
    op(context=context)
