"""How many made-up repair claims the photo checks catch, on cases built from the small test scenario."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta, timezone
from typing import Literal

from contracts.fakes import fake_naive_plan, tiny_scenario
from contracts.models import Assignment, Evidence, Scenario, Verification, Work
from evals.imports import optional

INDIA = timezone(timedelta(hours=5, minutes=30))
FAR_DEG = 0.005  # about 550 m north
NEAR_DEG = 0.00004  # about 4 m
LATE_DAYS = 5  # policy time_slack_days is 2

Kind = Literal["reused", "far", "late", "genuine"]
Target = Literal["reuse", "place", "time"]
CASES: list[tuple[Kind, Target | None, list[str]]] = [
    ("reused", "reuse", ["W-001", "T-001", "G-001", "R-001"]),
    ("far", "place", ["W-001", "T-001", "G-001"]),
    ("late", "time", ["W-001", "T-001", "G-001"]),
    ("genuine", None, ["W-001", "G-001"]),
]


@dataclass(frozen=True)
class Case:
    name: str
    kind: Kind
    target: Target | None
    work: Work
    assignment: Assignment
    evidence: list[Evidence]
    others: list[Evidence]


@dataclass
class FakeRepairResult:
    caught: int
    total: int
    genuine_passed: int
    genuine_total: int
    note: str


def photo_id(i: int) -> str:
    """16 hex digits, like a 64-bit photo fingerprint. The first 24 are at least 20 bits apart."""
    return f"{(0x9E3779B97F4A7C15 * (2 * i + 1)) & 0xFFFFFFFFFFFFFFFF:016x}"


class _Photos:
    """Numbers evidence ids and photo ids in the order the photos are made."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.count = 0
        self.next_photo = 0  # a copied photo takes no new id

    def at_nine(self, day: int) -> datetime:
        d = self.scenario.start_date + timedelta(days=day)
        return datetime.combine(d, time(9, 0), tzinfo=INDIA).astimezone(UTC)

    def make(self, work: Work, kind: Literal["before", "after"], url: str, lon: float, lat: float, day: int,
             phash: str | None = None) -> Evidence:
        self.count += 1
        if phash is None:
            phash = photo_id(self.next_photo)
            self.next_photo += 1
        taken = self.at_nine(day)
        return Evidence(evidence_id=f"EVAL-E{self.count}", work_id=work.work_id, kind=kind, file_url=url, lat=lat,
                        lon=lon, taken_at=taken, phash=phash, uploaded_at=taken)


def _first_point(scenario: Scenario, work: Work) -> tuple[float, float]:
    return next(s for s in scenario.segments if s.segment_id == work.segment_ids[0]).coords[0]


def build_cases() -> list[Case]:
    scenario = tiny_scenario()
    works = {w.work_id: w for w in scenario.works}
    plan = {a.work_id: a for a in fake_naive_plan(scenario).assignments}
    photos = _Photos(scenario)
    # one before photo of every work, already on file: the other works' photos each case is compared with
    on_file = {wid: photos.make(w, "before", f"evals://on-file/{wid}/before.jpg", *_first_point(scenario, w),
                                plan[wid].start_day) for wid, w in works.items()}
    cases: list[Case] = []
    for kind, target, work_ids in CASES:
        for wid in work_ids:
            work, a = works[wid], plan[wid]
            name = f"{kind}-{wid}"
            lon, lat = _first_point(scenario, work)
            other_ids = [o for o in works if o != wid]
            before = photos.make(work, "before", f"evals://{name}/before.jpg", lon, lat + NEAR_DEG, a.start_day)
            after_url = f"evals://{name}/after.jpg"
            others = [on_file[o] for o in other_ids[:2]]
            if kind == "reused":
                copied = on_file[other_ids[2]]
                others.append(copied)
                after = photos.make(work, "after", after_url, lon, lat, a.end_day, phash=copied.phash)
            elif kind == "far":
                after = photos.make(work, "after", after_url, lon, lat + FAR_DEG, a.end_day)
            elif kind == "late":
                after = photos.make(work, "after", after_url, lon, lat, a.start_day - LATE_DAYS)
            else:
                after = photos.make(work, "after", after_url, lon + NEAR_DEG * 0.75, lat - NEAR_DEG * 0.75, a.end_day)
            cases.append(Case(name=name, kind=kind, target=target, work=work, assignment=a, evidence=[before, after],
                              others=others))
    return cases


def load_decide() -> Callable[..., Verification] | None:
    return optional("backend.app.verify.decide", "decide")


def count_caught(decide: Callable[..., Verification] | None) -> FakeRepairResult:
    if decide is None:
        return FakeRepairResult(0, 0, 0, 0, "The photo checks are not merged yet.")
    scenario = tiny_scenario()
    cases = build_cases()
    caught = passed = 0
    stopped: list[str] = []
    for case in cases:
        try:
            v = decide(work=case.work, assignment=case.assignment, evidence=case.evidence, scenario=scenario,
                       others=case.others)
        except Exception as e:  # a broken check counts as not caught, and the note says what broke
            stopped.append(f"{case.name} ({type(e).__name__})")
            continue
        status = {c.name: c.status for c in v.checks}
        if case.target is None:
            passed += all(s != "fail" for s in status.values())
        else:
            caught += status.get(case.target) == "fail"
    note = f"The photo checks stopped on {', '.join(stopped)}." if stopped else ""
    return FakeRepairResult(caught=caught, total=sum(c.target is not None for c in cases), genuine_passed=passed,
                            genuine_total=sum(c.target is None for c in cases), note=note)
