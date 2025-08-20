import os
import re
from pathlib import Path

from loguru import logger


def camel_to_snake(content: str) -> str:
    """
    BaseWorker -> base_worker
    """
    snake_str = re.sub(r'(?<!^)(?=[A-Z])', '_', content).lower()
    return snake_str


def snake_to_camel(content: str) -> str:
    """
    base_worker -> BaseWorker
    """
    camel_str = "".join(x.capitalize() for x in content.split("_"))
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


def load_env(path: str | Path = None):
    if path is not None:
        path = Path(path)
        if path.exists():
            _load_env(path)
    else:
        path1 = Path(".env")
        path2 = Path("../.env")
        path3 = Path("../../.env")
        path4 = Path("../../../.env")
        path5 = Path("../../../.env")

        if path1.exists():
            path = path1
        elif path2.exists():
            path = path2
        elif path3.exists():
            path = path3
        elif path4.exists():
            path = path4
        elif path5.exists():
            path = path5
        else:
            raise FileNotFoundError(".env not found")

        logger.info(f"using path={path}")
        _load_env(path)
