from __future__ import annotations

import json
from pathlib import Path


def load_settings(path: Path | str) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_settings(path: Path | str, data: dict) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_settings(path: Path | str, updates: dict) -> dict:
    current = load_settings(path)
    current.update(updates)
    save_settings(path, current)
    return current
