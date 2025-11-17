"""日期时间工具函数模块。

提供用于处理日期范围、查找特定日期等功能的工具函数。
"""

from datetime import datetime, timedelta
from typing import List, Optional


def get_monday_fridays(start_str: str, end_str: str) -> List[List[str]]:
    """获取指定日期范围内所有周一到周五的日期范围列表。

    从开始日期开始，找到第一个周五，然后每隔7天获取一个周一到周五的日期范围，
    直到结束日期。

    Args:
        start_str: 开始日期字符串，格式为 "%Y%m%d"（例如："20240101"）
        end_str: 结束日期字符串，格式为 "%Y%m%d"（例如："20241231"）

    Returns:
        包含周一到周五日期范围的列表，每个元素是一个包含两个日期字符串的列表：
        [周一日期, 周五日期]。如果开始日期大于结束日期或范围内没有周五，返回空列表。
    """
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
        result.append(
            [
                (current - timedelta(days=4)).strftime("%Y%m%d"),
                current.strftime("%Y%m%d"),
            ],
        )
        current += timedelta(days=7)

    return result


def next_friday_or_same(date_str):
    """获取给定日期之后的下一个周五，如果当天就是周五则返回当天。

    Args:
        date_str: 日期字符串，格式为 "%Y%m%d"（例如："20240115"）

    Returns:
        下一个周五或当天的日期字符串，格式为 "%Y%m%d"
    """
    dt = datetime.strptime(date_str, "%Y%m%d")
    days_ahead = (4 - dt.weekday()) % 7
    next_fri = dt + timedelta(days=days_ahead)
    return next_fri.strftime("%Y%m%d")


def find_dt_less_index(dt: str | int, dt_list: List[str | int]):
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
