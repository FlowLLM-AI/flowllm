"""File editing utility functions.

This module provides utility functions for intelligently editing files by replacing text.
It supports exact matching, flexible matching (ignoring indentation), and regex-based matching.
"""

import re


def escape_regex(s: str) -> str:
    """Escape special regex characters."""
    return re.escape(s)


def restore_trailing_newline(original: str, modified: str) -> str:
    """Restore trailing newline to match original."""
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
    """Try exact string replacement."""
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
    """Try flexible replacement ignoring indentation."""
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
    """Try regex-based flexible replacement."""
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
