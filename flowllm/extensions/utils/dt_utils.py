"""Date and time utility functions module.

This module provides utility functions for working with date ranges, finding specific dates,
and performing binary search operations on date lists.
"""

from datetime import datetime, timedelta
from typing import List, Optional


def get_monday_fridays(start_str: str, end_str: str) -> List[List[str]]:
    """Get all Monday-to-Friday date ranges within the specified date range.

    Starting from the start date, finds the first Friday, then retrieves a Monday-to-Friday
    date range every 7 days until the end date.

    Args:
        start_str: Start date string in "%Y%m%d" format (e.g., "20240101")
        end_str: End date string in "%Y%m%d" format (e.g., "20241231")

    Returns:
        A list of Monday-to-Friday date ranges, where each element is a list containing
        two date strings: [Monday date, Friday date]. Returns an empty list if the start
        date is greater than the end date or if there are no Fridays in the range.
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


def next_friday_or_same(date_str: str) -> str:
    """Get the next Friday after the given date, or return the same date if it's already Friday.

    Args:
        date_str: Date string in "%Y%m%d" format (e.g., "20240115")

    Returns:
        The next Friday or the same date if it's already Friday, as a date string
        in "%Y%m%d" format.
    """
    dt = datetime.strptime(date_str, "%Y%m%d")
    days_ahead = (4 - dt.weekday()) % 7
    next_fri = dt + timedelta(days=days_ahead)
    return next_fri.strftime("%Y%m%d")


def find_dt_less_index(dt: str | int, dt_list: List[str | int]) -> Optional[int]:
    """Find the index of the date that is closest to and less than or equal to dt using binary search.

    This function performs a binary search to efficiently find the index of the largest date
    in the sorted list that is less than or equal to the target date.

    Args:
        dt: Target date as a string or integer
        dt_list: Sorted list of dates in ascending order (strings or integers)

    Returns:
        Index of the date that is closest to and less than or equal to dt, or None if
        dt is less than all dates in the list. Returns the last index if dt is greater
        than or equal to all dates in the list.

    Note:
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
