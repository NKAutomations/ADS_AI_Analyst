"""Thread-sicheres Zustandsmodell fuer Aufzeichnung und Diagrammfarben."""
from __future__ import annotations

import threading
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


DEFAULT_PLOT_COLORS = (
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B3", "#937860", "#DA8BC3", "#8C8C8C",
)


@dataclass
class VariableState:
    symbol: str
    data_type: str
    tc_type: str
    comment: str = ""
    value: object = None
    timestamp: Optional[datetime] = None
    valid: bool = False
    recording: bool = False
    plot_color: str = "#4C72B0"
    notification_handle: Optional[int] = None
    supported: bool = True


class StateModel:
    """Speichert Symbolzustand, Aufzeichnungsauswahl und Diagrammfarbe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._variables: Dict[str, VariableState] = {}

    def set_symbols(self, symbols: list[VariableState]) -> None:
        with self._lock:
            self._variables = {s.symbol: s for s in symbols}

    def update_value(
        self, symbol: str, value: object, ts: Optional[datetime] = None
    ) -> bool:
        """Aktualisiert Wert/Zeitstempel nur beim ersten oder neuen Wert."""
        with self._lock:
            state = self._variables.get(symbol)
            if state is None:
                return False
            changed = (
                not state.valid
                or type(state.value) is not type(value)
                or state.value != value
            )
            if changed:
                state.value = value
                state.timestamp = ts or datetime.now()
            state.valid = True
            return changed

    def mark_invalid(self, symbol: str) -> None:
        with self._lock:
            if symbol in self._variables:
                self._variables[symbol].valid = False

    def get_all(self) -> list[VariableState]:
        with self._lock:
            return [copy(v) for v in self._variables.values()]

    def get(self, symbol: str) -> Optional[VariableState]:
        with self._lock:
            value = self._variables.get(symbol)
            return copy(value) if value is not None else None

    def set_recording(self, symbol: str, recording: bool) -> None:
        with self._lock:
            if symbol in self._variables:
                self._variables[symbol].recording = bool(recording)

    def set_plot_color(self, symbol: str, color: str) -> None:
        with self._lock:
            if symbol in self._variables and color:
                self._variables[symbol].plot_color = str(color)

    def get_recorded_symbols(self) -> list[VariableState]:
        with self._lock:
            return [copy(v) for v in self._variables.values() if v.recording]

    def clear(self) -> None:
        with self._lock:
            self._variables.clear()
