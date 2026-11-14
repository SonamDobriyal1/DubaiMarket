"""Shared paths, configuration, and small utilities."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "config.yaml"

MISSING = "__MISSING__"
OTHER = "__OTHER__"


def load_config(path: Path | None = None) -> dict:
    with open(path or CONFIG_PATH, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else ROOT / path


def ensure_dirs(cfg: dict) -> None:
    for key in ("interim", "processed", "analytics", "models", "reports", "figures"):
        resolve(cfg["paths"][key]).mkdir(parents=True, exist_ok=True)
    (resolve(cfg["paths"]["figures"]) / "data").mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=_json_default)
        handle.write("\n")


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value):
    if value is None:
        return None
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:
        pass
    text = re.sub(r"\s+", " ", str(value).strip())
    return text or None


def slugify(value: str) -> str:
    text = normalize_text(value) or ""
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"


def community_key(kind: str, name: str) -> str:
    prefix = "master" if kind == "master_project" else "area"
    return f"{prefix}__{slugify(name)}"
