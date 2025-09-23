from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.op.base_op import BaseOp
from flowllm.schema.tool_call import ToolCall


class SequentialOp(BaseAsyncToolOp):

    @property
    def short_name(self) -> str:
        return self.ops[0].short_name

    def build_tool_call(self) -> ToolCall:
        first_op = self.ops[0]
        assert isinstance(first_op, BaseAsyncToolOp)
        return first_op.build_tool_call()

    def execute(self):
        for op in self.ops:
            assert op.async_mode is False
            op.call(context=self.context)

    async def async_execute(self):
        for op in self.ops:
            assert op.async_mode is True
            assert isinstance(op, BaseAsyncOp)
            await op.async_call(context=self.context)

    def __rshift__(self, op: BaseOp):
        if isinstance(op, SequentialOp):
            self.ops.extend(op.ops)
        else:
            self.ops.append(op)
        return self

    def __lshift__(self, op: "BaseOp"):
        raise RuntimeError(f"`<<` is not supported in {self.name}")