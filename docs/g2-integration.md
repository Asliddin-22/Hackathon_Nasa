# G2 integration into the current GravityGuard application

Branch: `feature/g2-watch`. The pre-integration application, including previously uncommitted assistant/research improvements, was preserved in checkpoint `68aa603`. `main` remains at `25bab49`; nothing was pushed or merged into it.

## Comparison and merge decisions

The supplied `GravityGuard-with-G2 (1).zip` contains a virtual watch and additional sensor infrastructure, alongside older versions of the medical assistant. Those older files would remove schema-v3 explanation/recommendation parts, bounded quality revision, educational follow-ups during an incident, and the current warning presentation. The ZIP also lacks the real research replay. It was therefore not unpacked over the application.

Archive documentation was treated as reference material, not as permission to replace the project or deploy it. Environment/private/runtime files were excluded from extraction. Deployment files (`Dockerfile`, Render configuration) and unrelated older assistant/doc changes were not adopted. Dependencies and the Meta transport were not changed.

## Exact implementation changes

| Area | Files and behavior |
| --- | --- |
| Watch UI | Reused `frontend/src/pages/G2Watch.tsx` and the watch-specific CSS. Face, heart rate, activity/sleep rings, freshness, alerts/notifications, symptom reporting, assistant navigation, and link status remain labeled simulated. |
| App integration | Merged watch navigation, scenario state, and shared feed controls into `frontend/src/App.tsx`, retaining research navigation and the current doctor/assistant components. The shared feed uses the selected scenario rather than resetting to the legacy trend on every tick. Added sidebar scrolling so seven navigation items do not make sign-out unreachable on short screens. |
| Dashboard/history | Reused G2 metric selectors and the origin-separated `TrendChart`. History shows source, device, provenance, and exported device IDs. Step charts use a daily maximum (cumulative daily total), not an average. |
| Types | Extended existing `api.ts` types with device IDs, simulator state, watch metric units/labels, watch alert names, and sensor-evidence rows. Kept schema-v3 short-answer parts and research types. |
| Scenarios | Reused `simulator/scenarios.py`: normal, elevated resting HR, reduced sleep, activity/recovery, reported symptom, concerning trend. Updated `/api/simulator` with persisted per-astronaut scenario/step state; legacy `nominal` and `trend` names remain aliases. |
| Ingestion | Merged `ingestion.py` with optional authenticated user binding, nullable device ID, SpO2/sleep/steps metrics, and `ingest_batch_and_monitor()`. Preserved the current generic heart-rate bounds used by research replay. `/api/measurements` now validates ownership, monitors new readings, and queues a delayed snapshot. Unverified browser requests cannot claim `origin=device`. |
| Monitoring | Reused `watch_rules.py`: repeated elevated resting HR and low SpO2 produce experimental **review** alerts, never diagnoses. Added freshness checks and separate episodes per origin so stale/manual data cannot be mistaken for current simulated evidence. Existing longitudinal rules remain unchanged. |
| Symptoms | Reused `services/symptoms.py` and merged the symptom endpoint to share existing severity/explicit-warning handling with the watch and reported-symptom scenario. |
| Database | Added nullable `health_measurements.device_id`, a new `simulator_state` table, and an idempotent SQLite additive migration. No DROP, replacement database, or history deletion is used. G2 seed provisioning only adds missing simulated watch history/baselines. |
| Doctor UI | Watch alerts use the existing evidence panel with delivered measurement values, units, collection times, source/device, and provenance. The current final-answer renderer and conversation archive are retained. |
| Future adapters | Reused `device_adapters.py` normalization contracts and their tests. They remain disabled; there is no native watch app or verified physical-device ingestion channel. |
| Tests | Added the ZIP's 18 watch tests and merge regressions for current-schema AI → delayed doctor delivery, provenance isolation, stale-reading rejection, and preservation of legacy rows during migration. Updated two legacy measurement-count checks for the added sensors; retained all assistant/research regressions. Added the ZIP's G2 browser flow and a new G2 → current assistant → delayed final-answer doctor workflow. |

## What was preserved

Compared with checkpoint `68aa603`, these core paths remain unchanged: `conversation.py`, `conversation_schema.py`, `emergency_support.py`, `assistant_jobs.py`, `api/assistant.py`, `earth_sync.py`, the complete medical knowledge corpus, and real research data/adapter. Thus the watch integration uses the current selective record reader, free generated explanations, two-part short answer, independent safety overlay, persisted conversations, background generation/retry, and complete final-answer downlinks.

No existing working database was copied over or reset by the integration/test commands. Tests use temporary/in-memory databases, dummy model credentials, audit-only synchronization keys, and blocked external model transport. On the next normal backend restart the additive migration runs and missing synthetic watch fixtures may be provisioned. Existing rows and conversations are retained. The migration is tested on a legacy-schema fixture, not applied manually to the user's database.

## Verification

Final results are recorded in `docs/verification.md`. The G2 browser tests exercise simulated source labels, scenario changes, review alerts, symptom reporting, watch/dashboard/history views, mobile layout, doctor evidence, selective AI retrieval of actual stored G2 values, and full final-response equality after offline reconnection and a configured nonzero delay. They do not validate live Muse Wonder medical reasoning.

## Run and limits

Restart the backend and open **G2 Watch** in the astronaut workspace. Choose a scenario and use **Send one reading** or **Start watch feed**. For a quick review-alert demonstration, choose the concerning trend and send about seven readings. Set the Earth delay before generating records; old queued events keep their original due times. Ask about watch data through the existing Medical assistant page, then restore/process the Earth link and inspect delivered doctor findings/conversations.

All G2 values, scenario symptoms, and the watch interface are simulated. Physical G2/Apple Watch/Wear OS connectivity is not implemented by the supplied ZIP. The existing PhysioNet mode remains real Earth clinical replay, isolated from synthetic astronaut data. Watch thresholds are team-authored demonstration rules, not clinically validated NASA limits or treatment recommendations. No real Meta key was accessed and no live Meta call was made.
