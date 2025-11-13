"""Test script for parse_message_by_keys function.

This script provides test functions for parse_message_by_keys in llm_utils module.
It can be run directly with: python test_parse_message_by_keys.py
"""

import pytest

from flowllm.core.utils import parse_message_by_keys


def test_parse_message_by_keys_basic():
    """Test parse_message_by_keys with two keys (basic case)."""
    content = "prefixkey1middlekey2suffix"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    assert result == {"key1": "middle", "key2": "suffix"}


def test_parse_message_by_keys_single_key():
    """Test parse_message_by_keys with a single key."""
    content = "prefixkey1suffix"
    keys = ["key1"]
    result = parse_message_by_keys(content, keys)
    assert result == {"key1": "suffix"}


def test_parse_message_by_keys_three_keys():
    """Test parse_message_by_keys with three keys."""
    content = "startkey1middle1key2middle2key3end"
    keys = ["key1", "key2", "key3"]
    result = parse_message_by_keys(content, keys)
    assert result == {"key1": "middle1", "key2": "middle2", "key3": "end"}


def test_parse_message_by_keys_with_spaces():
    """Test parse_message_by_keys with content containing spaces (should be stripped)."""
    content = "  prefixkey1  middle  key2suffix  "
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    # strip() is applied to origin_content, so spaces at start/end are removed
    # but spaces in the middle are preserved
    assert result == {"key1": "middle  ", "key2": "suffix"}


def test_parse_message_by_keys_key_at_start():
    """Test parse_message_by_keys when first key is at the start of content."""
    content = "key1middlekey2suffix"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    assert result == {"key1": "middle", "key2": "suffix"}


def test_parse_message_by_keys_key_not_found_first():
    """Test parse_message_by_keys when first key is not found."""
    content = "prefixmiddlekey2suffix"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    # When first key is not found, content is kept for next iteration
    # So "prefixmiddlekey2suffix" is split by "key2"
    assert result == {"key1": "prefixmiddle", "key2": "suffix"}


def test_parse_message_by_keys_key_not_found_middle():
    """Test parse_message_by_keys when a middle key is not found."""
    content = "prefixkey1middlekey3end"
    keys = ["key1", "key2", "key3"]
    result = parse_message_by_keys(content, keys)
    # key2 not found, so remaining content "middlekey3end" is assigned to key1
    # then when processing key3, it splits "middlekey3end" into ["middle", "end"]
    # so key2 gets "middle" and key3 gets "end"
    assert result == {"key1": "middlekey3end", "key2": "middle", "key3": "end"}


def test_parse_message_by_keys_key_not_found_last():
    """Test parse_message_by_keys when last key is not found."""
    content = "prefixkey1middle"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    # Last key not found, remaining content assigned to previous key
    assert result == {"key1": "middle", "key2": ""}


def test_parse_message_by_keys_all_keys_not_found():
    """Test parse_message_by_keys when all keys are not found."""
    content = "some content without any keys"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    # First key not found, content kept. Second key not found, content assigned to first key
    assert result == {"key1": "some content without any keys", "key2": ""}


def test_parse_message_by_keys_empty_content():
    """Test parse_message_by_keys with empty content."""
    content = ""
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    assert result == {"key1": "", "key2": ""}


def test_parse_message_by_keys_empty_keys():
    """Test parse_message_by_keys with empty keys list."""
    content = "some content"
    keys = []
    result = parse_message_by_keys(content, keys)
    # zip([None] + [], []) creates empty iterator, so result is empty dict
    assert not result


def test_parse_message_by_keys_multiple_occurrences():
    """Test parse_message_by_keys when keys appear multiple times (only first occurrence used)."""
    content = "key1firstkey2middlekey1secondkey2end"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    # Only first occurrence of each key is used
    # After splitting by first key1, content becomes "firstkey2middlekey1secondkey2end"
    # After splitting by first key2, content becomes "middlekey1secondkey2end"
    assert result == {"key1": "first", "key2": "middlekey1secondkey2end"}


def test_parse_message_by_keys_with_newlines():
    """Test parse_message_by_keys with content containing newlines."""
    content = "prefix\nkey1\nmiddle\nkey2\nsuffix"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    # After splitting by key1, content becomes "\nmiddle\nkey2\nsuffix"
    # strip() removes leading newline, so it becomes "middle\nkey2\nsuffix"
    # After splitting by key2, key1 gets "middle\n" (before key2), key2 gets "\nsuffix"
    assert result == {"key1": "middle\n", "key2": "\nsuffix"}


def test_parse_message_by_keys_special_characters():
    """Test parse_message_by_keys with special characters in keys and content."""
    content = "prefix@key1middle#key2suffix"
    keys = ["@key1", "#key2"]
    result = parse_message_by_keys(content, keys)
    assert result == {"@key1": "middle", "#key2": "suffix"}


def test_parse_message_by_keys_unicode():
    """Test parse_message_by_keys with unicode characters."""
    content = "前缀key1中间key2后缀"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    assert result == {"key1": "中间", "key2": "后缀"}


def test_parse_message_by_keys_consecutive_keys():
    """Test parse_message_by_keys with consecutive keys (no content between)."""
    content = "prefixkey1key2suffix"
    keys = ["key1", "key2"]
    result = parse_message_by_keys(content, keys)
    assert result == {"key1": "", "key2": "suffix"}


def main():
    """Run all tests."""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    main()
