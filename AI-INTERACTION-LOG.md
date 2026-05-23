# AI Interaction Log — Fleet Telemetry Take-Home

**Tools used**: Claude Code (Claude Opus 4.7 / 1M context) for code generation, code review, and ADR drafting. No other models.

**AI-assisted time**: ~3.5 h of 5.5 h budgeted (~64%). The remainder was reading the spec, designing the schema and concurrency strategy on paper, writing the ADR, and hand-rolling the parts I did not want to delegate.

---

## Entries

### Entry 01 — Scaffold backend + frontend + compose `[scaffold]`

**Goal**: Generate `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, root layout, frontend `package.json` + Vite + ESLint flat config + Tailwind setup, and a placeholder `/health` endpoint, all under one consistent monorepo structure.

**Prompt** (summary):
> Generate a hexagonal FastAPI scaffold with these constraints: SQLAlchemy 2.x async, uv as package manager, Alembic ready, ruff + mypy strict configured, pytest with asyncio_mode=auto, no leftover noqa or type-ignores. Mirror with a Vite + React 18 + TS strict (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) frontend using ESLint flat config, jsx-a11y, Vitest. One root Makefile, one docker-compose.

**Output (summary)**: Approximately correct layout. Three issues I had to redirect:

**Rejected / redirected**:
- Initial draft annotated `lifespan(app: FastAPI)` and ruff flagged the unused arg via N803. Renamed to `_app` to make intent explicit.
- It generated a `# type: ignore[call-arg]` on `Settings()` that mypy then complained about as *unused*. Pydantic v2's `BaseSettings` no longer needs that ignore. Deleted.
- It imported `AsyncIterator` from `typing` (deprecated in 3.10+). Moved to `collections.abc`.

**Time saved**: ~25 min vs typing the whole scaffolding by hand. Review effort: ~5 min.

---

### Entry 02 — Initial Alembic migration `[implementation]`

**Goal**: One reversible migration that creates all six tables + two ENUMs in a defensible order, with the schema-encoded invariants (partial unique on active missions, UNIQUE source_event_id on zone_entries, UNIQUE triggered_by_event_id on maintenance, CHECK constraints).

**Prompt** (summary):
> Write a single Alembic migration for tables [list] with these PostgreSQL features: ENUM types, partial unique index, CHECK constraints, JSONB, ARRAY(String), server defaults. Both upgrade and downgrade must be real; downgrade drops in dependency order including the ENUMs.

**Output**: ~90% correct.

**Rejected / redirected**:
- First draft used `create_type=True` on every ENUM column reference, which crashes on the second column declaration ("type already exists"). I corrected to create the ENUM once at the top of `upgrade()` and reference it with `create_type=False` on column declarations.
- Initial draft omitted the `postgresql_where` parameter on the partial unique index. Without it, the index becomes a regular UNIQUE and breaks the schema-encoded invariant. Added explicitly.

**Time saved**: ~20 min. Review effort: ~10 min — re-reading the SQL carefully because *this* schema is the spine of the concurrency guarantees.

---

### Entry 03 — Anomaly detector design `[design]`

**Goal**: Settle on the six rules and their thresholds *before* writing any code, so the ADR can defend the choice.

**Prompt** (summary):
> Given the take-home spec (1 Hz telemetry, statuses [idle, moving, charging, fault], industrial vehicles), propose 5–7 deterministic anomaly rules with concrete numeric thresholds. Justify each one operationally — what real problem does it catch? Note explicitly which rules need a previous event (stateful) and which are stateless.

**Output**: Eight candidate rules. Discussed each and trimmed to six.

**Rejected**:
- Suggested an "off-route" rule based on geofence violation. Out of scope (the edge client owns geometry).
- Suggested a "telemetry gap" rule for vehicles silent >N seconds. Stateful in a way that requires a scheduled scan, not in-line. Future Work.

**Accepted (and shipped)**: low_battery (edge-triggered), battery_anomaly (impossible spike / sudden drop), stuck, overspeed, status_inconsistency, fault_with_errors.

---

### Entry 04 — Concurrency tests for the zone counter `[test]`

**Goal**: Prove the implementation actually serialises correctly under load — the spec's most explicit concurrency requirement.

**Prompt** (summary):
> Write an async pytest using asyncio.gather to fire 50 concurrent ingest calls — one per vehicle — all naming the same `zone_entered="charging_bay_1"`, with distinct timestamps so the (vehicle_id, ts) UNIQUE doesn't catch them. Assert COUNT(*) on zone_entries for that zone is exactly 50.

**Output (summary)**:
- Correct gather pattern.
- Correct assertion (`== 50`, not `>= 1`).

**Rejected / redirected**:
- First draft used `await asyncio.gather(*[one() for _ in range(50)])` with `one()` being a closure that captured the same `i` due to Python's late binding. I caught it before commit: rewrote `one(i: int)` as a parameterised coroutine.
- I added a second test (`replaying the same event does not double-count`) that the agent had not suggested. This is the inverse-property test that *would* catch a regression where the UNIQUE on `source_event_id` was dropped.

