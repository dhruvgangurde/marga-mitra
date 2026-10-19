"""What changed between two plans, work by work, with the cost of each move."""
from __future__ import annotations

from contracts import costs
from contracts.models import Assignment, Plan, Scenario, Work, WorkChange


def _move(work: Work, a: Assignment, scenario: Scenario) -> int:
    group = next((g for g in scenario.parallel_groups if g.group_id == a.shared_group), None)
    share = group.saving_inr // len(group.work_ids) if group else 0
    return costs.move_cost_inr(work, a.start_day, a.mode, share)


def _changed(o: Assignment | None, n: Assignment) -> bool:
    return o is None or (o.start_day, o.end_day, o.mode, o.shared_group) != (n.start_day, n.end_day, n.mode, n.shared_group)


def plan_diff(old: Plan, new: Plan, scenario: Scenario) -> list[WorkChange]:
    old_by_id = {a.work_id: a for a in old.assignments}
    new_by_id = {a.work_id: a for a in new.assignments}
    changes: list[WorkChange] = []
    for work in scenario.works:
        n = new_by_id.get(work.work_id)
        if n is None:
            continue
        o = old_by_id.get(work.work_id)
        if not _changed(o, n):
            continue
        changes.append(WorkChange(
            work_id=work.work_id, dept=work.dept, title=f"{work.title}, {work.road_name} · {work.work_id}",
            from_start=o.start_day if o else None, from_end=o.end_day if o else None, mode_from=o.mode if o else None,
            to_start=n.start_day, to_end=n.end_day, mode_to=n.mode, shared_group=n.shared_group, reason=n.reason,
            cost_delta_inr=_move(work, n, scenario) - (_move(work, o, scenario) if o else 0),
        ))
    return changes
