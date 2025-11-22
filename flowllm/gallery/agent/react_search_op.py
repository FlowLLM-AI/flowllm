"""ReactAgentOp specialization that ensures search capability is available."""

from typing import Dict

from .react_agent_op import ReactAgentOp
from ...core.context import C
from ...core.op import BaseAsyncToolOp


@C.register_op()
class ReactSearchOp(ReactAgentOp):
    """Agent that guarantees a search tool fallback when none are configured."""

    async def build_tool_op_dict(self) -> dict:
        """Extend parent tools with a default search operator when needed."""
        tool_op_dict: Dict[str, BaseAsyncToolOp] = await super().build_tool_op_dict()
        if not tool_op_dict:
            from ..search.dashscope_search_op import DashscopeSearchOp

            search_op = DashscopeSearchOp()
            tool_op_dict[search_op.tool_call.name] = search_op

        return tool_op_dict
