"""Simple step that adds two numbers — used as a demo tool for agent wrapper."""

from ..base_step import BaseStep
from ...components import R


@R.register("add_step")
class AddStep(BaseStep):
    """Add two numbers (a, b from context) and return the sum as response answer."""

    async def execute(self):
        assert self.context is not None
        try:
            a, b = float(self.context.get("a", 0.0)), float(self.context.get("b", 0.0))
        except (TypeError, ValueError) as exc:
            self.context.response.success = False
            self.context.response.answer = f"Invalid add arguments: {exc}"
            return self.context.response
        result = a + b
        self.logger.info(f"[{self.name}] add({a}, {b}) = {result}")
        self.context.response.success = True
        self.context.response.answer = str(result)
        self.context.response.metadata.update({"a": a, "b": b, "result": result})
        return self.context.response
