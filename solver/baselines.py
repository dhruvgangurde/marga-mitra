"""The old way: every department digs on the day it asked for, in its default method."""
from __future__ import annotations

from datetime import UTC, datetime

from contracts.models import Assignment, Plan, PlanStatus, PlanVariant, Scenario


def naive_plan(scenario: Scenario) -> Plan:
    assignments = [
        Assignment(work_id=w.work_id, start_day=w.requested_start,
                   end_day=w.requested_start + w.modes[0].duration_days - 1, mode=w.modes[0].mode,
                   reason="As the department asked.")
        for w in scenario.works if not w.done
    ]
    return Plan(plan_id=f"P-{scenario.seed}-{PlanVariant.naive.value}", seed=scenario.seed, variant=PlanVariant.naive,
                status=PlanStatus.draft, created_at=datetime.now(UTC), assignments=assignments)
