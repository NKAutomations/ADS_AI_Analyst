"""
Reparatur fuer ADS_KI_Analyse:

1. HistoryModel.add() akzeptiert den echten ADS-Callback-Zeitstempel.
2. Dadurch funktionieren Rueckblick, Nachlauf und KI-Zeitreihe korrekt.
3. Die vorhandene Trigger-Nachlaufversion von main_window.py wird nicht
   ersetzt; nur die HistoryModel-API wird angepasst.

Ausfuehren im Repository-Hauptverzeichnis:
    python fix_trigger_history.py
"""
from pathlib import Path
import re

path = Path("app/domain/history_model.py")
if not path.exists():
    raise SystemExit(
        f"Datei nicht gefunden: {path}. Bitte im Repository-Hauptverzeichnis ausfuehren."
    )

source = path.read_text(encoding="utf-8")

pattern = re.compile(
    r"    def add\(self, symbol: str, data_type: str, value: object\) -> None:\n"
    r"        entry = HistoryEntry\(\n"
    r"            timestamp=datetime\.now\(\),\n"
    r"            symbol=symbol,\n"
    r"            data_type=data_type,\n"
    r"            value=value,\n"
    r"        \)\n"
    r"        with self\._lock:\n"
    r"            self\._entries\.append\(entry\)",
)

replacement = '''    def add(
        self,
        symbol: str,
        data_type: str,
        value: object,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Fuegt einen Verlaufseintrag mit ADS-Zeitstempel hinzu.

        Der Callback-Zeitstempel ist wichtig fuer Trigger-Rueckblicke:
        Die Qt-Signalzustellung kann zeitlich spaeter erfolgen als das
        eigentliche ADS-Ereignis. Ohne diesen Parameter wuerden Eintraege
        kuenstlich auf datetime.now() datiert und aus dem Fenster fallen.
        """
        entry = HistoryEntry(
            timestamp=timestamp or datetime.now(),
            symbol=symbol,
            data_type=data_type,
            value=value,
        )
        with self._lock:
            self._entries.append(entry)'''

match = pattern.search(source)
if not match:
    if "timestamp: Optional[datetime] = None" in source:
        print("HistoryModel ist bereits korrigiert; keine Aenderung notwendig.")
        raise SystemExit(0)
    raise SystemExit(
        "Die erwartete HistoryModel.add()-Funktion wurde nicht gefunden; "
        "keine Datei geaendert."
    )

backup = path.with_suffix(path.suffix + ".before_trigger_history_fix")
if not backup.exists():
    backup.write_text(source, encoding="utf-8")

updated = source[:match.start()] + replacement + source[match.end():]
path.write_text(updated, encoding="utf-8")
print(f"Geaendert: {path}")
print(f"Backup:    {backup}")
print("HistoryModel.add() akzeptiert nun timestamp=... aus dem ADS-Callback.")
