"""Which planned works are hit by a risk window."""

from contracts.models import Mode, Plan, RiskKind, RiskWindow, Scenario


def affected_works(scenario: Scenario, plan: Plan, windows: list[RiskWindow]) -> list[str]:
    works = {w.work_id: w for w in scenario.works}
    hit: set[str] = set()
    for a in plan.assignments:
        work = works.get(a.work_id)
        if work is None or work.done:
            continue
        segments = set(work.segment_ids)
        for w in windows:
            if w.kind in (RiskKind.rain, RiskKind.air) and a.mode != Mode.open_cut:
                continue
            if a.start_day > w.end_day or w.start_day > a.end_day:
                continue
            if segments & set(w.segment_ids):
                hit.add(a.work_id)
                break
    return sorted(hit)
