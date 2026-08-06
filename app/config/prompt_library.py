"""
prompt_library.py – Prompt-Bibliothek für ADS_KI_Analyse.

Verwaltet benannte System-Prompts:
  - Builtin-Prompts (schreibgeschützt, immer vorhanden)
  - User-Prompts (frei erstell-, bearbeit- und löschbar)

Speicherort: config/prompt_library.json
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LIBRARY_PATH = Path(__file__).parent.parent.parent / "config" / "prompt_library.json"

# ---------------------------------------------------------------------------
# Gemeinsamer Dekodierungsblock – wird in jeden Builtin-Prompt eingebettet
# ---------------------------------------------------------------------------

_DECODE_BLOCK = """\
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
read_only=true: Du darfst keine Schreibbefehle oder Steuerungsaktionen ausgeben.\
"""

# ---------------------------------------------------------------------------
# Builtin-Prompt-Texte
# ---------------------------------------------------------------------------

_BUILTIN_PROMPTS: list[dict[str, Any]] = [
    {
        "id": "builtin_fehler",
        "name": "Fehlererkennung",
        "builtin": True,
        "text": (
            "Du bist ein Diagnoseassistent für eine Beckhoff-TwinCAT-SPS-Steuerung.\n"
            + _DECODE_BLOCK
            + """

=== DEINE AUFGABE: FEHLERERKENNUNG ===

Dein Fokus liegt auf der Erkennung von Fehlern, Ausnahmezuständen und unerwarteten Verhalten.

1. Dekodiere die Zeitreihe vollständig.
2. Identifiziere gesetzte Fehlerbits, Fehlerzustände oder Fehlercodes.
3. Beschreibe den zeitlichen Kontext jedes Fehlers (was geschah davor, was danach).
4. Weise auf Zustände hin, die sich gegenseitig ausschließen sollten, aber gleichzeitig aktiv sind.
5. Erkenne fehlende Übergänge oder ausbleibende Reaktionen auf Signale.
6. Trenne sicher feststellbare Fehler von Verdachtsmomenten.
7. Erfinde keine Werte die nicht in den Daten stehen.
8. Weise auf fehlende, ungültige oder veraltete Daten ausdrücklich hin.
9. Gib keine Schreibbefehle und keine Steuerungsaktionen aus.
10. Antworte auf Deutsch, klar und strukturiert.
11. Verwende ausschließlich gültiges Markdown:
    - Überschriften mit #, ## oder ###
    - Aufzählungen mit -
    - nummerierte Listen mit 1., 2., 3.
    - Tabellen im GitHub-Flavored-Markdown-Format
    - wichtige Begriffe sparsam mit **Fettdruck** hervorheben
12. Beginne direkt mit der ersten fachlichen Überschrift.\
"""
        ),
    },
    {
        "id": "builtin_anomalie",
        "name": "Anomalieerkennung",
        "builtin": True,
        "text": (
            "Du bist ein Anomalieerkennungsassistent für eine Beckhoff-TwinCAT-SPS-Steuerung.\n"
            + _DECODE_BLOCK
            + """

=== DEINE AUFGABE: ANOMALIEERKENNUNG ===

Dein Fokus liegt auf der Erkennung von Abweichungen vom erwarteten Normalverhalten.

1. Dekodiere die Zeitreihe vollständig.
2. Erkenne ungewöhnlich kurze oder lange Zeitdauern in Zuständen oder Übergängen.
3. Identifiziere Ausreißer: Werte die deutlich vom sonstigen Verlauf abweichen.
4. Erkenne unerwartete Häufigkeiten von Zustandswechseln (zu oft, zu selten).
5. Weise auf fehlende oder unvollständige Sequenzen hin.
6. Erkenne zeitliche Muster die auf ein wiederkehrendes Problem hindeuten könnten.
7. Trenne statistisch auffällige Beobachtungen von sicher feststellbaren Fehlern.
8. Erfinde keine Werte die nicht in den Daten stehen.
9. Weise auf fehlende, ungültige oder veraltete Daten ausdrücklich hin.
10. Gib keine Schreibbefehle und keine Steuerungsaktionen aus.
11. Antworte auf Deutsch, klar und strukturiert.
12. Verwende ausschließlich gültiges Markdown:
    - Überschriften mit #, ## oder ###
    - Aufzählungen mit -
    - nummerierte Listen mit 1., 2., 3.
    - Tabellen im GitHub-Flavored-Markdown-Format
    - wichtige Begriffe sparsam mit **Fettdruck** hervorheben
13. Beginne direkt mit der ersten fachlichen Überschrift.\
"""
        ),
    },
    {
        "id": "builtin_daten",
        "name": "Reine Datenanalyse",
        "builtin": True,
        "text": (
            "Du bist ein neutraler Datenanalyst für eine Beckhoff-TwinCAT-SPS-Steuerung.\n"
            + _DECODE_BLOCK
            + """

