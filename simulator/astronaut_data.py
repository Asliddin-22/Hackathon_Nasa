"""Reproducible synthetic fixtures. No measurements represent real crew."""
import math
from datetime import datetime, timedelta, timezone

CREW = [('astro-01', 'Alex Morgan', 'Commander'), ('astro-02', 'Samira Chen', 'Flight engineer'), ('astro-03', 'Leo Reyes', 'Mission specialist')]
BASELINES = {'resting_hr': (65, 'bpm'), 'hrv': (52, 'ms'), 'strength': (42, 'kg'), 'balance_sway': (2.0, 'deg'), 'exercise_minutes': (120, 'min'), 'hydration': (2400, 'mL')}

def history(user_id, crew_index=0, anchor=None):
    anchor = anchor or datetime.now(timezone.utc).replace(microsecond=0)
    for day in range(30):
        drift = max(0, day - 19) if crew_index == 0 else 0
        values = {'resting_hr': 65 + crew_index * 2 + math.sin(day) * 1.4 + drift * 1.6,
                  'hrv': 52 - drift * 1.1 + math.sin(day) * 2,
                  'strength': 42 - drift * .52 + math.sin(day) * .2,
                  'balance_sway': 2 + drift * .07 + math.sin(day) * .05,
                  'exercise_minutes': 120 - drift * 2,
                  'hydration': 2400 + math.sin(day) * 120}
        for metric, value in values.items():
            yield {'id': f'seed-{user_id}-{day}-{metric}', 'user_id': user_id, 'metric': metric,
                   'value': round(value, 2), 'unit': BASELINES[metric][1],
                   'timestamp': (anchor - timedelta(days=29 - day)).isoformat(),
                   'source': 'Synthetic mission generator', 'origin': 'simulated', 'quality': 'valid'}
