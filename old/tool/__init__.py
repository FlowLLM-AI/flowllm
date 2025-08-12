from old.utils.registry import Registry

TOOL_REGISTRY = Registry()

from old.tool.code_tool import CodeTool
from old.tool.dashscope_search_tool import DashscopeSearchTool
from old.tool.tavily_search_tool import TavilySearchTool
from old.tool.terminate_tool import TerminateTool
from old.tool.mcp_tool import MCPTool
