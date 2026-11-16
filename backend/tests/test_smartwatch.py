"""G2 smartwatch pipeline: ingestion contract, monitoring, scenarios, integration."""
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, select, text
from backend.app.models.records import Measurement, Symptom, Alert
from backend.app.database.db import ensure_additive_columns
from backend.app.services.conversation import collect_records
from backend.app.services.conversation_schema import ContextPlan
from backend.app.services.device_adapters import normalize, DeviceSample, DeviceAdapterError, DEVICE_INGESTION_ENABLED
from backend.app.models.records import SyncEvent


def make_due(client):
    with client.sessions() as db:
        for event in db.scalars(select(SyncEvent).where(SyncEvent.status == 'queued')):
            event.available_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.commit()


def watch_reading(**changes):
    return {'id': str(uuid.uuid4()), 'metric': 'resting_hr', 'value': 72, 'unit': 'bpm',
            'timestamp': datetime.now(timezone.utc).isoformat(), 'source': 'Manual entry in demo workspace',
            'device_id': 'manual-entry', 'origin': 'manual', **changes}


def ticks(client, headers, scenario, count):
    results = [client.post('/api/simulator/tick', headers=headers, json={'scenario': scenario}).json()]
    results += [client.post('/api/simulator/tick', headers=headers, json={}).json() for _ in range(count - 1)]
    return results


def test_identity_is_derived_from_session(client, astronaut):
    body = client.post('/api/measurements', headers=astronaut, json=watch_reading()).json()
    assert body['created'] and body['measurement']['user_id'] == 'astro-01'
    assert body['measurement']['device_id'] == 'manual-entry'
    assert client.post('/api/measurements', headers=astronaut, json=watch_reading(user_id='astro-02')).status_code == 403


def test_unverified_device_provenance_is_rejected(client, astronaut):
    response = client.post('/api/measurements', headers=astronaut, json=watch_reading(origin='device'))
    assert response.status_code == 403
    assert 'registered device adapter' in response.json()['detail']


def test_watch_metric_bounds_and_units(client, astronaut):
    for changes in [{'metric': 'spo2', 'value': 101, 'unit': '%'}, {'metric': 'steps', 'value': 10, 'unit': 'steps'},
                    {'metric': 'heart_rate', 'value': 400, 'unit': 'bpm'}, {'metric': 'sleep_hours', 'value': -1, 'unit': 'h'},
                    {'metric': 'heart_rate', 'value': float('nan'), 'unit': 'bpm'}]:
        payload = watch_reading(**changes)
        if payload['value'] != payload['value']:
            payload['value'] = 'NaN'
        assert client.post('/api/measurements', headers=astronaut, json=payload).status_code == 422
    for metric, value, unit in [('heart_rate', 88, 'bpm'), ('spo2', 97.5, '%'), ('sleep_hours', 6.5, 'h'), ('steps', 4200, 'count')]:
        assert client.post('/api/measurements', headers=astronaut, json=watch_reading(metric=metric, value=value, unit=unit)).status_code == 201


def test_duplicate_reading_ids_are_idempotent(client, astronaut):
    payload = watch_reading()
    assert client.post('/api/measurements', headers=astronaut, json=payload).json()['created']
    assert not client.post('/api/measurements', headers=astronaut, json=payload).json()['created']
    assert client.post('/api/measurements', headers=astronaut, json={**payload, 'device_id': 'other'}).status_code == 409


def test_manual_readings_trigger_watch_monitoring(client, astronaut):
    results = [client.post('/api/measurements', headers=astronaut, json=watch_reading(value=104 + i)).json() for i in range(3)]
    assert results[0]['monitoring']['watch_alerts'] == [] and results[0]['monitoring']['longitudinal_skipped_for_origins'] == ['manual']
    alerts = results[2]['monitoring']['watch_alerts']
    assert alerts and alerts[0]['module'] == 'watch_resting_hr' and alerts[0]['origin'] == 'manual'
    stored = [a for a in client.get('/api/alerts', headers=astronaut).json() if a['module'] == 'watch_resting_hr']
    assert len(stored) == 1 and stored[0]['severity'] == 'review'
    assert 'not a diagnosis' in stored[0]['evidence']['certainty']
    # Manual data stays separate from synthetic baseline analysis.
    record = client.get('/api/astronauts/astro-01/health', headers=astronaut).json()
    assert all(f['statistics'].get('origin', 'simulated') == 'simulated' for f in record['assessments'])


