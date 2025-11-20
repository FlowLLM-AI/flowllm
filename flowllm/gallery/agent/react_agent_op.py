"""Reactive agent operator that orchestrates tool-augmented LLM reasoning."""

import datetime
import time
from typing import List, Dict

from loguru import logger

from ...core.context import C, BaseContext
from ...core.enumeration import Role
from ...core.op import BaseAsyncToolOp
from ...core.schema import Message, ToolCall


@C.register_op()
class ReactAgentOp(BaseAsyncToolOp):
    """React-style agent capable of iterative tool invocation."""

    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_30b_instruct",
        max_steps: int = 5,
        tool_call_interval: float = 1.0,
        add_think_tool: bool = False,
        **kwargs,
    ):
        """Initialize the agent runtime configuration."""
        super().__init__(llm=llm, **kwargs)
        self.max_steps: int = max_steps
        self.tool_call_interval: float = tool_call_interval
        self.add_think_tool: bool = add_think_tool

    def build_tool_call(self) -> ToolCall:
        """Expose metadata describing how to invoke the agent."""
        return ToolCall(
            **{
                "description": "A React agent that answers user queries.",
                "input_schema": {
                    "query": {
                        "type": "string",
                        "description": "query",
                        "required": False,
                    },
                    "messages": {
                        "type": "array",
                        "description": "messages",
                        "required": False,
                    },
                },
            },
        )

    async def build_tool_op_dict(self) -> dict:
        """Collect available tool operators from the execution context."""
        assert isinstance(self.ops, BaseContext), "self.ops must be BaseContext"
        tool_op_dict: Dict[str, BaseAsyncToolOp] = {
            op.tool_call.name: op for op in self.ops.values() if isinstance(op, BaseAsyncToolOp)
        }
        for op in tool_op_dict.values():
            op.language = self.language
        return tool_op_dict

    async def build_messages(self) -> List[Message]:
        """Build the initial message history for the LLM."""
        if "query" in self.input_dict:
            query: str = self.input_dict["query"]
            now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            messages = [
                Message(role=Role.SYSTEM, content=self.prompt_format(prompt_name="system_prompt", time=now_time)),
                Message(role=Role.USER, content=query),
            ]
            logger.info(f"round0.system={messages[0].model_dump_json()}")
            logger.info(f"round0.user={messages[1].model_dump_json()}")

        elif "messages" in self.input_dict:
            messages = self.input_dict["messages"]
            messages = [Message(**x) for x in messages]

            logger.info(f"round0.user={messages[-1].model_dump_json()}")
        else:
            raise ValueError("input_dict must contain either 'query' or 'messages'")

        return messages

    async def before_chat(self, messages: List[Message]):
        """Prepare the message history for the LLM."""
        return messages

    async def async_execute(self):
        """Main execution loop that alternates LLM calls and tool invocations."""
        from ..think_tool_op import ThinkToolOp

        think_op = ThinkToolOp(language=self.language)
        tool_op_dict = await self.build_tool_op_dict()
        if self.add_think_tool:
            tool_op_dict["think_tool"] = think_op

        messages = await self.build_messages()

        for i in range(self.max_steps):
            messages = await self.before_chat(messages)

            assistant_message: Message = await self.llm.achat(
                messages=messages,
                tools=[op.tool_call for op in tool_op_dict.values()],
            )
            messages.append(assistant_message)
            logger.info(f"round{i + 1}.assistant={assistant_message.model_dump_json()}")

            if not assistant_message.tool_calls:
                break

            op_list: List[BaseAsyncToolOp] = []
            has_think_tool_flag: bool = False
            for j, tool_call in enumerate(assistant_message.tool_calls):
                if tool_call.name == think_op.tool_call.name:
                    has_think_tool_flag = True

                if tool_call.name not in tool_op_dict:
                    logger.exception(f"unknown tool_call.name={tool_call.name}")
                    continue

                logger.info(f"round{i + 1}.{j} submit tool_calls={tool_call.name} argument={tool_call.argument_dict}")

                op_copy: BaseAsyncToolOp = tool_op_dict[tool_call.name].copy()
                op_copy.tool_call.id = tool_call.id
                op_list.append(op_copy)
                self.submit_async_task(op_copy.async_call, **tool_call.argument_dict)
                time.sleep(self.tool_call_interval)

            await self.join_async_task()

            for j, op in enumerate(op_list):
                logger.info(f"round{i + 1}.{j} join tool_result={op.output}")
                tool_result = str(op.output)
                tool_message = Message(role=Role.TOOL, content=tool_result, tool_call_id=op.tool_call.id)
                messages.append(tool_message)

            if self.add_think_tool:
                if not has_think_tool_flag:
                    tool_op_dict["think_tool"] = think_op
                else:
                    tool_op_dict.pop("think_tool")

        self.set_output(messages[-1].content)
        self.context.response.messages = messages
