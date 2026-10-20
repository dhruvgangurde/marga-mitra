from datetime import UTC, datetime

from backend.app import explain
from backend.app.explain import icon_for, plan_reasons, work_reasons
from contracts.fakes import tiny_scenario
from contracts.models import Assignment, Metrics, NegotiationMessage, NegotiationOption, Plan
from tests.backend.test_api_plans import wait_for_run

S = tiny_scenario(1)
WORKS = {w.work_id: w for w in S.works}
ACCEPT = "Telecom accepts option C for T-001: shared trench, 10–14 Nov. Saves ₹3,36,000."


def _p0001() -> Plan:
    def a(wid: str, start: int, end: int, reason: str, group: str | None = None) -> Assignment:
        return Assignment(work_id=wid, start_day=start, end_day=end, mode="open_cut", shared_group=group, reason=reason)

    return Plan(plan_id="P-0001", seed=1, variant="orchestrated", status="approved",
                created_at=datetime(2026, 11, 10, 4, 32, 23, tzinfo=UTC), assignments=[
                    a("W-001", 8, 12, "Shares one trench with Telecom T-001.", "G1"),
                    a("T-001", 8, 12, "Shares one trench with Water W-001.", "G1"),
                    a("G-001", 9, 12, "Dates agreed in the negotiation."),
                    a("R-001", 13, 15, "Resurfaces after every dig on the road.")])


def _accept() -> NegotiationMessage:
    option = NegotiationOption(label="C · Shared trench, 10–14 Nov", work_id="T-001", start_day=8, mode="open_cut",
                               shared_group="G1", cost_delta_inr=-336000)
    return NegotiationMessage(msg_id="M3", run_id="RUN-0001", round=1, sender="telecom", recipients=["coordinator"],
                              type="ACCEPT", work_ids=["T-001"], body=ACCEPT, options=[option], chosen_option=0,
                              ts=datetime(2026, 11, 10, 4, 32, 16, tzinfo=UTC))


def _why(wid: str) -> list[tuple[str, str, str, str]]:
    plan = _p0001()
    a = next(x for x in plan.assignments if x.work_id == wid)
    return [(r.icon, r.lead, r.text, r.source) for r in work_reasons(WORKS[wid], a, plan, S, [_accept()])]


def _metrics(*v: float) -> Metrics:
    return Metrics(plan_id="P", excavations=0, digs_per_road=v[0], lane_closure_hours=v[1], trench_hours_in_rain=v[2],
                   clashes=int(v[3]), days_late=v[4], cost_inr=int(v[5]), dust_score=0.0)


def test_icon_for_scheduler_reasons():
    reasons = {
        "Emergency: started at once.": "siren",
        "Shares one trench with Telecom T-001.": "handshake",
        "Trenchless: Test Road is a protected road.": "lock",
        "Trenchless: no road cut.": "road",
        "As the department asked.": "check",
        "Moved after the rain: the road is low-lying.": "rain",
        "Moved to keep the road free for Procession, 20 Nov.": "flag",
        "Resurfaces after every dig on the road.": "road",
        "Starts after the shared trench is closed.": "clock",
        "Dates agreed in the negotiation.": "handshake",
        "Moved to avoid a clash on Test Road.": "clock",
    }
    assert {r: icon_for(r) for r in reasons} == reasons


def test_shared_trench_and_moved_start():
    first, moved, order = _why("T-001")
    assert first == ("handshake", "Shares one trench with Water (W-001).", "One dig instead of two on the same 400 m.",
                     "negotiation, round 1, 10:02:16")
    assert moved == ("clock", "Starts on 10 Nov, not 12 Nov.", ACCEPT, "negotiation, round 1, 10:02:16")
    assert order[:2] == ("road", "Ends before resurfacing on 15 Nov.")


def test_resurfacing_reasons():
    reasons = _why("R-001")
    assert reasons[1] == ("clock", "Starts on 15 Nov, not 11 Nov.", "The Roads department asked for 11 Nov.",
                          "the scheduler, 10:02")
    assert reasons[-1][1:3] == ("Starts after the last dig ends on 14 Nov.", "Test Road is then protected for 3 years.")


def test_plan_reasons():
    reasons = plan_reasons(_metrics(2.7, 450, 48, 4, 0.0, 4988000), _metrics(2.0, 360, 0, 0, 0.4, 4364000), "x")
    assert [r.icon for r in reasons] == ["shovel", "car", "rain", "warning", "clock", "rupee"]
    assert (reasons[0].lead, reasons[-1].lead) == ("Digs per road 2.7 → 2.0.", "Cost ₹49,88,000 → ₹43,64,000.")
    assert [r.text for r in reasons].count("Worse than before.") == 1
    assert reasons[4].text == "Worse than before."
    same = _metrics(2.0, 360, 0, 0, 0.4, 4364000)
    assert [r.lead for r in plan_reasons(same, same, "x")] == ["Same numbers as before."]


def test_explain_a_work(client, monkeypatch):
    monkeypatch.setattr(explain, "forecast_summary", lambda *a: {"max_rain_mm": 18.0, "max_aqi": 88, "band": "Satisfactory"})
    why = client.get("/explain/W-001").json()
    assert client.get("/explain/work:W-001").json() == why
    assert (why["entity"], why["title"], why["ledger_seqs"]) == ("work:W-001", "Why these dates?", [])
    assert [(r["icon"], r["lead"]) for r in why["reasons"]] == [
        ("check", "As the department asked."), ("warning", "Still digging when resurfacing R-001 starts on 11 Nov.")]
    assert (why["reasons"][0]["text"], why["reasons"][0]["source"]) == (
        "Planned for 10–14 Nov, open cut.", "the departments' requests")
    assert [(c["severity"], c["name"], c["detail"]) for c in why["rules"]] == [
        ("ok", "Road is not protected", "Test Road is not in the protected-road list"),
        ("ok", "Deposit held until the repair is verified", "₹2,00,000"),
        ("warn", "Heavy rain on this road during the work", "Heavy rain, 14–15 Nov"),
        ("ok", "Air quality is fine for open cuts", "AQI 88 · Satisfactory"),
    ]
    monkeypatch.setattr(explain, "forecast_summary", lambda *a: None)
    assert client.get("/explain/W-001").json()["rules"][3]["detail"] == "No poor-air days in these dates"


def test_explain_a_plan(client):
    why = client.get("/explain/P-OLD-1").json()
    assert client.get("/explain/plan:P-OLD-1").json() == why
    assert (why["entity"], why["title"]) == ("plan:P-OLD-1", "Why this plan?")
    assert [r["lead"] for r in why["reasons"]] == ["This is the old way."]
    assert [(c["name"], c["severity"]) for c in why["rules"]] == [
        ("Protected roads", "ok"), ("Deposits", "ok"), ("Heavy rain", "warn"), ("Poor air", "ok"),
        ("Event routes", "ok"), ("Resurfacing order", "fail")]
    client.post("/plan/orchestrate")
    wait_for_run(client, "RUN-0001")
    [same] = client.get("/explain/P-FAKE").json()["reasons"]
    assert (same["icon"], same["lead"], same["source"]) == ("info", "Same numbers as before.", "compared with the old way")
    for unknown in ("W-999", "plan:P-9999", "work:P-OLD-1"):
        r = client.get(f"/explain/{unknown}")
        assert (r.status_code, r.json()["detail"]) == (404, "Unknown work or plan.")
