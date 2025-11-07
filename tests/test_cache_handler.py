"""Test script for CacheHandler.

This script provides comprehensive test functions for CacheHandler class.
It can be run directly with: python test_cache_handler.py
"""

import shutil
from pathlib import Path
from time import sleep

import pandas as pd
from loguru import logger

from flowllm.core.storage.cache_handler import CacheHandler


def test_dataframe():
    """Test DataFrame save and load."""
    logger.info("=" * 50)
    logger.info("Testing DataFrame save and load")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_dataframe")

    # Create test DataFrame
    df = pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie"],
            "age": [25, 30, 35],
            "city": ["New York", "London", "Tokyo"],
        },
    )

    # Test save
    assert cache.save("test_df", df) is True
    assert cache.exists("test_df") is True

    # Test load
    loaded_df = cache.load("test_df")
    assert loaded_df is not None
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 3
    assert list(loaded_df.columns) == ["name", "age", "city"]
    assert loaded_df.iloc[0]["name"] == "Alice"
    logger.info("✓ DataFrame save and load test passed")

    # Test get_info
    info = cache.get_info("test_df")
    assert info is not None
    assert info["data_type"] == "DataFrame"
    assert "row_count" in info
    assert info["row_count"] == 3
    assert "column_count" in info
    assert info["column_count"] == 3
    logger.info("✓ DataFrame get_info test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_dataframe", ignore_errors=True)


def test_dict():
    """Test dict save and load."""
    logger.info("=" * 50)
    logger.info("Testing dict save and load")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_dict")

    # Create test dict
    data_dict = {
        "name": "Alice",
        "age": 30,
        "city": "New York",
        "hobbies": ["reading", "coding"],
        "metadata": {"key1": "value1", "key2": 42},
    }

    # Test save
    assert cache.save("test_dict", data_dict) is True
    assert cache.exists("test_dict") is True

    # Test load
    loaded_dict = cache.load("test_dict")
    assert loaded_dict is not None
    assert isinstance(loaded_dict, dict)
    assert loaded_dict["name"] == "Alice"
    assert loaded_dict["age"] == 30
    assert loaded_dict["hobbies"] == ["reading", "coding"]
    assert loaded_dict["metadata"]["key1"] == "value1"
    logger.info("✓ Dict save and load test passed")

    # Test get_info
    info = cache.get_info("test_dict")
    assert info is not None
    assert info["data_type"] == "dict"
    assert "key_count" in info
    assert info["key_count"] == 5
    logger.info("✓ Dict get_info test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_dict", ignore_errors=True)


def test_list():
    """Test list save and load."""
    logger.info("=" * 50)
    logger.info("Testing list save and load")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_list")

    # Create test list
    data_list = ["apple", "banana", "cherry", {"nested": "dict"}, [1, 2, 3]]

    # Test save
    assert cache.save("test_list", data_list) is True
    assert cache.exists("test_list") is True

    # Test load
    loaded_list = cache.load("test_list")
    assert loaded_list is not None
    assert isinstance(loaded_list, list)
    assert len(loaded_list) == 5
    assert loaded_list[0] == "apple"
    assert loaded_list[3]["nested"] == "dict"
    assert loaded_list[4] == [1, 2, 3]
    logger.info("✓ List save and load test passed")

    # Test get_info
    info = cache.get_info("test_list")
    assert info is not None
    assert info["data_type"] == "list"
    assert "item_count" in info
    assert info["item_count"] == 5
    logger.info("✓ List get_info test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_list", ignore_errors=True)


def test_string():
    """Test string save and load."""
    logger.info("=" * 50)
    logger.info("Testing string save and load")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_string")

    # Create test string
    data_string = "This is a test string\nwith multiple lines\nand special chars: 你好世界 🎉"

    # Test save
    assert cache.save("test_string", data_string) is True
    assert cache.exists("test_string") is True

    # Test load
    loaded_string = cache.load("test_string")
    assert loaded_string is not None
    assert isinstance(loaded_string, str)
    assert loaded_string == data_string
    logger.info("✓ String save and load test passed")

    # Test get_info
    info = cache.get_info("test_string")
    assert info is not None
    assert info["data_type"] == "str"
    assert "char_count" in info
    assert info["char_count"] == len(data_string)
    logger.info("✓ String get_info test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_string", ignore_errors=True)