def test_watch_rule_requires_consecutive_readings(client, astronaut):
    for value in (110, 70, 110):
        result = client.post('/api/measurements', headers=astronaut, json=watch_reading(value=value)).json()
    assert result['monitoring']['watch_alerts'] == []


def test_scenario_state_and_labels(client, astronaut):
    state = client.get('/api/simulator/state', headers=astronaut).json()
    assert state['scenario'] == 'normal' and state['provenance'] == 'simulated' and len(state['scenarios']) == 6
    changed = client.post('/api/simulator/scenario', headers=astronaut, json={'scenario': 'activity_recovery'}).json()
    assert changed['scenario'] == 'activity_recovery' and changed['step'] == 0
    result = client.post('/api/simulator/tick', headers=astronaut, json={}).json()
    assert result['scenario'] == 'activity_recovery' and result['origin'] == 'simulated'
    with client.sessions() as db:
        rows = list(db.scalars(select(Measurement).where(Measurement.source == 'G2 virtual watch simulator')))
        assert rows and all(r.origin == 'simulated' and r.device_id == 'g2-virtual-watch' for r in rows)


def test_simulated_values_change_coherently(client, astronaut):
    results = ticks(client, astronaut, 'elevated_resting_hr', 10)
    resting = [r['readings']['resting_hr'] for r in results]
    steps = [r['readings']['steps'] for r in results]
    assert all(abs(b - a) < 6 for a, b in zip(resting, resting[1:]))
    assert all(b >= a for a, b in zip(steps, steps[1:]))
    assert resting[-1] > resting[0] + 8  # gradual upward trend, not random
    stamps = [datetime.fromisoformat(r['timestamp']) for r in client.get('/api/astronauts/astro-01/history', headers=astronaut).json()
              if r['source'] == 'G2 virtual watch simulator' and r['metric'] == 'resting_hr']
    assert stamps == sorted(stamps)


def test_activity_scenario_recovers(client, astronaut):
    hr = [r['readings']['heart_rate'] for r in ticks(client, astronaut, 'activity_recovery', 20)]
    assert max(hr[:8]) > 125 and hr[-1] < max(hr[:8]) - 40


def test_reduced_sleep_context(client, astronaut):
    result = ticks(client, astronaut, 'reduced_sleep', 2)
    assert result[0]['readings']['sleep_hours'] == 4.5 and 'sleep_hours' not in result[1]['readings']
    latest = client.get('/api/astronauts/astro-01/health', headers=astronaut).json()['latest']['sleep_hours']
    assert latest['value'] == 4.5 and latest['origin'] == 'simulated'


def test_reported_symptom_scenario_files_once_in_medical_history(client, astronaut):
    results = ticks(client, astronaut, 'reported_symptom', 3)
    assert results[0]['symptom_id'] and not results[1]['symptom_id']
    record = client.get('/api/astronauts/astro-01/health', headers=astronaut).json()
    simulated = [s for s in record['symptoms'] if s['description'].startswith('Simulated scenario')]
    assert len(simulated) == 1 and simulated[0]['origin'] == 'simulated'
    assert any(a['module'] == 'symptoms' and a['severity'] == 'review' for a in record['alerts'])


def test_concerning_trend_raises_review_without_diagnosis(client, astronaut):
    results = ticks(client, astronaut, 'concerning_trend', 8)
    modules = {a['module'] for r in results for a in r['watch_alerts']}
    assert {'watch_resting_hr', 'watch_spo2'} <= modules
    alerts = [a for a in client.get('/api/alerts', headers=astronaut).json() if a['module'].startswith('watch_')]
    assert len(alerts) == 2 and all(a['severity'] == 'review' for a in alerts)
    for alert in alerts:
        assert 'diagnos' not in alert['title'].lower()
        assert alert['evidence']['rule']['authority'].startswith('Team experimental')


