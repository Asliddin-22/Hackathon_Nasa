# GravityGuard implementation plan

Primary acceptance criterion: an astronaut can record synthetic health information while Earth is unavailable; local analysis and alerts continue; a doctor can review only delivered records, send feedback, and eventually receive the astronaut's acknowledgment.

## Phase 1 — Foundation (complete)

- Modular FastAPI application and SQLAlchemy/SQLite operational database.
- Users, missions, measurements, baselines, medical tests, symptoms, assessments, alerts, reviews, protocols, queue, ground replica, sessions, and audit records.
- Three synthetic astronauts, a doctor, and 30 days of deterministic timestamped telemetry per astronaut.
- Login, hashed passwords, expiring/revocable opaque sessions, role checks, and patient isolation.
- Validated measurements, required timezone/unit/origin/quality, immutable IDs, and duplicate/conflict handling.
- Acceptance: API ingestion/readback/auth tests; live server health check; disk persistence verified after reopening SQLite.

## Phase 2 — Health intelligence (complete for the bounded MVP)

- Daily aggregation, seven-day means, prior-week means, slopes, personal-baseline deltas, missing-day reporting, quality exclusions, and stale-data checks.
- Cardiovascular, strength-test, and balance-test experimental rules; three consecutive collection days required.
- Bone, kidney, and vision assessment requirements, synthetic exam records, and explicit unknown status.
- Deterministic explanations, source metadata, separate escalation rules, and an allowlist of workflow actions.
- Optional LLM integration selects existing evidence IDs only; local text and actions remain constrained. Provider behavior tested with stubs; actual paid API call unverified.
- Acceptance: sustained trends flag, isolated spikes and nonconsecutive observations do not; data origins do not mix; unavailable or invalid AI output falls back locally.

## Phase 3 — Ground review loop (complete as local simulation)

- Encrypted durable event payloads, per-leg delays, offline queues, retry backoff, and idempotent delivery.
- Distinct ground-record replica boundary and capture/receive timestamps.
- Doctor-authored feedback with idempotent review IDs, return delivery, astronaut acknowledgment, and acknowledgment downlink.
- Acceptance: full API round trip, delayed visibility, tampered-message retry, duplicate handling, and role enforcement.
- Deliberate limitation: one SQLite file holds logical onboard and ground stores; spacecraft networking and independent Earth deployment are not implemented.

## Phase 4 — Connected applications (complete)

- React/TypeScript astronaut overview, real history charts, evidence dialogs, symptom reporting, feedback, and acknowledgments.
- History filters, manual ingestion, CSV downloads, and periodic exam records.
- Doctor crew view, delivered-record evidence, review form, and delivery/acknowledgment receipts.
- Mission controls, simulated link interruption, delay controls, encrypted queue delivery log, and live-like simulator.
- Bundled fonts, responsive layout, mobile navigation, and visible API errors.
- Updates use eight-second polling; WebSockets remain deferred.
- Acceptance: production build and real Chrome tests cover both workspaces, API operations, history/export, simulator, and mobile layout.

## Phase 5 — Verification and handoff (complete)

- Backend tests and browser tests pass.
- Standalone running-API walkthrough passes against persisted SQLite.
- Setup, demo instructions, implementation boundaries, and extension points documented.

## Intentionally unfinished

- Clinically validated thresholds, diagnostic/predictive models, and approved clinical protocols.
- Bone/kidney/SANS detection, scan processing, and medical attachment uploads.
- Physical wearable integrations and device connectors.
- Production identity, account provisioning, TLS termination, database-wide encryption, key management/rotation, database migrations, and independent Earth infrastructure.
- Autonomous external LLM explanations or treatments; live provider verification requires an operator-supplied key and opt-in.

## Five-layer conversational assistant expansion

All five bounded prototype layers are implemented and verified. See [the phase report](medical-assistant.md) for the completed source foundation, NASA corpus, local retrieval/Muse Wonder planning, patient-context integration, connected UI, and exact remaining clinical/coverage limitations. This expansion preserves the original MVP's monitoring and review loop; it does not complete the clinical validation or production features listed above.

## General conversational redesign

The earlier explanation catalog and automatic profile injection have been replaced. See [the completed investigation and implementation](conversational-redesign.md) for the model-driven conversation flow, selective data access, free explanations, evidence labels, source/record checks, thread privacy, and test boundaries.
