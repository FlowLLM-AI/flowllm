"""Tiny local flow runner used by the ``fl`` command."""

import json
import sys
from collections.abc import Callable
from typing import Any, Generic, TypeVar, get_args, get_origin

from pydantic import BaseModel, ConfigDict


class BaseConfig(BaseModel):
    """Base model for flow configuration values."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


ConfigT = TypeVar("ConfigT", bound=BaseConfig)
Step = Callable[[], Any]
_FLOW_REGISTRY: dict[str, type["BaseFlow"]] = {}


class BaseFlow(Generic[ConfigT]):
    """Base class for lightweight command-line flows."""

    config_class: type[ConfigT]
    output_keys: list[str] = []

    def __init_subclass__(cls, **kwargs) -> None:
        """Infer the configuration model from the generic base when possible."""
        super().__init_subclass__(**kwargs)
        if "config_class" in cls.__dict__:
            return
        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is BaseFlow:
                config_class = get_args(base)[0]
                if isinstance(config_class, type) and issubclass(config_class, BaseConfig):
                    cls.config_class = config_class
                return

    def __init__(self, config: ConfigT, **kwargs) -> None:
        self.config = config
        self.context = dict(kwargs)

    def build_steps(self) -> list[Step]:
        """Return the ordered callables that make up this flow."""
        raise NotImplementedError

    @property
    def output(self) -> dict:
        """Return the configured output keys from the flow context."""
        return {key: self.context[key] for key in self.output_keys}

    def execute(self) -> dict:
        """Run each step and return the flow output."""
        for step in self.build_steps():
            step()
        return self.output


def register(name: str) -> Callable[[type[BaseFlow]], type[BaseFlow]]:
    """Register a flow class under a command-line action name."""
    action = name.strip()
    if not action:
        raise ValueError("Flow action cannot be empty")

    def decorator(cls: type[BaseFlow]) -> type[BaseFlow]:
        if not isinstance(cls, type) or not issubclass(cls, BaseFlow):
            raise ValueError(f"Registered flow must subclass BaseFlow: {cls!r}")
        _FLOW_REGISTRY[action] = cls
        return cls

    return decorator


def get_flow(name: str) -> type[BaseFlow]:
    """Return the flow class registered for an action name."""
    if name in _FLOW_REGISTRY:
        return _FLOW_REGISTRY[name]
    available = ", ".join(sorted(_FLOW_REGISTRY)) or "none"
    raise ValueError(f"Unknown flow action: {name}. Available: {available}")


def list_flows() -> dict[str, type[BaseFlow]]:
    """Return the currently registered flow classes by action name."""
    return dict(_FLOW_REGISTRY)


def parse_config_args(args: list[str]) -> dict:
    """Parse ``--field value`` command-line pairs into config data."""
    if len(args) % 2:
        raise ValueError("Config args must be pairs like --x 1")

    result: dict = {}
    for key, value in zip(args[0::2], args[1::2], strict=True):
        if not key.startswith("--") or key == "--":
            raise ValueError(f"Config key must look like --field: {key}")
        result[key[2:].replace("-", "_")] = value
    return result


def run_action(action: str, config_args: list[str]) -> dict:
    """Build and execute a registered flow for the given CLI arguments."""
    flow_cls = get_flow(action)
    config_class = getattr(flow_cls, "config_class", None)
    if not isinstance(config_class, type) or not issubclass(config_class, BaseConfig):
        raise ValueError(f"Flow '{action}' must define config_class as a BaseConfig subclass")

    config = config_class.model_validate(parse_config_args(config_args))
    return flow_cls(config).execute()


def print_flow_list() -> None:
    """Print registered flows in a tab-separated list."""
    for name, flow_cls in sorted(list_flows().items()):
        print(f"{name}\t{flow_cls.__module__}.{flow_cls.__name__}")


def parse_action_arg(arg: str) -> str:
    """Parse the first command-line flag into a flow action name."""
    if not arg.startswith("--") or arg == "--":
        raise ValueError(f"Flow action must look like --action: {arg}")
    return arg[2:].replace("-", "_")


def _print_help() -> None:
    """Print command usage information."""
    print("Usage: fl --list")
    print("       fl --action --field value ...")


def main(argv: list[str] | None = None) -> None:
    """Run the lightweight flow command-line interface."""
    args: list[str] = sys.argv[1:] if argv is None else argv
    if not args or args[0] in ("-h", "--help"):
        _print_help()
        return

    if args[0] == "--list":
        print_flow_list()
        return

    print(json.dumps(run_action(parse_action_arg(args[0]), args[1:]), ensure_ascii=False))


if __name__ == "__main__":
    main()
