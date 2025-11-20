"""File editing utility functions.

This module provides utility functions for intelligently editing files by replacing text.
It supports exact matching, flexible matching (ignoring indentation), and regex-based matching.
"""

import re


def escape_regex(s: str) -> str:
    """Escape special regex characters in a string.

    This function escapes all special regex characters in the input string so that
    it can be used as a literal string in a regular expression pattern.

    Args:
        s: The string containing characters that may need escaping

    Returns:
        A string with all special regex characters escaped
    """
    return re.escape(s)


def restore_trailing_newline(original: str, modified: str) -> str:
    """Restore trailing newline to match the original string.

    This function ensures that the modified string has the same trailing newline
    behavior as the original string, preserving the file's newline format.

    Args:
        original: The original string before modification
        modified: The modified string that may have lost or gained a trailing newline

    Returns:
        The modified string with trailing newline adjusted to match the original
    """
    had_newline = original.endswith("\n")
    if had_newline and not modified.endswith("\n"):
        return modified + "\n"
    elif not had_newline and modified.endswith("\n"):
        return modified.rstrip("\n")
    return modified


def calculate_exact_replacement(
    content: str,
    old_string: str,
    new_string: str,
) -> tuple[str, int] | None:
    """Perform exact string replacement in content.

    This function attempts to replace the old_string with new_string using exact
    matching. It normalizes line endings (converts \\r\\n to \\n) before matching
    and preserves the original trailing newline behavior.

    Args:
        content: The original content string to modify
        old_string: The exact string to find and replace
        new_string: The replacement string

    Returns:
        A tuple containing (modified_content, occurrence_count) if the old_string
        is found, or None if no match is found. The occurrence_count indicates
        how many times the old_string appears in the content.
    """
    normalized_content = content
    normalized_old = old_string.replace("\r\n", "\n")
    normalized_new = new_string.replace("\r\n", "\n")

    occurrences = len(normalized_content.split(normalized_old)) - 1
    if occurrences > 0:
        new_content = normalized_content.replace(normalized_old, normalized_new, 1)
        new_content = restore_trailing_newline(content, new_content)
        return new_content, occurrences
    return None


def calculate_flexible_replacement(
    content: str,
    old_string: str,
    new_string: str,
) -> tuple[str, int] | None:
    """Perform flexible string replacement that ignores indentation differences.

    This function matches and replaces text by comparing line content while ignoring
    leading whitespace (indentation). It preserves the indentation of the first matched
    line when applying the replacement, making it useful for code editing where
    indentation may vary.

    Args:
        content: The original content string to modify
        old_string: The string pattern to find (indentation is ignored during matching)
        new_string: The replacement string (will be indented to match the original)

    Returns:
        A tuple containing (modified_content, occurrence_count) if matches are found,
        or None if no match is found. The occurrence_count indicates how many times
        the pattern was found and replaced.
    """
    normalized_content = content
    normalized_old = old_string.replace("\r\n", "\n")
    normalized_new = new_string.replace("\r\n", "\n")

    source_lines = normalized_content.split("\n")
    search_lines_stripped = [line.strip() for line in normalized_old.split("\n") if line.strip()]
    replace_lines = normalized_new.split("\n")

    if not search_lines_stripped:
        return None

    occurrences = 0
    i = 0
    while i <= len(source_lines) - len(search_lines_stripped):
        window = source_lines[i : i + len(search_lines_stripped)]
        window_stripped = [line.strip() for line in window]
        if all(window_stripped[j] == search_lines_stripped[j] for j in range(len(search_lines_stripped))):
            occurrences += 1
            first_line = window[0]
            indent_match = re.match(r"^(\s*)", first_line)
            indent = indent_match.group(1) if indent_match else ""
            new_block = [f"{indent}{line}" for line in replace_lines]
            source_lines[i : i + len(search_lines_stripped)] = new_block
            i += len(replace_lines)
        else:
            i += 1

    if occurrences > 0:
        new_content = "\n".join(source_lines)
        new_content = restore_trailing_newline(content, new_content)
        return new_content, occurrences
    return None


def calculate_regex_replacement(
    content: str,
    old_string: str,
    new_string: str,
) -> tuple[str, int] | None:
    """Perform regex-based flexible replacement with whitespace tolerance.

    This function converts the old_string into a regex pattern by escaping special
    characters and allowing flexible whitespace between tokens. It's useful for
    matching code patterns where whitespace may vary. The replacement preserves
    the indentation of the matched block.

    Args:
        content: The original content string to modify
        old_string: The string pattern to find (converted to regex with flexible whitespace)
        new_string: The replacement string (will be indented to match the original)

    Returns:
        A tuple containing (modified_content, 1) if a match is found, or None if
        no match is found. Only the first match is replaced.
    """
    normalized_old = old_string.replace("\r\n", "\n")
    normalized_new = new_string.replace("\r\n", "\n")

    delimiters = ["(", ")", ":", "[", "]", "{", "}", ">", "<", "="]
    processed = normalized_old
    for delim in delimiters:
        processed = processed.replace(delim, f" {delim} ")

    tokens = [t for t in processed.split() if t]
    if not tokens:
        return None

    escaped_tokens = [escape_regex(t) for t in tokens]
    pattern = "\\s*".join(escaped_tokens)
    final_pattern = f"^(\\s*){pattern}"
    regex = re.compile(final_pattern, re.MULTILINE)

    match = regex.search(content)
    if not match:
        return None

    indent = match.group(1) or ""
    new_lines = normalized_new.split("\n")
    new_block = "\n".join(f"{indent}{line}" for line in new_lines)

    new_content = regex.sub(new_block, content, count=1)
    new_content = restore_trailing_newline(content, new_content)
    return new_content, 1