def test_expiration():
    """Test expiration functionality."""
    logger.info("=" * 50)
    logger.info("Testing expiration functionality")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_expiration")

    # Save data with short expiration time (0.001 hours = 3.6 seconds)
    test_data = {"key": "value"}
    assert cache.save("expired_data", test_data, expire_hours=0.001) is True
    assert cache.exists("expired_data") is True

    # Wait for expiration
    sleep(4)
    assert cache.exists("expired_data") is False
    assert cache.load("expired_data") is None
    logger.info("✓ Expiration test passed")

    # Save data without expiration
    assert cache.save("permanent_data", test_data) is True
    sleep(1)
    assert cache.exists("permanent_data") is True
    assert cache.load("permanent_data") is not None
    logger.info("✓ No expiration test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_expiration", ignore_errors=True)


def test_delete():
    """Test delete functionality."""
    logger.info("=" * 50)
    logger.info("Testing delete functionality")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_delete")

    # Save multiple items
    cache.save("item1", {"key1": "value1"})
    cache.save("item2", {"key2": "value2"})
    cache.save("item3", "test string")

    assert cache.exists("item1") is True
    assert cache.exists("item2") is True
    assert cache.exists("item3") is True

    # Delete one item
    assert cache.delete("item1") is True
    assert cache.exists("item1") is False
    assert cache.load("item1") is None
    assert cache.exists("item2") is True
    assert cache.exists("item3") is True
    logger.info("✓ Delete test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_delete", ignore_errors=True)


def test_clean_expired():
    """Test clean_expired functionality."""
    logger.info("=" * 50)
    logger.info("Testing clean_expired functionality")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_clean")

    # Save expired data
    cache.save("expired1", {"key": "value"}, expire_hours=0.001)
    cache.save("expired2", "test", expire_hours=0.001)

    # Save permanent data
    cache.save("permanent1", {"key": "value"})
    cache.save("permanent2", "test")

    # Wait for expiration
    sleep(4)

    # Clean expired
    cleaned_count = cache.clean_expired()
    assert cleaned_count == 2
    assert cache.exists("expired1") is False
    assert cache.exists("expired2") is False
    assert cache.exists("permanent1") is True
    assert cache.exists("permanent2") is True
    logger.info("✓ Clean expired test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_clean", ignore_errors=True)


def test_list_all():
    """Test list_all functionality."""
    logger.info("=" * 50)
    logger.info("Testing list_all functionality")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_list_all")

    # Save multiple items
    cache.save("item1", {"key1": "value1"})
    cache.save("item2", {"key2": "value2"})
    cache.save("item3", "test string", expire_hours=0.001)

    # Wait for item3 to expire (0.001 hours = 3.6 seconds)
    sleep(4)

    # Test list_all without expired
    all_items = cache.list_all(include_expired=False)
    assert len(all_items) == 2
    assert "item1" in all_items
    assert "item2" in all_items
    assert "item3" not in all_items
    logger.info("✓ list_all (exclude expired) test passed")

    # Test list_all with expired
    all_items_with_expired = cache.list_all(include_expired=True)
    assert len(all_items_with_expired) == 3
    assert "item1" in all_items_with_expired
    assert "item2" in all_items_with_expired
    assert "item3" in all_items_with_expired
    logger.info("✓ list_all (include expired) test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_list_all", ignore_errors=True)


def test_get_cache_stats():
    """Test get_cache_stats functionality."""
    logger.info("=" * 50)
    logger.info("Testing get_cache_stats functionality")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_stats")

    # Save multiple items
    cache.save("item1", {"key1": "value1"})
    cache.save("item2", {"key2": "value2"})
    cache.save("item3", "test string", expire_hours=0.001)

    # Wait for item3 to expire (0.001 hours = 3.6 seconds)
    sleep(4)

    stats = cache.get_cache_stats()
    assert stats["total_count"] == 3
    assert stats["expired_count"] == 1
    assert stats["active_count"] == 2
    assert stats["total_size_bytes"] > 0
    # Check that cache_dir is a valid path (check if it contains the expected directory name)
    assert "test_cache_stats" in stats["cache_dir"]
    assert Path(stats["cache_dir"]).exists() or Path(stats["cache_dir"]).parent.exists()
    logger.info("✓ get_cache_stats test passed")
    logger.info(f"  Stats: {stats}")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_stats", ignore_errors=True)


