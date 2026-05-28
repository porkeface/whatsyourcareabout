import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


def _expand_env(value: str) -> str:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        return os.environ.get(env_key, "")
    return value


def _expand_dict(d: dict) -> dict:
    expanded = {}
    for k, v in d.items():
        if isinstance(v, dict):
            expanded[k] = _expand_dict(v)
        elif isinstance(v, list):
            expanded[k] = [_expand_env(i) if isinstance(i, str) else i for i in v]
        elif isinstance(v, str):
            expanded[k] = _expand_env(v)
        else:
            expanded[k] = v
    return expanded


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _expand_dict(raw)
