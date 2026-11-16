# Five-layer AI medical assistant prototype

This report describes the earlier bounded milestone. The catalog-based conversational path has been superseded by the [model-generated conversational redesign](conversational-redesign.md).

The bounded end-to-end prototype is implemented. It reuses the existing FastAPI service, SQLite database, authentication, trend engine, doctor review, encrypted simulated synchronization, and React workspaces. No private model credential was inspected or used during development. All provider tests used mocks; the user retains live-provider verification in their own Terminal.

## Phases and verification

| Layer | Implementation | Verification before proceeding |
| --- | --- | --- |
| 1 — Fundamentals | Reviewed source snapshots, permission metadata, checksums, idempotent SQLite/FTS5 ingestion, source-cited API/CLI retrieval | 64 backend tests passed; heartbeat retrieval returned actual NHLBI conduction-system text |
| 2 — Space medicine | Four NASA source documents; general physiology and spaceflight categories remain distinct | Five source/retrieval tests passed after adding NASA sources |
| 3 — RAG + Muse Wonder | Small diverse evidence packet, structured Responses API planning, local ID validation, fallback | Full 68-test backend suite passed, including mocked provider success/failure and invented-citation rejection |
| 4 — Patient intelligence | Current records, origin-matched baselines, fresh deterministic findings, prior symptoms, mission context, local warning signs, persisted questions and doctor-review alerts | Full 74-test suite passed, including urgent behavior when the knowledge index is missing |
| 5 — Connected UI | Short answer by default; expandable evidence, reasoning, possibilities, questions, uncertainty, recommendations, citations; doctor sees delivered answers | Production build and four real Chrome workflows passed; final backend suite includes subsequent citation/coverage regressions |

The final corpus contains **13 source documents / 30 selected passages**: nine NIH/NLM fundamentals documents covering the six systems plus dizziness/dehydration, and four NASA documents. These are reviewed excerpts, not full textbooks or complete web pages. See the [source inventory and permissions](../medical_knowledge/README.md).

## Use it

```sh
.venv/bin/python scripts/dev.py
```

Open http://127.0.0.1:5173, enter the astronaut workspace, and select **Medical assistant**. Ask:

> I feel dizzy after exercise. How could microgravity affect my heart rate?

The short answer uses the same structured response as **Detailed analysis**. The latter shows exact stored measurements, provenance, personal baselines, descriptive trends, missing BP measurements, source passages, conditional explanations, targeted questions, and local review/escalation steps. Reloading preserves the conversation. Questions create review alerts and are included in the existing encrypted simulated downlink; doctors can inspect the delivered response and send their own feedback.

The app works without remote AI. To use Muse Wonder, start the backend from the private Terminal session where `MODEL_API_KEY` is already exported and set `ENABLE_LLM=true`. No key file or React variable is needed. The answer label distinguishes **Muse Wonder · grounded**, **Offline · reference evidence**, and immediate local escalation. A transport/schema failure retains local output; the application timeout remains bounded.

## Retrieval demonstration

```sh
.venv/bin/python scripts/knowledge.py 'What controls the rate and rhythm of the heartbeat?'
```

This ingests the checked-in, reviewed snapshots into the configured local database and returns passages and source metadata. No network, embeddings API, or model key is used.

