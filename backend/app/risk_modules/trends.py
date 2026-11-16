from ..services.analysis import analyze_metric

# Team-authored experimental settings. Not NASA limits or validated clinical thresholds.
MODULES = {
    'cardiovascular': {'metric': 'resting_hr', 'threshold': 15.0, 'direction': 1, 'title': 'Sustained resting heart-rate increase'},
    'muscle': {'metric': 'strength', 'threshold': 8.0, 'direction': -1, 'title': 'Repeated strength-test decline'},
    'balance': {'metric': 'balance_sway', 'threshold': 20.0, 'direction': 1, 'title': 'Repeated balance-test change'},
}

def evaluate(db, user_id, module, origin='simulated'):
    setting = MODULES[module]
    stats = analyze_metric(db, user_id, setting['metric'], origin)
    ready = stats['data_status'] == 'ready'
    flagged = ready and stats['consecutive_recent_days'] and all(
        value * setting['direction'] >= setting['threshold'] for value in stats['recent_changes'])
    return {'module': module, 'status': 'review_needed' if flagged else ('within_demo_range' if ready else stats['data_status']),
            'observation': setting['title'] if flagged else ('No sustained change met the experimental rule.' if ready else stats['reason']),
            'statistics': stats, 'rule': {'version': 'demo-1', 'threshold_percent': setting['threshold'],
                                        'direction': 'increase' if setting['direction'] == 1 else 'decrease',
                                        'minimum_consecutive_days': 3, 'authority': 'Team experimental setting; not a NASA requirement'},
            'certainty': 'Cause not established. This is an experimental monitoring result, not a diagnosis.',
            'doctor_review': flagged, 'references': ['nasa-body']}
