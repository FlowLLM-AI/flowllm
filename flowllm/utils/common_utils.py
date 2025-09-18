import json
import os
import re
from datetime import datetime
from pathlib import Path

from loguru import logger


def camel_to_snake(content: str) -> str:
    """
    BaseWorker -> base_worker
    """
    # FIXME
    content = content.replace("LLM", "Llm")

    snake_str = re.sub(r'(?<!^)(?=[A-Z])', '_', content).lower()
    return snake_str


def snake_to_camel(content: str) -> str:
    """
    base_worker -> BaseWorker
    """
    camel_str = "".join(x.capitalize() for x in content.split("_"))

    # FIXME
    camel_str = camel_str.replace("Llm", "LLM")
    return camel_str


def _load_env(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                continue

            line_split = line.strip().split("=", 1)
            if len(line_split) >= 2:
                key = line_split[0].strip()
                value = line_split[1].strip()
                os.environ[key] = value


def load_env(path: str | Path = None, enable_log: bool = True):
    if path is not None:
        path = Path(path)
        if path.exists():
            _load_env(path)

    else:
        for i in range(5):
            path = Path("../" * i + ".env")
            if path.exists():
                if enable_log:
                    logger.info(f"load env_path={path}")
                _load_env(path)
                return

        logger.warning(".env not found")


def extract_json(text: str) -> dict | None:
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)

    if match:
        json_content = match.group(1).strip()
        try:
            return json.loads(json_content)
        except json.JSONDecodeError as e:
            return None

    else:
        return None


def extract_python(text: str) -> str:
    match = re.search(r'```python\s*(.*?)\s*```', text, re.DOTALL)

    if match:
        return match.group(1).strip()
    else:
        return ""


def get_datetime():
    now = datetime.now()
    formatted_time = now.strftime("%Y年%m月%d日 %H:%M:%S")
    return formatted_time
