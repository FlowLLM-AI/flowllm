"""Common utility functions for string conversion, environment loading, and content extraction.

This module provides utility functions for:
- String format conversion (camelCase to snake_case and vice versa)
- Environment variable loading from .env files
- Extracting and parsing content from Markdown code blocks
"""

import json
import os
import re
from pathlib import Path

from loguru import logger

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


def extract_content(text: str, language_tag: str = "json"):
    """Extract and parse content from Markdown code blocks.

    Searches for content within Markdown code blocks (triple backticks)
    and extracts it. If the language tag is "json", attempts to parse
    the extracted content as JSON. If no code block is found, returns
    the original text (or parsed JSON if applicable).

    Args:
        text: The text to search for code blocks.
        language_tag: The language tag of the code block (e.g., "json",
            "python"). Defaults to "json".

    Returns:
        If language_tag is "json":
            - Parsed JSON object/dict/list if valid JSON is found
            - None if JSON parsing fails
        Otherwise:
            - Extracted content string from code block
            - Original text if no code block is found

    Example:
        ```python
        extract_content("```json\\n{\"key\": \"value\"}\\n```")  # noqa
        # {'key': 'value'}
        extract_content("``` json\\n{\"key\": \"value\"}\\n```")  # noqa
        # {'key': 'value'}
        extract_content("```python\\nprint('hello')\\n```", "python")
        # "print('hello')"
        ```
    """
    pattern = rf"```\s*{re.escape(language_tag)}\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        result = match.group(1).strip()
    else:
        result = text

    if language_tag == "json":
        try:
            result = json.loads(result)

        except json.JSONDecodeError:
            result = None

    return result


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
