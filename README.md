# GravityGuard

A working local astronaut-health monitoring demonstration for the NASA Space Apps hackathon. React/TypeScript + FastAPI + SQLAlchemy/SQLite. The core workflow runs without an LLM or internet access after dependencies are installed.

All seeded astronaut telemetry, crew identities, and exam records are synthetic. A separate **Real Research Data Replay** mode uses explicitly labeled Earth-based clinical measurements. This prototype is not an approved medical system. Its experimental trend flags do not establish diagnoses, predict outcomes, or recommend treatments.

## Run locally

Prerequisites: Python 3.12+, Node 20.19+ (or Node 22+), and npm. Run commands from the repository root.

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
.venv/bin/python scripts/dev.py
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**. The launcher starts both services and stops them on Ctrl+C. Stop any existing process on these ports before launching it.

For a single onboard process with bundled, offline assets:

```sh
npm run build --prefix frontend
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Build before starting the backend; the static mount is detected at startup. No Google Fonts/CDN or cloud service is required. Runtime-only Python dependencies are in `backend/requirements.txt`; `backend/requirements.lock.txt` records the exact environment used for verification.

Choose **Astronaut** or **Flight surgeon** on the sign-in screen. Both use the prefilled demo password `demo-orbit-2026`. API usernames are `astronaut` and `doctor`; additional synthetic accounts are `astronaut2` and `astronaut3`. Sign out using the icon beside your name to switch workspaces. Separate browser tabs have separate sessions.

The first launch seeds three astronauts with 30 days of history, matching synthetic baselines, exam placeholders, and an initial delivered ground snapshot. Subsequent launches preserve the database; seed logic does not overwrite readings. Alex Morgan's synthetic history contains the intended sustained cardiovascular, strength, and balance changes.

## Demonstrate the full workflow

1. Sign in as **Astronaut**. Explore the chart and click a health module to inspect evidence and experimental rules. **Start simulator** appends readings immediately and every eight seconds while enabled.
2. In **Mission & Earth link**, set the delay to `0` for a fast demonstration, save, and select **Simulate offline**. The default is 20 demo seconds per leg.
3. Open **Medical assistant** and submit a synthetic dizziness report. The record and alert save locally. An explicit warning-sign report or self-rated severity >= 8 shows immediate onboard escalation without waiting for Earth.
4. Sign out and enter **Flight surgeon**. The new symptom alert is absent because its downlink has not arrived. Capture and receive times identify the ground record's freshness.
5. Return as **Astronaut**, restore the link, and select **Process due messages**. With a nonzero delay, wait until the queue's eligible time. The signed-in app also processes due messages every eight seconds.
6. Enter **Flight surgeon**. Choose the newly delivered symptom finding, enter a review note and your own feedback, and select **Send reviewed feedback**. Process due messages in **Earth link** after the return delay.
7. Return as **Astronaut**, open **Alerts & feedback**, and **Acknowledge** the delivered review. Process due messages again. The doctor receives the acknowledgment after its downlink.

The same sequence can be checked against the running API:

```sh
.venv/bin/python scripts/demo_workflow.py
```

This script adds a synthetic symptom/review, verifies each delivery boundary, signs out its API sessions, and leaves the demo link connected with zero delay. It does not reset history.

## Implemented and verified

- Role-based API access, hashed passwords, expiring sessions, revocation, and astronaut record isolation.
- Persistent synthetic measurements, matching baselines, exam records, provenance, units, quality, duplicate handling, and audit records.
- Current readings, seven-day means, prior-week comparison, descriptive slopes, baseline deltas, missing/stale data, and three sustained-change rules.
- Local evidence explanations, separate safety escalation, demo-only workflow guidance, and versioned NASA background references.
- Encrypted local store-and-forward events, link outages, per-leg delay, retries, idempotent delivery, distinct ground snapshots, clinician feedback, and downlinked acknowledgments.
- Connected astronaut and doctor interfaces, history filters, manual ingestion, CSV export, evidence details, mission controls, simulator controls, and responsive navigation.
- A built dashboard served directly from FastAPI, including local font assets.

## G2 Watch integration

The **G2 Watch** page reuses the supplied virtual-watch implementation: six coherent scenarios, heart rate/resting heart rate, HRV, SpO2, sleep, steps, sensor freshness, notifications, and symptom reporting. **All G2 readings are simulated; no physical watch is connected.** The selected feed is shared with the dashboard/history, current medical assistant, and delayed Earth doctor records. Source/device/provenance are retained. Watch alerts and generic measurement uploads now use the shared ingestion-and-monitoring path.

Restart the backend for the additive device-ID column and simulator-state table; existing records and conversations are retained. Choose **G2 Watch**, select a scenario, and send individual readings or start the feed. The concerning scenario produces experimental review notifications after about seven readings. Doctor views expose the delivered sensor evidence and complete AI conversations after the configured delay.

Work is on `feature/g2-watch`; main was not merged or pushed. [Exact ZIP comparison, retained components, migration, and verification](docs/g2-integration.md). [Watch controls and scenarios](docs/smartwatch.md).

## Real Research Data Replay

Sign in as Astronaut and choose **Real Research Data Replay** in the sidebar. It replays **481 real heart-rate readings across eight minutes** from [PhysioNet BIDMC record 01](https://physionet.org/content/bidmc/1.0.0/), with original bpm values and elapsed seconds preserved. Use one-sample-per-second playback, advance 30 samples, or load the full record; restart playback without duplicating stored measurements. The chart, downloadable original CSV, citations, license, and checksum are available offline.

These are **Earth ICU measurements, not astronaut or established resting-heart-rate data**. Research data use a separate subject and cannot mix with astronaut records, baselines, AI context, or Earth downlinks. Eight minutes cannot satisfy the existing multi-day monitoring rules; the view reports insufficient longitudinal data and shows descriptive statistics instead. No clinical validation or future prediction is claimed. [Exact provenance, timestamp adapter, and real-versus-simulated inventory](research_data/README.md).

Restart the backend to create additive replay tables. The original simulator, AI, and communication workflow remain available.

## Conversational space medical assistant

Muse Wonder now generates the medical explanation rather than selecting predefined answers. It supports general medical education, space-medicine questions, personal assessments, and threaded follow-ups. It dynamically plans relevant patient data and source retrieval; educational questions do not load the clinical profile or automatically create review alerts. Empty local RAG coverage does not prevent an ordinary educational answer.

Personal short answers now show **Possible problem** and **Recommendation**, using the same generated blocks shown in **Detailed analysis**. A single independent emergency notice stays separate, with expandable support details. Incomplete or repetitive model answers receive one bounded quality revision; failed generation is labeled unavailable instead of replaced by warning text. Educational follow-ups retain their conceptual intent even during an unresolved incident. See the [short-answer investigation and changes](docs/short-answer-redesign.md). Source-supported statements link to verified local citation IDs; general model knowledge is explicitly labeled as not independently source-verified. Structural validation and an automated evidence/policy audit check the output without enforcing a wording template or disease list. For personal questions, the model can propose a few uncertain explanations and targeted follow-ups; patient facts remain read-only.

The local corpus remains **15 reviewed NIH/NLM/NASA documents / 34 passages**. [Source inventory and permissions](medical_knowledge/README.md). No model training or external embeddings API is used.

Use **Medical assistant** in the astronaut workspace. Continue the current thread or select **New conversation**. Restart the backend for the additive thread, job, and ground-archive tables. In your private backend Terminal, keep `MODEL_API_KEY` exported and set `ENABLE_LLM=true`. No credential file or React variable is needed. All development calls were mocked. When the model is unavailable, the assistant says so honestly; monitoring, local alerts, symptom recording, and reference retrieval still work offline.

Emergency warnings now appear before remote generation and stay visible alongside generated explanations. Chat remains available during generation and after escalation. Failed/interrupted jobs retain local guidance and support explicit retry. Every new conversation turn is queued for Earth delivery, with a separate doctor conversation archive obeying the configured delay. No mission-approved clinical treatment procedures are installed; basic reference guidance is labeled separately.

Read the [global architecture investigation and limitations](docs/global-assistant-architecture.md), plus the [root-cause investigation, new architecture, test results, and safety limitations](docs/conversational-redesign.md). The earlier [five-layer report](docs/medical-assistant.md) describes the superseded bounded prototype.

Offline reference retrieval remains available:

```sh
.venv/bin/python scripts/knowledge.py 'What controls the rate and rhythm of the heartbeat?'
```

## Checks

```sh
.venv/bin/python -m pytest backend/tests -q
npm run build --prefix frontend
npm run test:e2e --prefix frontend
```

Browser tests use installed Google Chrome by default. Alternatively install Playwright Chromium and set `PLAYWRIGHT_BROWSER=chromium`:

```sh
cd frontend
npx playwright install chromium
PLAYWRIGHT_BROWSER=chromium npm run test:e2e
```

Browser tests start isolated API/Vite servers on ports 8002/8003/5174 with a new temporary SQLite database per run. Build first: one test exercises FastAPI's built dashboard directly. Tests do not reset or modify the normal demo database. API tests use isolated in-memory or temporary databases. Browser screenshots/traces on failure live under ignored `frontend/test-results/`; successful test screenshots are also kept in that directory.

Verified in this implementation: **185 backend tests, 10 Chrome browser workflows, and the production TypeScript/Vite build**. Model calls are mocked for development; tests establish integration behavior, not medical accuracy. See [verification details](docs/verification.md).

## Legacy trend-explanation connection check

This section covers the preserved trend selector and standalone connectivity check. The conversational generator above uses the same secure transport with free structured explanations and an automated audit.

The default explanation is an offline deterministic template. The legacy trend explanation adapter can select existing evidence IDs to emphasize; it cannot produce user-visible diagnoses, treatments, actions, or new facts. All evidence is retained and rendered locally. Its timeout and invalid-output fallback are tested with stubbed provider responses. No live provider call was made by the implementation agent; provider behavior is verified with mocks. Real connectivity is tested separately by the operator.

The backend uses `https://api.meta.ai/v1/responses`, model `muse-wonder-1.0`, and the `MODEL_API_KEY` environment variable. The legacy `/api/assessments` endpoint requires both `ENABLE_LLM=true` and `use_llm=true` for remote evidence selection. The new conversational `/api/assistant/messages` endpoint uses `ENABLE_LLM=true` as its operator opt-in when an astronaut submits a question. No key is supplied to React, stored in application records, or logged. Disabled/missing credentials use the offline template; network, authentication, rate-limit, and invalid-output failures use the offline fallback. Requests have a finite timeout, reject redirects, and limit response size.

