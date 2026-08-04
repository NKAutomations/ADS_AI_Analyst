"""
prompt_builder.py - Erstellt den Prompt fuer LM Studio aus dem aktuellen Zustand.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import List, Optional

from app.domain.history_model import HistoryEntry
from app.domain.state_model import VariableState


def build_user_message(
    ai_variables: List[VariableState],
    history: List[HistoryEntry],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
    ads_connected: bool,
) -> str:
    lines = []
    lines.append("=== ADS-KI-Analyse ===")
    lines.append(f"Analysezeitpunkt: {datetime.now().isoformat(timespec='milliseconds')}")
    lines.append(f"ADS-Verbindung: {'verbunden' if ads_connected else 'NICHT verbunden'}")
    lines.append(f"Modus: read_only=true")
    lines.append("")

    lines.append("--- Aktuelle Werte (KI-ausgewaehlte Symbole) ---")
    if not ai_variables:
        lines.append("Keine Symbole fuer KI ausgewaehlt.")
    else:
        for v in ai_variables:
            ts_str = v.timestamp.isoformat(timespec="milliseconds") if v.timestamp else "unbekannt"
            valid_str = "gueltig" if v.valid else "UNGUELTIG"
            lines.append(
                f"  {v.symbol} [{v.data_type}]: {v.value}  "
                f"(Zeitstempel: {ts_str}, Status: {valid_str})"
            )
    lines.append("")

    from_str = from_dt.isoformat(timespec="milliseconds") if from_dt else "Anfang"
    to_str = to_dt.isoformat(timespec="milliseconds") if to_dt else "jetzt"
    lines.append(f"--- Verlaufshistorie ({from_str} bis {to_str}) ---")
    if not history:
        lines.append("Keine Verlaufsdaten im gewaehlten Zeitfenster.")
    else:
        lines.append(f"Anzahl Ereignisse: {len(history)}")
        for entry in history:
            lines.append(
                f"  {entry.timestamp.isoformat(timespec='milliseconds')}  "
                f"{entry.symbol} [{entry.data_type}] = {entry.value}"
            )
    lines.append("")
    lines.append("=== Ende der Daten ===")
    return "\n".join(lines)
