# MargaMitra · roadmap

Everything is built and merged by Oct 23, 23:59 IST. Oct 24 and 25 at NITK are only for joining, deploying and the demo. Each phase ends with every person's Phase Report.

## Phase 0 · Oct 18 night · setup and frozen contracts
Dhruv adds the root files and runs the Phase 0 prompt (contracts, policy, tests, folders). Saumya adds the web scaffold (configs, design tokens, component styles). Everyone sets up and runs `pytest -q` (7 passed, 16 skipped).

## Frontend track · Oct 19, 10:00 to Oct 21, 09:00 · every screen on mock data
Runs beside Phases 1 and 2 in a second agent session and needs no backend: the app's data layer answers every endpoint from mock demo data. Its screenshots go into the proposal PDF due on Oct 21.
- FE-A Saumya: data layer and mock demo data, live-event player, app shell, landing page, map, command centre (metrics, side panel tabs, timeline, copilot bar, work drawer, rain re-plan).
- FE-B Dhruv: the 24 UI components, approvals on a phone, field crew photos and result, resident report and confirmation, public record, impact report.

## Phase 1 · Oct 19–20 · core backend and ML
- T1 Nidhi: FastAPI app, config, tables, IDs, public record with verify, rules check, WebSocket hub, Deps with fakes, Phase 1 endpoints, OpenAPI export.
- T2 Dhruv: CP-SAT scheduler (modes, shared trenches, order, protected roads, risk penalties, negotiation constraints), old-way plan, metrics, plan diff.
- T3 Tanuj: LLM client (Claude, Gemini, none; cache; timeout), clash finder, options tool, department agents and prompts, no-LLM fallback.
- T4 Saumya: OSM import (committed snapshot), road segments, elevations and low-lying roads, test case 1 by hand, shared-trench groups, test cases 2–50 generated.

## Phase 2 · Oct 20–21 · second core layer
- T1: evidence upload, photo place and time, reuse check, vision repair check, decision, resident confirmation, protected-roads list, demo photos.
- T2: the 50-case evaluation for all five variants, results file, ablation table.
- T3: negotiation coordinator (3 rounds), LangGraph workflow with the approval pause, re-plan on rain and emergencies.
- T4: India AQI, Open-Meteo forecasts (live and fixtures), risk windows, affected works.

## Phase 3 · Oct 21–23 · the real API under the screens
- FE-A Saumya: landing and command centre on the real API and live events.
- FE-B Dhruv: phone screens, public record and impact report on the real API.
- T2 Dhruv: scheduler tuning for the demo story, results on the real modules.
- T4 Saumya: live forecasts, demo data checks.
- T1 Nidhi: auditor, Why?, what-if, emergency flow, copilot and evals endpoints, seed and tamper scripts, Dockerfile, production compose, Caddy.
- T3 Tanuj: the copilot (tool calls over the API, screen actions, steps), prompt tuning, demo script.

## Phase 4 · Oct 24 · integration
Real modules replace the fakes and the mocks, the full demo runs end to end on one laptop, bugs are fixed.

## Phase 5 · Oct 24–25 · deploy and demo
API on AWS EC2 with Caddy and HTTPS, web on Vercel, two full rehearsals, a backup video, the pitch.
