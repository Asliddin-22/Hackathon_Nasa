"""Deterministic escalation and allowed workflow actions. No LLM dependency."""
WORKFLOW_ACTIONS = {
    'record_context': 'Record the measurement context, quality, and any symptoms.',
    'request_review': 'Request crew medical officer review using the actual mission-approved procedures.',
    'urgent_escalation': 'Contact the onboard crew medical officer now and follow the actual onboard emergency procedures. Do not wait for Earth communication.',
}

def safety_actions(warning_signs=False):
    codes = ['urgent_escalation'] if warning_signs else ['record_context', 'request_review']
    return [{'code': code, 'text': WORKFLOW_ACTIONS[code]} for code in codes]

def validate_actions(codes):
    if any(code not in WORKFLOW_ACTIONS for code in codes):
        raise ValueError('Unsupported guidance action')
    return [WORKFLOW_ACTIONS[code] for code in codes]
