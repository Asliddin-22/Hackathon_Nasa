# Verification report

Date: November 15, 2026 (America/New_York). Environment: macOS arm64, Python 3.12.4, Node 23.9.0, installed Google Chrome. Exact Python packages are recorded in `backend/requirements.lock.txt`; frontend dependencies are in `frontend/package-lock.json`.

| Check | Result | Coverage |
| --- | --- | --- |
| `python -m pytest backend/tests -q` | 16 passed | API authentication, patient and role isolation, synthetic seed provenance, validated ingestion, duplicate/conflict handling, logout, sustained trend rules, single-spike rejection, stale/missing/quality/origin behavior, urgent local escalation, constrained model outputs/fallback, delayed offline feedback loop, encrypted payloads/retries, simulator persistence, and SQLite reopen persistence |
| `npm run build --prefix frontend` | Passed | Strict TypeScript check, Vite production assets, bundled fonts, chart/app chunk split |
| `npm run test:e2e --prefix frontend` | 3 passed | Real Chrome sessions using isolated real FastAPI and SQLite plus Vite; offline visibility, doctor review, return delivery, acknowledgment downlink, record history, manual ingestion, CSV download, evidence dialogs, simulator controls, mobile navigation/width, and built same-origin frontend with external asset requests blocked |
| `python scripts/demo_workflow.py` | All 3 milestones passed | Standalone running API on port 8000 with on-disk demo database; offline reporting, delivered ground record, reviewed feedback, and synchronized acknowledgment |
| Launcher readiness and shutdown | Passed | `scripts/dev.py` starts API and Vite; both HTTP endpoints respond; Ctrl+C shuts down owned process groups |

Initial browser verification exposed a selector that included the dynamic unread count. Navigation now has a stable accessible label, and the full browser round trip passes. Screenshot inspection also exposed the initial chart animation showing an empty plot; plots render immediately. KPI sparklines use actual stored synthetic measurements. Desktop doctor and astronaut pages and the 390px mobile history layout were visually inspected.

One non-failing backend warning remains: the installed Starlette version deprecates its HTTPX TestClient integration in favor of `httpx2`. All API tests pass; this does not affect the application's runtime HTTP endpoints. Browser-runner NO_COLOR/FORCE_COLOR warnings are cosmetic.

## Verification boundaries

- The optional model-provider integration is tested with stubbed success, timeout, and unsupported-output responses. No real paid API call was made. No provider performance or medical accuracy is claimed.
- Tests verify application behavior, not clinical validity, sensitivity/specificity, or real astronaut outcomes.
- Queues, delay, and ground replication run locally. No physical sensor, spacecraft communications link, external Earth deployment, approved clinical protocol, or prediction model was tested or represented as implemented.
- Encryption verification covers event payloads and tamper detection; it is not a security audit or a claim of full database encryption.
- The mobile test verifies navigation and horizontal containment at 390px; broader browser/device and accessibility audits remain outside this hackathon scope.

## Meta Muse Wonder integration update

The optional model adapter now uses the Meta Responses API at `https://api.meta.ai/v1/responses`, model `muse-wonder-1.0`, and backend-only `MODEL_API_KEY`. No actual credential was accessed or placed in a file, and no real provider request was made during implementation. Test invocations supplied dummy process credentials; the standalone mock check replaces credential lookup and transport without inspecting the environment.

- Full backend suite after integration: **39 passed**. Added coverage verifies request URL/model/headers/schema, missing or disabled credentials, timeout/network/401/429/500 fallback, invalid evidence, incomplete/refused/oversized responses, redirect rejection, bounded timeout, and the real assessment endpoint's analysis and urgent-symptom safety behavior during provider failure.
- `.venv/bin/python scripts/test_meta_connection.py`: **passed**, using a synthetic fixture, mock credentials, and an intercepted HTTP transport.
- Syntax compilation of the adapter, assistant, and connection script: **passed**.
- Existing React code, statistical rules, and local safety engine were unchanged. The previous browser/build verification above was not rerun for this backend-only change.
- The real Meta connection remains unverified, as requested. The README documents an explicit operator-only `--live` check using a hidden macOS Terminal prompt and no credential file.

## Connection-check investigation and regression fix

