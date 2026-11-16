from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from backend.app.models.records import Measurement, Alert
from backend.app.services.analysis import analyze_metric
from backend.app.services.safety import validate_actions
from backend.app.services.ai_assistant import select_evidence
import pytest


def test_trends_and_idempotent_alerts(client, astronaut):
    findings = client.post('/api/assessments', headers=astronaut, json={}).json()
    assert {r['module'] for r in findings if r['status'] == 'review_needed'} == {'cardiovascular', 'muscle', 'balance'}
    assert len([r for r in findings if r['status'] == 'assessment_required']) == 3
    cardio = next(r for r in findings if r['module'] == 'cardiovascular')
    assert cardio['statistics']['change_percent'] > 15
    assert cardio['explanation']['mode'] == 'offline_template'
    assert cardio['rule']['authority'].startswith('Team experimental')
    client.post('/api/assessments', headers=astronaut, json={})
    assert len(client.get('/api/alerts', headers=astronaut).json()) == 3


def test_quality_origin_and_staleness(client):
    with client.sessions() as db:
        db.add(Measurement(id='bad', user_id='astro-01', metric='resting_hr', value=200, unit='bpm',
                           timestamp=datetime.now(timezone.utc).isoformat(), source='test', origin='simulated', quality='suspect'))
        db.commit()
        stats = analyze_metric(db, 'astro-01', 'resting_hr')
        assert stats['excluded_count'] == 1
        assert stats['current_mean'] < 100
        assert analyze_metric(db, 'astro-01', 'resting_hr', 'device')['data_status'] == 'insufficient_data'
        for row in db.scalars(select(Measurement).where(Measurement.user_id == 'astro-01')):
            row.timestamp = (datetime.fromisoformat(row.timestamp) - timedelta(days=10)).isoformat()
        db.commit()
        assert analyze_metric(db, 'astro-01', 'resting_hr')['data_status'] == 'stale'


def test_one_spike_does_not_trigger(client, astronaut):
    with client.sessions() as db:
        rows = list(db.scalars(select(Measurement).where(Measurement.user_id == 'astro-01', Measurement.metric == 'resting_hr').order_by(Measurement.timestamp)))
        for r in rows:
            r.value = 65
        rows[-1].value = 130
        db.commit()
    findings = client.post('/api/assessments', headers=astronaut, json={}).json()
    assert next(r for r in findings if r['module'] == 'cardiovascular')['status'] == 'within_demo_range'


def test_urgent_symptoms_are_local(client, astronaut):
    response = client.post('/api/symptoms', headers=astronaut, json={'description': 'Demo dizziness with warning signs', 'severity': 8, 'warning_signs': True})
    assert response.status_code == 201
    assert response.json()['alert']['severity'] == 'urgent'
    assert 'Do not wait for Earth' in response.json()['actions'][0]['text']
    with pytest.raises(ValueError):
        validate_actions(['prescribe_medication'])


def test_llm_unavailable_fallback(monkeypatch):
    monkeypatch.setenv('ENABLE_LLM', 'true')
    monkeypatch.setenv('MODEL_API_KEY', 'test-key')
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr('backend.app.services.meta_model.open_response', fail)
    order, mode = select_evidence({'baseline': '65 bpm'})
    assert order == ['baseline'] and mode == 'offline_template_fallback'


def test_llm_output_is_constrained(monkeypatch):
    import io
    import json
    from backend.app.services.ai_assistant import select_evidence
    monkeypatch.setenv('ENABLE_LLM', 'true')
    monkeypatch.setenv('MODEL_API_KEY', 'fake-test-key')
    def model_output(focus):
        return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'focus':focus})}]}]}).encode())
    monkeypatch.setattr('backend.app.services.meta_model.open_response', lambda *args,**kwargs:model_output(['current']))
    assert select_evidence({'baseline':'65 bpm','current':'80 bpm'}) == (['current','baseline'],'llm_evidence_assisted')
    monkeypatch.setattr('backend.app.services.meta_model.open_response', lambda *args,**kwargs:model_output(['prescribe_medication']))
    assert select_evidence({'baseline':'65 bpm'}) == (['baseline'],'offline_template_fallback')


def test_missing_days_cannot_masquerade_as_consecutive(client, astronaut):
    with client.sessions() as db:
        rows = list(db.scalars(select(Measurement).where(Measurement.user_id=='astro-01',Measurement.metric=='resting_hr').order_by(Measurement.timestamp)))
        db.delete(rows[-2])
        db.commit()
        stats = analyze_metric(db,'astro-01','resting_hr')
        assert stats['consecutive_recent_days'] is False
    findings = client.post('/api/assessments',headers=astronaut,json={}).json()
    assert next(f for f in findings if f['module']=='cardiovascular')['status']=='within_demo_range'