def test_clear_all():
    """Test clear_all functionality."""
    logger.info("=" * 50)
    logger.info("Testing clear_all functionality")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_clear")

    # Save multiple items of different types
    cache.save("df1", pd.DataFrame({"a": [1, 2, 3]}))
    cache.save("dict1", {"key": "value"})
    cache.save("list1", [1, 2, 3])
    cache.save("str1", "test")

    assert len(cache.list_all()) == 4

    # Clear all
    assert cache.clear_all() is True
    assert len(cache.list_all()) == 0
    assert cache.exists("df1") is False
    assert cache.exists("dict1") is False
    assert cache.exists("list1") is False
    assert cache.exists("str1") is False
    logger.info("✓ clear_all test passed")

    # Cleanup
    shutil.rmtree("test_cache_clear", ignore_errors=True)


def test_auto_clean_expired():
    """Test auto_clean_expired in load."""
    logger.info("=" * 50)
    logger.info("Testing auto_clean_expired in load")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_auto_clean")

    # Save expired data
    cache.save("expired_data", {"key": "value"}, expire_hours=0.001)

    # Wait for expiration
    sleep(4)

    # Load with auto_clean_expired=True (default)
    result = cache.load("expired_data")
    assert result is None
    assert cache.exists("expired_data") is False
    logger.info("✓ auto_clean_expired test passed")

    # Test with auto_clean_expired=False
    cache.save("expired_data2", {"key": "value"}, expire_hours=0.001)
    sleep(4)
    result = cache.load("expired_data2", auto_clean_expired=False)
    assert result is None
    # File should still exist (not auto-deleted)
    assert cache.exists("expired_data2", check_expired=False) is True
    logger.info("✓ auto_clean_expired=False test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_auto_clean", ignore_errors=True)


def test_multiple_types():
    """Test saving and loading multiple data types in the same cache."""
    logger.info("=" * 50)
    logger.info("Testing multiple data types in same cache")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_multiple")

    # Save different types
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    dict_data = {"key": "value"}
    list_data = [1, 2, 3]
    string_data = "hello world"

    cache.save("df", df)
    cache.save("dict", dict_data)
    cache.save("list", list_data)
    cache.save("string", string_data)

    # Load and verify
    loaded_df = cache.load("df")
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 2

    loaded_dict = cache.load("dict")
    assert isinstance(loaded_dict, dict)
    assert loaded_dict["key"] == "value"

    loaded_list = cache.load("list")
    assert isinstance(loaded_list, list)
    assert loaded_list == [1, 2, 3]

    loaded_string = cache.load("string")
    assert isinstance(loaded_string, str)
    assert loaded_string == "hello world"

    logger.info("✓ Multiple types test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_multiple", ignore_errors=True)


def test_nonexistent_key():
    """Test handling of nonexistent keys."""
    logger.info("=" * 50)
    logger.info("Testing nonexistent key handling")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_nonexistent")

    # Test load nonexistent key
    assert cache.load("nonexistent") is None
    logger.info("✓ Load nonexistent key test passed")

    # Test exists nonexistent key
    assert cache.exists("nonexistent") is False
    logger.info("✓ Exists nonexistent key test passed")

    # Test get_info nonexistent key
    assert cache.get_info("nonexistent") is None
    logger.info("✓ Get info nonexistent key test passed")

    # Test delete nonexistent key (should not raise error)
    assert cache.delete("nonexistent") is True
    logger.info("✓ Delete nonexistent key test passed")

    # Cleanup
    shutil.rmtree("test_cache_nonexistent", ignore_errors=True)


def test_update_existing_key():
    """Test updating an existing key."""
    logger.info("=" * 50)
    logger.info("Testing update existing key")
    logger.info("=" * 50)

    cache = CacheHandler(cache_dir="test_cache_update")

    # Save initial data
    cache.save("test_key", {"old": "value"})
    assert cache.load("test_key")["old"] == "value"

    # Update with new data
    cache.save("test_key", {"new": "value"})
    loaded = cache.load("test_key")
    assert "old" not in loaded
    assert loaded["new"] == "value"
    logger.info("✓ Update existing key test passed")

    # Cleanup
    cache.clear_all()
    shutil.rmtree("test_cache_update", ignore_errors=True)


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 70)
    logger.info("Starting CacheHandler Tests")
    logger.info("=" * 70 + "\n")

    try:
        test_dataframe()
        test_dict()
        test_list()
        test_string()
        test_expiration()
        test_delete()
        test_clean_expired()
        test_list_all()
        test_get_cache_stats()
        test_clear_all()
        test_auto_clean_expired()
        test_multiple_types()
        test_nonexistent_key()
        test_update_existing_key()

        logger.info("\n" + "=" * 70)
        logger.info("All CacheHandler Tests Passed! ✓")
        logger.info("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
