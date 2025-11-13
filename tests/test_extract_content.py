"""Test script for common_utils.

This script provides test functions for common_utils module.
It can be run directly with: python test_common_utils.py
"""

import pytest

from flowllm.core.utils import extract_content


def test_extract_content_json_no_space():
    """Test extract_content with JSON code block and no space between ``` and json."""
    text = '```json\n{"key": "value"}\n```'
    result = extract_content(text, language_tag="json")
    assert result == {"key": "value"}


def test_extract_content_json_one_space():
    """Test extract_content with JSON code block and one space between ``` and json."""
    text = '``` json\n{"key": "value"}\n```'
    result = extract_content(text, language_tag="json")
    assert result == {"key": "value"}


def test_extract_content_json_two_spaces():
    """Test extract_content with JSON code block and two spaces between ``` and json."""
    text = '```  json\n{"key": "value"}\n```'
    result = extract_content(text, language_tag="json")
    assert result == {"key": "value"}


def test_extract_content_json_multiple_spaces():
    """Test extract_content with JSON code block and multiple spaces between ``` and json."""
    text = '```   json\n{"key": "value"}\n```'
    result = extract_content(text, language_tag="json")
    assert result == {"key": "value"}


def test_extract_content_python_no_space():
    """Test extract_content with Python code block and no space between ``` and python."""
    text = "```python\nprint('hello')\n```"
    result = extract_content(text, language_tag="python")
    assert result == "print('hello')"


def test_extract_content_python_one_space():
    """Test extract_content with Python code block and one space between ``` and python."""
    text = "``` python\nprint('hello')\n```"
    result = extract_content(text, language_tag="python")
    assert result == "print('hello')"


def test_extract_content_python_two_spaces():
    """Test extract_content with Python code block and two spaces between ``` and python."""
    text = "```  python\nprint('hello')\n```"
    result = extract_content(text, language_tag="python")
    assert result == "print('hello')"


def test_extract_content_json_complex():
    """Test extract_content with complex JSON."""
    text = '```json\n{"name": "test", "value": 123, "nested": {"key": "val"}}\n```'
    result = extract_content(text, language_tag="json")
    assert result == {"name": "test", "value": 123, "nested": {"key": "val"}}


def test_extract_content_json_with_spaces_complex():
    """Test extract_content with complex JSON and spaces."""
    text = '```  json\n{"name": "test", "value": 123}\n```'
    result = extract_content(text, language_tag="json")
    assert result == {"name": "test", "value": 123}


def test_extract_content_no_match():
    """Test extract_content when no matching code block is found."""
    text = "This is plain text without code blocks"
    result = extract_content(text, language_tag="json")
    # When language_tag is "json" and no code block is found, it tries to parse
    # the text as JSON, which fails and returns None
    assert result is None


def test_extract_content_invalid_json():
    """Test extract_content with invalid JSON."""
    text = "```json\n{invalid json}\n```"
    result = extract_content(text, language_tag="json")
    assert result is None


def main():
    """Run all tests."""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    main()
