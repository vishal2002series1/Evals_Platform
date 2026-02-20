import json
import yaml
import os
import re
from pathlib import Path
from typing import Any

# Repo root = parent of /api
ROOT = Path(__file__).resolve().parents[1]

def load_json(rel_path: str) -> Any:
    return json.loads((ROOT / rel_path).read_text(encoding="utf-8"))

def _expand_env_vars(data: Any) -> Any:
    """Recursively expand ${VAR} or ${VAR:default} in strings."""
    if isinstance(data, str):
        # Pattern: ${VAR} or ${VAR:default}
        def replacer(match):
            var_name = match.group(1)
            default = match.group(2) if match.group(2) else ""
            return os.getenv(var_name, default)
        return re.sub(r'\$\{([^:}]+)(?::([^}]*))?\}', replacer, data)
    elif isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    return data

def load_yaml(rel_path: str) -> Any:
    content = yaml.safe_load((ROOT / rel_path).read_text(encoding="utf-8"))
    return _expand_env_vars(content)

def dump_yaml(obj: Any) -> str:
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=120)

def ensure_outputs_dir() -> Path:
    out = ROOT / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out
