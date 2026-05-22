# Fleet Telemetry Monitoring Service

A vertical slice of a fleet monitoring system for 50 autonomous industrial vehicles emitting telemetry at 1 Hz. Take-home for **Qualitara** / Staff–Principal Full-Stack Engineer role.

## What's in here

- **Backend**: FastAPI (async) + SQLAlchemy 2.x (async) + Postgres 16, hexagonal layout.
- **Frontend**: React + TypeScript + Vite, Redux Toolkit + RTK Query, Tailwind. Polling at 1.5 s.
- **Concurrency primitives**: append-only `zone_entries` (no lost updates by construction); `SERIALIZABLE` + retry for fault transitions; partial unique index enforcing "≤1 active mission per vehicle".
- **Anomaly detection**: 6 deterministic rules behind a `Protocol` (designed to evolve into a learning detector — see `ADR.md`).

Full design rationale in [`ADR.md`](./ADR.md). AI usage in [`AI-INTERACTION-LOG.md`](./AI-INTERACTION-LOG.md).

## Run it

The fastest path:

```bash
docker compose up --build
```

When the API is healthy:

```bash
# (one shot, in another terminal)
docker compose exec api uv run alembic upgrade head
docker compose exec api uv run python -m scripts.seed
```

Then open:

- Dashboard:   http://localhost:8080
- API docs:    http://localhost:8000/docs
- Health:      http://localhost:8000/health

### Run without Docker

```bash
# Postgres on localhost:5432 (db=fleet, user=fleet, password=fleet) required
cd backend && uv sync && uv run alembic upgrade head && uv run python -m scripts.seed
uv run uvicorn app.main:app --port 8000 &
cd ../frontend && pnpm install && pnpm dev
```

## Send a telemetry event

```bash
curl -X POST http://localhost:8000/api/v1/telemetry \
  -H 'Content-Type: application/json' \
  -d '{
    "vehicle_id": "v-12",
    "timestamp": "2026-05-22T10:30:00Z",
    "lat": 37.41, "lon": -122.08,
    "battery_pct": 78, "speed_mps": 1.2,
    "status": "moving", "error_codes": [],
    "zone_entered": "charging_bay_1"
  }'
```

## Tests

```bash
make backend-test     # unit + integration (Testcontainers boots a real Postgres)
make frontend-test    # vitest + MSW
make ci               # everything: lint + typecheck + test on both sides
```

Concurrency tests live in `backend/tests/integration/`:

- `test_zone_counter_concurrency.py` — 50 concurrent same-zone events ⇒ count exactly 50.
- `test_fault_transition_concurrency.py` — 2 concurrent fault triggers ⇒ exactly 1 maintenance record and 1 cancelled mission.

## Endpoints (summary)

| Method | Path                                  | Purpose |
| ------ | ------------------------------------- | ------- |
| POST   | `/api/v1/telemetry`                   | Ingest a single telemetry event. Idempotent on `(vehicle_id, timestamp)`. |
| GET    | `/api/v1/vehicles`                    | All 50 vehicles with current status, battery, last anomaly. |
| GET    | `/api/v1/fleet/status`                | Per-status counts across the fleet. |
| GET    | `/api/v1/zones/counts`                | Entry count per zone (all 20). |
| GET    | `/api/v1/anomalies`                   | Recent anomalies; filter by `vehicle_id`, `from`, `to`. |
| POST   | `/api/v1/vehicles/{id}/status`        | Admin status update (`fault` triggers atomic mission cancel + maintenance). |
| GET    | `/health`                             | DB ping. |

## Decisions, briefly

The two or three most important decisions, in one line each:

1. **Append-only `zone_entries`** instead of a mutable counter. Eliminates lost-update risk by construction; counter is a derived `COUNT(*) GROUP BY`.
2. **`SERIALIZABLE` + bounded retry** for the fault transition, plus a **partial unique index** `missions(vehicle_id) WHERE status='active'` for defense in depth.
3. **Polling (1.5 s)** instead of WebSockets — equivalent UX at this scale, dramatically simpler infrastructure.

Full details and the four-question ADR are in [`ADR.md`](./ADR.md).

## AI usage

I used Claude Code (Opus 4.7) throughout. Every meaningful prompt, redirect, and the closing reflection are in [`AI-INTERACTION-LOG.md`](./AI-INTERACTION-LOG.md). Short version: AI was a force multiplier for scaffolding and ADR drafts; it needed close review on anything touching concurrency and isolation, which is exactly what the take-home evaluates.

## Future work / out of scope

- Auth (JWT) — open API in demo, CORS-restricted.
- WebSockets / SSE — polling sufficient at this scale.
- Geometric zone detection — spec defers to the edge client.
- Multi-tenant.
- Mutation testing, full Playwright E2E.
- Cloud deploy (Fly.io / Render manifests).
- Batch telemetry endpoint.