def test_watch_alerts_reach_earth_only_after_delay(client, astronaut, doctor):
    client.patch('/api/mission/context', headers=astronaut, json={'online': True, 'delay_seconds': 600})
    ticks(client, astronaut, 'concerning_trend', 8)
    client.post('/api/sync', headers=astronaut)
    ground = client.get('/api/doctors/crew', headers=doctor).json()
    alex = next(c for c in ground if c['user_id'] == 'astro-01')
    assert not any(a['module'].startswith('watch_') for a in alex['snapshot']['alerts'])
    make_due(client)
    assert client.post('/api/sync', headers=astronaut).json()['delivered'] >= 1
    alex = next(c for c in client.get('/api/doctors/crew', headers=doctor).json() if c['user_id'] == 'astro-01')
    assert {'watch_resting_hr', 'watch_spo2'} <= {a['module'] for a in alex['snapshot']['alerts']}
    assert any(m['metric'] == 'spo2' and m['source'] == 'G2 virtual watch simulator' for m in alex['snapshot']['measurements'])


def test_offline_monitoring_is_independent_of_earth_and_ai(client, astronaut, monkeypatch):
    monkeypatch.setenv('ENABLE_LLM', 'false')
    monkeypatch.delenv('MODEL_API_KEY', raising=False)
    client.patch('/api/mission/context', headers=astronaut, json={'online': False})
    ticks(client, astronaut, 'concerning_trend', 8)
    assert {a['module'] for a in client.get('/api/alerts', headers=astronaut).json()} >= {'watch_resting_hr', 'watch_spo2'}
    make_due(client)
    assert client.post('/api/sync', headers=astronaut).json() == {'delivered': 0, 'status': 'offline'}


def test_assistant_can_retrieve_watch_history(client, astronaut):
    ticks(client, astronaut, 'concerning_trend', 3)
    plan = ContextPlan(intent='personal_assessment', uses_patient_records=True, metrics=['heart_rate', 'spo2', 'sleep_hours'],
                       include_history=True, include_symptoms=False, test_types=[], include_mission=False,
                       use_conversation_history=False, retrieval_queries=[], symptom_scope='current')
    with client.sessions() as db:
        context, facts = collect_records(db, 'astro-01', 'simulated', plan)
    metrics = {o['metric'] for o in context['observations']}
    assert metrics == {'heart_rate', 'spo2', 'sleep_hours'}
    assert any(h['module'] == 'spo2' for h in context['history'])


def test_simulator_cannot_write_for_doctor(client, doctor):
    assert client.post('/api/simulator/tick', headers=doctor, json={}).status_code == 403


def test_migration_adds_device_column_to_old_database(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "old.db"}')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE health_measurements (id VARCHAR PRIMARY KEY, user_id VARCHAR, metric VARCHAR, value FLOAT, unit VARCHAR, timestamp VARCHAR, received_at VARCHAR, source VARCHAR, origin VARCHAR, quality VARCHAR)'))
    ensure_additive_columns(engine)
    ensure_additive_columns(engine)  # idempotent
    with engine.connect() as connection:
        assert 'device_id' in {row[1] for row in connection.execute(text('PRAGMA table_info(health_measurements)'))}


def test_device_adapters_normalize_without_enabling_ingestion():
    assert DEVICE_INGESTION_ENABLED is False
    now = datetime.now(timezone.utc) - timedelta(minutes=1)
    hk = normalize(DeviceSample(platform='healthkit', type='HKQuantityTypeIdentifierOxygenSaturation', value=0.97,
                                unit='%', start=now, sample_id='abc', device_id='watch-1'), 'astro-01', verified=True)
    assert hk.metric == 'spo2' and hk.value == 97 and hk.origin == 'device' and hk.id == 'healthkit:watch-1:abc'
    wear = normalize(DeviceSample(platform='wear_os', type='HEART_RATE_BPM', value=71, unit='bpm', start=now,
                                  sample_id='x1', device_id='pixel-watch'), 'astro-01', verified=True)
    assert wear.metric == 'heart_rate' and wear.unit == 'bpm'
    for sample, verified in [(DeviceSample(platform='healthkit', type='HKQuantityTypeIdentifierHeartRate', value=70, unit='count/min', start=now, sample_id='a', device_id='w'), False),
                             (DeviceSample(platform='healthkit', type='HKCategoryTypeIdentifierMindfulSession', value=1, unit='', start=now, sample_id='b', device_id='w'), True)]:
        try:
            normalize(sample, 'astro-01', verified=verified)
            raise AssertionError('expected rejection')
        except DeviceAdapterError:
            pass


