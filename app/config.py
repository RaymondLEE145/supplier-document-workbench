# -*- coding: utf-8 -*-
"""Global paths, settings and small helpers."""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
STATIC_DIR = APP_DIR / "static"
ASSETS_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
SCRIPT_DIR = DATA_DIR / "scripts"
STATE_DIR = DATA_DIR / "state"
TEMPLATE_DIR = DATA_DIR / "template"
TESTDATA_DIR = ROOT / "testdata"
RESEARCH_DIR = ROOT / "research"
DEFAULT_TEMPLATE = ASSETS_DIR / "template.xlsx"

for _p in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, SCRIPT_DIR, STATE_DIR, TEMPLATE_DIR):
    _p.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".xlsx", ".xlsm", ".xls"}
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
SETTINGS_PATH = DATA_DIR / "settings.json"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def now_display() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def new_id(prefix: str = "") -> str:
    token = uuid.uuid4().hex[:12]
    return f"{prefix}{token}" if prefix else token


def safe_filename(name: str, fallback: str = "file") -> str:
    name = os.path.basename(name or "").strip()
    bad = '<>:"/\\|?*\x00'
    cleaned = "".join("_" if ch in bad else ch for ch in name)
    cleaned = cleaned.strip(" .")
    return cleaned[:180] or fallback


def load_settings() -> dict:
    defaults = {
        "llm": {
            "base_url": os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1"),
            "model": os.environ.get("LLM_MODEL", "deepseek-chat"),
            "api_key": os.environ.get("LLM_API_KEY", ""),
            "enabled": bool(os.environ.get("LLM_API_KEY")),
        },
        "compliance": {
            "enabled": True,
            "timeout_sec": 25,
            "use_browser": True,
        },
    }
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        for k, v in defaults.items():
            if isinstance(v, dict):
                merged = dict(v)
                merged.update(data.get(k) or {})
                data[k] = merged
        return data
    except Exception:
        return defaults


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
