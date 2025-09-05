from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.op.llm import SimpleLLMOp, ReactLLMOp, StreamLLMOp
from flowllm.op.search import DashscopeSearchOp
from flowllm.op.search import TavilySearchOp
from flowllm.schema.tool_call import ToolCall


@C.register_tool_flow()
class TavilySearchToolFlow(BaseToolFlow):

    def __init__(self,
                 use_async: bool = True,
                 stream: bool = False,
                 service_type: str = "http+mcp",
                 **kwargs):
        super().__init__(use_async=use_async, stream=stream, service_type=service_type, **kwargs)

    def build_flow(self):
        return TavilySearchOp()

    def build_tool_call(self) -> ToolCall:
        return self.flow_op.tool_call

    def after_flow(self, context):
        context.response.answer = context.tavily_search_result


@C.register_tool_flow()
class DashscopeSearchToolFlow(BaseToolFlow):

    def __init__(self,
                 use_async: bool = True,
                 stream: bool = False,
                 service_type: str = "http+mcp",
                 **kwargs):
        super().__init__(use_async=use_async, stream=stream, service_type=service_type, **kwargs)

    def build_flow(self):
        return DashscopeSearchOp()

    def build_tool_call(self) -> ToolCall:
        return self.flow_op.tool_call

    def after_flow(self, context):
        context.response.answer = context.tavily_search_result


@C.register_tool_flow(name="stream_llm_tool_flow")
class StreamLLMToolFlow(BaseToolFlow):

    def __init__(self,
                 use_async: bool = True,
                 stream: bool = True,
                 service_type: str = "http",
                 **kwargs):
        super().__init__(use_async=use_async, stream=stream, service_type=service_type, **kwargs)

    def build_flow(self):
        return StreamLLMOp()

    def build_tool_call(self) -> ToolCall:
        return self.flow_op.tool_call


@C.register_tool_flow(name="simple_llm_tool_flow")
class SimpleLLMToolFlow(BaseToolFlow):

    def __init__(self,
                 use_async: bool = True,
                 stream: bool = False,
                 service_type: str = "http",
                 **kwargs):
        super().__init__(use_async=use_async, stream=stream, service_type=service_type, **kwargs)

    def build_flow(self):
        return SimpleLLMOp()

    def build_tool_call(self) -> ToolCall:
        return self.flow_op.tool_call


@C.register_tool_flow(name="react_llm_tool_flow")
class ReactLLMToolFlow(BaseToolFlow):

    def __init__(self,
                 use_async: bool = True,
                 stream: bool = False,
                 service_type: str = "http",
                 **kwargs):
        super().__init__(use_async=use_async, stream=stream, service_type=service_type, **kwargs)

    def build_flow(self):
        return ReactLLMOp()

    def build_tool_call(self) -> ToolCall:
        return self.flow_op.tool_call
