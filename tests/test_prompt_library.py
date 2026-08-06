"""
test_prompt_library.py – Unit-Tests für die Prompt-Bibliothek.

Testet ausschließlich die Bibliothekslogik ohne Dateisystem-Seiteneffekte.
Kein echter ADS-Client, kein LM Studio, keine Simulation.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Wir importieren das Modul und patchen LIBRARY_PATH auf ein Temp-Verzeichnis
import prompt_library as pl


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_library_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Leitet LIBRARY_PATH auf ein temporäres Verzeichnis um."""
    lib_path = tmp_path / "config" / "prompt_library.json"
    monkeypatch.setattr(pl, "LIBRARY_PATH", lib_path)
    return lib_path


@pytest.fixture()
def fresh_library(tmp_library_path: Path) -> list[dict]:
    """Gibt eine frisch geladene Bibliothek zurück (nur Builtins)."""
    return pl.load_library()


# ---------------------------------------------------------------------------
# load_library
# ---------------------------------------------------------------------------

class TestLoadLibrary:
    def test_creates_file_if_missing(self, tmp_library_path: Path, fresh_library):
        assert tmp_library_path.exists()

    def test_contains_all_builtins(self, fresh_library):
        builtin_ids = {p["id"] for p in fresh_library if p.get("builtin")}
        expected = {"builtin_fehler", "builtin_anomalie", "builtin_daten", "builtin_schritt", "builtin_diagnose"}
        assert expected == builtin_ids

    def test_builtin_texts_not_empty(self, fresh_library):
        for p in fresh_library:
            if p.get("builtin"):
                assert len(p["text"]) > 50, f"Builtin '{p['name']}' hat zu kurzen Text"

    def test_builtin_names_present(self, fresh_library):
        names = {p["name"] for p in fresh_library}
        assert "Fehlererkennung" in names
        assert "Anomalieerkennung" in names
        assert "Reine Datenanalyse" in names
        assert "Schrittdokumentation" in names
        assert "Allgemeine Diagnose" in names

    def test_missing_builtin_is_restored(self, tmp_library_path: Path):
        """Wenn ein Builtin fehlt, wird es beim nächsten Laden ergänzt."""
        tmp_library_path.parent.mkdir(parents=True, exist_ok=True)
        # Schreibe Bibliothek ohne builtin_anomalie
        data = {"prompts": [p for p in pl._BUILTIN_PROMPTS if p["id"] != "builtin_anomalie"]}
        tmp_library_path.write_text(json.dumps(data), encoding="utf-8")
        library = pl.load_library()
        ids = {p["id"] for p in library}
        assert "builtin_anomalie" in ids

    def test_returns_list(self, fresh_library):
        assert isinstance(fresh_library, list)
        assert len(fresh_library) > 0


# ---------------------------------------------------------------------------
# add_prompt
# ---------------------------------------------------------------------------

class TestAddPrompt:
    def test_adds_user_prompt(self, fresh_library, tmp_library_path):
        updated, new_id = pl.add_prompt(fresh_library, "Mein Test", "Testtext")
        assert any(p["id"] == new_id for p in updated)

    def test_new_prompt_not_builtin(self, fresh_library, tmp_library_path):
        updated, new_id = pl.add_prompt(fresh_library, "Mein Test", "Testtext")
        p = pl.get_prompt_by_id(updated, new_id)
        assert p is not None
        assert p["builtin"] is False

    def test_new_prompt_name_and_text(self, fresh_library, tmp_library_path):
        updated, new_id = pl.add_prompt(fresh_library, "  Mein Prompt  ", "Inhalt")
        p = pl.get_prompt_by_id(updated, new_id)
        assert p["name"] == "Mein Prompt"  # strip
        assert p["text"] == "Inhalt"

    def test_id_starts_with_user(self, fresh_library, tmp_library_path):
        _, new_id = pl.add_prompt(fresh_library, "X", "Y")
        assert new_id.startswith("user_")

    def test_file_is_updated(self, fresh_library, tmp_library_path):
        pl.add_prompt(fresh_library, "Gespeichert", "Text")
        data = json.loads(tmp_library_path.read_text(encoding="utf-8"))
        names = [p["name"] for p in data["prompts"]]
        assert "Gespeichert" in names

    def test_multiple_prompts_independent(self, fresh_library, tmp_library_path):
        lib, id1 = pl.add_prompt(fresh_library, "Eins", "A")
        lib, id2 = pl.add_prompt(lib, "Zwei", "B")
        assert id1 != id2
        assert pl.get_prompt_by_id(lib, id1) is not None
        assert pl.get_prompt_by_id(lib, id2) is not None


# ---------------------------------------------------------------------------
# update_prompt
# ---------------------------------------------------------------------------

