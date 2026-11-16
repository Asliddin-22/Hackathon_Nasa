"""Local retrieval + constrained Muse Wonder planning, with offline fallback."""
from .knowledge import retrieve_balanced
from .ai_assistant import llm_enabled
from . import meta_model

def retrieve_evidence(db,question,context=None,explanations=None,questions=None,references=None):
    # Preserve both terrestrial fundamentals and mission-specific evidence.
    if references is None:
        references=retrieve_balanced(db,question)
    options=explanations or {}
    followups=questions or {}
    plan={'focus':[r['chunk_id'] for r in references], 'explanations':list(options)[:3], 'questions':list(followups)[:3]}
    mode='offline_reference_summary'
    if references and llm_enabled():
        try:
            selected=meta_model.request_grounded_plan(context or {'question':question},references,options,followups)
            if selected is not None:
                # Keep every retrieved source available, even if model focus is empty.
                plan=selected
                mode='muse_wonder_grounded'
        except Exception:
            mode='offline_provider_fallback'
    return {'references':references,'plan':plan,'mode':mode,'coverage':'references_found' if references else 'no_coverage'}
