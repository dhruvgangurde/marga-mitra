import time

import pytest

from contracts import costs, rules
from contracts.models import Dept
from data.demo import demo_scenario
from data.groups import find_parallel_groups
from data.scenario import generate_scenario

pytestmark = pytest.mark.usefixtures("need_snapshot")

SEEDS = range(2, 51)


def test_seed_one_is_the_demo():
    assert generate_scenario(1) == demo_scenario()


def test_same_seed_gives_the_same_scenario():
    for seed in SEEDS:
        assert generate_scenario(seed) == generate_scenario(seed), seed


def test_every_generated_case_is_sound(naive):
    for seed in SEEDS:
        scenario = generate_scenario(seed)
        segment_ids = {s.segment_id for s in scenario.segments}
        protected = {s.segment_id for s in scenario.segments if s.protected_until}
        assert scenario.seed == seed
        assert 14 <= len(scenario.works) <= 20, seed
        work_ids = [w.work_id for w in scenario.works]
        assert len(work_ids) == len(set(work_ids)), seed
        for w in scenario.works:
            assert set(w.segment_ids) <= segment_ids, (seed, w.work_id)
            assert not set(w.segment_ids) & protected, (seed, w.work_id)
            assert w.earliest_start == w.requested_start, (seed, w.work_id)
            end = w.requested_start + w.modes[0].duration_days - 1
            assert end <= w.latest_end <= 27, (seed, w.work_id)
            assert w.deposit_inr == costs.deposit_inr(w.dept, w.length_m, w.modes[0].mode), (seed, w.work_id)
        assert rules.clash_count(scenario, naive(scenario)) >= 3, seed
        assert scenario.parallel_groups, seed
        assert scenario.parallel_groups == find_parallel_groups(scenario.works, scenario.segments), seed
        assert {w.dept for w in scenario.works} == set(Dept), seed


def test_all_fifty_cases_are_quick():
    started = time.perf_counter()
    for seed in range(1, 51):
        generate_scenario(seed)
    assert time.perf_counter() - started < 20
