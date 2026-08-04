"""
state_model.py – Zustandsmodell für ADS-Variablen
"""
from __future__ import annotations
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class VariableState:
    symbol: str
    data_type: str          # normalisierter Typ (BOOL, INT, ...)
    tc_type: str            # originaler TwinCAT-Typ
    comment: str = ""
    value: object = None
    timestamp: Optional[datetime] = None
    valid: bool = False
    # Auswahlflags
    show: bool = False
    log: bool = False
    ai: bool = False
    # Notification-Handle
    notification_handle: Optional[int] = None
    supported: bool = True  # False für komplexe/unbekannte Typen


class StateModel:
    """Thread-sicherer Container für alle bekannten ADS-Variablen."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._variables: Dict[str, VariableState] = {}

    def set_symbols(self, symbols: list[VariableState]) -> None:
        with self._lock:
            self._variables = {s.symbol: s for s in symbols}

    def update_value(self, symbol: str, value: object, ts: Optional[datetime] = None) -> None:
        with self._lock:
            if symbol in self._variables:
                self._variables[symbol].value = value
                self._variables[symbol].timestamp = ts or datetime.now()
                self._variables[symbol].valid = True

    def mark_invalid(self, symbol: str) -> None:
        with self._lock:
            if symbol in self._variables:
                self._variables[symbol].valid = False

    def get_all(self) -> list[VariableState]:
        with self._lock:
            return list(self._variables.values())

    def get(self, symbol: str) -> Optional[VariableState]:
        with self._lock:
            return self._variables.get(symbol)

    def set_selection(self, symbol: str, show: bool, log: bool, ai: bool) -> None:
        with self._lock:
            if symbol in self._variables:
                self._variables[symbol].show = show
                self._variables[symbol].log = log
                self._variables[symbol].ai = ai

    def get_ai_symbols(self) -> list[VariableState]:
        with self._lock:
            return [v for v in self._variables.values() if v.ai]

    def get_log_symbols(self) -> list[VariableState]:
        with self._lock:
            return [v for v in self._variables.values() if v.log]

    def clear(self) -> None:
        with self._lock:
            self._variables.clear()
