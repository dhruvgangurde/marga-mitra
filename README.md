# MargaMitra

**Dig once. Fix right. Keep roads moving.**

MargaMitra helps an Indian city dig each road once instead of again and again. Agents for water, drainage, gas, power, telecom and roads negotiate one plan; an OR-Tools scheduler picks the dates and shares trenches; rain, air and event forecasts move work out of risky days; photo checks release repair money only after proof; and every decision goes into a public record anyone can check.

Built for ChronoForge 2026 at NITK Surathkal (Agentic AI track, "Cities of the Future") by team ExploreeTinkerBell, Sardar Patel Institute of Technology, Mumbai.

## What the demo shows

1. The old way: one road in Surathkal is dug four times in a month.
2. Orchestrate: department agents negotiate live; two digs merge into one trench; resurfacing moves last.
3. Heavy rain is forecast: trenches move off low-lying roads and the new plan goes for approval.
4. A reused photo is caught and the money is held; a real repair passes and a resident confirms it.
5. The public record checks itself; one changed entry is found at once.
6. Impact across 50 test cases, and what each part adds.

## How it works

```text
web (React, Vite, MapLibre)  --REST + WebSocket-->  API (FastAPI)
API --> workflow (LangGraph): forecasts -> clashes -> negotiation -> scheduler (CP-SAT) -> rules check -> approval
API --> photo checks (place, time, reuse, repair), auditor, public record (hash chain)
PostgreSQL + PostGIS: roads, works, plans, messages, photos, record
```

## Tech

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL 17 with PostGIS, LangGraph, Google OR-Tools CP-SAT, the Claude API (Gemini optional), Pillow and ImageHash; React 18, Vite 8, TypeScript, MapLibre GL JS, TanStack Query. The API runs on AWS EC2 behind Caddy; the web app on Vercel.

## Run it locally

You need Git, Python 3.12, Node.js 22 or newer, and Docker.

```bash
git clone https://github.com/dhruvgangurde/marga-mitra.git
cd marga-mitra
git config core.hooksPath .githooks
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db
uvicorn backend.app.main:app --reload --port 8000
```

On Windows use `py -3.12 -m venv .venv` and `.\.venv\Scripts\Activate.ps1`. Put your key in `.env`, or set `LLM_PROVIDER=none` to run without an LLM. Then start the web app in a second terminal: `cd web`, `npm ci`, `npm run dev`, and open http://localhost:5173.

Tests: `pytest -q` and `ruff check .`; in `web/`, `npm run typecheck` and `npm run build`.

## Repository map

- `contracts/`: shared data models, costs, clash rules, interfaces
- `data/`, `risk/`: Surathkal roads, test cases, forecasts
- `solver/`, `evals/`: the scheduler and the 50-case tests
- `agents/`: department agents, negotiation, workflow, copilot
- `backend/`: the API, public record, rules check, photo checks
- `web/`: the app built on the MargaMitra design system

## Team

- Nidhi Dhyani: API, public record, photo checks
- Dhruv Gangurde: scheduler, impact tests, review screens
- Tanuj Bhide: department agents, negotiation, copilot
- Saumya Singh (team lead): roads data, risk, command centre

## Credits

- Road data © OpenStreetMap contributors, under the Open Database License (ODbL).
- Weather, air-quality and elevation data by Open-Meteo.com (CC BY 4.0).
- Icons: Phosphor Icons (MIT). Fonts: Bowlby One, Kaushan Script and Geist (SIL Open Font License).
- Google OR-Tools (Apache 2.0), LangGraph (MIT), MapLibre GL JS (BSD 3-Clause), FastAPI (MIT).
