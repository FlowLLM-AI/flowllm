"""Operation for a skill-enabled reactive agent.

This module provides the SkillAgentOp class which extends ReactAgentOp to
automatically use pre-built skills relevant to the query. The agent loads
skill metadata from a specified skill directory and makes those skills
available as tools during the reasoning process.
"""

import datetime
from typing import List

from loguru import logger

from ...core.context import C
from ...core.enumeration import Role
from ...core.op import BaseAsyncToolOp
from ...core.schema import Message, ToolCall
from ...gallery.agent import ReactAgentOp


@C.register_op()
class SkillAgentOp(ReactAgentOp):
    """Reactive agent that automatically uses pre-built skills to answer queries.

    This agent extends ReactAgentOp to provide skill-based reasoning. It loads
    skill metadata from a specified directory and makes those skills available
    as tools during the agent's reasoning process. The agent can automatically
    select and use relevant skills based on the user's query.

    The agent:
    1. Loads skill metadata from the specified skill directory
    2. Builds a system prompt that includes available skills
    3. Uses the React (Reasoning and Acting) pattern to iteratively reason
       and call tools (including skills)
    4. Automatically passes skill_metadata_dict to skill operations when
       they are invoked

    Attributes:
        file_path (str): Path to the operation file, used for prompt loading.
        Inherits all attributes from ReactAgentOp, including:
            - llm: The language model to use (default: "qwen3_max_instruct")
            - max_steps: Maximum number of reasoning steps (default: 5)
            - tool_call_interval: Delay between tool calls in seconds (default: 1.0)
            - add_think_tool: Whether to add a thinking tool (default: False)

    Note:
        - The skill_dir must contain SKILL.md files with valid metadata
        - Skills are loaded via LoadSkillMetadataOp before the agent starts
        - The skill_metadata_dict is stored in context and passed to skill operations
    """

    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_30b_instruct",
        max_steps: int = 50,
        tool_call_interval: float = 1.0,
        add_think_tool: bool = False,
        **kwargs,
    ):
        """Initialize the skill agent with configuration.

        Args:
            llm: The language model identifier to use for reasoning.
                Default is "qwen3_max_instruct".
            max_steps: Maximum number of reasoning steps the agent can take.
                Default is 5. Note: This is passed as max_retries to the parent.
            tool_call_interval: Delay in seconds between tool calls to avoid
                rate limiting. Default is 1.0.
            add_think_tool: Whether to add a thinking tool that allows the agent
                to explicitly reason before taking actions. Default is False.
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        super().__init__(
            llm=llm,
            max_steps=max_steps,
            tool_call_interval=tool_call_interval,
            add_think_tool=add_think_tool,
            **kwargs,
        )

    def build_tool_call(self) -> ToolCall:
        """Build the tool call definition for the skill agent.

        Creates and returns a ToolCall object that defines the skill agent tool.
        This tool requires both query and skill_dir parameters to identify what
        to answer and which skills are available.

        Returns:
            ToolCall: A ToolCall object defining the skill agent tool with
                the following properties:
                - description: Description of what the tool does
                - input_schema: A schema requiring:
                    - "query" (string, required): The user's query to answer
                    - "skill_dir" (string, required): The directory containing
                      skill definitions (SKILL.md files)
        """
        return ToolCall(
            **{
                "description": "Automatically uses pre-built Skills relevant to the query when needed.",
                "input_schema": {
                    "query": {
                        "type": "string",
                        "description": "query",
                        "required": True,
                    },
                    "skill_dir": {
                        "type": "string",
                        "description": "skill dir",
                        "required": True,
                    },
                },
            },
        )

    async def build_messages(self) -> List[Message]:
        """Build the initial messages for the agent conversation.

        Loads skill metadata from the specified skill directory and constructs
        the initial conversation messages. The system prompt includes information
        about available skills, allowing the agent to understand what tools
        are at its disposal.

        The method:
        1. Extracts query and skill_dir from context
        2. Loads skill metadata using LoadSkillMetadataOp
        3. Stores the skill_metadata_dict in context for later use
        4. Formats skill metadata as a list for inclusion in the system prompt
        5. Builds system and user messages with the current time and skill info

        Returns:
            List[Message]: A list containing:
                - A SYSTEM message with the formatted system prompt including:
                  skill directory, current time, and list of available skills
                - A USER message containing the user's query

        Note:
            - The skill_metadata_dict is stored in context.skill_metadata_dict
              for use by skill operations
            - The system prompt is formatted using the "system_prompt" template
              from the operation's prompt file
            - Current time is formatted as "YYYY-MM-DD HH:MM:SS"
        """
        # Extract query and skill directory from context
        query: str = self.context.query
        skill_dir: str = self.context.skill_dir
        logger.info(f"SkillAgentOp processing query: {query} with access to skills in {skill_dir}")

        # Load skill metadata from the skill directory
        # This populates the skill_metadata_dict with all available skills
        from .load_skill_metadata_op import LoadSkillMetadataOp

        op = LoadSkillMetadataOp()
        await op.async_call(skill_dir=skill_dir)
        # Store the skill metadata dictionary in context for use by skill operations
        self.context.skill_metadata_dict = skill_metadata_dict = op.output

        # Format skill metadata as a list for inclusion in the system prompt
        skill_metadata_list = [f"- {k}: {v['description']}" for k, v in skill_metadata_dict.items()]
        logger.info(f"SkillAgentOp loaded skill metadata: {skill_metadata_dict}")

        # Get current time for the system prompt
        now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Build the initial conversation messages
        messages = [
            Message(
                role=Role.SYSTEM,
                content=self.prompt_format(
                    "system_prompt",
                    time=now_time,
                    skill_metadata="\n".join(skill_metadata_list),
                ),
            ),
            Message(role=Role.USER, content=query),
        ]

        return messages

    async def execute_tool(self, op: BaseAsyncToolOp, tool_call: ToolCall):
        """Execute a tool operation with skill metadata context.

        Overrides the parent class method to automatically pass the
        skill_metadata_dict to skill operations when they are invoked.
        This ensures that skill operations have access to the metadata
        they need to function correctly.

        Args:
            op: The tool operation to execute (e.g., LoadSkillOp,
                ReadReferenceFileOp, RunShellCommandOp).
            tool_call: The tool call object containing the arguments
                for the operation.

        Note:
            - The skill_metadata_dict is automatically passed to all tool
              operations, allowing them to look up skill directories
            - Additional arguments from tool_call.argument_dict are also
              passed to the operation
            - The operation is executed asynchronously via submit_async_task
        """
        self.submit_async_task(
            op.async_call,
            skill_metadata_dict=self.context.skill_metadata_dict,
            **tool_call.argument_dict,
        )
