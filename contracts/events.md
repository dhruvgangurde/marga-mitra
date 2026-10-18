# Live events on /ws · frozen list

Every message is one WsEvent: {"type": "...", "data": {...}, "ts": "2026-11-02T10:02:11+05:30"}.

| type | data | sent when | sent by |
|---|---|---|---|
| negotiation.message | NegotiationMessage | an agent, the coordinator or the scheduler speaks | agents (through emit) |
| plan.updated | {"plan_id", "status", "variant", "metrics": Metrics or null} | a plan is made, approved, rejected or replaced | agents/workflow, backend |
| risk.windows_changed | {"windows": RiskWindow[]} | a forecast override, a new event, a live refresh | backend |
| approval.requested | Approval | the workflow pauses for a person | agents/workflow |
| approval.decided | Approval | a person approves or rejects | backend |
| verification.result | Verification | a photo check finishes | backend |
| ledger.appended | LedgerEntry | every new record entry | backend |
| auditor.flag | AuditorFlag | the auditor raises a flag | backend |
| copilot.step | CopilotStep plus "reply_id" | a copilot step starts or ends | agents/copilot |
| ui.action | UiAction plus "reply_id" | the copilot asks the screen to move | agents/copilot |

The web app must ignore event types it does not know.
