"""Transparent longitudinal statistics. No forecasting or diagnostic inference."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from sqlalchemy import select
from ..models.records import Measurement, Baseline


def analyze_metric(db, user_id, metric, origin='simulated', *, as_of=None):
    # Replay may supply an explicit archival clock; live monitoring is unchanged.
    clock = as_of or datetime.now(timezone.utc)
    cutoff = clock - timedelta(days=30)
    rows = list(db.scalars(select(Measurement).where(
        Measurement.user_id == user_id, Measurement.metric == metric,
        Measurement.origin == origin, Measurement.timestamp >= cutoff.isoformat(),
        Measurement.timestamp <= clock.isoformat() if as_of is not None else True
    ).order_by(Measurement.timestamp)))
    valid = [r for r in rows if r.quality == 'valid']
    baseline = db.scalar(select(Baseline).where(Baseline.user_id == user_id, Baseline.metric == metric, Baseline.origin == origin))
    result = {'metric': metric, 'origin': origin, 'excluded_count': len(rows) - len(valid),
              'sample_count': len(valid), 'baseline': baseline.value if baseline else None,
              'baseline_period': baseline.period if baseline else None}
    if not valid or not baseline or baseline.value == 0:
        return {**result, 'data_status': 'insufficient_data', 'reason': 'A matching baseline and valid readings are required.'}
    daily = defaultdict(list)
    for row in valid:
        daily[datetime.fromisoformat(row.timestamp).date().isoformat()].append(row.value)
    days = sorted((day, mean(values)) for day, values in daily.items())
    latest_time = datetime.fromisoformat(valid[-1].timestamp)
    if clock - latest_time > timedelta(hours=48):
        return {**result, 'data_status': 'stale', 'reason': 'Latest valid reading is over 48 hours old.'}
    anchor = latest_time.date()
    current = [(d, v) for d, v in days if datetime.fromisoformat(d).date() > anchor - timedelta(days=7)]
    previous = [v for d, v in days if anchor - timedelta(days=14) < datetime.fromisoformat(d).date() <= anchor - timedelta(days=7)]
    if len(current) < 3:
        return {**result, 'data_status': 'insufficient_data', 'reason': 'At least three distinct collection days in the latest seven-day window are required.'}
    current_mean = mean(v for _, v in current)
    recent = current[-3:]
    # An anomaly must persist across three consecutive calendar days.
    consecutive = all((datetime.fromisoformat(recent[i][0]) - datetime.fromisoformat(recent[i-1][0])).days == 1 for i in range(1, 3))
    x = [(datetime.fromisoformat(d).date() - datetime.fromisoformat(current[0][0]).date()).days for d, _ in current]
    xmean, ymean = mean(x), current_mean
    denom = sum((a - xmean) ** 2 for a in x)
    slope = sum((a - xmean) * (v - ymean) for a, (_, v) in zip(x, current)) / denom if denom else 0
    return {**result, 'data_status': 'ready', 'current_mean': round(current_mean, 2),
            'previous_mean': round(mean(previous), 2) if previous else None,
            'change_percent': round((current_mean / baseline.value - 1) * 100, 2),
            'slope_per_day': round(slope, 3), 'unit': valid[-1].unit,
            'latest_at': valid[-1].timestamp, 'window_days': len(current),
            'missing_days': 7 - len(current), 'consecutive_recent_days': consecutive,
            'recent_changes': [round((v / baseline.value - 1) * 100, 2) for _, v in recent],
            'reading_ids': [r.id for r in valid if r.timestamp[:10] >= current[0][0]]}
