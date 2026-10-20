from backend.app.main import app

PHASE_1_PATHS = [
    "/health", "/scenario/load", "/segments", "/departments", "/works", "/works/{work_id}", "/plan/naive",
    "/plan/solver-only", "/plan/orchestrate", "/plans", "/plan/{plan_id}", "/plan/{plan_id}/metrics",
    "/plan/{plan_id}/diff", "/runs/{run_id}", "/negotiation", "/risk/windows", "/risk/forecast-override", "/events",
    "/approvals", "/approvals/{approval_id}", "/ledger", "/ledger/verify",
]


PHASE_2_PATHS = [
    "/works/{work_id}/evidence", "/works/{work_id}/verify", "/works/{work_id}/verification", "/reports/confirmation",
    "/no-dig", "/files/{path}",
]


def test_every_phase_1_path_is_described():
    spec = app.openapi()
    assert set(PHASE_1_PATHS + PHASE_2_PATHS) <= set(spec["paths"])
    assert {"WorkView", "Plan", "RunResult", "LedgerEntry"} <= set(spec["components"]["schemas"])
