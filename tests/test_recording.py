from datetime import datetime, timedelta
from app.domain.history_model import HistoryModel
from app.domain.state_model import StateModel, VariableState
from app.llm.prompt_builder import build_user_message


def make_state(symbol="MAIN.Signal", data_type="BOOL", value=False):
    state = VariableState(symbol=symbol, data_type=data_type, tc_type=data_type)
    state.value = value
    state.timestamp = datetime.now()
    state.valid = True
    state.recording = True
    return state


def test_one_recording_flag_controls_all_data_paths():
    model = StateModel()
    model.set_symbols([make_state("A"), make_state("B")])
    model.set_recording("A", True)
    model.set_recording("B", False)
    assert [v.symbol for v in model.get_recorded_symbols()] == ["A"]


def test_timestamp_changes_only_when_value_changes():
    model = StateModel()
    model.set_symbols([VariableState("A", "BOOL", "BOOL")])
    first = datetime(2026, 8, 4, 12, 0, 0)
    second = first + timedelta(seconds=1)
    assert model.update_value("A", False, first) is True
    assert model.update_value("A", False, second) is False
    assert model.get("A").timestamp == first
    assert model.update_value("A", True, second) is True
    assert model.get("A").timestamp == second


def test_history_preserves_ads_timestamp_and_limits():
    history = HistoryModel(max_entries=2)
    t0 = datetime(2026, 8, 4, 12, 0, 0)
    history.add("A", "BOOL", False, t0)
    history.add("A", "BOOL", True, t0 + timedelta(seconds=1))
    history.add("A", "BOOL", False, t0 + timedelta(seconds=2))
    entries = history.get_window(None, None)
    assert entries[0].timestamp == t0 + timedelta(seconds=1)
    assert history.evicted_total == 1


def test_prompt_contains_only_recorded_symbols_and_timestamps():
    selected = make_state("A", value=True)
    not_selected = make_state("B", value=True)
    not_selected.recording = False
    message = build_user_message([selected], [], None, None, True)
    assert "A" in message
    assert "B" not in message
    assert "@2026" not in message or "A" in message
