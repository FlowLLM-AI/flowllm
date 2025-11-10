"""ReAct (Reasoning and Acting) search operation module.

This module implements a ReAct agent that answers user queries by reasoning about
the problem and taking actions (such as searching) in an iterative manner. The agent
can use search tools to gather information and provide comprehensive answers.
"""

import datetime
import time
from typing import List

from loguru import logger

from ..core.context import C
from ..core.enumeration import Role
from ..core.op import BaseAsyncToolOp
from ..core.schema import Message
from ..core.schema import ToolCall


@C.register_op()
class ReactSearchOp(BaseAsyncToolOp):
    """A ReAct (Reasoning and Acting) agent for answering queries using search tools.

    This operation implements a ReAct agent that iteratively reasons about user queries
    and takes actions (like searching) to gather information. The agent continues until
    it has enough information to provide a final answer or reaches the maximum number
    of steps.

    Attributes:
        llm: The language model to use for reasoning (default: "qwen3_30b_instruct").
        max_steps: Maximum number of reasoning-action iterations (default: 5).
    """

    file_path: str = __file__

    def __init__(self, llm: str = "qwen3_30b_thinking", max_steps: int = 5, **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.max_steps: int = max_steps

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "A React agent that answers user queries.",
                "input_schema": {
                    "query": {
                        "type": "string",
                        "description": "query",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        query: str = self.input_dict["query"]
        if "search" in self.ops:
            search_op = self.ops.search
        else:
            from .dashscope_search_op import DashscopeSearchOp

            search_op = DashscopeSearchOp()

        assert isinstance(search_op, BaseAsyncToolOp)
        # NOTE search_op.tool_call.name √ search_op.name ×
        tool_dict = {search_op.tool_call.name: search_op}

        now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_prompt = self.prompt_format(
            prompt_name="role_prompt",
            time=now_time,
            tools=",".join(tool_dict.keys()),
            query=query,
        )
        messages: List[Message] = [Message(role=Role.USER, content=user_prompt)]
        logger.info(f"step.0 user_prompt={user_prompt}")

        for i in range(self.max_steps):
            assistant_message: Message = await self.llm.achat(
                messages,
                tools=[op.tool_call for op in tool_dict.values()],
            )
            messages.append(assistant_message)
            logger.info(
                f"assistant.round{i}.reasoning_content={assistant_message.reasoning_content}\n"
                f"content={assistant_message.content}\n"
                f"tool.size={len(assistant_message.tool_calls)}",
            )

            if not assistant_message.tool_calls:
                break

            op_list: List[BaseAsyncToolOp] = []
            for j, tool_call in enumerate(assistant_message.tool_calls):
                logger.info(f"submit step={i} tool_calls.name={tool_call.name} argument_dict={tool_call.argument_dict}")

                if tool_call.name not in tool_dict:
                    logger.exception(f"step={i} no tool_call.name={tool_call.name}")
                    continue

                op_copy = tool_dict[tool_call.name].copy()
                op_list.append(op_copy)
                self.submit_async_task(op_copy.async_call, **tool_call.argument_dict)
                time.sleep(1)

            await self.join_async_task()

            for j, op in enumerate(op_list):
                logger.info(f"submit step.index={i}.{j} tool_result={op.output}")
                tool_result = str(op.output)
                tool_message = Message(role=Role.TOOL, content=tool_result, tool_call_id=op.tool_call.id)
                messages.append(tool_message)

        self.set_output(messages[-1].content)
        self.context.response.messages = messages
