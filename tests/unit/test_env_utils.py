"""Unit tests for environment loading helpers."""

# pylint: disable=protected-access

from flowllm.utils import env_utils


def test_parse_env_file_skips_comments_and_invalid_lines(tmp_path):
    """Only valid KEY=VALUE entries are returned."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
        # comment
        FOO=bar
        QUOTED="hello world"
        EMPTY_KEY_IGNORED
        =missing
        SPACED = 'trimmed'
        """,
        encoding="utf-8",
    )

    assert env_utils._parse_env_file(env_file) == {
        "FOO": "bar",
        "QUOTED": "hello world",
        "SPACED": "trimmed",
    }


def test_load_env_from_explicit_path_respects_override(monkeypatch, tmp_path):
    """Explicit .env loading does not overwrite existing values when override=False."""
    env_file = tmp_path / ".env"
    env_file.write_text("FLOWLLM_ENV_TEST=file\nNEW_VALUE=created\n", encoding="utf-8")
    monkeypatch.setenv("FLOWLLM_ENV_TEST", "existing")

    loaded = env_utils.load_env(env_file, override=False)

    assert loaded == {"NEW_VALUE": "created"}
    assert env_utils.os.environ["FLOWLLM_ENV_TEST"] == "existing"
    assert env_utils.os.environ["NEW_VALUE"] == "created"


def test_load_env_searches_cwd_once_and_returns_cached_values(monkeypatch, tmp_path):
    """Implicit .env loading caches the discovered values."""
    env_file = tmp_path / ".env"
    env_file.write_text("FLOWLLM_CACHED_ENV=first\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FLOWLLM_CACHED_ENV", raising=False)
    monkeypatch.setattr(env_utils, "_LOADED", False)
    monkeypatch.setattr(env_utils, "_LOADED_VALUES", {})

    assert env_utils.load_env() == {"FLOWLLM_CACHED_ENV": "first"}

    env_file.write_text("FLOWLLM_CACHED_ENV=second\n", encoding="utf-8")
    monkeypatch.setenv("FLOWLLM_CACHED_ENV", "changed")

    assert env_utils.load_env() == {"FLOWLLM_CACHED_ENV": "first"}
    assert env_utils.os.environ["FLOWLLM_CACHED_ENV"] == "changed"
