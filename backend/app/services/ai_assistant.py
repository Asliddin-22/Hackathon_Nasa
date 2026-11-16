"""Optional constrained LLM evidence selection; all displayed text is local.
The model cannot introduce diagnoses, treatments, or actions. Offline fallback
preserves every observation and guidance action. No identifiers leave onboard.
"""
import os
from . import meta_model


def llm_enabled():
    return os.getenv('ENABLE_LLM', 'false').lower() == 'true'


def select_evidence(evidence):
    if not evidence or not llm_enabled():
        return list(evidence), 'offline_template'
    try:
        selected = meta_model.request_focus(evidence)
        if selected is None:
            return list(evidence), 'offline_template'
        # Preserve all evidence; the model can only change its emphasis/order.
        return list(dict.fromkeys(selected + list(evidence))), 'llm_evidence_assisted'
    except Exception:
        # Never expose provider bodies, exceptions, headers, or credentials.
        # Availability/schema failures cannot interrupt local monitoring.
        return list(evidence), 'offline_template_fallback'


def explain(finding, use_llm=False):
    stats = finding.get('statistics', {})
    evidence = {}
    if stats.get('data_status') == 'ready':
        evidence = {
            'baseline': f"Personal reference: {stats['baseline']:g} {stats['unit']} ({stats['baseline_period']}).",
            'current': f"Latest {stats['window_days']}-day mean: {stats['current_mean']:g} {stats['unit']}; {stats['change_percent']:+.1f}% from baseline.",
            'persistence': f"Latest three daily changes: {', '.join(f'{v:+.1f}%' for v in stats['recent_changes'])}.",
            'quality': f"{stats['sample_count']} valid samples; {stats['excluded_count']} excluded; {stats['missing_days']} days missing in the seven-day window.",
        }
    else:
        evidence = {'limitations': stats.get('reason', 'Dedicated clinical examination required.')}
    order, mode = select_evidence(evidence) if use_llm else (list(evidence), 'offline_template')
    return {'mode': mode, 'observation': finding['observation'], 'evidence': [evidence[key] for key in order],
            'certainty': finding['certainty'], 'possible_explanations': [],
            'limitation': 'These data do not establish a cause. No diagnosis, medication, dosage, or treatment is generated.',
            'references': finding['references'], 'guidance_status': 'Demo workflow only; no clinically approved protocol installed.'}
