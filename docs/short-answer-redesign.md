# Medical short answers without repeated warning boilerplate

## Confirmed causes

Inspection found several shared restrictions, independent of the question's symptoms:

- The model selected an undifferentiated array of summary block IDs. A generic referral could satisfy that structure without providing a possible explanation or a useful next assessment step.
- `emergency_support.attach()` replaced pending/unavailable short answers with concatenated local escalation and guidance text. Provider or validation failure therefore looked like a medical answer consisting entirely of warnings.
- The UI rendered overlapping escalation actions, basic guidance, a separate no-delay sentence, delay/personnel warnings, and the general warning again in detailed next steps.
- An active incident forced educational follow-ups into patient-assessment mode and replaced the question's intent with `urgent`.
- Every emergency recommendation required a retrieved citation, including ordinary non-procedural assessment advice. Missing one rejected the entire generated explanation, producing the warning-only fallback.
- Full warning prose was included in generation context, and saved operational/fallback answers were fed into conversation memory as earlier medical answers.

These are confirmed code paths. No private session records or real provider credentials were inspected to identify which path a particular previous live response took.

## General changes

The model now returns a `short_answer` object with `explanation_id` and `recommendation_id`, referring to its own free-form explanation blocks. Personal assessments require both IDs and distinct blocks. Educational questions require the conceptual answer and can omit a next action when none is relevant. The API derives `short_answer_parts` and the compatible plain `short_answer` from those same blocks; detailed reasoning cannot silently substitute a different summary.

The doctor finding view also delegates safety rendering to the answer card instead of appending a second escalation-action list.

The UI labels personal parts **Possible problem** and **Recommendation**, with provenance still visible. These are presentation roles, not medical response templates. The model chooses the conditions/mechanisms, uncertainty, reasoning, and practical next step; there is no new question keyword rule or disease catalog. When information is genuinely insufficient, the explanation should identify the specific missing information rather than invent a diagnosis.

Structural checks require the applicable parts. The semantic audit separately checks whether they actually answer the question and whether generic escalation replaces or repeats the medical substance. Missing explanation/recommendation or repetitive output receives **one bounded model revision**, using unchanged patient facts and references. Substantive audit failures (unsupported facts, fabricated sources, definitive diagnoses, unapproved treatment) still reject the candidate. Revision does not authorize weaker evidence checks or unbounded retries.

Independent safety remains intact. One prominent notice appears alongside the answer; reference-based support, communication information, and procedure availability are expandable in **Emergency support details**. The warning is never concatenated into a pending/failed short answer. Failures stay explicitly unavailable rather than pretending to explain symptoms. Real emergency support remains visible even when generation fails.

Question intent and active incident urgency are separate. Educational follow-ups may receive a direct conceptual explanation while the unresolved warning persists. Only relevant patient data are requested; education does not load the clinical profile. The planner/generator receive compact incident facts instead of repeated local warning prose. Failed/pending turns retain user questions and safety state in memory but do not supply their operational status text as previous medical reasoning.

Cited claims still require real supplied IDs, and source support remains subject to audit. Uncited, properly labeled non-procedural assessment, clarification, or care-seeking advice is allowed. Specific emergency clinical interventions still require authorized procedures and supporting references; medication/dosing, invasive procedures, invented measurements, unsupported definitive diagnoses, and unapproved treatment changes remain prohibited. No mission-approved treatment protocol has been installed or invented.

## Verification and limits

Regression tests cover six unfamiliar presentations with both ordinary and urgent flags, separate short-answer roles, exact reuse of generated blocks in detail, no-RAG assessment advice, semantic quality revisions, missing/overlapping role IDs, bounded failure, retained local safety, educational follow-ups during an unresolved emergency, changing personal context, and rejecting unsafe advice. Examples and mock medical prose exist only in tests. Chrome checks verify both visible parts, one copy of the safety notice, expandable support details, continued conceptual conversation, doctor delivery, and concurrent generation/sync, alongside the existing monitoring workflows.

The latest verification results are recorded in [verification.md](verification.md). All provider calls during development were mocked with dummy process credentials. These tests validate orchestration, presentation, and evidence contracts—not actual Muse Wonder medical accuracy. Semantic relevance and clinical quality still depend on the generator/audit and need operator evaluation. Existing deterministic emergency recognition is unchanged and remains finite prototype triage. Stored historical responses are preserved; they are not silently rewritten or regenerated.

Restart the backend to load the new schema/orchestration, and use the rebuilt dashboard. Ask a new turn to obtain the new two-part answer format. No database reset or credential change is required.