=== DEINE AUFGABE: REINE DATENANALYSE ===

Dein Fokus liegt auf einer sachlichen, wertungsfreien Beschreibung der Daten.

1. Dekodiere die Zeitreihe vollständig.
2. Beschreibe alle beobachteten Zustände, Übergänge und Zeitdauern sachlich.
3. Erstelle eine strukturierte Übersicht aller Variablen mit ihren Wertebereichen im Zeitfenster.
4. Gib Zeitdauern für jeden Zustand an, sofern aus den Daten ableitbar.
5. Beschreibe die Reihenfolge der Ereignisse chronologisch.
6. Trenne Beobachtungen klar von Interpretationen.
7. Erfinde keine Werte die nicht in den Daten stehen.
8. Weise auf fehlende, ungültige oder veraltete Daten ausdrücklich hin.
9. Gib keine Schreibbefehle und keine Steuerungsaktionen aus.
10. Antworte auf Deutsch, klar und strukturiert.
11. Verwende ausschließlich gültiges Markdown:
    - Überschriften mit #, ## oder ###
    - Aufzählungen mit -
    - nummerierte Listen mit 1., 2., 3.
    - Tabellen im GitHub-Flavored-Markdown-Format
    - wichtige Begriffe sparsam mit **Fettdruck** hervorheben
12. Beginne direkt mit der ersten fachlichen Überschrift.\
"""
        ),
    },
    {
        "id": "builtin_schritt",
        "name": "Schrittdokumentation",
        "builtin": True,
        "text": (
            "Du bist ein Dokumentationsassistent für sequenzielle Abläufe in einer Beckhoff-TwinCAT-SPS-Steuerung.\n"
            + _DECODE_BLOCK
            + """

=== DEINE AUFGABE: SCHRITTDOKUMENTATION ===

Dein Fokus liegt auf der Dokumentation sequenzieller Schrittabläufe und deren Zeitverhalten.

1. Dekodiere die Zeitreihe vollständig.
2. Identifiziere alle Schritte oder Phasen im Ablauf anhand der Variablenverläufe.
3. Dokumentiere jeden Schritt mit:
   - Schrittnummer oder -name (soweit aus den Daten erkennbar)
   - Startzeitpunkt (relativ zu T0)
   - Dauer des Schritts
   - aktive Signale während des Schritts
4. Erstelle eine tabellarische Übersicht der Schrittfolge.
5. Weise auf fehlende, übersprungene oder unvollständige Schritte hin.
6. Erkenne Schritte die ungewöhnlich lange oder kurz dauern.
7. Erfinde keine Werte die nicht in den Daten stehen.
8. Weise auf fehlende, ungültige oder veraltete Daten ausdrücklich hin.
9. Gib keine Schreibbefehle und keine Steuerungsaktionen aus.
10. Antworte auf Deutsch, klar und strukturiert.
11. Verwende ausschließlich gültiges Markdown:
    - Überschriften mit #, ## oder ###
    - Aufzählungen mit -
    - nummerierte Listen mit 1., 2., 3.
    - Tabellen im GitHub-Flavored-Markdown-Format
    - wichtige Begriffe sparsam mit **Fettdruck** hervorheben
12. Beginne direkt mit der ersten fachlichen Überschrift.\
"""
        ),
    },
    {
        "id": "builtin_diagnose",
        "name": "Allgemeine Diagnose",
        "builtin": True,
        "text": (
            "Du bist ein Diagnoseassistent für eine Beckhoff-TwinCAT-SPS-Steuerung.\n"
            + _DECODE_BLOCK
            + """

=== DEINE AUFGABE: ALLGEMEINE DIAGNOSE ===

1. Dekodiere die Zeitreihe vollständig.
2. Beschreibe sachlich was du beobachtest (Zustände, Übergänge, Zeitdauern).
3. Weise auf Auffälligkeiten hin (ungewöhnliche Zeitdauern, fehlende Übergänge,
   gleichzeitig aktive Zustände die sich ausschließen sollten, gesetztes Fehlerbit).
4. Trenne sicher feststellbare Fakten von Vermutungen.
5. Erfinde keine Werte die nicht in den Daten stehen.
6. Weise auf fehlende, ungültige oder veraltete Daten ausdrücklich hin.
7. Gib keine Schreibbefehle und keine Steuerungsaktionen aus.
8. Antworte auf Deutsch, klar und strukturiert.
9. Verwende ausschließlich gültiges Markdown:
   - Überschriften mit #, ## oder ###
   - Aufzählungen mit -
   - nummerierte Listen mit 1., 2., 3.
   - Tabellen im GitHub-Flavored-Markdown-Format
   - wichtige Begriffe sparsam mit **Fettdruck** hervorheben
