"""
test_core.py - Automatisierte Tests fuer Kernlogik.
Laufen ohne echte SPS und ohne LM Studio.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.domain.history_model import HistoryModel, HistoryEntry
from app.domain.state_model import StateModel, VariableState
from app.llm.prompt_builder import build_user_message


# ------------------------------------------------------------------
# HistoryModel Tests
# ------------------------------------------------------------------

class TestHistoryModel:
    def test_add_and_count(self):
        h = HistoryModel(max_entries=100)
        h.add("MAIN.bRed", "BOOL", True)
        h.add("MAIN.bGreen", "BOOL", False)
        assert h.count() == 2

    def test_max_entries_limit(self):
        h = HistoryModel(max_entries=5)
        for i in range(10):
            h.add("SYM", "INT", i)
        assert h.count() == 5

    def test_window_filter_by_time(self):
        h = HistoryModel()
        now = datetime.now()
        h.add("SYM", "BOOL", True)
        result = h.get_window(from_dt=now - timedelta(seconds=5), to_dt=now + timedelta(seconds=5))
        assert len(result) == 1

    def test_window_filter_by_symbol(self):
        h = HistoryModel()
        h.add("SYM_A", "BOOL", True)
        h.add("SYM_B", "INT", 42)
        result = h.get_window(from_dt=None, to_dt=None, symbols=["SYM_A"])
        assert len(result) == 1
        assert result[0].symbol == "SYM_A"

    def test_clear(self):
        h = HistoryModel()
        h.add("SYM", "BOOL", True)
        h.clear()
        assert h.count() == 0

    def test_max_entries_change(self):
        h = HistoryModel(max_entries=100)
        for i in range(50):
            h.add("SYM", "INT", i)
        h.max_entries = 10
        assert h.count() == 10


# ------------------------------------------------------------------
# StateModel Tests
# ------------------------------------------------------------------

class TestStateModel:
    def _make_vs(self, symbol: str) -> VariableState:
        return VariableState(symbol=symbol, data_type="BOOL", tc_type="BOOL")

    def test_set_and_get(self):
        sm = StateModel()
        sm.set_symbols([self._make_vs("MAIN.bRed")])
        vs = sm.get("MAIN.bRed")
        assert vs is not None
        assert vs.symbol == "MAIN.bRed"

    def test_update_value(self):
        sm = StateModel()
        sm.set_symbols([self._make_vs("MAIN.bRed")])
        sm.update_value("MAIN.bRed", True)
        vs = sm.get("MAIN.bRed")
        assert vs.value is True
        assert vs.valid is True

    def test_mark_invalid(self):
        sm = StateModel()
        sm.set_symbols([self._make_vs("MAIN.bRed")])
        sm.update_value("MAIN.bRed", True)
        sm.mark_invalid("MAIN.bRed")
        assert sm.get("MAIN.bRed").valid is False

    def test_selection(self):
        sm = StateModel()
        sm.set_symbols([self._make_vs("MAIN.bRed")])
        sm.set_selection("MAIN.bRed", show=True, log=True, ai=True)
        vs = sm.get("MAIN.bRed")
        assert vs.show and vs.log and vs.ai

    def test_get_ai_symbols(self):
        sm = StateModel()
        vs1 = self._make_vs("A")
        vs2 = self._make_vs("B")
        sm.set_symbols([vs1, vs2])
        sm.set_selection("A", show=True, log=False, ai=True)
        sm.set_selection("B", show=True, log=False, ai=False)
        ai = sm.get_ai_symbols()
        assert len(ai) == 1
        assert ai[0].symbol == "A"

    def test_clear(self):
        sm = StateModel()
        sm.set_symbols([self._make_vs("A")])
        sm.clear()
        assert sm.get_all() == []


# ------------------------------------------------------------------
# PromptBuilder Tests
# ------------------------------------------------------------------

class TestPromptBuilder:
    def _make_vs(self, symbol: str, value=True, valid=True) -> VariableState:
        vs = VariableState(symbol=symbol, data_type="BOOL", tc_type="BOOL")
        vs.value = value
        vs.valid = valid
        vs.timestamp = datetime.now()
        return vs

    def test_prompt_contains_symbol(self):
        vs = self._make_vs("MAIN.bRed", True)
        msg = build_user_message([vs], [], None, None, True)
        assert "MAIN.bRed" in msg

    def test_prompt_contains_value(self):
        vs = self._make_vs("MAIN.bRed", True)
        msg = build_user_message([vs], [], None, None, True)
        assert "True" in msg

    def test_prompt_no_unselected_symbols(self):
        vs_ai = self._make_vs("MAIN.bRed", True)
        vs_not = self._make_vs("MAIN.bGreen", False)
        msg = build_user_message([vs_ai], [], None, None, True)
        assert "MAIN.bGreen" not in msg

    def test_prompt_contains_history(self):
        from app.domain.history_model import HistoryEntry
        entry = HistoryEntry(
            timestamp=datetime.now(),
            symbol="MAIN.bRed",
            data_type="BOOL",
            value=True,
        )
        vs = self._make_vs("MAIN.bRed")
        msg = build_user_message([vs], [entry], None, None, True)
        assert "MAIN.bRed" in msg
        assert "Verlaufshistorie" in msg

    def test_prompt_ads_disconnected(self):
        msg = build_user_message([], [], None, None, False)
        assert "NICHT verbunden" in msg

    def test_prompt_no_ai_symbols(self):
        msg = build_user_message([], [], None, None, True)
        assert "Keine Symbole" in msg

    def test_prompt_read_only_flag(self):
        msg = build_user_message([], [], None, None, True)
        assert "read_only=true" in msg


# ------------------------------------------------------------------
# LmStudioClient Tests (ohne echtes LM Studio)
# ------------------------------------------------------------------

class TestLmStudioClient:
    def test_check_connection_fails_gracefully(self):
        from app.llm.lm_studio_client import LmStudioClient
        client = LmStudioClient(base_url="http://127.0.0.1:9999/v1")
        ok, msg = client.check_connection()
        assert ok is False
        assert len(msg) > 0

    def test_analyze_fails_gracefully(self):
        from app.llm.lm_studio_client import LmStudioClient
        client = LmStudioClient(base_url="http://127.0.0.1:9999/v1", timeout_seconds=2.0)
        answer, ok = client.analyze("system", "user")
        assert ok is False
        assert len(answer) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