class TestUpdatePrompt:
    def test_updates_user_prompt(self, fresh_library, tmp_library_path):
        lib, new_id = pl.add_prompt(fresh_library, "Alt", "Alter Text")
        lib = pl.update_prompt(lib, new_id, "Neu", "Neuer Text")
        p = pl.get_prompt_by_id(lib, new_id)
        assert p["name"] == "Neu"
        assert p["text"] == "Neuer Text"

    def test_builtin_cannot_be_updated(self, fresh_library, tmp_library_path):
        original_text = pl.get_prompt_by_id(fresh_library, "builtin_fehler")["text"]
        lib = pl.update_prompt(fresh_library, "builtin_fehler", "Geändert", "Neuer Text")
        p = pl.get_prompt_by_id(lib, "builtin_fehler")
        assert p["text"] == original_text  # unverändert

    def test_unknown_id_returns_unchanged(self, fresh_library, tmp_library_path):
        count_before = len(fresh_library)
        lib = pl.update_prompt(fresh_library, "user_nichtvorhanden", "X", "Y")
        assert len(lib) == count_before


# ---------------------------------------------------------------------------
# delete_prompt
# ---------------------------------------------------------------------------

class TestDeletePrompt:
    def test_deletes_user_prompt(self, fresh_library, tmp_library_path):
        lib, new_id = pl.add_prompt(fresh_library, "Lösch mich", "Text")
        lib = pl.delete_prompt(lib, new_id)
        assert pl.get_prompt_by_id(lib, new_id) is None

    def test_builtin_cannot_be_deleted(self, fresh_library, tmp_library_path):
        count_before = len(fresh_library)
        lib = pl.delete_prompt(fresh_library, "builtin_fehler")
        assert len(lib) == count_before
        assert pl.get_prompt_by_id(lib, "builtin_fehler") is not None

    def test_unknown_id_returns_unchanged(self, fresh_library, tmp_library_path):
        count_before = len(fresh_library)
        lib = pl.delete_prompt(fresh_library, "user_nichtvorhanden")
        assert len(lib) == count_before

    def test_file_updated_after_delete(self, fresh_library, tmp_library_path):
        lib, new_id = pl.add_prompt(fresh_library, "Weg", "Text")
        lib = pl.delete_prompt(lib, new_id)
        data = json.loads(tmp_library_path.read_text(encoding="utf-8"))
        ids = [p["id"] for p in data["prompts"]]
        assert new_id not in ids


# ---------------------------------------------------------------------------
# is_builtin / get_prompt_by_id
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_is_builtin_true(self, fresh_library):
        assert pl.is_builtin(fresh_library, "builtin_fehler") is True

    def test_is_builtin_false_for_user(self, fresh_library, tmp_library_path):
        lib, new_id = pl.add_prompt(fresh_library, "User", "Text")
        assert pl.is_builtin(lib, new_id) is False

    def test_is_builtin_false_for_unknown(self, fresh_library):
        assert pl.is_builtin(fresh_library, "unbekannt") is False

    def test_get_prompt_by_id_returns_none_for_unknown(self, fresh_library):
        assert pl.get_prompt_by_id(fresh_library, "xyz") is None

    def test_get_prompt_by_id_returns_correct(self, fresh_library):
        p = pl.get_prompt_by_id(fresh_library, "builtin_anomalie")
        assert p is not None
        assert p["name"] == "Anomalieerkennung"


# ---------------------------------------------------------------------------
# Datenschutz: Kein KI-Symbol ohne Auswahl
# (Bibliothekslogik selbst überträgt keine Daten – Test dokumentiert Grenze)
# ---------------------------------------------------------------------------

class TestDataBoundary:
    def test_library_contains_no_ads_values(self, fresh_library):
        """Die Bibliothek enthält keine ADS-Prozesswerte – nur Prompt-Texte."""
        for p in fresh_library:
            assert "ADS-Verbindung:" not in p["text"] or "verbunden" not in p["text"], (
                "Prompt-Text enthält unerwartete ADS-Laufzeitdaten"
            )

    def test_builtin_texts_contain_decode_rule(self, fresh_library):
        """Alle Builtins enthalten die Dekodierungsregel."""
        for p in fresh_library:
            if p.get("builtin"):
                assert "DEKODIERUNGSREGEL" in p["text"], (
                    f"Builtin '{p['name']}' enthält keine Dekodierungsregel"
                )

    def test_builtin_texts_contain_read_only(self, fresh_library):
        """Alle Builtins enthalten den read_only-Hinweis."""
        for p in fresh_library:
            if p.get("builtin"):
                assert "read_only=true" in p["text"], (
                    f"Builtin '{p['name']}' enthält keinen read_only-Hinweis"
                )