Confirmed local defects were reproduced with mocks; no live API calls, actual credential inspection, or `.env` reads were performed. The old `--live` path called `select_evidence`, whose `ENABLE_LLM` gate could skip HTTP entirely. It then collapsed that skip and every transport/response failure into “Connection not confirmed.” The submitted schema also permitted empty/repeated evidence IDs that the parser rejected. These are verified defects, but the operator's particular live failure cannot be conclusively attributed without the new sanitized diagnostic code.

The endpoint, model ID, typed input, `text.format` schema, and nested `output[].content[].text` parsing were checked against Meta's official Responses, structured-output, and Muse Wonder documentation. There was no evidence of a wrong endpoint/model or a need to parse Chat Completions `choices` or an SDK-only top-level `output_text` property.

The explicit CLI live check now invokes the provider directly; the health application retains its opt-in feature gate. The parser accepts schema-conforming empty/repeated IDs without losing evidence, ignores reasoning items, and rejects incomplete generation, refusals, and unknown IDs. The generated-token budget increased from 512 to 2,048 because the documented limit includes reasoning tokens. The CLI now has a separate configurable 60-second timeout; application calls remain limited to 10 seconds. The old limits could cause failures but were not proven to cause the reported live failure.

Verification after the fixes:

- **58 backend tests passed** with dummy process credentials. Coverage includes the CLI path with application AI disabled, documented response envelopes with reasoning and split text, missing credentials, HTTP 400/401/429/500, TLS/network/timeouts, schema-conforming outputs, invalid evidence, and incomplete HTTP-200 responses. Existing monitoring, local urgent escalation, persistence, and astronaut–doctor tests also pass.
- Default mock connection script: **passed**.
- Python syntax compilation: **passed**.
- CLI messages contain fixed diagnostic codes or numeric HTTP status only; mocked exception/body content and mock credentials are verified absent from output.
- Live provider connectivity remains for the operator to verify. Frontend assets were unchanged, so browser/build checks were not repeated.

## macOS Python TLS trust fix

The operator's live check reported `tls_verification_failed` while their curl request succeeded. This narrows the failure to Python's TLS setup/handshake, not an HTTP authentication response. Missing default Python CA roots are a likely explanation; the exact failing certificate chain was not inspected and no live request was made by the implementation agent.

The provider now constructs a secure default SSL context, augments its existing trusted roots with certifi's Mozilla bundle, and supplies that context to urllib's HTTPS handler. Certificate-chain verification remains `CERT_REQUIRED`, hostname checking remains enabled, and redirect blocking is retained. certifi is now an explicit runtime dependency; its tested version was already present in the lock file.

Verification: **60 backend tests passed**, and the default mock connection script passed. New tests reproduce an empty Python CA store, verify that certifi supplies trusted roots without weakening verification, confirm the actual transport receives the verified context, and verify offline fallback if the CA bundle cannot load. No actual API key was accessed or live API call performed. Operator retesting is still required to confirm the real connection.

## Five-layer medical assistant expansion

All five layers were implemented sequentially with checks before advancing. Details, source inventory, permissions, retrieval examples, changed files, and scope are recorded in [medical-assistant.md](medical-assistant.md) and [the corpus inventory](../medical_knowledge/README.md).

Final verification: **78 backend tests passed**, the production TypeScript/Vite build passed, and **4 real Chrome browser workflows passed** using isolated local FastAPI/SQLite/Vite servers. The existing mock Meta connection check also passed. A standalone offline corpus demonstration indexed **13 documents / 30 passages** and retrieved NHLBI cardiac-conduction text with provenance. Existing authentication, ingestion, trends, TLS/provider fallback, synchronization, doctor feedback, and acknowledgment tests remain passing.

New tests cover source permission/checksum validation, idempotent indexing and FTS repair, all-six-system coverage, NASA-specific citations, real retrieval endpoints, bounded model packets, invented-citation rejection, absent-coverage behavior, patient-specific baselines/trends, stale and missing data, origin separation, question persistence/idempotency, urgent local escalation without model calls or a knowledge index, and unresolved urgent alerts. The browser addition asks a medical question, verifies a short answer, opens detailed patient evidence/citations, reloads the saved question, delivers it to the doctor, and submits reviewed feedback. Screenshot inspection led to stricter passage-level explanation citations.

