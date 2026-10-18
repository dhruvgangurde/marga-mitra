# MargaMitra · project brief

Everything an agent needs to know about the project. Read it before any task.

## The problem

In Indian cities, water, drainage, gas, power, telecom and roads each plan their digging on their own calendar. The same road is cut again and again, sometimes weeks after it was resurfaced; trenches stay open in heavy rain; repairs are paid without proof. India recorded 2,385 deaths in pothole crashes in 2024 (PTI, Feb 2026) and loses about ₹3,000 crore a year to underground assets damaged by digging (PIB, Mar 2023). Mangaluru alone plans 1,289 km of new water pipes under its roads (NewsKarnataka, Jun 2026).

## What MargaMitra does

1. **Plan.** Each department's agent books its works. The coordinator finds clashes: the same road on the same days, digging during or after resurfacing, cutting a protected road. The agents negotiate for up to 3 rounds, choosing only among options that the cost tool computed. The OR-Tools CP-SAT scheduler then fixes the dates, puts works into one shared trench where the departments agreed, and the rules check decides who must approve. The workflow pauses until that person approves.
2. **Adapt.** The risk agent reads rain and air-quality forecasts (Open-Meteo) and event windows (processions, markets). When heavy rain (50 mm or more in 24 h) is forecast for low-lying roads, the affected works are negotiated again and re-planned, and the new plan goes for approval.
3. **Verify.** Crews upload before and after photos. MargaMitra checks the place (within 50 m of the work), the time (inside the work dates), photo reuse (perceptual hash), the repair (vision model) and a resident's confirmation, plus a 10% random inspection. Only then is the deposit released. Every decision is added to a hash-chained public record that anyone can check.

Also: a copilot that drives the command centre through the same API, an auditor that flags odd patterns, "Why?" explanations for every date, and "What if" re-plans that are never saved.

## Users and screens

Ward engineer: command centre, approves big plans. Department officer: approvals on a phone. Field crew: before and after photos. Resident: emergency report, "Is the road restored?". Anyone: public record. Judges: impact report.

## The demo story (test case 1: Surathkal, 2 to 29 Nov 2026)

1. Old way: Munchur Road is dug 4 times in a month: W-104 water main, T-221 fibre duct, G-310 gas line, and R-501 resurfacing before the others finish.
2. Orchestrate: the agents negotiate live. Water and Telecom share one trench (10 to 15 Nov), Gas moves after it, Roads resurfaces last (24 to 27 Nov), and the road is then protected for 3 years.
3. Simulate 70 mm of rain on 14 and 15 Nov: D-412 (storm-water drain on the low-lying NH-66 service road), P-118 and W-118 move out; trench-hours in rain fall to 0; the plan goes for approval again. A procession on 20 Nov keeps the service road free that day.
4. A crew's after photo for T-230 is the same as T-221's before photo: money held, inspector called. W-104's repair passes and a resident says yes: the deposit is released.
5. Public record: "Check the record" passes; the tamper script changes one entry and the check fails at exactly that entry.
6. Impact page: results across test cases 1 to 50 and what each part adds.

## Architecture

- **web** (React + Vite on Vercel) talks to the **API** (FastAPI on AWS) over REST and the `/ws` WebSocket.
- The API starts the **workflow** (`agents/workflow.py`, LangGraph): risk windows → baseline plan → clashes → negotiation → scheduler → metrics → rules check → approval pause → apply.
- The pure modules are `data`, `risk` (T4), `solver`, `evals` (T2) and `agents` (T3). They import only `contracts`; the backend (T1) wires them through `contracts.interfaces.Deps` and owns the database, files and WebSocket.
- **PostgreSQL 17 + PostGIS** stores roads, works, plans, messages, photos, verifications and the record. LangGraph's checkpoints live in the same database.
- LLM calls go through `agents/llm.py`: Claude by default (`claude-haiku-5-5` for agents, `claude-sonnet-5-5` for the copilot and photo checks), Gemini optional, `none` for the deterministic fallback.

## Contracts (frozen in Phase 0)

- `contracts/models.py`: every data shape. `costs.py`: money, deposits, lane-closure hours, the ₹ format. `rules.py`: clashes, digs per segment, rain trench-hours. `interfaces.py`: who implements what, `Deps`, the LLM client. `fakes.py`: stand-ins. `api.md`, `events.md`: endpoints and live events. `policy/policy.yaml`: thresholds, approval tiers, rates.
- Day 0 is `scenario.start_date`; every end day is inclusive.
- IDs: segments `S-0001`; works `<letter>-<number>` with W water, D drainage, G gas, P power, T telecom, R roads; plans `P-…`, runs `RUN-…`, approvals `A-…`, evidence `E-…`, verifications `V-…`, resident reports `CR-…`, auditor flags `F-…`.

## Metrics (what the impact page reports)

- **Digs per road:** average number of separate cuts per touched road segment. A shared trench counts once, trenchless work counts zero (`rules.digs_per_segment`).
- **Lane-closure hours:** lanes shut × how busy the road is × 10 working hours × days (`costs.lane_closure_hours`).
- **Trench-hours in rain:** 24 hours for every day an open trench overlaps a heavy-rain window on its road (`rules.rain_trench_hours`).
- **Clashes:** same road on the same days without a shared trench, digging during or after resurfacing, cutting a protected road (`rules.clash_count`).
- **Days late:** average days a work starts after the day its department asked for.
- **Cost:** dig + restoration + delay − shared-trench savings (`costs`).
- Variants: `naive` (old way, first come first dug), `solver_only` (scheduler without agents or forecasts), `agents` (+ negotiation), `risk` (+ forecasts), `full` (+ photo checks). Results report the median and the range over test cases 1 to 50.

## Design

- Design system: https://claude.ai/artifact/LzVXA5Q35cCSZaGdw8by5a
- Screen specs (12 artboards): https://claude.ai/artifact/PYvk5u8A6zwxgU3NSEmYBB
- Words on screen follow its Words to use section.

## Not in scope

No login system (roles are picked on screen for the demo), no real payments (a deposit release is a record entry), no live link to municipal systems, no third-party basemap.
