# Real Research Data Replay

## Tonight's demo

Restart the backend (additive replay tables are created automatically). Sign in as Astronaut and select **Real Research Data Replay** in the sidebar. Use **Start research replay** for one original sample per second, **Replay next 30 samples** for a quick batch, or **Load full record**. **Restart playback** rewinds the cursor without changing or duplicating stored measurements. The original synthetic simulator remains in Health overview. No new dependency, account, API key, or runtime download is needed.

## What is real versus simulated

| Item | Provenance |
| --- | --- |
| Research HR values and elapsed seconds | Actual publicly released Earth-based clinical measurements: BIDMC record 01 |
| Source CSV's PULSE, RESP, SpO2 columns and NaN markers | Original source data, preserved in the raw download and `source_fields`; not ingested as sensor metrics in this MVP |
| Replay speed and cursor | Application playback controls; not measurement times |
| Displayed min/max/mean | Calculations on replayed HR values; explicitly labeled derived |
| Astronaut identities, personal telemetry, baselines, exams, simulator history | Still synthetic; the research subject never becomes an astronaut |
| Mission context, spacecraft environment, Earth link/delay | Existing simulation; not attached to the research record |
| AI explanations and existing experimental monitoring thresholds | Not validated by this dataset; no new clinical validation or prediction claim |

## Dataset and citations

Bundled unchanged: [`bidmc_01_Numerics.csv`](bidmc-1.0.0/bidmc_01_Numerics.csv), **7,644 bytes**, 481 rows from elapsed **0 through 480 seconds**, HR in **bpm**. The source header states a one-Hz numerical record; HR is monitor-derived from ECG. This is **not established resting heart rate**, so a separate generic `heart_rate` metric is used rather than relabeling the values as `resting_hr`.

Contains information from the [BIDMC PPG and Respiration Dataset v1.0.0](https://physionet.org/content/bidmc/1.0.0/) by Marco Pimentel, Alistair Johnson, Peter Charlton, and David Clifton, available under the [Open Data Commons Attribution License v1.0](https://physionet.org/content/bidmc/view-license/1.0.0/). The data were acquired during hospital care from critically ill patients at Beth Israel Deaconess Medical Centre, Boston. They are **Earth ICU data, not astronaut measurements**. No inference about an astronaut or healthy spaceflight physiology is warranted from this record.

- Dataset DOI: [10.13026/C2208R](https://doi.org/10.13026/C2208R).
- Source publication: Pimentel et al., *Towards a Robust Estimation of Respiratory Rate from Pulse Oximeters*, [10.1109/TBME.2016.2613124](https://doi.org/10.1109/TBME.2016.2613124).
- PhysioNet citation: Pollard et al. (2026), *PhysioNet as a global platform for biomedical research*, [10.1038/s44360-026-00096-z](https://doi.org/10.1038/s44360-026-00096-z).
- [Original CSV](https://physionet.org/files/bidmc/1.0.0/bidmc_csv/bidmc_01_Numerics.csv).
- [Local provenance manifest](bidmc-1.0.0/manifest.json), original publisher [LICENSE](bidmc-1.0.0/LICENSE), [README](bidmc-1.0.0/README), [numerical header](bidmc-1.0.0/bidmc01n.hea), and [SHA256SUMS.txt](bidmc-1.0.0/SHA256SUMS.txt) are included. All four downloaded source files were checked against the publisher's checksum list.

CSV SHA-256: `27d43794cf2e7150db10e8bfe61d2bfdb26873a8f1629ffc5fbee5c9a4eb6ef5`. Runtime verifies it before import/download. The public source file is redistributed byte-for-byte, without interpolation, normalization, imputation, or filtering. No extra waveform download was needed.

The supplied NASA challenge URL returned HTTP 502 during this investigation. OSDR/NLSP exposed portal shells to the browsing tool; no suitable small NASA physiological file was selected within the deadline. NASA HRP was checked for research context. PhysioNet offered this immediately downloadable, explicitly licensed numeric record, so the simulator-only fallback was unnecessary. No claim of NASA endorsement or challenge-resource approval is made.

## Timestamp handling

The CSV supplies **relative elapsed seconds only**. No absolute recording date or timezone is invented. The API, table, chart, and original CSV use the original elapsed-time axis. Original time/value strings and all other columns are retained in `research_samples.source_fields`; parsed numeric values preserve their source values and units.

The existing ingestion schema requires timezone-aware datetimes. Its isolated SQL measurement rows therefore encode time as **1970-01-01T00:00:00Z + original elapsed seconds**. This is a reversible internal ordering adapter, **not the actual clinical collection date**. It is documented in the manifest and expandable UI details and never presented as a measured calendar timestamp. `received_at` is the application's import time, not the source collection time.

## Existing pipeline and isolation

The adapter calls the existing `Reading` validation and `ingest()` database/audit function with `origin=imported`, a generic `heart_rate` metric, and a separate subject with `role=research`. `research_samples` retains source provenance and elapsed time; `research_replays` retains each signed-in operator's cursor. Research IDs are separate from every astronaut ID. The view labels provenance as `real_research`, not simulated or device-live.

The existing `analyze_metric()` function receives an explicit archival replay clock; the ordinary live clock and detection settings remain unchanged. Future replay samples remain excluded after a rewind. The record has no matching personal baseline and covers only eight minutes, so multi-day analysis reports **insufficient_data**, not a healthy result, anomaly clearance, or astronaut diagnosis. Descriptive statistics and the original sample trace are available; long-term anomaly detection cannot responsibly be demonstrated on eight minutes. Numerical validation does not establish sensor quality or clinical interpretation.

Research replay does not invoke the LLM, write astronaut baselines, create astronaut alerts, enqueue research data to Earth, or change smartwatch or communication behavior. It remains usable offline after installation. Integrity failure returns an explicit 503 and leaves the simulator operational. Cursor checks and transaction boundaries prevent concurrent duplicate advancement; source measurements persist through reload/restart and are reused on playback rewind.

API: `GET /api/research-replay`, `POST /api/research-replay/advance` (`expected_cursor`, `count`), `POST /api/research-replay/restart` (`expected_cursor`), and `GET /api/research-replay/source.csv`. Existing astronaut authentication is required; no API accepts arbitrary download URLs or subject IDs.

## Essential verification

Tests compare all 481 ingested values and original time/value strings with the checked-in CSV, verify its checksum and byte-identical download, inspect ingestion audit rows, check persistence/idempotency/authentication, prove astronaut/doctor snapshots and queue are unaffected, reject tampered sources atomically, and confirm offline operation. Rewind tests verify no duplicate measurements and no future-sample leakage into analysis. The browser workflow exercises the chart, source labels, original elapsed time, download, persistence, rewind/play/pause, and switching back to the synthetic dashboard.
