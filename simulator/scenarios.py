"""Coherent synthetic G2 watch scenarios. All output is SIMULATED.

Values are derived from each astronaut's synthetic personal baseline, ramp in
gradually, and use smooth deterministic variation instead of random jumps, so a
reading always follows plausibly from the previous one. Scenarios describe data
patterns only; they never encode or imply a diagnosis.
"""
import math
from datetime import datetime, timezone

SCENARIOS = {
    'normal': {'label': 'Normal monitoring',
               'summary': 'Readings stay close to the personal baseline.'},
    'elevated_resting_hr': {'label': 'Increased resting heart-rate trend',
                            'summary': 'Resting heart rate rises gradually (about +22%) and HRV dips.'},
    'reduced_sleep': {'label': 'Reduced sleep / fatigue context',
                      'summary': 'A short night (4.5 h) is logged; resting HR edges up and HRV falls.'},
    'activity_recovery': {'label': 'Activity and recovery changes',
                          'summary': 'Repeating exercise bouts: heart rate and steps rise, then recover.'},
    'reported_symptom': {'label': 'A reported symptom',
                         'summary': 'A mild synthetic symptom report is filed once, with small vital changes.'},
    'concerning_trend': {'label': 'Medically concerning trend requiring review',
                         'summary': 'Resting HR climbs past 100 bpm and SpO2 drifts below 92%, triggering watch review rules.'},
}
LEGACY_ALIASES = {'nominal': 'normal', 'trend': 'elevated_resting_hr'}
SIMULATED_SYMPTOM = ('Simulated scenario: mild light-headedness after standing up from the exercise device.', 4)
DEVICE_ID = 'g2-virtual-watch'
SOURCE = 'G2 virtual watch simulator'
RAMP_STEPS = 5

# Wearable metrics added to the original synthetic set. value, unit
WATCH_BASELINES = {'heart_rate': (77, 'bpm'), 'spo2': (97.6, '%'), 'sleep_hours': (7.3, 'h'), 'steps': (7000, 'count')}


def _wave(step, scale):
    """Smooth, repeatable variation (no random jumps between ticks)."""
    return (math.sin(step * 0.9) * 0.6 + math.sin(step * 0.37 + 1.1) * 0.4) * scale


def sample(scenario, base, step, steps_so_far, now=None):
    """Return {metric: value} for one tick.

    base: personal synthetic baselines {metric: value}.
    step: ticks since the scenario started (0-based).
    steps_so_far: today's cumulative step count before this tick.
    """
    now = now or datetime.now(timezone.utc)
    p = min(1.0, (step + 1) / RAMP_STEPS)
    rest, hrv, spo2 = base['resting_hr'], base['hrv'], base.get('spo2', 97.6)
    resting = rest + _wave(step, 0.8)
    hr = rest + 10 + _wave(step, 3)
    variability = hrv + _wave(step, 1.5)
    oxygen = spo2 + _wave(step, 0.3)
    increment = 18 + _wave(step, 6)
    if scenario == 'elevated_resting_hr':
        resting = rest * (1 + 0.22 * p) + _wave(step, 0.8)
        hr = resting + 9 + _wave(step, 2)
        variability = hrv * (1 - 0.2 * p) + _wave(step, 1)
    elif scenario == 'reduced_sleep':
        resting = rest * (1 + 0.07 * p) + _wave(step, 0.6)
        hr = resting + 9 + _wave(step, 2)
        variability = hrv * (1 - 0.18 * p) + _wave(step, 1)
        increment = 8 + _wave(step, 3)
    elif scenario == 'activity_recovery':
        cycle = step % 20
        if cycle < 8:
            effort = min(1.0, (cycle + 1) / 3)
            increment = 150 + _wave(step, 20)
        else:
            effort = math.exp(-(cycle - 8) / 2.5)
            increment = 12 + _wave(step, 4)
        hr = rest + 10 + 65 * effort + _wave(step, 2)
        variability = hrv * (1 - 0.3 * effort) + _wave(step, 1)
    elif scenario == 'reported_symptom':
        resting = rest * (1 + 0.05 * p) + _wave(step, 0.6)
        hr = resting + 14 + _wave(step, 2)
        variability = hrv * (1 - 0.08 * p) + _wave(step, 1)
    elif scenario == 'concerning_trend':
        resting = rest * (1 + 0.62 * p) + _wave(step, 0.8)
        hr = resting + 8 + _wave(step, 2)
        variability = hrv * (1 - 0.4 * p) + _wave(step, 1)
        oxygen = spo2 - 6.6 * p + _wave(step, 0.15)
    return {'heart_rate': round(max(30, hr)), 'resting_hr': round(resting, 1), 'hrv': round(max(5, variability), 1),
            'spo2': round(min(100, oxygen), 1), 'steps': int(max(0, steps_so_far + increment))}


def sleep_hours(scenario, base_sleep, step):
    return 4.5 if scenario == 'reduced_sleep' else round(base_sleep + _wave(step, 0.3), 2)


def day_start_steps(base_steps, now=None):
    """Plausible cumulative steps when no reading exists yet today (UTC day fraction)."""
    now = now or datetime.now(timezone.utc)
    fraction = (now.hour * 3600 + now.minute * 60 + now.second) / 86400
    return int(base_steps * fraction)


def watch_history(user_id, crew_index=0, anchor=None):
    """30 days of daily wearable summaries matching the original history's shape."""
    from datetime import timedelta
    anchor = anchor or datetime.now(timezone.utc).replace(microsecond=0)
    for day in range(30):
        drift = max(0, day - 19) if crew_index == 0 else 0
        rest = 65 + crew_index * 2 + math.sin(day) * 1.4 + drift * 1.6
        values = {'heart_rate': rest + 12 + math.sin(day * 1.3) * 2,
                  'spo2': 97.6 + math.sin(day * 0.8) * 0.4 - drift * 0.05,
                  'sleep_hours': 7.3 + math.sin(day * 0.6) * 0.4 - drift * 0.12,
                  'steps': 7000 + math.sin(day * 0.5) * 900 - drift * 180}
        for metric, value in values.items():
            yield {'id': f'seed-{user_id}-{day}-{metric}', 'user_id': user_id, 'metric': metric,
                   'value': int(value) if metric == 'steps' else round(value, 2), 'unit': WATCH_BASELINES[metric][1],
                   'timestamp': (anchor - timedelta(days=29 - day)).isoformat(),
                   'source': 'Synthetic mission generator', 'device_id': DEVICE_ID,
                   'origin': 'simulated', 'quality': 'valid'}
