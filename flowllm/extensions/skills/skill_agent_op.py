"""Skill agent operation for orchestrating skill-based task execution.

This module provides the SkillAgentOp class which coordinates the execution
of skills by managing tool calls and LLM interactions.
"""

from typing import List

from loguru import logger

from ...core.context import C
from ...core.enumeration import Role
from ...core.op import BaseAsyncToolOp, BaseAsyncOp
from ...core.schema import Message


@C.register_op()
class SkillAgentOp(BaseAsyncOp):
    """An agent operation that orchestrates skill-based task execution.

    This operation manages a conversation loop with an LLM, allowing it to
    use various skill-related tools (load_skill, read_reference_file,
    run_shell_command) to complete tasks. It iterates up to max_iterations
    times, allowing the LLM to make multiple tool calls as needed.

    Attributes:
        max_iterations: Maximum number of iterations for the agent loop.
    """

    file_path: str = __file__

    def __init__(self, llm: str = "qwen3_max_instruct", max_iterations: int = 10, **kwargs):
        """Initialize the SkillAgentOp.

        Args:
            llm: The LLM model identifier to use for chat interactions.
            max_iterations: Maximum number of agent loop iterations.
            **kwargs: Additional arguments passed to the base class.
        """
        super().__init__(llm=llm, **kwargs)
        self.max_iterations: int = max_iterations

    async def async_execute(self):
        """Execute the skill agent operation.

        This method orchestrates the skill-based task execution by:
        1. Loading skill metadata
        2. Setting up the system prompt with available skills
        3. Running an iterative loop where the LLM can use tools
        4. Collecting tool outputs and continuing the conversation
        5. Setting the final response in the context

        The operation stops when the LLM no longer makes tool calls or
        max_iterations is reached.
        """
        query: str = self.context.query
        skill_dir: str = self.context.skill_dir
        logger.info(f"SkillAgentOp processing query: {query} with access to skills in {skill_dir}")

        load_metadata_op: BaseAsyncToolOp = self.ops.load_metadata
        load_skill_op: BaseAsyncToolOp = self.ops.load_skill
        read_reference_op: BaseAsyncToolOp = self.ops.read_reference
        run_shell_op: BaseAsyncToolOp = self.ops.run_shell

        await load_metadata_op.async_call(skill_dir=skill_dir)
        skill_metadata = load_metadata_op.output
        logger.info(f"SkillAgentOp loaded skill metadata: {skill_metadata}")
        system_prompt = self.prompt_format(
            "system_prompt",
            skill_dir=skill_dir,
            skill_metadata=skill_metadata,
        )

        messages = [
            Message(role=Role.SYSTEM, content=system_prompt),
            Message(role=Role.USER, content=query),
        ]

        tool_op_dict: dict = {op.tool_call.name: op for op in [load_skill_op, read_reference_op, run_shell_op]}

        for i in range(self.max_iterations):
            assistant_message = await self.llm.achat(
                messages=messages,
                tools=[x.tool_call for x in tool_op_dict.values()],
            )
            messages.append(assistant_message)
            logger.info(assistant_message.model_dump_json())

            if not assistant_message.tool_calls:
                break

            ops: List[BaseAsyncToolOp] = []
            for j, tool in enumerate(assistant_message.tool_calls):
                op: BaseAsyncToolOp = tool_op_dict[tool.name].copy()
                op.tool_call.id = tool.id
                ops.append(op)
                logger.info(f"{self.name} submit op{j}={op.name} argument={tool.argument_dict}")
                self.submit_async_task(op.async_call, skill_dir=skill_dir, **tool.argument_dict)

            await self.join_async_task()

            for op in ops:
                messages.append(Message(role=Role.TOOL, content=op.output, tool_call_id=op.tool_call.id))
                tool_content = f"[{self.name}.{i}.{op.name}] {op.output[:200]}...\n\n"
                logger.info(tool_content)

        self.context.response.answer = messages[-1].content
        self.context.response.metadata["messages"] = [x.simple_dump() for x in messages]