Run the default connection check without credentials or network access:

```sh
.venv/bin/python scripts/test_meta_connection.py
```

For your own live test in macOS Terminal (zsh), enter the key using a hidden prompt. These commands keep the value out of shell history and files; do not run them with shell tracing enabled:

```sh
read -rs "MODEL_API_KEY?Meta API key: "
export MODEL_API_KEY
.venv/bin/python scripts/test_meta_connection.py --live
```

The explicit `--live` flag calls the provider directly, independently of the application's `ENABLE_LLM` setting. The check sends only a fixed synthetic evidence fixture and prints a success result or a fixed, sanitized diagnostic code. It does not load `.env`, print provider responses, or print credentials. A successful mock check verifies request construction and parsing, not a real connection. No real Meta call was made during implementation.

For the application, also run `export ENABLE_LLM=true` and start or restart `.venv/bin/python scripts/dev.py` from that same Terminal session so the backend inherits the variables. Choose **Refresh explanation** in the assistant; it calls the existing `/api/assessments` endpoint with `use_llm=true`. The response labels AI-assisted selection or offline fallback. AI availability never controls detection or urgent escalation. Do not put the key in `.env`, frontend configuration, or a `VITE_` variable. When finished, use `unset MODEL_API_KEY` in that Terminal session.

Connection diagnostics distinguish `missing_credentials`, `http_400` (request rejected), `http_401` (authentication rejected), `http_429` (rate limit), `timeout`, `network_error`, and `tls_verification_failed` (Python certificate trust). Response diagnostics distinguish `output_token_limit`, `response_not_completed`, `empty_output`, `refused_response`, `invalid_focus`, `invalid_response`, and `response_too_large`. No raw exception or provider body is printed. An HTTP 200 does not by itself establish that structured generation completed successfully.

