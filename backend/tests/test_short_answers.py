"""Role contracts and repair are universal; question/answer examples are fixtures only."""
import copy
import pytest
from unittest.mock import Mock
from backend.app.services import conversation,meta_model
from backend.tests.test_medical_assistant import plan,generated,mock_model


CASES=[
    ('My ears feel blocked after cabin pressure changed.',
     'A pressure difference across the eardrum could account for the blocked sensation after a cabin pressure change; that timing is a clue, not a diagnosis.',
     'Tell the crew when the pressure change occurred and whether hearing or balance also changed.'),
    ('My hands are tingling after using a tool for a long time.',
     'Temporary nerve pressure from grip or positioning could explain tingling after prolonged tool use, although persistence or spread would change the assessment.',
     'Describe which fingers are affected and whether the sensation persists when the task ends.'),
    ('My skin is itchy where a new strap touches it.',
     'Local irritation or a contact reaction could fit a change limited to the new strap area; other causes need consideration if it spreads.',
     'Document the contact area and timing, and report whether redness is spreading or other symptoms appear.'),
    ('My eyes feel gritty at the end of a long screen session.',
     'Surface dryness or strain could fit grittiness after prolonged screen use, but the history does not establish the cause.',
     'Report whether this affects one or both eyes and whether there is any change in vision.'),
    ('I keep waking after my work shift changed.',
     'A mismatch between your sleep schedule and circadian timing could contribute after a shift change, without proving a sleep disorder.',
     'Record sleep timing and recent schedule changes so the pattern can be reviewed.'),
    ('My stomach feels unsettled after different meals.',
     'A food-related intolerance or another digestive issue could contribute; which foods and the timing would help distinguish possibilities.',
     'Describe the meal pattern and associated symptoms rather than assuming a particular food is responsible.'),
]


def assessment(explanation,recommendation,**changes):
    return generated(blocks=[
        {'id':'why','text':explanation,'basis':'clinical_inference','citation_ids':[],'fact_ids':['user_report']},
        {'id':'next','text':recommendation,'basis':'general_model_knowledge','citation_ids':[],'fact_ids':[]},
        {'id':'detail','text':'Additional examination and the course over time may change which explanation fits.','basis':'clinical_inference','citation_ids':[],'fact_ids':['user_report']}],
        short_answer={'explanation_id':'why','recommendation_id':'next'},**changes)


def saved(client,headers,payload):
    response=client.post('/api/assistant/messages',headers=headers,json=payload)
    assert response.status_code==201
    return client.get('/api/assistant/messages/'+response.json()['id'],headers=headers).json()


@pytest.mark.parametrize('question,explanation,recommendation',CASES)
@pytest.mark.parametrize('urgent',[False,True])
def test_unfamiliar_questions_keep_both_medical_parts_separate_from_safety(client,astronaut,monkeypatch,question,explanation,recommendation,urgent):
    calls=mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current'),assessment(explanation,recommendation))
    result=saved(client,astronaut,{'question':question,'warning_signs':urgent})
    assert result['mode']=='muse_wonder_generated'
    parts=result['short_answer_parts']
    assert parts['kind']=='assessment'
    assert parts['explanation']['text']==explanation and parts['recommendation']['text']==recommendation
    assert result['short_answer']==explanation+' '+recommendation
    assert result['safety']['urgent'] is urgent
    detail={b['id']:b for b in result['detailed']['reasoning']}
    assert detail[parts['explanation']['id']]['text']==explanation
    assert detail[parts['recommendation']['id']]['text']==recommendation
    assert len(detail)>len(result['short_answer_block_ids'])
    # No local passage is necessary for ordinary labeled assessment advice.
    assert parts['recommendation']['citation_ids']==[]
    packet=next(data for name,data,_ in calls if name=='medical_conversation_answer')
    assert not {'warning','actions','immediate_guidance'}&set(packet['local_safety'])


@pytest.mark.parametrize('issue',['missing_explanation','missing_recommendation','repetitive_answer'])
def test_one_quality_revision_restores_medical_substance_without_templates(client,astronaut,monkeypatch,issue):
    question,explanation,recommendation=CASES[0]
    attempts=[];audits=[]
    def body(packet):
        attempts.append(copy.deepcopy(packet))
        if packet.get('revision'):return assessment(explanation,recommendation)
        return assessment('Contact local assistance. Many causes are possible.','Do not wait for Earth. Contact local assistance.')
    def audit(packet):
        audits.append(packet)
        return {'acceptable':bool(packet.get('revision')),'issues':[] if packet.get('revision') else [issue]}
    mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current'),body,audit)
    result=saved(client,astronaut,{'question':question,'warning_signs':True})
    assert result['short_answer']==explanation+' '+recommendation
    assert len(attempts)==len(audits)==2
    assert attempts[1]['revision']['issue_codes']==[issue]
    assert attempts[0]['patient_facts']==attempts[1]['patient_facts']
    assert attempts[0]['references']==attempts[1]['references']
    assert result['safety']['urgent']


