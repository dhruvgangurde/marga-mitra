from agents.copilot_rules import HELP, plan
from agents.copilot_tools import Next

TOAST = "Plan updated. {moved} works moved out of the rain window."


def fields(steps):
    return [n.model_dump(exclude_none=True) for n in steps]


def test_the_rain_question():
    steps = plan("Rain is coming on 14 Nov. Re-plan and show me what moved.")
    assert fields(steps) == [
        {"tool": "simulate_rain", "start_day": 12, "end_day": 13, "mm": 70.0},
        {"tool": "set_day", "day": 12},
        {"tool": "open_tab", "tab": "risk"},
        {"tool": "show_toast", "text": TOAST},
    ]


def test_rain_with_dates_and_millimetres():
    steps = plan("Simulate 85 mm of rain on 20–21 Nov")
    assert fields(steps)[0] == {"tool": "simulate_rain", "start_day": 18, "end_day": 19, "mm": 85.0}
    assert fields(steps)[1] == {"tool": "set_day", "day": 18}


def test_rain_outside_the_horizon_is_not_simulated():
    assert plan("Rain on 30 Nov") == []
    assert plan("Rain on 1 Nov") == []


def test_a_storm_counts_as_rain_without_a_date():
    assert fields(plan("What if a storm hits?"))[0] == {"tool": "simulate_rain", "start_day": 12, "end_day": 13, "mm": 70.0}


def test_the_road_question():
    assert fields(plan("Show every dig on Munchur Road next week")) == [
        {"tool": "list_works", "road": "Munchur Road"},
        {"tool": "open_tab", "tab": "works"},
        {"tool": "select_work", "work_id": "{first}"},
        {"tool": "fit_work", "work_id": "{first}"},
    ]


def test_why_questions_open_the_work():
    assert fields(plan("Why does W-104 start on 10 Nov?")) == [
        {"tool": "explain", "work_id": "W-104"}, {"tool": "open_drawer", "work_id": "W-104"}]
    assert fields(plan("Why did D-412 move out of the rain?")) == [
        {"tool": "explain", "work_id": "D-412"}, {"tool": "open_drawer", "work_id": "D-412"}]


def test_a_work_id_in_lower_case_is_upper_cased():
    assert plan("why t-221?")[0].work_id == "T-221"


def test_what_if_a_work_starts_late():
    assert fields(plan("What if T-221 starts 2 days late?")) == [{"tool": "what_if", "work_id": "T-221", "days": 2}]


def test_a_date_moves_the_day():
    assert fields(plan("Go to 20 Nov")) == [{"tool": "set_day", "day": 18}]


def test_anything_else_gets_the_help_text():
    assert plan("Hello") == []
    assert "Munchur Road" in HELP


def test_plans_are_next_steps():
    assert all(isinstance(n, Next) for n in plan("Show every dig on Munchur Road"))
