# API · frozen list (owner: T1 backend)

All bodies are JSON unless marked multipart. Every response model is in contracts/models.py.
"Active plan" = the newest approved plan; else the newest plan waiting for approval; else the old-way plan.

| Method | Path | Input | Returns | Phase |
|---|---|---|---|---|
| GET | /health | – | {"ok": true, "db": true, "llm_provider": "anthropic", "weather_mode": "fixture"} | 1 |
| POST | /scenario/load | query seed=1 | {"seed", "start_date", "works", "segments"} (counts) | 1 |
| GET | /segments | query bbox=minLon,minLat,maxLon,maxLat (optional) | GeoJSON FeatureCollection; properties: segment_id, name, road_class, low_lying, protected_until | 1 |
| GET | /departments | – | [{"id", "name", "icon", "color_token"}] | 1 |
| GET | /works | query plan_id (default: active plan) | WorkView[] | 1 |
| GET | /works/{work_id} | – | WorkView | 1 |
| POST | /works | Work | Work | 1 |
| POST | /plan/naive | – | Plan (variant naive, saved) | 1 |
| POST | /plan/solver-only | – | Plan (variant solver_only, saved) | 1 |
| POST | /plan/orchestrate | – | RunResult (status running; progress on /ws) | 1 |
| GET | /plans | – | Plan[] newest first | 1 |
| GET | /plan/{plan_id} | – | Plan | 1 |
| GET | /plan/{plan_id}/metrics | – | Metrics | 1 |
| GET | /plan/{plan_id}/diff | query against=naive or a plan id | WorkChange[] | 1 |
| GET | /runs/{run_id} | – | RunResult | 1 |
| GET | /negotiation | query run_id (default: newest run) | NegotiationMessage[] oldest first | 1 |
| GET | /risk/windows | – | RiskWindow[] | 1 |
| POST | /risk/forecast-override | {"kind", "start_day", "end_day", "value", "label"?} | RunResult (re-plan started) | 1 |
| POST | /events | {"label", "start_day", "end_day", "segment_ids"} | RiskWindow | 1 |
| GET | /approvals | query status=pending (optional) | Approval[] | 1 |
| POST | /approvals/{approval_id} | {"decision": "approve" or "reject", "by", "reason"?} | RunResult | 1 |
| GET | /ledger | query limit=50, before_seq (optional) | LedgerEntry[] newest first | 1 |
| GET | /ledger/verify | – | LedgerVerify | 1 |
| POST | /works/{work_id}/evidence | multipart: kind, photo, lat?, lon?, taken_at? | Evidence | 2 |
| GET | /works/{work_id}/evidence | – | Evidence[] | 2 |
| POST | /works/{work_id}/verify | – | Verification | 2 |
| GET | /works/{work_id}/verification | – | Verification (404 if none) | 2 |
| POST | /reports/confirmation | {"work_id", "answer", "problems", "lat"?, "lon"?} | CitizenReport | 2 |
| GET | /no-dig | – | [{"segment_id", "name", "protected_until", "why"}] | 2 |
| GET | /files/{path} | – | an uploaded photo | 2 |
| POST | /reports/emergency | multipart: category, lat, lon, note?, photo? | CitizenReport (also creates the emergency work and starts a re-plan) | 3 |
| GET | /auditor/flags | – | AuditorFlag[] | 3 |
| GET | /explain/{entity} | entity = work id or plan id | Explanation | 3 |
| POST | /plan/whatif | {"work_id", "delay_days"} | {"plan": Plan, "diff": WorkChange[], "metrics": Metrics} (never approved) | 3 |
| POST | /copilot | {"message", "context"} | CopilotReply (steps and screen actions also stream on /ws) | 3 |
| GET | /evals/summary | – | EvalSummary | 3 |
| WS | /ws | – | a stream of WsEvent JSON objects (see events.md) | 1 |

Errors: 404 {"detail": "..."} for unknown ids, 422 for bad input (FastAPI default), 409 when an approval is already decided.
