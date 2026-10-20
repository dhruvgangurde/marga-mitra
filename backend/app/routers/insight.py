from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import ValidationError

from backend.app import explain, store
from backend.app.config import get_settings
from backend.app.db import session
from backend.app.deps import in_session
from backend.app.routers.plans import current_scenario, save_old_way
from contracts.models import AuditorFlag, EvalSummary, Explanation, Plan, PlanVariant, Reason, Scenario, Work

router = APIRouter(tags=["insight"])

RULE_NAMES = {"protected_roads": "Protected roads", "deposits": "Deposits", "rain": "Heavy rain", "air": "Poor air",
              "events": "Event routes", "order": "Resurfacing order"}
OLD_WAY = Reason(icon="info", lead="This is the old way.",
                 text="Every work on the dates its department asked for, with no shared trench.",
                 source="the departments' requests")


@router.get("/auditor/flags")
def auditor_flags(request: Request) -> list[AuditorFlag]:
    return in_session(store.list_flags, request.app.state.seed)


def _why_work(app: FastAPI, scenario: Scenario, work: Work) -> Explanation:
    with session() as s:
        plan = store.active_plan(s, app.state.seed)
        run = store.run_of_plan(s, plan.plan_id)
        messages = store.list_messages(s, run.run_id) if run else []
        seqs = store.seqs_for(s, [f"work:{work.work_id}", f"plan:{plan.plan_id}"])
    a = next((a for a in plan.assignments if a.work_id == work.work_id), None)
    start, end, _ = explain.days_of(work, a)
    return Explanation(entity=f"work:{work.work_id}", title="Why these dates?",
                       reasons=explain.work_reasons(work, a, plan, scenario, messages),
                       rules=explain.work_rules(work, a, scenario, explain.forecast_summary(scenario, start, end)),
                       ledger_seqs=seqs)


def _why_plan(app: FastAPI, scenario: Scenario, plan: Plan) -> Explanation:
    deps = app.state.wiring.deps
    if plan.variant == PlanVariant.naive:
        base, reasons = None, [OLD_WAY]
    else:
        base = ((in_session(store.get_plan, plan.base_plan_id) if plan.base_plan_id else None)
                or in_session(store.get_plan, f"P-OLD-{plan.seed}") or save_old_way(deps, scenario))
        source = "compared with the old way" if base.variant == PlanVariant.naive else f"compared with plan {base.plan_id}"
        reasons = explain.plan_reasons(deps.compute_metrics(base, scenario), deps.compute_metrics(plan, scenario), source)
    rules = [c.model_copy(update={"name": RULE_NAMES.get(c.name, c.name)})
             for c in deps.check_policy(plan, base, scenario).checks]
    return Explanation(entity=f"plan:{plan.plan_id}", title="Why this plan?", reasons=reasons, rules=rules,
                       ledger_seqs=in_session(store.seqs_for, [f"plan:{plan.plan_id}"]))


@router.get("/explain/{entity}")
def why(request: Request, entity: str) -> Explanation:
    """'W-104', 'work:W-104', 'P-0007' or 'plan:P-0007'; with no prefix a work wins."""
    scenario = current_scenario(request.app)
    prefix, _, ident = entity.rpartition(":")
    works = {w.work_id: w for w in scenario.works}
    if prefix in ("work", "") and ident in works:
        return _why_work(request.app, scenario, works[ident])
    if prefix in ("plan", ""):
        plan = in_session(store.get_plan, ident)
        if plan and plan.seed == request.app.state.seed:
            return _why_plan(request.app, scenario, plan)
    raise HTTPException(404, "Unknown work or plan.")


@router.get("/evals/summary")
def evals_summary() -> EvalSummary:
    path = Path(get_settings().evals_summary_path)
    if not path.is_file():
        raise HTTPException(404, "No results yet.")
    try:
        return EvalSummary.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as e:
        raise HTTPException(500, "The results file could not be read.") from e
