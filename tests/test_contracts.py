import asyncio
import inspect

from contracts import costs, interfaces, models
from contracts.fakes import MemoryStore, fake_deps, tiny_scenario
from contracts.models import Dept, Mode


def test_every_model_has_a_json_schema():
    for name, obj in vars(models).items():
        if inspect.isclass(obj) and issubclass(obj, models.Model) and obj is not models.Model:
            assert obj.model_json_schema()["title"] == name


def test_tiny_scenario_round_trips():
    s = tiny_scenario()
    again = models.Scenario.model_validate_json(s.model_dump_json())
    assert again == s
    assert s.parallel_groups[0].saving_inr > 0


def test_costs_are_deterministic_and_indian_formatted():
    assert costs.work_cost_inr(Dept.water, 620, Mode.open_cut) == costs.work_cost_inr(Dept.water, 620, Mode.open_cut)
    assert costs.work_cost_inr(Dept.telecom, 300, Mode.trenchless) > costs.dig_cost_inr(Dept.telecom, 300, Mode.open_cut)
    assert costs.inr(240000) == "₹2,40,000"
    assert costs.inr(-1640000) == "−₹16,40,000"
    assert costs.inr(950) == "₹950"
    assert costs.deposit_inr(Dept.water, 620, Mode.open_cut) % 10000 == 0


def test_fake_deps_run_and_ledger_chains():
    store = MemoryStore()
    deps = fake_deps(store)
    s = deps.generate_scenario(1)
    plan = deps.solve(s, models.SolveConstraints())
    out = asyncio.run(deps.negotiate(s, plan, deps.detect_conflicts(s, plan), "RUN-1", deps.emit))
    assert out.messages and store.events[0].type == "negotiation.message"
    a = asyncio.run(deps.ledger_append("scheduler", "plan.decided", "plan:P-FAKE", "Plan made", {}))
    b = asyncio.run(deps.ledger_append("rules", "rules.passed", "plan:P-FAKE", "Rules check passed", {}))
    assert b.prev_hash == a.hash and len(a.hash) == 64


def test_interface_table_names_exist():
    for name in interfaces.IMPLEMENTATIONS:
        assert callable(getattr(interfaces, name))


def test_rules_on_the_tiny_scenario():
    from contracts import rules
    from contracts.fakes import fake_naive_plan

    s = tiny_scenario()
    plan = fake_naive_plan(s)
    kinds = sorted(c.kind.value for c in rules.find_clashes(s, plan))
    assert kinds == ["order", "order", "order", "risk", "risk", "same_road"]
    assert rules.clash_count(s, plan) == 4
    assert rules.digs_per_segment(s, plan) == {"S-0001": 3, "S-0002": 3, "S-0003": 2}
    assert rules.rain_trench_hours(s, plan) == 48.0
    shared = plan.model_copy(update={"assignments": [
        a.model_copy(update={"shared_group": "G1", "start_day": 10, "end_day": 14}) if a.work_id in ("W-001", "T-001") else a
        for a in plan.assignments]})
    assert rules.digs_per_segment(s, shared)["S-0001"] == 2


def test_fake_workflow_waits_for_approval_then_records_it():
    from contracts.fakes import fake_resume_run, fake_start_run

    store = MemoryStore()
    deps = fake_deps(store)
    res = asyncio.run(fake_start_run(deps, "RUN-1", 1))
    assert res.status == "waiting_approval" and res.approval_id in store.approvals
    done = asyncio.run(fake_resume_run(deps, "RUN-1", "approve", "ward_engineer"))
    assert done.status == "approved" and store.ledger[-1].action == "plan.approved"
