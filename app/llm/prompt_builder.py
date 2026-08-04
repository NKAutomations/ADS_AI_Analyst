"""
prompt_builder.py – Komprimierter User-Prompt mit MAP + Delta-Encoding.

Format:
  STUFE 1 – HEADER:  T0, MAP-Block, aktueller Snapshot
  STUFE 2 – ZEITREIHE: INIT + DELTA-Zeilen (nur geänderte Werte, +ms seit T0)
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from app.domain.history_model import HistoryEntry
from app.domain.state_model import VariableState


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _bool_val(value: object) -> str:
    """Konvertiert bool-artige Werte zu 0/1-String."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return "1" if value.lower() == "true" else "0"
    return str(value)


def _fmt_value(value: object, data_type: str) -> str:
    """Formatiert einen Wert abhängig vom Datentyp."""
    if data_type.upper() == "BOOL":
        return _bool_val(value)
    return str(value)


def _ms_since_t0(t0: datetime, ts: datetime) -> int:
    """Millisekunden zwischen t0 und ts (nie negativ)."""
    delta = ts - t0
    ms = int(delta.total_seconds() * 1000)
    return max(0, ms)


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------

def build_user_message(
    ai_variables: List[VariableState],
    history: List[HistoryEntry],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
    ads_connected: bool,
) -> str:
    """
    Erstellt den komprimierten User-Prompt im MAP + Delta-Encoding-Format.

    Aufbau:
      - Verbindungsstatus / Modus
      - T0 = Referenzzeitpunkt (erster Historieneintrag oder jetzt)
      - MAP-Block: ID → Symbolname [Typ] Kommentar
      - Aktueller Snapshot aller KI-Variablen
      - Zeitreihe: INIT + DELTA-Zeilen
    """
    lines: List[str] = []

    # --- Verbindungsheader ---
    lines.append(f"ADS-Verbindung: {'verbunden' if ads_connected else 'NICHT verbunden'}")
    lines.append("read_only=true")

    # --- T0 bestimmen ---
    # Filtere History auf KI-Symbole (sollte bereits gefiltert sein, aber sicher ist sicher)
    ai_symbols = {v.symbol for v in ai_variables}
    relevant_history = [e for e in history if e.symbol in ai_symbols]

    if relevant_history:
        t0 = relevant_history[0].timestamp
    elif from_dt:
        t0 = from_dt
    else:
        t0 = datetime.now()

    lines.append(f"T0={t0.isoformat(timespec='milliseconds')}")
    lines.append("")

    # --- MAP-Block ---
    # Stabile Reihenfolge: alphabetisch nach Symbolname
    sorted_vars = sorted(ai_variables, key=lambda v: v.symbol)
    id_map: Dict[str, int] = {v.symbol: idx for idx, v in enumerate(sorted_vars)}

    lines.append("=== MAP ===")
    if not sorted_vars:
        lines.append("# Keine KI-Symbole ausgewählt.")
    else:
        for idx, vs in enumerate(sorted_vars):
            comment_part = f" {vs.comment}" if vs.comment else ""
            lines.append(f"{idx}={vs.symbol} [{vs.data_type}]{comment_part}")
    lines.append("")

    # --- Aktueller Snapshot ---
    lines.append("=== AKTUELLER ZUSTAND ===")
    if not sorted_vars:
        lines.append("# Keine KI-Symbole ausgewählt.")
    else:
        snapshot_parts = []
        for vs in sorted_vars:
            vid = id_map[vs.symbol]
            val = _fmt_value(vs.value if vs.value is not None else "?", vs.data_type)
            snapshot_parts.append(f"{vid}={val}")
        lines.append(",".join(snapshot_parts))
    lines.append("")

    # --- Zeitreihe ---
    lines.append("=== ZEITREIHE ===")

    if not relevant_history:
        lines.append("# Keine Verlaufsdaten im gewählten Zeitfenster.")
    else:
        # INIT: vollständiger Zustand zum Zeitpunkt T0
        # Wir rekonstruieren den Zustand zum Zeitpunkt des ersten Eintrags:
        # Für jedes Symbol nehmen wir den ersten bekannten Wert aus der History.
        first_known: Dict[str, str] = {}
        for entry in relevant_history:
            if entry.symbol not in first_known:
                first_known[entry.symbol] = _fmt_value(entry.value, entry.data_type)

        init_parts = []
        for vs in sorted_vars:
            vid = id_map[vs.symbol]
            val = first_known.get(vs.symbol, "?")
            init_parts.append(f"{vid}={val}")

        lines.append(f"+0;     INIT:  {','.join(init_parts)}")

        # DELTA-Zeilen: nur geänderte Werte seit letztem Eintrag
        # Wir gruppieren History-Einträge nach Zeitstempel (ms-Auflösung)
        # und erzeugen pro Zeitschritt eine DELTA-Zeile.
        last_state: Dict[str, str] = dict(first_known)

        # Einträge nach Zeitstempel sortieren (sollten bereits sortiert sein)
        sorted_history = sorted(relevant_history, key=lambda e: e.timestamp)

        # Zeitstempel-Gruppen bilden (gleicher ms-Wert → eine Zeile)
        from itertools import groupby

        def _ms_key(entry: HistoryEntry) -> int:
            return _ms_since_t0(t0, entry.timestamp)

        for ms_offset, group in groupby(sorted_history, key=_ms_key):
            if ms_offset == 0:
                # T0-Einträge sind bereits im INIT abgedeckt
                # Wir aktualisieren aber last_state
                for entry in group:
                    last_state[entry.symbol] = _fmt_value(entry.value, entry.data_type)
                continue

            changed_parts = []
            group_entries = list(group)
            new_state = dict(last_state)

            for entry in group_entries:
                new_val = _fmt_value(entry.value, entry.data_type)
                new_state[entry.symbol] = new_val

            for vs in sorted_vars:
                sym = vs.symbol
                if sym not in id_map:
                    continue
                new_val = new_state.get(sym)
                old_val = last_state.get(sym)
                if new_val is not None and new_val != old_val:
                    changed_parts.append(f"{id_map[sym]}={new_val}")

            if changed_parts:
                lines.append(f"+{ms_offset}; DELTA: {','.join(changed_parts)}")

            last_state = new_state

    lines.append("")
    return "\n".join(lines)
