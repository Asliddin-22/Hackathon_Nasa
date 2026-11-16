"""Reusable local emergency overlay, separate from generation and diagnosis.
Authoritative basic reference information is not mission clinical approval.
"""
import json
from sqlalchemy import select
from ..config import ROOT
from ..models.records import Mission,Protocol
from .assistant_safety import check
from .safety import safety_actions
from .knowledge import validate_document


def support_references():
    result=[]
    for category,id in [('fundamentals','medlineplus-first-aid'),('space_medicine','nasa-medical-operations')]:
        try:
            doc=json.loads((ROOT/'medical_knowledge'/category/(id+'.json')).read_text())
            validate_document(doc)
            for i,section in enumerate(doc['sections'],1):
                result.append({'chunk_id':f'{id}:{i}','heading':section['heading'],'text':section['text'],'rank':len(result)+1,
                              'citation':{'source_id':id,'title':doc['title'],'url':doc['url'],'publisher':doc['publisher'],'category':category,'system':doc['system'],
                                          'source_updated':doc['source_updated'],'reviewed_on':doc['reviewed_on'],'version':doc['version'],'text_sha256':doc['text_sha256'],
                                          'attribution':doc['rights']['attribution'],'scope':doc['scope']}})
        except (OSError,ValueError,KeyError):
            continue  # Local escalation must work even if reference files are unavailable.
    return result


def approved_procedures(db):
    # Runtime authority is the installed protocol registry, never model output.
    # No seeded demo workflow has this approval status. Deployment operators must
    # supply actual mission-authorized documents; publisher authority alone is not approval.
    return [{'id':r.id,'title':r.title,'version':r.version,'steps':r.steps,'references':r.references,'approval_status':r.approval_status}
            for r in db.scalars(select(Protocol).where(Protocol.approval_status=='mission_approved'))]


def overlay(db,screen,support=None):
    refs=support_references();available={r['chunk_id'] for r in refs}
    actions=safety_actions(True)
    guidance=[{'code':'activate_local_help','text':'Activate onboard emergency assistance now and alert an available crewmember. Do not wait for Earth or this conversation.',
               'citation_ids':['medlineplus-first-aid:1'],'scope':'Reference-based basic assistance; adapted to the onboard setting.'},
              {'code':'trained_assistance','text':'If the medical officer is unavailable, ask an available trained crewmember to use the actual mission emergency checklist within their training and authorization.',
               'citation_ids':['medlineplus-first-aid:2','nasa-medical-operations:1'],'scope':'Use installed mission procedures; this app does not invent replacement treatment instructions.'},
              {'code':'do_not_delay','text':'Give follow-up information or collect existing readings only when doing so will not delay immediate assistance.',
               'citation_ids':['medlineplus-first-aid:1'],'scope':'Questions and measurements are secondary to urgent help.'}]
    guidance=[g for g in guidance if set(g['citation_ids'])<=available]
    mission=db.get(Mission,'ares-01')
    procedures=approved_procedures(db)
    return {**screen,'urgent':True,'actions':actions,'immediate_guidance':guidance,'approved_procedures':procedures,
            'protocol_status':'mission_approved_available' if procedures else 'no_mission_approved_clinical_procedure_installed',
            'reference_status':'authoritative_basic_information_not_mission_treatment_approval',
            'communication':{'online':mission.online,'delay_seconds':mission.delay_seconds,'simulation':True} if mission else {},
            'support':support or {},'do_not_delay_for_questions':True}


def preflight(db,question,severity=None,warning_signs=False,parent_response=None,support=None):
    screen=check(question,severity,warning_signs)
    # Carry a confirmed incident through the same parent chain, but never lock
    # the conversation or treat a new model response as clinical clearance.
    carry=bool(parent_response and parent_response.get('safety',{}).get('urgent'))
    confirmed=warning_signs or (severity is not None and severity>=8) or carry
    if confirmed:
        if carry and (support or {}).get('medical_personnel_available') is None:
            support={**parent_response['safety'].get('support',{}),**{k:v for k,v in (support or {}).items() if v is not None}}
        if carry:screen['matched_warning_signs'].append('Continuing a previously escalated conversation')
        return overlay(db,screen,support)
    return {'urgent':False,'matched_warning_signs':[],'potential_warning_signs':screen['matched_warning_signs'],
            'warning':'If these warning signs describe what is happening now, activate onboard emergency assistance immediately; do not wait for the AI.' if screen['urgent'] else '',
            'actions':[],'scope':'Potential text matches need context; explicit reported danger escalates independently.'}


def model_context(safety):
    """Supply incident facts without feeding displayed warning prose back to the LLM."""
    if not safety or not safety.get('urgent'):return {'urgent':False}
    return {key:safety.get(key) for key in ('urgent','matched_warning_signs','communication',
                                           'support','approved_procedures','protocol_status')} | {'local_notice_already_displayed':True}


def attach(result,safety):
    """A monotonic safety overlay never overwrites validated generated reasoning."""
    if not safety or not safety.get('urgent'):return result
    result['safety']=safety
    result['needs_medical_review']=True
    local_refs=support_references()
    existing={r['chunk_id'] for r in result['detailed']['references']}
    result['detailed']['references'] += [r for r in local_refs if r['chunk_id'] not in existing]
    # Keep immediate non-treatment guidance available in BOTH initial/fallback
    # and generated responses; model-generated recommendations remain separate.
    result['detailed']['emergency_guidance']=safety.get('immediate_guidance',[])
    result['detailed']['approved_procedures']=safety.get('approved_procedures',[])
    # Pending/failure status stays operational. Guidance is displayed once in
    # its own safety panel and never masquerades as a medical short answer.
    return result
