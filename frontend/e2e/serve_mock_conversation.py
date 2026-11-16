"""Test-only server. No production test switch; every remote transport is blocked."""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import uvicorn
from backend.app.main import app
from backend.app.services import meta_model

PLANS={
 'An unfamiliar serious change is happening. Can you help me understand it?':True,
 'It started suddenly and I am alone. What information matters?':True,
 'Why do hormone signals act at a distance?':False,
 'What makes those signals stop?':False,
 'My arms tire earlier in resistance sessions. What should I consider?':True,
}

def blocked(*args,**kwargs):
    raise RuntimeError('Remote transport is forbidden in this browser fixture')


def mock(name,instructions,data,schema,**kwargs):
    if name=='medical_context_plan':
        if data.get('local_emergency',{}).get('urgent'):time.sleep(2)
        personal=PLANS[data['question']]
        return {'intent':'personal_assessment' if personal else 'general_education',
                'uses_patient_records':personal,'metrics':['strength'] if personal else [],'include_history':personal,
                'include_symptoms':False,'test_types':[],'include_mission':False,'use_conversation_history':bool(data['conversation']),
                'retrieval_queries':['muscle contract'] if personal else [],'symptom_scope':'current' if personal else 'educational'}
    if name=='medical_answer_audit':return {'acceptable':True,'issues':[]}
    if name=='medical_conversation_answer':
        personal=data['intent']=='personal_assessment'
        if personal:
            text='Workload and recovery are possibilities to distinguish with the timing of your symptoms; the available record alone does not establish their cause.'
        elif data['context']:
            text='Signals diminish as hormones are removed from circulation or receptor activity changes, allowing the response to wind down.'
        else:
            text='Hormones travel in the circulation and affect distant cells that have the matching receptors, which is why the response can be far from the releasing gland.'
        urgent=data.get('local_safety',{}).get('urgent',False)
        return {'blocks':[{'id':'main','text':text,'basis':'clinical_inference' if personal else 'general_model_knowledge',
                           'citation_ids':[],'fact_ids':['user_report'] if personal else []}],
                'short_answer_ids':['main'],'possible_explanations':[],'follow_up_questions':['How does the timing relate to workload changes?'] if personal else [],
                'recommendations':[],'uncertainties':['Fixture model output; not clinical validation.'],
                'needs_medical_review':personal,'needs_urgent_attention':urgent}
    raise RuntimeError('Unsupported fixture request')

meta_model.request_structured=mock
meta_model.open_response=blocked
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=8003)
