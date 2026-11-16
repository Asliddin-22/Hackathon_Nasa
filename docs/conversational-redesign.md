# Conversational Medical Assistant redesign

The primary conversational path is now model-generated. This supersedes the bounded catalog-based assistant described in the earlier five-layer milestone report. The original monitoring, ingestion, authentication, encrypted synchronization, review/acknowledgment loop, reference corpus, and dashboards remain in place.

## Confirmed cause, before changes

Inspection found five restrictions in the actual implementation:

1. `meta_model.request_grounded_plan()` submitted a schema containing only arrays of predefined IDs and told the model to return catalog IDs. It could not return an explanation, regardless of credits or model capability.
2. `rag.retrieve_evidence()` called the model only when `references` was nonempty. The local corpus determined whether a question was answerable.
3. `medical_assistant.answer()` always read patient measurements, baselines, recent symptoms, and mission context, and ran every risk module before considering what the question meant.
4. `candidates()` built a small fixed explanation catalog based on question terms. The short answer was then assembled locally from catalog text and unconditional monitoring/referral/warning sentences. Useful model prose was impossible by design.
5. Stored messages were displayed as history but not sent back as conversation context. Every turn created a medical-review alert and downlink, including educational turns.

The user's architecture concern was therefore confirmed by the code, not assumed. Provider configuration can separately cause offline fallback, but credentials were not inspected as part of this investigation.

## Implemented flow

**Persist turn/job and independent safety overlay → return immediately to the chat → model context plan → selective local data/references → generated structured explanation → structural/provenance checks → automated evidence/policy audit → update the saved short/detailed response and queue downlink.**

See [the global emergency/conversation investigation](global-assistant-architecture.md) for the latest lifecycle, recovery, synchronization, and verification changes.

`conversation.py` is the orchestrator and `conversation_schema.py` defines contracts. The compatibility entry point `medical_assistant.answer` delegates to the new orchestrator. There is no diagnosis catalog, question keyword classifier, per-question answer, or fixed medical explanation in this path.

1. **Intent and scope.** Muse Wonder classifies general education, space education, personal assessment, or clarification using the question and at most eight selected ancestor turns. It requests only relevant metrics, history, symptoms, tests, and mission context. The server clears clinical-data requests on educational intents. Context planning sees a metric schema, not the patient's values.
2. **Records and retrieval.** Server-authored queries enforce signed-in user and data-origin boundaries. Only planned metrics are read; descriptive historical statistics are computed only when requested. Missing/stale data remain explicit facts. Model-generated SQL is never executed. Relevant local NIH/NASA passages may be retrieved from up to three model-planned searches, but empty coverage does not block generation.
3. **Generation.** Muse Wonder writes free-form explanation blocks, possible explanations, targeted questions, uncertainty, and appropriate next steps. There is no hardcoded list of diseases or common causes. The model is instructed to consider common/simple possibilities alongside other supported explanations, and to avoid unsupported definitive diagnoses, unapproved treatments, invented measurements, and personalized forecasts.
4. **Evidence distinction.** Blocks are labeled `retrieved_evidence`, `general_model_knowledge`, or `clinical_inference`. Citation IDs resolve only to actually retrieved passages. Patient-fact IDs resolve only to the server's read-only facts. Ordinary uncited model knowledge is allowed and visibly labeled as not independently source-verified. Raw model-generated citation URLs are not turned into verified links.
5. **Consistency and validation.** A generated answer contains blocks plus IDs selecting the short answer. The backend composes the short answer directly from those same blocks, which also appear in detail. It validates structure, summary IDs, citation IDs, fact IDs, and evidence-label consistency. A separate Muse Wonder audit checks substantive unsupported facts, source support, diagnoses/treatments, scope, and consistency. Different useful wording is accepted verbatim. Failed validation produces an honest availability status; it does not pretend a fixed medical template is a generated answer.
6. **Conversation and review.** Additive `assistant_threads` and `assistant_turns` tables bind messages to owned conversations and explicit parent chains. Unrelated chats and other patients' turns are not included. Retried request IDs remain idempotent. Only urgent turns or generated personal assessments requiring review create clinical alerts. Every new turn and completed response is saved locally and queued for delayed Earth delivery, including education. The ground conversation archive is separate from the bounded recent-message snapshot. Existing unthreaded messages remain viewable and start a new conversation if selected. Legacy symptom logging and the full monitoring panel remain available in a collapsed tools section rather than appearing as an unsolicited assessment beneath educational answers.

