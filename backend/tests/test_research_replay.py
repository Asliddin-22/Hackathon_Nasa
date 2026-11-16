import hashlib
import json
import csv
import io
from sqlalchemy import select,func
from backend.app.models.records import Measurement,Baseline,Alert,SyncEvent,User,AuditEvent
from backend.app.models.research import ResearchReplay,ResearchSample
from backend.app.services import research_replay


def test_public_source_integrity_and_original_download(client,astronaut):
    manifest,rows=research_replay.load_source()
    raw=(research_replay.DATA/manifest['file']).read_bytes()
    assert len(raw)==7644
    assert hashlib.sha256(raw).hexdigest()=='27d43794cf2e7150db10e8bfe61d2bfdb26873a8f1629ffc5fbee5c9a4eb6ef5'
    checks=(research_replay.DATA/'SHA256SUMS.txt').read_text()
    assert manifest['sha256'] in checks
    assert len(rows)==481 and rows[0]['Time [s]']=='0' and rows[-1]['Time [s]']=='480'
    assert [row['HR'] for row in rows[:4]]==['94','94','94','92']
    response=client.get('/api/research-replay/source.csv',headers=astronaut)
    assert response.status_code==200 and response.content==raw
    assert 'attachment' in response.headers['content-disposition']


def test_full_record_reuses_ingestion_and_analysis_without_changing_source_values(client,astronaut):
    response=client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':481})
    assert response.status_code==200
    result=response.json();manifest,rows=research_replay.load_source()
    assert result['inserted']==result['cursor']==result['total']==481
    assert result['dataset']['calendar_time_available'] is False
    assert result['dataset']['unit']=='bpm'
    for point,source in zip(result['points'],rows):
        assert point['original_time']==source['Time [s]']
        assert point['original_value']==source['HR'] and point['value']==float(source['HR'])
        assert point['source_fields']==source
        assert point['unit']=='bpm' and point['origin']=='real_research'
        assert 'timestamp' not in point  # Do not present the ordering epoch as a collection date.
    assert result['monitoring']['sample_count']==481
    assert result['monitoring']['data_status']=='insufficient_data'
    assert result['monitoring']['baseline'] is None
    assert result['summary']['latest']==float(rows[-1]['HR'])
    assert result['summary']['count']==481
    with client.sessions() as db:
        state=db.get(ResearchReplay,'astro-01')
        assert db.get(User,state.subject_id).role=='research'
        records=list(db.scalars(select(Measurement).where(Measurement.user_id==state.subject_id).order_by(Measurement.timestamp)))
        assert len(records)==481 and all(r.metric=='heart_rate' and r.origin=='imported' for r in records)
        assert records[0].timestamp=='1970-01-01T00:00:00+00:00'
        assert records[-1].timestamp=='1970-01-01T00:08:00+00:00'
        assert db.scalar(select(func.count()).select_from(ResearchSample))==481
        audits=list(db.scalars(select(AuditEvent).where(AuditEvent.actor=='astro-01',AuditEvent.action=='measurement.ingest')))
        assert len(audits)==481


def test_replay_is_persistent_and_stale_advances_cannot_duplicate_rows(client,astronaut):
    first=client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':30}).json()
    assert first['cursor']==30 and len(first['points'])==30
    assert client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':30}).status_code==409
    assert client.get('/api/research-replay',headers=astronaut).json()['cursor']==30
    rest=client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':30,'count':481}).json()
    assert rest['cursor']==481 and rest['inserted']==451
    last=client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':481,'count':1}).json()
    assert last['inserted']==0 and len(last['points'])==481


def test_research_never_changes_astronaut_monitoring_or_downlink(client,astronaut,doctor):
    before=client.get('/api/astronauts/astro-01/health',headers=astronaut).json()
    before_queue=client.get('/api/sync',headers=astronaut).json()['queued']
    before_ground=client.get('/api/doctors/crew',headers=doctor).json()
    assert client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':481}).status_code==200
    after=client.get('/api/astronauts/astro-01/health',headers=astronaut).json()
    for field in ['measurements','baselines','alerts','assessments','assistant_messages']:
        assert after[field]==before[field]
    assert client.get('/api/sync',headers=astronaut).json()['queued']==before_queue
    assert client.get('/api/doctors/crew',headers=doctor).json()==before_ground


def test_replay_authentication_and_per_operator_isolation(client,astronaut,doctor):
    assert client.get('/api/research-replay').status_code==401
    assert client.get('/api/research-replay',headers=doctor).status_code==403
    assert client.get('/api/research-replay/source.csv').status_code==401
    assert client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':1}).status_code==200
    other=client.post('/api/auth/login',json={'username':'astronaut2','password':'demo-orbit-2026'}).json()
    headers={'Authorization':'Bearer '+other['token']}
    assert client.get('/api/research-replay',headers=headers).json()['cursor']==0
    assert client.get('/api/research-replay',headers=headers).json()['points']==[]
    with client.sessions() as db:subject=db.get(ResearchReplay,'astro-01').subject_id
    assert client.get('/api/astronauts/'+subject+'/health',headers=astronaut).status_code==403


def test_integrity_failure_is_atomic_and_does_not_disable_simulator(client,astronaut,monkeypatch,tmp_path):
    manifest,_=research_replay.load_source()
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    (tmp_path/manifest['file']).write_text('tampered data')
    monkeypatch.setattr(research_replay,'DATA',tmp_path)
    assert client.get('/api/research-replay',headers=astronaut).status_code==503
    assert client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':1}).status_code==503
    with client.sessions() as db:
        assert db.get(ResearchReplay,'astro-01') is None
        assert db.scalar(select(func.count()).select_from(ResearchSample))==0
    assert client.post('/api/simulator/tick',headers=astronaut,json={'scenario':'nominal'}).status_code==200


def test_replay_works_without_network_and_validates_controls(client,astronaut,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Research replay must use checked-in data only')
    monkeypatch.setattr('urllib.request.urlopen',forbidden)
    assert client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':1}).status_code==200
    for payload in [{'expected_cursor':-1},{'expected_cursor':1,'count':0},{'expected_cursor':1,'count':482}]:
        assert client.post('/api/research-replay/advance',headers=astronaut,json=payload).status_code==422


def test_restart_reuses_original_rows_and_analysis_cannot_see_future_samples(client,astronaut):
    client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':481})
    restarted=client.post('/api/research-replay/restart',headers=astronaut,json={'expected_cursor':481}).json()
    assert restarted['cursor']==0 and restarted['points']==[] and restarted['monitoring'] is None
    replayed=client.post('/api/research-replay/advance',headers=astronaut,json={'expected_cursor':0,'count':30}).json()
    assert replayed['cursor']==30 and replayed['inserted']==0
    assert len(replayed['points'])==replayed['monitoring']['sample_count']==30
    assert replayed['points'][-1]['original_time']=='29'
    with client.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ResearchSample))==481
    assert client.post('/api/research-replay/restart',headers=astronaut,json={'expected_cursor':0}).status_code==409