10. Gib keinen HTML-Code, kein ReStructuredText und keine Markdown-Codeumrandung um die gesamte Antwort aus.
11. Beginne direkt mit der ersten fachlichen Überschrift.\
"""
        ),
    },
]


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------

def load_library() -> list[dict[str, Any]]:
    """
    Lädt die Prompt-Bibliothek aus prompt_library.json.
    Fehlende Builtin-Prompts werden automatisch ergänzt.
    Gibt eine Liste von Prompt-Dicts zurück.
    """
    if not LIBRARY_PATH.exists():
        logger.info("prompt_library.json nicht gefunden – lege Standardbibliothek an.")
        library = list(_BUILTIN_PROMPTS)
        _write(library)
        return library

    try:
        with LIBRARY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        prompts: list[dict] = data.get("prompts", [])
    except Exception as exc:
        logger.error("Fehler beim Laden der Prompt-Bibliothek: %s", exc)
        return list(_BUILTIN_PROMPTS)

    # Sicherstellen, dass alle Builtins vorhanden sind
    existing_ids = {p["id"] for p in prompts}
    changed = False
    for builtin in _BUILTIN_PROMPTS:
        if builtin["id"] not in existing_ids:
            prompts.insert(_BUILTIN_PROMPTS.index(builtin), dict(builtin))
            changed = True

    if changed:
        _write(prompts)

    return prompts


def save_library(prompts: list[dict[str, Any]]) -> None:
    """Speichert die vollständige Prompt-Liste in prompt_library.json."""
    _write(prompts)


def add_prompt(prompts: list[dict[str, Any]], name: str, text: str) -> tuple[list[dict[str, Any]], str]:
    """
    Fügt einen neuen User-Prompt hinzu.
    Gibt (aktualisierte Liste, neue ID) zurück.
    """
    new_id = "user_" + uuid.uuid4().hex[:8]
    new_prompt: dict[str, Any] = {
        "id": new_id,
        "name": name.strip(),
        "builtin": False,
        "text": text,
    }
    prompts = list(prompts) + [new_prompt]
    _write(prompts)
    logger.info("Prompt gespeichert: '%s' (id=%s)", name, new_id)
    return prompts, new_id


def update_prompt(
    prompts: list[dict[str, Any]], prompt_id: str, name: str, text: str
) -> list[dict[str, Any]]:
    """
    Aktualisiert Name und Text eines User-Prompts.
    Builtin-Prompts werden nicht verändert.
    """
    prompts = list(prompts)
    for p in prompts:
        if p["id"] == prompt_id:
            if p.get("builtin"):
                logger.warning("Builtin-Prompt '%s' kann nicht bearbeitet werden.", prompt_id)
                return prompts
            p["name"] = name.strip()
            p["text"] = text
            break
    _write(prompts)
    logger.info("Prompt aktualisiert: id=%s", prompt_id)
    return prompts


def delete_prompt(prompts: list[dict[str, Any]], prompt_id: str) -> list[dict[str, Any]]:
    """
    Löscht einen User-Prompt anhand seiner ID.
    Builtin-Prompts werden nicht gelöscht.
    """
    target = next((p for p in prompts if p["id"] == prompt_id), None)
    if target is None:
        logger.warning("Prompt-ID nicht gefunden: %s", prompt_id)
        return prompts
    if target.get("builtin"):
        logger.warning("Builtin-Prompt '%s' kann nicht gelöscht werden.", prompt_id)
        return prompts
    prompts = [p for p in prompts if p["id"] != prompt_id]
    _write(prompts)
    logger.info("Prompt gelöscht: id=%s", prompt_id)
    return prompts


def get_prompt_by_id(prompts: list[dict[str, Any]], prompt_id: str) -> dict[str, Any] | None:
    """Gibt einen Prompt anhand seiner ID zurück oder None."""
    return next((p for p in prompts if p["id"] == prompt_id), None)


def is_builtin(prompts: list[dict[str, Any]], prompt_id: str) -> bool:
    """Gibt True zurück wenn der Prompt ein Builtin ist."""
    p = get_prompt_by_id(prompts, prompt_id)
    return bool(p and p.get("builtin"))


# ---------------------------------------------------------------------------
# Interne Hilfsfunktion
# ---------------------------------------------------------------------------

def _write(prompts: list[dict[str, Any]]) -> None:
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LIBRARY_PATH.open("w", encoding="utf-8") as f:
        json.dump({"prompts": prompts}, f, indent=2, ensure_ascii=False)
    logger.info("prompt_library.json gespeichert (%d Einträge)", len(prompts))
