from datetime import datetime

from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall


class OpenResearchOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "research_topic",
            "description": "Conduct logical and in-depth research based on the research_topic, and finally provide a detailed conclusion on the research_topic.",
            "input_schema": {
                "research_topic": {
                    "type": "string",
                    "description": "research topic",
                    "required": True
                },
            }
        })

    @staticmethod
    def get_today_str() -> str:
        """Get current date formatted for display in prompts and outputs.

        Returns:
            Human-readable date string in format like 'Mon Jan 15, 2024'
        """
        now = datetime.now()
        return f"{now:%a} {now:%b} {now.day}, {now:%Y}"

    async def async_execute(self):
        research_topic: str = self.input_dict["research_topic"]

        assert self.ops, "OpenResearchOp requires a search tool"
        search_op = self.ops[0]
        assert isinstance(search_op, BaseAsyncToolOp)
        research_system_prompt = self.prompt_format(prompt_name="research_system_prompt",
                                                    date=self.get_today_str(),
                                                    mcp_prompt="",
                                                    search_tool=search_op.tool_call.name)

        messages = [
            Message(role=Role.SYSTEM, content=research_system_prompt),
            Message(role=Role.USER, content=research_topic),
        ]

        tools = [

        ]
        assistant_message = await self.llm.achat(messages)