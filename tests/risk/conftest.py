import pytest

from contracts import fakes
from contracts.models import Assignment, Plan, PlanVariant, Scenario
from data.osm_import import SNAPSHOT


@pytest.fixture
def need_snapshot():
    if not SNAPSHOT.exists():
        pytest.skip("Run: python -m data.osm_import --fetch")


@pytest.fixture
def old_way():
    """The old way: every work starts when the department asked, in its first mode."""

    def build(scenario: Scenario) -> Plan:
        assignments = []
        for work in scenario.works:
            if work.done:
                continue
            option = work.modes[0]
            assignments.append(Assignment(
                work_id=work.work_id, start_day=work.requested_start,
                end_day=work.requested_start + option.duration_days - 1, mode=option.mode,
                reason="As the department asked."))
        return Plan(plan_id=f"P-OLD-{scenario.seed}", seed=scenario.seed, variant=PlanVariant.naive,
                    created_at=fakes.now(), assignments=assignments)

    return build