def test_g2_current_ai_answer_and_watch_data_sync_without_changing_contract(client,astronaut,doctor,monkeypatch):
    from backend.app.services.knowledge import ingest_corpus
    from backend.tests.test_medical_assistant import plan,generated,mock_model
    with client.sessions() as db:ingest_corpus(db);db.commit()
    client.patch('/api/mission/context',headers=astronaut,json={'online':False,'delay_seconds':600})
    ticks(client,astronaut,'concerning_trend',8)
    latest=client.get('/api/astronauts/astro-01/health',headers=astronaut).json()['latest']
    metrics=['heart_rate','resting_hr','spo2','sleep_hours','steps']
    def answer(packet):
        measurements={f['value']['metric']:f['value'] for f in packet['patient_facts'].values() if f['kind']=='measurement'}
        assert set(measurements)==set(metrics)
        assert all(measurements[m]['value']==latest[m]['value'] for m in metrics)
        return generated(f"The recorded heart rate is {measurements['heart_rate']['value']} bpm; activity and recovery are possibilities to assess, not an established cause.",
                         personal=True,needs_medical_review=True)
    calls=mock_model(monkeypatch,plan('personal_assessment',uses_patient_records=True,metrics=metrics,include_history=True,
        include_mission=True,use_conversation_history=True,retrieval_queries=['heart blood pressure'],symptom_scope='current'),answer)
    initial=client.post('/api/assistant/messages',headers=astronaut,json={'question':'Help interpret my recorded watch measurements and what to assess next.','wait_for_completion':False}).json()
    final=client.get('/api/assistant/messages/'+initial['id'],headers=astronaut).json()
    assert final['schema_version']=='3' and final['generation_status']=='complete'
    assert final['short_answer_parts']['explanation'] and final['short_answer_parts']['recommendation']
    assert final['detailed']['references'] and len(final['detailed']['patient_observations'])==5
    assert client.get('/api/doctors/conversations/astro-01',headers=doctor).json()==[]
    assert client.post('/api/sync',headers=astronaut).json()['status']=='offline'
    client.patch('/api/mission/context',headers=astronaut,json={'online':True})
    assert client.post('/api/sync',headers=astronaut).json()['delivered']==0  # Not due yet.
    make_due(client);assert client.post('/api/sync',headers=astronaut).json()['delivered']>0
    archived=client.get('/api/doctors/conversations/astro-01',headers=doctor).json()
    assert next(r['message'] for r in archived if r['message']['id']==initial['id'])==final
    ground=next(r for r in client.get('/api/doctors/crew',headers=doctor).json() if r['user_id']=='astro-01')['snapshot']
    assert ground['latest']['spo2']['device_id']=='g2-virtual-watch'
    assert {'watch_spo2','watch_resting_hr'}<={a['module'] for a in ground['alerts']}
    assert client.post('/api/sync',headers=astronaut).json()['delivered']==0


def test_watch_alerts_do_not_mix_provenance(client,astronaut):
    for _ in range(3):client.post('/api/measurements',headers=astronaut,json=watch_reading(value=110))
    ticks(client,astronaut,'concerning_trend',8)
    alerts=[a for a in client.get('/api/alerts',headers=astronaut).json() if a['module']=='watch_resting_hr']
    assert len(alerts)==2
    assert {a['evidence']['origin'] for a in alerts}=={'manual','simulated'}


def test_watch_rules_cannot_trigger_from_stale_readings(client,astronaut):
    old=datetime.now(timezone.utc)-timedelta(days=2)
    for i in range(3):
        response=client.post('/api/measurements',headers=astronaut,json=watch_reading(value=110,timestamp=(old+timedelta(seconds=i)).isoformat()))
        assert response.status_code==201
        assert response.json()['monitoring']['watch_alerts']==[]


def test_old_database_migration_preserves_records_and_is_idempotent(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "legacy-preservation.db"}')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE health_measurements (id VARCHAR PRIMARY KEY, value FLOAT, timestamp VARCHAR)'))
        connection.execute(text("INSERT INTO health_measurements (id,value,timestamp) VALUES ('existing',72,'2026-01-01T00:00:00+00:00')"))
    ensure_additive_columns(engine);ensure_additive_columns(engine)
    with engine.connect() as connection:
        assert connection.execute(text('SELECT id,value,timestamp,device_id FROM health_measurements')).one()==('existing',72,'2026-01-01T00:00:00+00:00',None)
    engine.dispose()
