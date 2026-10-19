from agents.conflicts import cluster_conflicts, detect_conflicts
from contracts import rules
from contracts.fakes import fake_naive_plan, tiny_scenario
from contracts.models import Conflict, ConflictKind


def _clash(cid: str, works: list[str], segs: list[str]) -> Conflict:
    return Conflict(conflict_id=cid, kind=ConflictKind.same_road, work_ids=works, segment_ids=segs, start_day=0,
                    end_day=1, note=cid)


def test_detect_conflicts_is_the_shared_rule():
    s = tiny_scenario()
    p = fake_naive_plan(s)
    found = detect_conflicts(s, p)
    assert found == rules.find_clashes(s, p)
    assert sorted(c.kind.value for c in found) == ["order", "order", "order", "risk", "risk", "same_road"]


def test_tiny_scenario_is_one_cluster():
    s = tiny_scenario()
    clusters = cluster_conflicts(detect_conflicts(s, fake_naive_plan(s)))
    assert len(clusters) == 1
    assert len(clusters[0]) == 6


def test_separate_clashes_make_separate_clusters():
    a = _clash("A", ["W-1", "T-1"], ["S-1"])
    b = _clash("B", ["G-1", "P-1"], ["S-9"])
    c = _clash("C", ["D-1", "X-1"], ["S-1"])
    assert cluster_conflicts([a, b]) == [[a], [b]]
    assert cluster_conflicts([a, b, c]) == [[a, c], [b]]
    assert cluster_conflicts([a, b, c]) == cluster_conflicts([a, b, c])


def test_a_clash_links_two_clusters_through_a_shared_work():
    a = _clash("A", ["W-1", "T-1"], ["S-1"])
    b = _clash("B", ["G-1", "P-1"], ["S-9"])
    bridge = _clash("C", ["T-1", "G-1"], ["S-5"])
    assert cluster_conflicts([a, b, bridge]) == [[a, b, bridge]]


def test_no_clashes_no_clusters():
    assert cluster_conflicts([]) == []
