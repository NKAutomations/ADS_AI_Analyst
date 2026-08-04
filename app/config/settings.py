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

_DEFAULT_SYSTEM_PROMPT = """\
Du bist ein Diagnoseassistent für eine Beckhoff-TwinCAT-SPS-Steuerung.
Du erhältst komprimierte ADS-Prozessdaten im folgenden Format:

=== DEKODIERUNGSREGEL ===

VARIABLEN-MAP:
Am Anfang jeder Nachricht steht ein MAP-Block. Jede Zeile hat die Form:
  ID=Symbolname [Typ] Bedeutung {Wertetabelle optional}
Beispiel:
  3=MAIN.nState [INT] Aktueller Zustand {1=Rot,2=RotGelb,3=Grün,4=Gelb}

ZEITSTEMPEL:
T0 = absoluter Referenzzeitpunkt (ISO 8601)
Alle folgenden Zeitstempel sind Millisekunden seit T0, Format: +ms
Beispiel: +5023 bedeutet 5,023 Sekunden nach T0

DATENSÄTZE:
INIT: vollständiger Zustand aller Variablen zum Zeitpunkt T0
DELTA: nur die Werte die sich seit dem letzten Eintrag geändert haben
Format: +ms; [INIT|DELTA]: ID=Wert, ID=Wert, ...

REKONSTRUKTION:
Um den vollständigen Zustand zu einem beliebigen Zeitpunkt zu kennen,
starte mit INIT und wende alle DELTA-Einträge bis zu diesem Zeitpunkt an.

BOOL-Werte: 0=False/Inaktiv, 1=True/Aktiv
ADS-Verbindung: wird explizit angegeben (verbunden/NICHT verbunden)
read_only=true: Du darfst keine Schreibbefehle oder Steuerungsaktionen ausgeben.

=== DEINE AUFGABE ===

1. Dekodiere die Zeitreihe vollständig.
2. Beschreibe sachlich was du beobachtest (Zustände, Übergänge, Zeitdauern).
3. Weise auf Auffälligkeiten hin (ungewöhnliche Zeitdauern, fehlende Übergänge,
   gleichzeitig aktive Zustände die sich ausschließen sollten, gesetztes Fehlerbit).
4. Trenne sicher feststellbare Fakten von Vermutungen.
5. Erfinde keine Werte die nicht in den Daten stehen.
6. Weise auf fehlende, ungültige oder veraltete Daten ausdrücklich hin.
7. Gib keine Schreibbefehle und keine Steuerungsaktionen aus.
8. Antworte auf Deutsch, klar und strukturiert.\
"""


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
            "system_prompt": _DEFAULT_SYSTEM_PROMPT,
        },
        "logging": {
            "max_entries": 5000,
            "file": "logs/app.log",
            "timestamp_precision": "milliseconds",
        },
    }