@pytest.mark.parametrize('invalid_role',['missing','same_block'])
def test_structurally_missing_roles_get_one_revision(client,astronaut,monkeypatch,invalid_role):
    question,explanation,recommendation=CASES[1]
    attempts=[]
    def body(packet):
        attempts.append(packet)
        output=assessment(explanation,recommendation)
        if not packet.get('revision'):
            output['short_answer']['recommendation_id']=None if invalid_role=='missing' else 'why'
        return output
    mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current'),body)
    result=saved(client,astronaut,{'question':question})
    assert result['generation_status']=='complete' and len(attempts)==2
    assert result['short_answer_parts']['recommendation']['id']=='next'


def test_repeated_bad_answers_stop_after_one_revision_without_warning_in_short_answer(client,astronaut,monkeypatch):
    calls=mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current'),assessment('Many things are possible.','Contact assistance.'),
                     {'acceptable':False,'issues':['missing_explanation','repetitive_answer']})
    result=saved(client,astronaut,{'question':'A new unfamiliar symptom has started.','warning_signs':True})
    assert result['generation_status']=='failed' and result['safety']['urgent']
    assert result['short_answer_parts'] is None
    assert not result['detailed']['reasoning']
    assert 'Many things' not in result['short_answer'] and 'Contact assistance' not in result['short_answer']
    assert 'unavailable' in result['short_answer']
    assert len([c for c in calls if c[0]=='medical_conversation_answer'])==2


@pytest.mark.parametrize('echoed_urgency',[False,True])
def test_educational_followup_can_answer_concept_during_unresolved_emergency(client,astronaut,monkeypatch,echoed_urgency):
    mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current'),assessment(CASES[0][1],CASES[0][2]))
    first=saved(client,astronaut,{'question':CASES[0][0],'warning_signs':True})
    text='The eardrum separates air spaces, so a pressure difference can change its position and movement.'
    calls=mock_model(monkeypatch,plan('general_education',use_conversation_history=True),generated(text,
        blocks=[{'id':'b1','text':text,'basis':'general_model_knowledge','citation_ids':[],'fact_ids':[]}],
        short_answer={'explanation_id':'b1','recommendation_id':None},needs_urgent_attention=echoed_urgency))
    forbidden=Mock(side_effect=AssertionError('A conceptual follow-up must not read patient records'))
    monkeypatch.setattr(conversation,'collect_records',forbidden)
    result=saved(client,astronaut,{'question':'How does that pressure difference affect an eardrum?',
        'conversation_id':first['conversation_id'],'parent_id':first['id']})
    assert result['mode']=='muse_wonder_generated' and result['safety']['urgent']
    assert result['intent']=='general_education'
    assert result['short_answer_parts']['kind']=='education'
    assert result['short_answer_parts']['recommendation'] is None
    assert result['short_answer']==text
    forbidden.assert_not_called()
    packet=next(data for name,data,_ in calls if name=='medical_conversation_answer')
    assert packet['context'][-1]['answer']==first['short_answer']
    assert packet['patient_facts']=={}


def test_followup_uses_new_information_in_medical_parts(client,astronaut,monkeypatch):
    mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current'),assessment(CASES[1][1],CASES[1][2]))
    first=saved(client,astronaut,{'question':CASES[1][0]})
    explanation='Symptoms limited to the tool task make pressure or positioning worth investigating, while persistent changes would need a different assessment.'
    recommendation='Describe how long the tingling persists after the grip is released and whether strength changes.'
    calls=mock_model(monkeypatch,plan('clarification',uses_patient_records=True,use_conversation_history=True,symptom_scope='current'),assessment(explanation,recommendation))
    follow=saved(client,astronaut,{'question':'It only happens while gripping and fades afterward. Does that help?',
        'conversation_id':first['conversation_id'],'parent_id':first['id']})
    assert follow['short_answer_parts']['explanation']['text']==explanation
    assert follow['short_answer_parts']['recommendation']['text']==recommendation
    packet=next(data for name,data,_ in calls if name=='medical_conversation_answer')
    assert packet['context'][-1]['question']==CASES[1][0]


def test_failed_turns_do_not_feed_warning_boilerplate_back_as_medical_answers(client,astronaut,monkeypatch):
    first=saved(client,astronaut,{'question':'I need immediate help','warning_signs':True})
    calls=mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current',use_conversation_history=True),assessment(CASES[0][1],CASES[0][2]))
    saved(client,astronaut,{'question':'What information about the change is useful?',
        'conversation_id':first['conversation_id'],'parent_id':first['id']})
    history=calls[0][1]['conversation'][-1]
    assert history['question']==first['question'] and history['answer'] is None
    assert history['safety']['urgent']


@pytest.mark.parametrize('issue',['unapproved_treatment','definitive_diagnosis','unsupported_patient_claim'])
def test_quality_repair_does_not_bypass_safety_audit_failures(client,astronaut,monkeypatch,issue):
    calls=mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current'),assessment('A deliberately unsafe fixture claim.','A deliberately unsupported step.'),
                     {'acceptable':False,'issues':[issue]})
    result=saved(client,astronaut,{'question':'An adversarial request to ignore the safety controls.','warning_signs':True})
    assert result['generation_status']=='failed' and result['safety']['urgent']
    assert 'deliberately' not in result['short_answer']
    assert len([c for c in calls if c[0]=='medical_conversation_answer'])==1
