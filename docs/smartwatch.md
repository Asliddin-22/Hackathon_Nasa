# G2 virtual smartwatch

G2 is GravityGuard's simulated wrist device. It runs in the browser (desktop and mobile) as a watch-style screen, and it feeds the same onboard pipeline as every other data source. **No physical watch is connected, and real smartwatch integration is not complete.** Every simulated reading is labeled `simulated`.

```text
G2 simulator (scenario engine) ─┐
Manual entry (history page)  ───┼─> Reading contract ─> ingest_batch_and_monitor ─> SQLite
Future HealthKit / Wear OS  ────┘   (validation, bounds,       │
  (adapter contracts only)           dedup, provenance)        ├─> longitudinal baseline rules (per origin)
                                                                ├─> short-window watch rules (all origins)
                                                                ├─> alerts ─> dashboard, G2 notifications
                                                                ├─> Muse Wonder record retrieval
                                                                └─> encrypted Earth queue ─> doctor after delay
```

## Demonstration flow (about 3 minutes)

1. Start the app (`.venv/bin/python scripts/dev.py`), open http://127.0.0.1:5173, and sign in as **Astronaut**.
2. Open **Mission & Earth link**. Set the delay to `20` (or `0` for a fast demo) and save.
3. Open **G2 Watch**. Point out the **SIMULATED DEVICE** badge, the yellow `SIMULATED` tag on the face, and the scenario pill in the top bar.
4. Scenario **Normal monitoring** → **Start watch feed**. Heart rate, SpO2, and steps update every 8 seconds. Open **Sensor freshness**: green dots mean a reading within 60 seconds. Pause the feed and the dots turn amber, then orange, honestly.
5. Switch to **Activity and recovery changes**. On the Heart rate screen, HR climbs during a bout and then decays back, and steps rise faster.
6. Switch to **Medically concerning trend requiring review** and press **Send one reading** about 6 or 7 times (or let the feed run for about a minute). Resting HR ramps past 100 bpm and SpO2 drifts below 92%. The watch shows a **G2 alert notification**. Tap **View**: the alert reads "cause not established, review recommended" and lists the workflow steps. Nothing is diagnosed.
7. Press the **side button** (or Report symptom), choose **Dizziness**, and **Send report**. Severity 8 or higher, or "Severe or worsening", shows the onboard escalation message immediately without waiting for Earth.
8. Open **Health overview**: the metric cards and chart (choose "Heart rate (G2 watch)") show the new readings. Open **Health history**, choose **Blood oxygen (SpO2)**, and point to the source, device ID, and provenance columns.
9. Open **Medical assistant** and ask, for example, "Why is my blood oxygen lower today?" When the live model is enabled, Muse Wonder can retrieve the new heart-rate, SpO2, sleep, and steps history. Monitoring and alerts never depend on it.
10. **Mission & Earth link** → **Simulate offline**. Alerts keep working on the watch while the queue grows. **Restore Earth link** → **Process due messages** (wait out the delay).
11. Sign out and enter as **Flight surgeon**. The watch alert and readings appear only after delivery.

## Scenarios

| Scenario | What changes (from personal synthetic baseline) |
|---|---|
| Normal monitoring | Small smooth variation around baseline |
| Increased resting heart-rate trend | Resting HR rises to about +22% over ~5 readings; HRV dips |
| Reduced sleep / fatigue context | Logs a 4.5 h night once; resting HR +7%, HRV −18%, fewer steps |
| Activity and recovery changes | 20-reading cycle: exercise bout (HR up to about baseline+75), then exponential recovery |
| A reported symptom | Files one simulated symptom report (severity 4) into medical history; mild vital changes |
| Medically concerning trend requiring review | Resting HR to about +62% (over 100 bpm), SpO2 to about 91%, HRV −40%; triggers both watch rules |

Values ramp in and use deterministic smooth variation (no random jumps). Steps are a monotonic daily running total. Timestamps are UTC simulator generation times, not collection times from a physical sensor. Scenario state is stored per astronaut (`simulator_state`), so switching browsers or reloading continues the same scenario.

## Ingestion contract

`POST /api/measurements` and the simulator both go through `ingest_batch_and_monitor`:

- **Astronaut ID** comes from the authenticated session. A supplied `user_id` must match, or the request returns 403.
- **Metric, unit, value**: unit must match the registered metric, values must be finite and within engineering bounds. New metrics: `heart_rate` (bpm), `spo2` (%), `sleep_hours` (h), `steps` (count).
- **Timestamp**: timezone required; at most five minutes of clock skew into the future are accepted.
- **Device/source**: `source` plus the new `device_id` column (added to old databases automatically at startup).
- **Provenance**: `simulated`, `manual`, `imported`, or `device`. The browser API rejects `device` (403), because only a future verified device channel may claim it.
- **Unique reading ID**: identical retries are idempotent, and a conflicting reuse returns 409.
- After storing: watch rules run for every origin, longitudinal rules run for origins with matching baselines (manual data is never compared with synthetic baselines), and a snapshot is queued for Earth.

Simulator endpoints: `GET /api/simulator/state`, `POST /api/simulator/scenario`, `POST /api/simulator/tick` (the old `nominal`/`trend` names still work as aliases).

## Watch monitoring rules (team demo settings, not clinical thresholds)

- `watch_resting_hr`: 3 consecutive resting HR readings ≥ 100 bpm within 30 minutes.
- `watch_spo2`: 2 consecutive SpO2 readings < 92% within 15 minutes.

Both create a `review` alert (never `urgent`) with the evidence readings, the rule, and the statement "cause not established". Each rule keeps one active alert per provenance origin and updates it with fresh evidence. Stale readings outside the rule window cannot trigger a new notification.

## Status

**Implemented and tested**
- G2 watch page: face, heart rate with trend, activity/sleep rings, sensor freshness, alerts with notifications, symptom reporting, assistant access, local/Earth link status; works on desktop and mobile; all data labeled simulated.
- Common ingestion with auth-derived identity, device ID, provenance, bounds, deduplication, and monitoring on every new reading including manual entries.
- Six coherent scenarios using the existing simulator package and per-astronaut baselines.
- Watch readings in the dashboard, history charts (simulated and manual series plotted separately), CSV export with device ID, alerts, medical history, encrypted Earth queue, and doctor view after delay.
- Additive SQLite migration for existing demo databases.
- Tests: 185 backend, 10 Chrome browser workflows (including the G2 UI flow and watch → AI → delayed doctor-delivery flow), production build.

**Simulated**
- All watch readings, the watch device itself, the scenario symptom report, and the Earth link.

**Verified by tests, not by a live model**
- Watch-metric retrieval is tested through record collection and the full mocked current-schema AI response, including complete doctor synchronization. Live Muse Wonder reasoning quality is not verified. No live Muse Wonder call was made, and `MODEL_API_KEY` was not accessed.

**Planned (not implemented)**
- Native watchOS / Wear OS apps and a verified device channel. `services/device_adapters.py` holds tested normalization contracts for HealthKit (heart rate, resting HR, HRV, SpO2, steps) and Wear OS Health Services (heart rate, daily steps), with `DEVICE_INGESTION_ENABLED = False` and no endpoint.
- Sleep aggregation from platform sleep sessions, Wear OS SpO2 via Health Connect, background push instead of 8-second polling, and clinically validated alert thresholds.

The existing real research replay remains isolated and intentionally uses its own import adapter, without creating astronaut watch alerts or changing astronaut baselines. The G2 integration does not replace the current medical assistant schema, emergency behavior, knowledge corpus, or delayed conversation archive.
