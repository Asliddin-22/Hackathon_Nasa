"""Future real-device adapter layer (Apple HealthKit, Wear OS Health Services).

STATUS: normalization contracts only. No native watchOS/Wear OS app exists, no
endpoint accepts device payloads, and DEVICE_INGESTION_ENABLED is False. Real
smartwatch integration is NOT complete.

A future companion app would read platform samples, send them over an
authenticated, device-attested channel, and this module would map them onto the
same ``Reading`` contract the simulator and manual entry already use. Only a
verified device channel may produce origin='device'.
"""
from dataclasses import dataclass
from datetime import datetime
from .ingestion import Reading, METRICS

DEVICE_INGESTION_ENABLED = False


class DeviceAdapterError(ValueError):
    pass


@dataclass
class DeviceSample:
    platform: str  # 'healthkit' | 'wear_os'
    type: str      # platform data-type identifier
    value: float
    unit: str      # unit as reported by the platform
    start: datetime
    sample_id: str  # platform sample UUID; used for deduplication
    device_id: str


# platform type -> (metric, accepted platform units, conversion factor)
HEALTHKIT = {
    'HKQuantityTypeIdentifierHeartRate': ('heart_rate', {'count/min', 'bpm'}, 1),
    'HKQuantityTypeIdentifierRestingHeartRate': ('resting_hr', {'count/min', 'bpm'}, 1),
    'HKQuantityTypeIdentifierHeartRateVariabilitySDNN': ('hrv', {'ms'}, 1),
    'HKQuantityTypeIdentifierOxygenSaturation': ('spo2', {'%'}, 100),  # HealthKit reports a 0-1 fraction
    'HKQuantityTypeIdentifierStepCount': ('steps', {'count'}, 1),
}
WEAR_OS = {
    'HEART_RATE_BPM': ('heart_rate', {'bpm'}, 1),
    'STEPS_DAILY': ('steps', {'count', 'steps'}, 1),
}
PLATFORMS = {'healthkit': HEALTHKIT, 'wear_os': WEAR_OS}
# Planned but not mapped: sleep (HealthKit category samples / Health Connect
# sessions need nightly aggregation) and SpO2 on Wear OS (Health Connect).


def normalize(sample: DeviceSample, user_id: str, verified: bool) -> Reading:
    """Map one platform sample onto the common ingestion contract."""
    if not verified:
        raise DeviceAdapterError('Device provenance requires a verified, attested device channel')
    mapping = PLATFORMS.get(sample.platform, {}).get(sample.type)
    if not mapping:
        raise DeviceAdapterError(f'Unsupported {sample.platform} data type: {sample.type}')
    metric, units, factor = mapping
    if sample.unit not in units:
        raise DeviceAdapterError(f'Unexpected unit {sample.unit} for {sample.type}')
    value = round(sample.value * factor, 2)
    return Reading(id=f'{sample.platform}:{sample.device_id}:{sample.sample_id}'[:100], user_id=user_id, metric=metric,
                   value=value, unit=METRICS[metric][0], timestamp=sample.start, source=f'{sample.platform} adapter',
                   device_id=sample.device_id, origin='device')
