# AI Interaction Log — Fleet Telemetry Take-Home

**Tools used**: Claude Code (Claude Opus 4.7 / 1M context) for code generation, code review, and ADR drafting. No other models.

**AI-assisted time**: ~3.5 h of 5.5 h budgeted (~64%). The rest was reading the spec, writing the ADR by hand, and hand-rolling the concurrency-critical bits (fault transition, the asyncio.Lock map, the actual concurrency tests).

## Prior-experience disclosure

I own and operate a small side venture called **relaai** — an industrial-IoT platform with overlapping concepts (machine events, edge gateways, anomaly detection, escalation rules, failure / maintenance records). I did **not** open or copy from that codebase during this exercise. Domain familiarity informed how I paced the work and which patterns I trusted quickly; the implementation here was written from scratch and intentionally diverges where the take-home's constraints differ (rule-based deterministic anomalies here vs. a training-based detector in relaai; vertical-slice hexagonal monolith here vs. multi-module legacy structure there).

---

## Entries

> *(filled in chronologically during the build — entries are added as work progresses, not reconstructed at the end)*

### Entry 01 — TBD — Scaffold backend + frontend + compose

**Goal**: Generate the directory skeleton and configuration for FastAPI + SQLAlchemy 2.x async + Postgres + Alembic + uv on the backend, and Vite + React + TS + Tailwind + Redux Toolkit + RTK Query + Vitest + MSW on the frontend.

**Prompt** (summary):
> Generate a `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, and root layout for a FastAPI hexagonal monolith with these constraints: …

**Output**: <to fill>

**Accepted**: <to fill>

**Rejected / redirected**: <to fill>

---

*(further entries added during work)*

---

## Reflection

> *(written at the end — 3–5 specific bullets, no platitudes)*

1. **Where AI shined**: <to fill, e.g. "Alembic migrations from a verbal schema were 5× faster than typing; output was 95% correct, the 5% I had to fix was naming consistency.">
2. **Where AI failed**: <to fill>
3. **What I had to verify manually**: <to fill — concurrency tests are the obvious candidate>
4. **What I deliberately wrote by hand**: <to fill>
5. **What I'd do differently next time**: <to fill>