The CLI defaults to a 60-second connection/read timeout, configurable with `--timeout 1` through `--timeout 120`. The health application's timeout remains 10 seconds. Requests allow 2,048 total generated tokens because reasoning and visible output share that budget. Incomplete generation is still rejected safely. The Python transport adds certifi's Mozilla CA bundle to its default trust context. This supports macOS Python installations with missing default roots while preserving certificate-chain and hostname verification. Install updated dependencies with `.venv/bin/pip install -r backend/requirements.txt` if needed. If `tls_verification_failed` persists, check whether a network proxy requires an organization-provided CA or whether the server certificate chain is invalid; do not disable certificate verification.

Provider references: [Meta Responses API](https://dev.meta.ai/docs/protocols/responses), [structured output](https://dev.meta.ai/docs/structured-output), and [Muse Wonder](https://dev.meta.ai/docs/muse-wonder).

## Scope and limitations

- Bone, kidney, and vision support stores/displays synthetic exam placeholders and requests dedicated assessment; it does not detect bone loss, stones, or SANS.
- No clinically approved protocols are installed. Background references are not approval of the team's demo thresholds or workflows.
- Onboard and ground stores are logically separated inside one SQLite file. Earth communication is simulated locally; there is no external medical transport.
- Only queue payloads are encrypted. Local key generation is suitable for the demo; full-database encryption, TLS, secret rotation, deployment hardening, rate limiting, account provisioning, migrations, and disaster recovery remain unfinished.
- Updates use polling. WebSockets, background delivery workers, medical attachment upload, physical wearable integration, and prediction models are deferred.
- The `SEED_DEMO=false` switch disables synthetic provisioning and the simulator; non-demo provisioning is not implemented.

Local data is stored in ignored `gravityguard.db` and `.local/sync.key`. Keep the key with the demo database; deleting it prevents queued payload decryption. To start a fresh synthetic demo, stop services and move the database, SQLite sidecar files, and key directory aside before restarting. Never use real medical data in this prototype.

## Project map

```text
backend/app/api/            Auth, records, analysis, symptoms, doctor review, sync, simulator
backend/app/models/         SQLAlchemy data models
backend/app/services/       Ingestion, statistics, safety, explanations, encryption, transfer
backend/app/risk_modules/   Experimental longitudinal rule registry
backend/app/database/       SQLite connection and session lifecycle
backend/tests/             API, analysis, sync, safety, and persistence tests
frontend/src/              Connected React components, pages, and typed API client
frontend/e2e/              Chrome workflow and responsive-interface tests
simulator/                 Reproducible synthetic history generator
medical_knowledge/         Versioned reference metadata and demo-only workflow
scripts/                   Local launcher and live API walkthrough
docs/                      Plan, architecture, and verification report
```

Read the [implementation plan](docs/implementation-plan.md) and [architecture](docs/architecture.md) for phase acceptance criteria, data flow, and extension contracts. The future prediction interface is reserved in `services/interfaces.py`; no forecast implementation exists.
