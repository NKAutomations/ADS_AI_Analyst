"""
settings.py – Konfiguration laden und speichern
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.json"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        logger.warning("config.json nicht gefunden – verwende Standardwerte")
        return _default_config()
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    logger.info("Konfiguration gespeichert: %s", CONFIG_PATH)


def _default_config() -> dict[str, Any]:
    return {
        "ads": {
            "host": "",
            "ams_net_id": "",
            "port": 851,
            "timeout_seconds": 3.0,
            "notification_cycle_ms": 100,
        },
        "variables": [],
        "llm": {
            "base_url": "http://127.0.0.1:1234/v1",
            "model": "",
            "timeout_seconds": 60.0,
            "temperature": 0.1,
            "max_tokens": 1200,
            "context_length": 4096,
            "top_p": 0.95,
            "top_k": 40,
            "repeat_penalty": 1.1,
            "stream": False,
            "system_prompt": (
                "Analysiere ausschließlich die übergebenen ADS-Daten und ihren zeitlichen Verlauf. "
                "Beschreibe sachlich Beobachtungen, Auffälligkeiten und mögliche Ursachen. "
                "Erfinde keine Werte und gib keine Steuerungs- oder Schreibbefehle aus. "
                "Antworte als verständlicher Freitext."
            ),
        },
        "logging": {
            "max_entries": 5000,
            "file": "logs/app.log",
            "timestamp_precision": "milliseconds",
        },
    }
