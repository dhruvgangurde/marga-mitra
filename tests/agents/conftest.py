import itertools
from types import SimpleNamespace

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from agents import workflow
from agents.llm import get_llm
from contracts.fakes import fake_naive_plan, tiny_scenario
from contracts.models import Metrics, WorkStatus, WorkView


@pytest.fixture(autouse=True)
def _no_model_unless_a_test_asks(monkeypatch):
    # .env may hold a real key; tests must never reach the network
    monkeypatch.setenv("LLM_PROVIDER", "none")
    get_llm.cache_clear()
    yield
    get_llm.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_runs():
    # run ids repeat across tests, so each test gets its own checkpoints
    workflow.set_checkpointer(InMemorySaver())
    workflow._deps.clear()
    yield
    workflow.set_checkpointer(InMemorySaver())


# ---------- a stand-in city API for the copilot tests ----------
class FakeApi:
    """Plays the city API over httpx.MockTransport and records every request."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def handler(self, request):
        assert not request.url.path.startswith("/approvals"), "the copilot must never touch approvals"
        self.requests.append((request.method, request.url.path, dict(request.url.params), request.content))
        route = self.routes.get((request.method, request.url.path))
        if route is None:
            return httpx.Response(404, json={"detail": "not found"})
        out = route(request) if callable(route) else route
        return out if isinstance(out, httpx.Response) else httpx.Response(200, json=out)

    def client(self, base_url="http://api"):
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler), base_url=base_url)

    @property
    def calls(self):
        return [f"{m} {p}" for m, p, _, _ in self.requests]


def once_then(first, then):
    """A route that answers `first` once and `then` afterwards."""
    answers = itertools.chain([first], itertools.repeat(then))
    return lambda request: next(answers)


def metrics_json(plan_id, rain=0.0, digs=2.0, clashes=0):
    return Metrics(plan_id=plan_id, excavations=4, digs_per_road=digs, lane_closure_hours=360.0, trench_hours_in_rain=rain,
                   clashes=clashes, days_late=0.0, cost_inr=0, dust_score=0.0).model_dump(mode="json")


def tiny_views():
    s = tiny_scenario()
    plan = fake_naive_plan(s)
    shared = {"W-001", "T-001"}
    out = []
    for w in s.works:
        a = next(x for x in plan.assignments if x.work_id == w.work_id)
        if w.work_id in shared:
            a = a.model_copy(update={"start_day": 8, "end_day": 12, "shared_group": "G1"})
        out.append(WorkView(work=w, assignment=a, status=WorkStatus.planned).model_dump(mode="json"))
    return out


def demo_views():
    """The Munchur Road story: W-104 and T-221 share a trench on 10–15 Nov."""
    base = tiny_views()
    spec = [("W-104", "water", 8, 13, "G1", "Munchur Road"), ("T-221", "telecom", 8, 13, "G1", "Munchur Road"),
            ("G-310", "gas", 16, 20, None, "Munchur Road east"), ("R-501", "roads", 22, 25, None, "Munchur Road"),
            ("D-412", "drainage", 14, 17, None, "NH-66 service road"), ("P-118", "power", 14, 16, None, "Kana Road"),
            ("W-118", "water", 15, 18, None, "Kana Road")]
    views = []
    for work_id, dept, start, end, group, road in spec:
        view = {k: dict(v) if isinstance(v, dict) else v for k, v in base[0].items()}
        view["work"] = {**base[0]["work"], "work_id": work_id, "dept": dept, "title": f"{dept.title()} work",
                        "road_name": road}
        view["assignment"] = {**base[0]["assignment"], "work_id": work_id, "start_day": start, "end_day": end,
                              "shared_group": group}
        views.append(view)
    return views


def rain_routes(run_status=None, run_id="RUN-0008", plan_id="P-0008", base="P-0007", moved=("D-412", "P-118", "W-118")):
    ready = {"run_id": run_id, "status": "waiting_approval", "plan_id": plan_id}
    messages = [{"type": "NOTICE", "round": 1, "work_ids": list(moved)}]
    messages += [{"type": "ACCEPT", "round": 1, "work_ids": [w]} for w in moved]
    messages.append({"type": "DECISION", "round": 1, "work_ids": list(moved)})
    return {
        ("POST", "/risk/forecast-override"): {"run_id": run_id, "status": "running"},
        ("GET", f"/runs/{run_id}"): run_status or once_then({"run_id": run_id, "status": "running"}, ready),
        ("GET", f"/plan/{plan_id}"): {"plan_id": plan_id, "base_plan_id": base},
        ("GET", f"/plan/{plan_id}/diff"): [{"work_id": w} for w in moved],
        ("GET", "/negotiation"): messages,
        ("GET", f"/plan/{plan_id}/metrics"): metrics_json(plan_id),
    }


@pytest.fixture
def kit():
    return SimpleNamespace(FakeApi=FakeApi, tiny_views=tiny_views, demo_views=demo_views, rain_routes=rain_routes,
                           once_then=once_then, metrics_json=metrics_json)
