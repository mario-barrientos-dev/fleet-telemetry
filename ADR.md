# Architecture Decision Record — Fleet Telemetry Monitoring Service

**Status**: Accepted · **Date**: 2026-05-22

## 1. The most important decisions, and why

### 1.1 Append-only `zone_entries` table; counter = `COUNT(*) GROUP BY zone_id`

The hardest concurrency requirement is *every entry is counted, even when 50 vehicles cross the same zone in the same second*. A mutable counter row with `UPDATE zones SET cnt = cnt + 1` is atomic in Postgres but serialises around hot rows at shift change (50 vehicles converging on `charging_bay_1`). I write a row per entry instead, with `UNIQUE (source_event_id)` for idempotency. The counter becomes a derived read. This eliminates lost-update risk *by construction*, gives me an audit trail for free, and keeps the read fast for 20 zones. Cost: read grows with history — addressed at scale by a refreshable materialized view.

### 1.2 `SERIALIZABLE` + bounded retry for `TransitionToFault`, plus schema-encoded invariants

REQ-F-008 demands the `fault` status transition atomically (a) cancel the vehicle's active mission and (b) create a maintenance record. Three tables are touched. I chose `SERIALIZABLE` with bounded retry on `serialization_failure`. Correctness over throughput — fault transitions are rare. As **defense in depth**: `missions` has a partial unique index `(vehicle_id) WHERE status='active'`, so even with the wrong isolation level the schema forbids two active missions; `maintenance_records.triggered_by_event_id` is UNIQUE, so a re-delivered fault event cannot create a duplicate. A `READ COMMITTED + SELECT FOR UPDATE` approach would also work and be cheaper; I'd switch only if SERIALIZABLE retries showed up in p99 latency.

### 1.3 Polling (1.5 s) over WebSockets

For a single-client dashboard, WebSockets adds server-side fan-out, reconnection handling, and backpressure for no perceptible UX gain (a human eye does not distinguish 200 ms from 1.5 s on a fleet count). Polling is observable, debuggable, and a one-liner in RTK Query. SSE would be the second choice if true server-push became necessary.

## 2. What was unclear; what I assumed

- **"Active mission" was undefined.** I seed each of the 50 vehicles with an `active` mission on startup and expose an admin endpoint to create more. Without this seed the atomicity requirement (REQ-F-008) has nothing to cancel.
- **"Recent anomalies"** has no time window — defaulted to the last 24 h with keyset pagination and `from/to` query overrides.
- **`fault` arrives two ways** — via telemetry with `status="fault"` *or* via the explicit `POST /vehicles/{id}/status`. Both invoke the same use case; idempotent on `triggered_by_event_id`.
- **Anomaly definition** was left open. I implemented 6 deterministic rules (`low_battery` edge-trigger, `battery_anomaly`, `stuck`, `overspeed`, `status_inconsistency`, `fault_with_errors`) with published thresholds. *No ML today* — there is no historical data, and a rule-based real-time approach is defensible and testable. The detector sits behind a `Protocol`, so a statistical detector can replace it without touching the use case — see §3.
- **No auth was requested**, so the API is open in the demo with CORS restricted to the frontend origin.

### Prior-experience disclosure

I own and operate a small side venture (**relaai**) — an industrial-IoT platform with overlapping concepts (machine events, edge gateways, anomaly detection, escalation rules, failure / maintenance records). Domain familiarity informed *pacing*, not *content*: I did not open or copy from that codebase during the exercise, and the take-home design diverges where it matters (rule-based deterministic anomalies here vs. a training-based detector in relaai; vertical-slice hexagonal monolith here vs. multi-module legacy structure there). Calling this out so reviewers can ask sharper follow-up questions.

## 3. What would change at significant scale

I define **"significantly"** as ≥10 000 vehicles at 1 Hz (~10 000 writes/s) or sub-100 ms event-to-dashboard latency.

- **Ingestion**: `POST /telemetry` moves behind a gateway publishing to Kafka/MQTT, partitioned by `vehicle_id`. The in-process `asyncio.Lock` per vehicle becomes a partition key — ordering is preserved by topology, not by lock.
- **Persistence**: `telemetry_events` becomes a Postgres declarative partition by day, monthly archival to S3 / Iceberg.
- **Zone counter**: from `COUNT(*) GROUP BY` to a refreshable materialized view, or a Redis counter incremented from the consumer (reconciled against `zone_entries` as source of truth).
- **Anomaly detection — explicit evolution path**:
  1. **Today (0 days of data)**: deterministic rules with published thresholds.
  2. **After ~7–30 days of capture**: baseline per vehicle on a rolling window (z-score on battery drain rate, speed distribution, zone dwell-time). The hard rules become a safety floor; the statistical layer sits on top.
  3. **At scale**: tunable sensitivity, configurable detection window, historical backfill for onboarding new fleets, and a feedback loop (`confirmed / false_positive / resolved`) that tightens or relaxes thresholds. This is the pattern I run in production in **relaai** (see §2 disclosure) — the take-home detector is intentionally simpler and lives behind a `Protocol` so the swap is local.
- **Fleet aggregate**: `vehicles_current` stays as a snapshot table; under heavy write load, swap to a streaming projection.
- **Frontend**: polling → SSE or WebSockets when multiple operators watch simultaneously; CDN-served static bundle.

## 4. What I deliberately left out

- **Geometric zone detection.** The spec explicitly trusts the edge client.
- **Auth/authz.** Not requested; would have been costly to demo well in the budget.
- **Geographic map view.** Spec asks for a list, not a map.
- **WebSockets/SSE.** Polling sufficient at this scale.
- **Mutation testing & full E2E (Playwright).** Replaced by targeted concurrency tests and component tests with MSW.
- **Batch ingestion.** Bursts handled by client concurrency, not batching, matching the spec wording.
- **Multi-process / multi-region readiness.** Single-process correctness documented; multi-process path is sketched (advisory locks, distributed cache) but not implemented.

All exclusions are recorded in the README as *Future work / out of scope*.
