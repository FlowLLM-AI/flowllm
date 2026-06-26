"""Demo for ``fl --demo --x 1 --y 2``."""

from .cli import BaseConfig, BaseFlow, register


class DemoConfig(BaseConfig):
    """Configuration for the demo addition flow."""

    x: int
    y: int


@register("demo")
class DemoFlow(BaseFlow[DemoConfig]):
    """Flow that adds two demo configuration values."""

    output_keys = ["result"]

    def build_steps(self) -> list:
        """Return the demo addition step."""
        return [self.add]

    def add(self) -> None:
        """Store the sum of the configured values in the context."""
        self.context["result"] = self.config.x + self.config.y