**Verification step (still pending Docker)**: To prove the test actually exercises the race, I planned to temporarily remove the `asyncio.Lock` in `IngestTelemetry` and confirm the test fails. Once Docker is up, that's the first thing I do.

---

### Entry 05 — Fault transition isolation strategy `[design]`

**Goal**: Pick an isolation level and write the use case so two concurrent fault triggers can't double-cancel or double-create.

**Prompt** (summary):
> The fault transition touches three tables (vehicles_current, missions, maintenance_records). I want to pick between SERIALIZABLE + retry vs READ COMMITTED + SELECT FOR UPDATE. List the trade-offs concretely for *this* shape: low frequency, three-table write, schema already has UNIQUE on maintenance_records.triggered_by_event_id. Make a recommendation.

**Output (summary)**: Recommended SERIALIZABLE with bounded retry, citing the rare-operation argument and the clarity of a single statement in the ADR. Suggested the partial unique index on missions as defense-in-depth.

**Accepted**: yes — both the isolation choice and the defense-in-depth pattern landed in ADR-0005 and the migration.

---

### Entry 06 — Pydantic v2 schemas + uniform problem+json envelope `[implementation]`

**Goal**: Schemas for HTTP boundary + an exception handler that maps `DomainError` subclasses to consistent `application/problem+json` bodies.

**Output**:
- Schemas correct, including a `field_validator` for `zone_entered ∈ ZONES_SET`.
- Error handler initially included an artificial `_ = (...)` block at the end "to silence ruff for unused inner function names". I deleted it — the inner functions are registered by the decorator and ruff doesn't actually complain about them.

**Rejected**: the artificial silencer was a hallucination — a fix for a non-problem. Removed before commit.

---

### Entry 07 — Frontend dashboard structure `[implementation]`

**Goal**: Three panels (fleet status, vehicle list, zone counts), feature-sliced layout, 1.5 s polling via RTK Query.

**Output**: Mostly correct. RTKQ wired with `pollingInterval` cleanly.

**Rejected / redirected**:
- The agent's first draft of `vite.config.ts` had `test: {...}` inside `defineConfig` from `vite` — that block belongs to `vitest/config`'s defineConfig, not vite's. Split into a separate `vitest.config.ts`.
- Generated MSW-based integration tests; running them surfaced the known undici/jsdom `AbortSignal` incompatibility (https://github.com/mswjs/msw/issues/1934). I replaced the MSW test with direct component tests on `StatusBadge` and `BatteryBar` to avoid flakiness, and documented the limitation in a code comment.

---

### Entry 08 — Type-checking the use cases against `mypy --strict` `[refactor]`

**Goal**: Get a clean strict pass on 37 source files including the new use cases.

**Errors caught**:
- `uow_factory` annotated as bare callable without parameters. Introduced `IngestUoWFactory = Callable[[], SqlAlchemyUnitOfWork]` and `FaultUoWFactory = Callable[..., SqlAlchemyUnitOfWork]` (the latter takes an optional `isolation` kwarg).
- `AnomalyDetector` Protocol didn't accept `source_event_id` keyword, but the implementation did. Mypy correctly caught the mismatch at the call site. Added the kwarg to the Protocol.
- `Mapped[dict]` missing type args on the `AnomalyRow.details` column. Made it `Mapped[dict[str, object]]`.

---

## Reflection

1. **Where AI shined**: Scaffolding and "boring infrastructure" — Alembic migrations, RTK Query wiring, Tailwind utility classes, the bulk of the SQLAlchemy 2.x model definitions. It also drafted a credible first version of the ADR I could then sharpen. Net: roughly a 3–5× speed-up on those categories.

2. **Where AI failed**: Anything involving subtle correctness — concurrency tests (late-binding closure bug), Vite vs Vitest `defineConfig` confusion, hallucinated "fixes" (the unused-name silencer in `error_handlers.py`), and the predictable `from typing import AsyncIterator` regression. Strictly: the categories the take-home is built to evaluate are the categories I had to police hardest.

3. **What I had to verify manually**: Every concurrency test. I treated agent-written assertions as suggestions, then re-derived the expected post-condition from first principles before accepting. I also re-read the migration SQL line by line because it's the spine of the schema-level invariants the rest of the code relies on.

4. **What I deliberately wrote by hand**: The `TransitionToFault` retry loop (I wanted to reason about `serialization_failure` mapping directly), the `VehicleLockMap` (so I could think about the double-checked locking pattern), and the ADR (the whole point of an ADR is that *I* believe each decision, not the model).

5. **What I'd do differently next time**: I went into this with a heavy planning pass — requirements, assumptions, architecture, data model, API contracts, design patterns, testing strategy, an implementation roadmap with DoD per phase, a trade-offs matrix, and a set of ADRs, all drafted **before** writing any code. That strategic planning is what kept the architecture coherent under time pressure, and I'd do it the same way again. Where I'd be sharper is the **tactical layer**: even with a perfect plan, the agent still produces line-level mistakes — wrong import paths, late-binding closures, framework-version confusion. Those don't get caught by the plan; they get caught by reading each diff slowly. Next time I'd impose a stricter review cadence — every agent diff reviewed against an explicit checklist before it lands, no exceptions, even for "boilerplate-looking" output.
