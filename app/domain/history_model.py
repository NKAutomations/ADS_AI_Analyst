"""Thread-sichere, begrenzte In-Memory-Historie fuer echte ADS-Ereignisse."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, List, Optional


@dataclass(frozen=True)
class HistoryEntry:
    timestamp: datetime
    symbol: str
    data_type: str
    value: object


class HistoryModel:
    def __init__(self, max_entries: int = 5000) -> None:
        if max_entries < 1:
            raise ValueError("max_entries muss groesser als 0 sein")
        self._lock = threading.RLock()
        self._max_entries = int(max_entries)
        self._entries: Deque[HistoryEntry] = deque(maxlen=self._max_entries)
        self._evicted_total = 0

    @property
    def max_entries(self) -> int:
        with self._lock:
            return self._max_entries

    @max_entries.setter
    def max_entries(self, value: int) -> None:
        if value < 1:
            raise ValueError("max_entries muss groesser als 0 sein")
        with self._lock:
            old = list(self._entries)
            if len(old) > value:
                self._evicted_total += len(old) - value
            self._max_entries = int(value)
            self._entries = deque(old, maxlen=self._max_entries)

    @property
    def evicted_total(self) -> int:
        with self._lock:
            return self._evicted_total

    def add(
        self,
        symbol: str,
        data_type: str,
        value: object,
        timestamp: Optional[datetime] = None,
    ) -> None:
        entry = HistoryEntry(
            timestamp=timestamp or datetime.now(),
            symbol=symbol,
            data_type=data_type,
            value=value,
        )
        with self._lock:
            if len(self._entries) == self._max_entries:
                self._evicted_total += 1
            self._entries.append(entry)

    def get_window(
        self,
        from_dt: Optional[datetime],
        to_dt: Optional[datetime],
        symbols: Optional[List[str]] = None,
    ) -> List[HistoryEntry]:
        with self._lock:
            result = list(self._entries)
        if from_dt is not None:
            result = [e for e in result if e.timestamp >= from_dt]
        if to_dt is not None:
            result = [e for e in result if e.timestamp <= to_dt]
        if symbols is not None:
            allowed = set(symbols)
            result = [e for e in result if e.symbol in allowed]
        return result

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._entries)
