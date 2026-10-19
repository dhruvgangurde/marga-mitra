"""The time-indexed scheduling model: one yes/no choice per work, method and start day."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from ortools.sat.python import cp_model

from contracts import costs
from contracts.models import Mode, ParallelGroup, Scenario, Segment, SolveConstraints, Work, WorkModeOption

UNPLACED_COST = 100000


def weights() -> dict[str, float]:
    return costs.policy()["objective_weights"]


@dataclass
class Built:
    model: cp_model.CpModel
    choices: dict[tuple[str, Mode, int], tuple[cp_model.IntVar, int]] = field(default_factory=dict)
    trenches: dict[tuple[str, int], tuple[cp_model.IntVar, int]] = field(default_factory=dict)
    placed: dict[str, cp_model.IntVar] = field(default_factory=dict)
    groups: dict[str, ParallelGroup] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def protected_on(scenario: Scenario, work: Work, start: int) -> bool:
    day = scenario.start_date + timedelta(days=start)
    segs = {s.segment_id: s for s in scenario.segments}
    return any(segs[s].protected_until and segs[s].protected_until >= day for s in work.segment_ids)


def allowed(scenario: Scenario, constraints: SolveConstraints, work: Work, option: WorkModeOption, start: int) -> bool:
    end = start + option.duration_days - 1
    if start < work.earliest_start or end > work.latest_end or end > scenario.horizon_days - 1:
        return False
    pinned = constraints.pinned_start.get(work.work_id)
    if pinned is not None and pinned != start:
        return False
    if start < constraints.min_start.get(work.work_id, start):
        return False
    if any(start <= d <= end for d in constraints.forbidden_days.get(work.work_id, [])):
        return False
    if work.is_emergency:
        return start == work.requested_start
    return not (option.mode == Mode.open_cut and protected_on(scenario, work, start))


def _choice_cost(work: Work, option: WorkModeOption, start: int, segments_by_id: dict[str, Segment],
                 w: dict[str, float]) -> int:
    """The one place where the weights turn a choice into a cost."""
    shift = start - work.requested_start
    cost = option.cost_inr // 1000 + round(2 * w["delay"]) * max(0, shift) + abs(shift)
    cost += round(w["disruption"] * costs.lane_closure_hours(work, option.mode, option.duration_days, segments_by_id))
    if option.mode == Mode.open_cut:
        cost += round(100 * w["excavations"])
    return cost


def build(scenario: Scenario, constraints: SolveConstraints) -> Built:
    built = Built(model=cp_model.CpModel())
    m = built.model
    w = weights()
    segments_by_id = {s.segment_id: s for s in scenario.segments}
    lits: list[cp_model.IntVar] = []
    coefs: list[int] = []
    unplaced_const = 0
    for work in scenario.works:
        if work.done:
            continue
        placed = m.new_bool_var(f"placed_{work.work_id}")
        built.placed[work.work_id] = placed
        xs = []
        for option in work.modes:
            for start in range(scenario.horizon_days):
                if not allowed(scenario, constraints, work, option, start):
                    continue
                x = m.new_bool_var(f"x_{work.work_id}_{option.mode.value}_{start}")
                built.choices[(work.work_id, option.mode, start)] = (x, option.duration_days)
                xs.append(x)
                lits.append(x)
                coefs.append(_choice_cost(work, option, start, segments_by_id, w))
        m.add(cp_model.LinearExpr.sum(xs) == placed)
        if work.is_emergency:
            m.add(placed == 1)
        # UNPLACED_COST * (1 - placed)
        unplaced_const += UNPLACED_COST
        lits.append(placed)
        coefs.append(-UNPLACED_COST)
    m.minimize(cp_model.LinearExpr.weighted_sum(lits, coefs) + unplaced_const)
    return built