Network calls occur without a pending write transaction, so conversation generation does not hold a SQLite writer lock and block telemetry ingestion. The existing TLS/certifi transport, backend-only key resolution, redirect blocking, response limits, and failure handling are reused. No real key was accessed and no live model call was made during development.

## Safety boundary and remaining hardcoded behavior

Explicit warning-sign reports and high self-rated severity escalate before **any** model call. The existing local phrase-based safety checks are retained unchanged for personal or ambiguous reports, and remain conservative if planning is unavailable. Unresolved urgent alerts take precedence on personal turns. A model can promote personal urgency but cannot cancel explicit reported danger or local escalation already triggered for a personal/ambiguous turn. Educational generation cannot create a patient-urgency declaration.

Distinguishing an abstract educational mention of a warning sign from an actual report of it is **model-dependent language understanding**. An educational plan can treat such mentions as education; this is not a deterministic clinical triage guarantee. Explicit warning controls and the separate symptom-reporting/emergency workflow remain model-independent. Intent errors, missed symptoms, and false positives remain possible; a negative check is never medical clearance.

Hardcoded logic that remains: access/provenance checks, schemas/size limits, evidence IDs, source allowlists, the existing statistical detection settings, existing safety phrases and escalation workflow actions, and operational unavailable/error messages. The local FTS retriever retains its existing token normalization/aliases; those do not choose conversational intent or a disease. The legacy trend-explanation selector and `/api/knowledge/answer` reference-planning endpoint remain for compatibility and are not the primary conversational generator.

The response audit is automated, probabilistic, and uses the same provider family. It cannot prove clinical correctness or independently establish the truth of uncited general knowledge. Verified citation IDs prove source identity; semantic source support is assessed by the audit rather than a formal proof. Professional clinical validation remains unfinished.

## Verified behavior and tests

The backend suite covers:

- Previously unseen education across endocrine, auditory, skin, pharmacology, and cardiovascular topics, including the reported blood-pressure question.
- Ordinary generation with no local references; no patient-data reads, emergency boilerplate, or clinical alert for educational turns.
- Source-backed generated prose with verified local citation IDs and explicit unverified background labels.
- Personal symptom/recovery questions with only the requested metric, descriptive history, free-form hypotheses outside the old catalog, and generated follow-ups.
- Spaceflight education using NASA passages without injecting the personal profile.
- Actual multi-turn context, fresh-chat isolation, other-user/thread/parent rejection, persistence, and idempotency.
- Explicit emergencies publishing local guidance before model calls and continuing generated reasoning; current warning-sign escalation; model-promoted urgency; educational mentions and existing alerts scoped separately.
- Unknown citations/facts, inconsistent summary IDs, unsupported measurements, unapproved treatments, definitive diagnoses, invented references, audit failures, and provider failures.
- An adversarial request cannot broaden educational data access or retrieve another astronaut's profile. No model has tools to inspect credentials.
- The actual mocked Responses wire protocol exercises planning, generation, parsing, and audit through the existing HTTPS transport abstraction.

Browser coverage retains the original monitoring/sync/review/export/mobile tests and adds honest offline conversation behavior plus generated education, follow-up, selective personal evidence, and doctor delivery. The generated-path browser backend is an isolated test-only Python runner whose model responses are mocked and whose remote transport is blocked; it is not a production bypass or an actual Meta call. Assertions check scope, identity, provenance, consistency, and behavior rather than exact preferred medical wording.

Latest verification is recorded in [the global architecture report](global-assistant-architecture.md). Mocks verify integration behavior, not live model reasoning quality or medical accuracy. Actual provider behavior, latency, audit false positives/negatives, and broader clinical evaluation remain to be tested by the operator.

## Try it

Restart the local backend to create the additive conversation, job, and ground-archive tables. In the private Terminal session where `MODEL_API_KEY` is already exported, set `ENABLE_LLM=true` and start `scripts/dev.py`. No key file or frontend key is needed. Ask an unfamiliar educational question, then a follow-up; use **New conversation** to start a separate topic. A personal question should show only relevant available records. General-knowledge and source-backed paragraphs have separate evidence labels.

When the provider is disabled, unavailable, or fails validation, the assistant explicitly reports that conversational generation is unavailable. It does not emulate Muse Wonder with fixed explanations. The existing health dashboard, symptom workflow, statistical monitoring, alerts, and reference-search API/CLI remain available offline.