Observed top result: `nhlbi-heart-beats:1`, **Electrical activity**, from [NHLBI: How the Heart Beats](https://www.nhlbi.nih.gov/health/heart/heart-beats), with the cardiac-conduction-system explanation, source date, review date, version, attribution, and SHA-256. The next result is NHLBI's **The Heart — Electrical system**. Tests also retrieve renal/nephron text, retina/optic-nerve text, and NASA SANS material. Unsupported questions return `no_coverage`; the small corpus intentionally cannot answer a general fever question.

API routes:

- `POST /api/knowledge/search` — authenticated reference retrieval.
- `POST /api/knowledge/answer` — authenticated reference-only grounded planning.
- `POST /api/assistant/messages` — astronaut-owned patient-context answer; accepts question, optional severity/warning signs, origin, and an idempotency UUID.
- `GET /api/assistant/messages` — the signed-in astronaut's last 20 persisted answers.

## Safety and model boundaries

Safety is local and runs before provider planning. Explicit warning signs, high self-rated severity, or recognized warning-sign phrases produce onboard escalation and an urgent alert without a model request. Knowledge-index failure does not block local urgent output. These conservative checks are not a comprehensive or validated triage instrument; a negative match is not clearance.

The model receives a short retrieved evidence packet, pseudonymous measurement context, descriptive trends, the question, and a catalog of supported explanations/questions. Database user IDs, reading IDs, and device/source identifiers are removed from the model context. User-entered questions/symptoms can themselves contain identifying text, so this is not a claim of automatic anonymization. Runtime transmission is opt-in; all demo records remain synthetic.

Muse Wonder can prioritize only retrieved passage IDs, supported explanation IDs, and follow-up question IDs. It cannot manufacture patient measurements, source links, diagnoses, medication, dosages, or new actions. The backend validates the selected IDs and renders locally authored conditional reasoning, real source passages, and the separate action allowlist. A citation is attached to an explanation only when a supporting retrieved passage is present. No source text is promoted to a mission-approved clinical procedure.

The short answer has 2–4 sentences. Its detailed counterpart uses the same response object, including the recorded patient evidence, conditional possibilities, citations, uncertainties, and clinician-review workflow. Ranking is a discussion priority, not a validated probability or clinical differential.

## Files added or changed

- `medical_knowledge/fundamentals/*.json`, `space_medicine/*.json`, and `medical_knowledge/README.md`: curated text snapshots, rights records, and inventory.
- `backend/app/models/knowledge.py`: source/chunk tables and persisted assistant messages.
- `backend/app/services/knowledge.py`, `rag.py`, `medical_assistant.py`, `assistant_safety.py`: ingestion, retrieval, planning, patient context, rendering, and separate local escalation.
- `backend/app/services/meta_model.py`: shared existing TLS/auth transport and Responses parsing, extended with structured grounded-plan requests.
- `backend/app/api/knowledge.py`, `assistant.py`, and `main.py`: API routes and offline corpus indexing on startup.
- `scripts/knowledge.py`: reproducible offline indexing and retrieval demonstration.
- `backend/tests/test_knowledge.py`, `test_rag.py`, `test_medical_assistant.py`: source integrity, retrieval, model-boundary, patient-specificity, persistence, and safety tests.
- `frontend/src/components/AssistantConversation.tsx`, `AssistantAnswer.tsx`, services/types, pages, `App.tsx`, and styles: connected conversation and shared answer rendering in both workspaces.
- `frontend/e2e/workflow.spec.ts`, `playwright.config.ts`: real workflow coverage with model access disabled and dummy credentials.
- README and architecture/verification/plan documentation: setup, behavior, scope, and observed results.

## Remaining limits

This is a tested integration prototype, not a clinically validated medical assistant. Coverage is small, lexical retrieval can miss paraphrases, and supported explanation catalogs are strongest for dizziness, exertion, and gravity-related fluid changes. General illness coverage, broader differential reasoning, calibrated probabilities, embedding/hybrid retrieval, source refresh/retraction administration, clinical review of recommendations, and comprehensive triage remain unfinished. NCBI Bookshelf content was not bulk-downloaded; individual licenses and approved retrieval channels must be reviewed before expansion. MedlinePlus A.D.A.M., drug monographs, third-party media, and logos were excluded.

No physical sensor or predictive model was added. Bone/kidney/SANS diagnoses remain outside the implemented capability. Ground communication remains the existing local simulation. The new grounded-plan API request is tested with mocked Meta responses; a live call of that new request format remains for the operator to verify.
