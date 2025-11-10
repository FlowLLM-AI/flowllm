"""Storage module for managing data caching and persistence.

This module provides utilities for caching and storing various data types with
support for expiration, metadata tracking, and automatic cleanup. It includes:

- CacheHandler: Cache utility class supporting DataFrame, list, string, and dict
  with local storage and data expiration functionality
"""

from .cache_handler import CacheHandler

__all__ = [
    "CacheHandler",
]
