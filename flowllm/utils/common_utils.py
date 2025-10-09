import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from loguru import logger

ENV_LOADED = False

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
                value = line_split[1].strip().strip("\"")
                os.environ[key] = value


def load_env(path: str | Path = None, enable_log: bool = True):
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

def extract_json(text: str) -> dict | None:
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)

    if match:
        json_content = match.group(1).strip()
        try:
            return json.loads(json_content)
        except json.JSONDecodeError as _:
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
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    return formatted_time


def get_monday_fridays(start_str: str, end_str: str):
    start = datetime.strptime(str(start_str), "%Y%m%d")
    end = datetime.strptime(str(end_str), "%Y%m%d")
    if start > end:
        return []

    current = start
    while current.weekday() != 4:
        current += timedelta(days=1)
        if current > end:
            return []

    result = []
    while current <= end:
        result.append([
            (current - timedelta(days=4)).strftime("%Y%m%d"),
            current.strftime("%Y%m%d"),
        ])
        current += timedelta(days=7)

    return result


def next_friday_or_same(date_str):
    dt = datetime.strptime(date_str, "%Y%m%d")
    days_ahead = (4 - dt.weekday()) % 7
    next_fri = dt + timedelta(days=days_ahead)
    return next_fri.strftime("%Y%m%d")


def find_dt_less_index(dt: str, dt_list: List[str]):
    """
    Use binary search to find the index of the date that is closest to and less than dt.
    Time complexity: O(log n)
    """
    if not dt_list:
        return None

    left, right = 0, len(dt_list) - 1

    if dt < dt_list[left]:
        return None

    if dt >= dt_list[right]:
        return right

    while left < right:
        mid = (left + right + 1) // 2
        if dt_list[mid] <= dt:
            left = mid
        else:
            right = mid - 1

    return left


from typing import List, Optional


def find_dt_greater_index(dt: str, dt_list: List[str]) -> Optional[int]:
    """
    Use binary search to find the index of the date that is closest to and greater than dt.
    Time complexity: O(log n)

    Args:
        dt: Target date string (e.g., '2023-05-15')
        dt_list: Sorted list of date strings in ascending order

    Returns:
        Index of the first date in dt_list that is strictly greater than dt,
        or None if no such date exists.
    """
    if not dt_list:
        return None

    left, right = 0, len(dt_list) - 1

    # If dt is >= the last element, no greater element exists
    if dt >= dt_list[right]:
        return None

    # If dt is < the first element, the first element is the answer
    if dt < dt_list[left]:
        return left

    # Binary search for the first element > dt
    while left < right:
        mid = (left + right) // 2
        if dt_list[mid] <= dt:
            left = mid + 1
        else:
            right = mid

    return left
