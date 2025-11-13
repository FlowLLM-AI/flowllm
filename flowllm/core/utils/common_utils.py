"""Common utility functions for string conversion, environment loading, content extraction,
and flow expression parsing.

This module provides utility functions for:
- String format conversion (camelCase to snake_case and vice versa)
- Environment variable loading from .env files
- Extracting and parsing content from Markdown code blocks
- Parsing flow expressions into composed `BaseOp` trees
"""

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..op import BaseOp

ENV_LOADED = False


def camel_to_snake(content: str) -> str:
    """Convert a camelCase or PascalCase string to snake_case.

    Args:
        content: The camelCase or PascalCase string to convert.

    Returns:
        The converted snake_case string.

    Example:
        ```python
        camel_to_snake("BaseWorker")
        # 'base_worker'
        camel_to_snake("MyLLMClass")
        # 'my_llm_class'
        ```
    """
    content = content.replace("LLM", "Llm")
    snake_str = re.sub(r"(?<!^)(?=[A-Z])", "_", content).lower()
    return snake_str


def snake_to_camel(content: str) -> str:
    """Convert a snake_case string to PascalCase (camelCase with first letter capitalized).

    Args:
        content: The snake_case string to convert.

    Returns:
        The converted PascalCase string.

    Example:
        ```python
        snake_to_camel("base_worker")
        # 'BaseWorker'
        snake_to_camel("my_llm_class")
        # 'MyLLMClass'
        ```
    """
    camel_str = "".join(x.capitalize() for x in content.split("_"))
    camel_str = camel_str.replace("Llm", "LLM")
    return camel_str


def _load_env(path: Path):
    """Load environment variables from a .env file.

    Reads the specified .env file line by line, parses key-value pairs,
    and sets them as environment variables. Lines starting with '#' are
    treated as comments and skipped.

    Args:
        path: Path to the .env file to load.
    """
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                continue

            line_split = line.strip().split("=", 1)
            if len(line_split) >= 2:
                key = line_split[0].strip()
                value = line_split[1].strip().strip('"')
                os.environ[key] = value


def load_env(path: str | Path = None, enable_log: bool = True):
    """Load environment variables from a .env file.

    This function ensures that environment variables are loaded only once
    (controlled by the ENV_LOADED flag). If a path is provided, it loads
    from that specific path. Otherwise, it searches for a .env file in the
    current directory and up to 4 parent directories.

    Args:
        path: Optional path to the .env file. If None, searches for .env
            in current and parent directories.
        enable_log: Whether to log when the .env file is found and loaded.

    Note:
        The function uses a global flag to ensure it only runs once per
        execution. Subsequent calls will be ignored.
    """
    global ENV_LOADED
    if ENV_LOADED:
        return

    if path is not None:
        path = Path(path)
        if path.exists():
            _load_env(path)
            ENV_LOADED = True

    else:
        for i in range(5):
            path = Path("../" * i + ".env")
            if path.exists():
                if enable_log:
                    logger.info(f"load env_path={path}")
                _load_env(path)
                ENV_LOADED = True
                return

        logger.warning(".env not found")


def singleton(cls):
    """Decorator to create a singleton class.

    Ensures that only one instance of the decorated class is created.
    Subsequent instantiations will return the same instance.

    Args:
        cls: The class to be decorated as a singleton.

    Returns:
        A wrapper function that returns the singleton instance of the class.

    Example:
        ```python
        @singleton
        class Config:
            def __init__(self):
                self.value = 42

        c1 = Config()
        c2 = Config()
        c1 is c2  # True
        ```
    """
    _instance = {}

    def _singleton(*args, **kwargs):
        if cls not in _instance:
            _instance[cls] = cls(*args, **kwargs)
        return _instance[cls]

    return _singleton


def parse_flow_expression(flow_content: str) -> "BaseOp":
    """Parse a textual flow script into a composed `BaseOp` operation tree.

    The flow content must explicitly instantiate op classes that have been
    registered in `C.registry_dict["op"]`. Multi-line content is supported:
    all preceding non-empty lines are executed in a restricted environment to
    prepare context (e.g., variable assignments), and the last non-empty line
    is evaluated as an expression that must return a `BaseOp`.

    Rules for the final line:
        - The last non-empty line MUST be an expression that evaluates to a
          single `BaseOp` instance or a composed `BaseOp` expression (e.g.,
          `OpA() >> OpB()` or `OpA() | OpB()`).
        - It CANNOT be an assignment statement (e.g., `opx = OpA() >> OpB()`).
          Assignments are only allowed in preceding lines.
        - The evaluated result of this final expression is the flow to run.

    Examples:
        OpA() >> OpB()

        op = ContainerOp()
        op.ops.search = OpA()
        op.ops.find = OpB()
        (op | OpB()) >> (OpA() | OpC()) >> op

    Args:
        flow_content: Raw flow script text.

    Returns:
        BaseOp: The parsed flow as an executable operation tree.

    Raises:
        ValueError: If the provided content is empty.
        AssertionError: If the last line does not evaluate to a `BaseOp`.
    """
    from ..context import C
    from ..enumeration import RegistryEnum
    from ..op import BaseOp

    flow_content = flow_content.strip()
    if not flow_content:
        raise ValueError("flow content is empty")

    # Prepare environment with registered op classes available by name.
    # When an op is registered without an explicit name, fall back to its class name.
    op_registry = C.registry_dict[RegistryEnum.OP]
    env: dict = {name or cls.__name__: cls for name, cls in op_registry.items()}

    # Execute all but the last non-empty line to set up context
    lines = [x.strip() for x in flow_content.splitlines() if x.strip()]
    if len(lines) > 1:
        exec_content = "\n".join(lines[:-1])
        exec(exec_content, {"__builtins__": {}}, env)

    # Evaluate the final line; it must return a BaseOp
    last_line_expr = lines[-1]
    result = eval(last_line_expr, {"__builtins__": {}}, env)
    assert isinstance(result, BaseOp), f"Expression '{last_line_expr}' did not evaluate to a BaseOp instance"
    return result
