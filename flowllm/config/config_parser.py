"""YAML config parser with CLI argument overrides."""

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).parent
_SUPPORTED_EXTS = (".yaml", ".yml", ".json")
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?}")
_LEADING_ZERO_RE = re.compile(r"^-?0\d")


def _repl(m: re.Match) -> str:
    name: str = m.group(1)
    default: str | None = m.group(2)
    v = os.environ.get(name)
    if v is None:
        if default is not None:
            return default
        raise ValueError(f"Config references undefined env var: {name}")
    return v


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand `${VAR}` / `${VAR:-default}` in strings."""
    if isinstance(value, str):
        expanded = _ENV_VAR_RE.sub(_repl, value)
        return _convert_value(expanded) if expanded != value else value
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    return value


def _discover_configs() -> dict[str, Path]:
    """Map config file stems to paths in the config directory."""
    discovered: dict[str, Path] = {}
    if _CONFIG_DIR.is_dir():
        files = sorted(
            (p for p in _CONFIG_DIR.iterdir() if p.is_file() and p.suffix in _SUPPORTED_EXTS),
            key=lambda p: (_SUPPORTED_EXTS.index(p.suffix), p.name),
        )
        for p in files:
            discovered.setdefault(p.stem, p)
    return discovered


_CONFIG_REGISTRY = _discover_configs()


def parse_dot_notation(dot_list: list[str]) -> dict:
    """Parse "key.subkey=value" strings into a nested dict."""
    result: dict = {}
    for item in dot_list:
        if "=" not in item:
            raise ValueError(f"Invalid dot notation format (missing '='): {item}")
        key_path, value_str = item.split("=", 1)
        keys = key_path.split(".")
        if not key_path or any(not key for key in keys):
            raise ValueError(f"Invalid dot notation key: {key_path!r}")
        current = result
        for key in keys[:-1]:
            if key in current and not isinstance(current[key], dict):
                raise ValueError(f"Cannot set nested key '{key_path}': '{key}' is already a value")
            current = current.setdefault(key, {})
        last_key = keys[-1]
        if last_key in current and isinstance(current[last_key], dict):
            raise ValueError(f"Cannot overwrite nested dict at '{key_path}' with scalar value")
        current[last_key] = _convert_value(value_str)
    return result


def _convert_value(value_str: str) -> Any:
    """Convert string to bool/int/float/JSON, preserving leading-zero strings."""
    s = value_str.strip()
    lower = s.lower()

    if lower in ("none", "null"):
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False

    if not _LEADING_ZERO_RE.match(s):
        for converter in (int, float):
            try:
                return converter(s)
            except ValueError:
                continue

    try:
        return json.loads(s)
    except (ValueError, json.JSONDecodeError):
        pass

    return s


def _load_config(name_or_path: str, encoding: str = "utf-8") -> dict:
    """Load a config by registry name or file path."""
    if name_or_path in _CONFIG_REGISTRY:
        return _read_config_file(_CONFIG_REGISTRY[name_or_path], encoding)

    p = Path(name_or_path)
    if p.suffix in _SUPPORTED_EXTS:
        candidates = [p]
        if not p.is_absolute():
            candidates.append(_CONFIG_DIR / p)
        for candidate in candidates:
            if candidate.exists():
                return _read_config_file(candidate, encoding)
        raise FileNotFoundError(f"Config file not found: {p}")

    known = ", ".join(sorted(_CONFIG_REGISTRY)) if _CONFIG_REGISTRY else "none"
    raise FileNotFoundError(f"Config file not found: {name_or_path}. Available: {known}")


def _read_config_file(path: Path, encoding: str = "utf-8") -> dict:
    """Read and env-expand a YAML or JSON config file."""
    with path.open(encoding=encoding) as f:
        if path.suffix == ".json":
            result = json.load(f)
        else:
            result = yaml.safe_load(f)
    if result is None:
        return {}
    if not isinstance(result, dict):
        raise ValueError(f"Config root must be a mapping/object: {path}")
    return _expand_env_vars(result)


def _deep_merge(base: dict, update: dict) -> dict:
    """Recursively merge update into base."""
    result = base.copy()
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _strip_arg_dashes(arg: str) -> str:
    """Strip one leading `--` or `-` prefix."""
    if arg.startswith("--"):
        return arg[2:]
    if arg.startswith("-"):
        return arg[1:]
    return arg


def parse_args(*args) -> tuple[str, dict]:
    """Parse CLI args into (action, key=value dict)."""
    if not args:
        raise ValueError("No arguments provided")

    first = _strip_arg_dashes(args[0])
    if "=" in first:
        raise ValueError(f"First argument must be action, got: {args[0]}")

    kvs: list[str] = []
    for raw in args[1:]:
        arg = _strip_arg_dashes(raw)
        if "=" in arg:
            kvs.append(arg)
        else:
            raise ValueError(f"Invalid argument format (expected key=value): {raw}")

    parsed = parse_dot_notation(kvs) if kvs else {}
    return first, parsed


def resolve_app_config(**kwargs) -> dict:
    """Load config file and deep-merge with kwargs overrides."""
    from ..utils import get_logger

    logger = get_logger()
    configs: list[dict] = []

    config_value = kwargs.get("config")
    if isinstance(config_value, str):
        kwargs.pop("config")
        logger.info(f"Loading config: {config_value}")
        configs.append(_load_config(config_value))
    elif "default" in _CONFIG_REGISTRY:
        logger.info("No config specified, loading 'default'")
        configs.append(_load_config("default"))

    configs.append(kwargs)

    merged: dict = {}
    for cfg in configs:
        merged = _deep_merge(merged, cfg)

    return merged