All Meta calls during development were mocked or disabled, and test processes used dummy credentials. No actual MODEL_API_KEY was inspected or accessed. The new structured grounded-plan request still needs operator live verification. No clinical accuracy, validated diagnosis, treatment safety, comprehensive illness coverage, physical-sensor performance, or prediction performance is claimed.

## Model-generated conversational redesign

The code investigation and completed redesign are documented in [conversational-redesign.md](conversational-redesign.md). The previously catalog-restricted conversational path has been replaced; prior milestone results above remain historical records.

Latest results: **102 backend tests passed**, **5 Chrome browser workflows passed**, and the TypeScript/production build passed. The existing Starlette TestClient deprecation warning remains non-failing.

New behavioral coverage includes diverse endocrine, auditory, skin, pharmacology, cardiovascular, renal, spaceflight, symptom/recovery, and multi-turn examples. Tests assert patient-scope selection, absence of educational data access/alerts, no-RAG generation, preserved generated wording, source/fact IDs, consistent shared summary blocks, owned parent-chain context, idempotency, stale/missing evidence, unknown citations, unsupported facts/treatments, audit/provider failures, explicit emergencies, personal warning signals, and education about warning signs. A mocked raw Responses transport exercises the full planning → generation → audit sequence.

The browser suite runs an ordinary offline backend and a separate isolated model-mocked backend with remote transport blocked. It retains monitoring/history/export/mobile and feedback/acknowledgment workflows, verifies honest offline conversation behavior, and verifies generated education, follow-up context, selective strength data, and physician delivery of a personal review request. No actual Meta API calls or private MODEL_API_KEY access occurred.

Mocks verify contracts and integration, not real model clinical reasoning, routing accuracy, source-entailment accuracy, or medical safety. Distinguishing hypothetical educational mentions from current unstructured symptoms depends on language-model planning; explicit warning flags/high severity bypass the model and the separate local emergency workflow is preserved. The same-provider automated answer audit is a safeguard, not independent clinical validation.


## Global emergency and conversation lifecycle

See [the architectural investigation and implementation report](global-assistant-architecture.md). Latest verification: **131 backend tests**, **7 Chrome workflows**, and the production TypeScript/Vite build pass with mocked model calls and dummy process credentials. No real API key was accessed or live Meta request made. The reference inventory is now **15 documents / 34 passages**.

Added coverage verifies immediate durable escalation plus continued generated reasoning, diverse ordinary/urgent presentations across eight categories, follow-ups while generation is pending, retained unavailable-personnel context, failures/audit rejection without loss of local guidance, restart/retry, ownership on status/retry, all new turns downlinked with delay, ground archival beyond the recent-message window, and late older completions. The browser emergency workflow exercises a deliberately delayed mock model and delivered doctor history. A simultaneous generation/polling/sync browser test and an outer-transaction rollback regression also pass. These are integration/contract tests, not medical or live-model validation.


## Medical short-answer roles and warning deduplication

Latest results: **155 backend tests**, **7 Chrome workflows**, and the production TypeScript/Vite build pass. See the [confirmed causes and architectural changes](short-answer-redesign.md). New coverage exercises two distinct short-answer roles, semantic quality repair and its one-revision limit, six unfamiliar ordinary/urgent presentations, labeled assessment advice without local evidence, educational follow-ups during an unresolved emergency, unavailable-output handling, and unchanged rejection of unsafe advice. Browser checks inspect both parts, one visible warning, expandable emergency support, continued conceptual answers, and doctor synchronization. Provider calls are mocked; no real API key or live model connection was used.


## Real Research Data Replay

**163 backend tests**, **8 Chrome browser workflows**, and the production TypeScript/Vite build pass. The PhysioNet BIDMC record-01 numeric CSV is real, downloaded from the publisher and verified against its checksum; it is not a mocked physiological fixture. Tests verify all 481 heart-rate values, original elapsed-time strings, provenance, byte-identical source download, existing ingestion/analysis, authentication, data isolation, offline replay, checksum failure, and nonduplicating rewind with no future-sample leakage. The browser tests real replay, chart/source labels, elapsed seconds, CSV download, reload persistence, rewind/play/pause, and returning to the synthetic astronaut dashboard. Existing AI tests still use mocked provider calls and dummy process credentials. See [the real-versus-simulated inventory and limitations](../research_data/README.md).
