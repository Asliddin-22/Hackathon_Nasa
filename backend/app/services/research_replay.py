"""Offline, provenance-preserving adapter into the existing ingestion/analysis path."""
import csv
import hashlib
import io
import json
import secrets
from datetime import datetime,timedelta,timezone
from statistics import mean
from sqlalchemy import select
from ..config import ROOT
from ..models.records import User,Measurement,AuditEvent
from ..models.research import ResearchReplay,ResearchSample
from .auth import password_hash
from .ingestion import Reading,ingest
from .analysis import analyze_metric

DATA=ROOT/'research_data'/'bidmc-1.0.0'
ENCODING_EPOCH=datetime(1970,1,1,tzinfo=timezone.utc)


def load_source():
    manifest=json.loads((DATA/'manifest.json').read_text())
    raw=(DATA/manifest['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['sha256']:
        raise ValueError('Research source checksum mismatch')
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8')),skipinitialspace=True))
    if len(rows)!=manifest['rows'] or list(rows[0])!=['Time [s]','HR','PULSE','RESP','SpO2']:
        raise ValueError('Research source layout mismatch')
    times=[float(r['Time [s]']) for r in rows]
    if times!=list(range(481)):raise ValueError('Unexpected source time axis')
    return manifest,rows


def advance(db,owner_id,count):
    manifest,rows=load_source()
    replay=db.get(ResearchReplay,owner_id)
    if replay is None:
        subject_id='research-bidmc01-'+owner_id
        # A separate non-astronaut subject keeps this clinical record out of
        # personal AI context, synthetic baselines, alerts, and Earth snapshots.
        db.add(User(id=subject_id,username=subject_id,name='BIDMC 01 — Earth clinical research subject',
                    role='research',password_hash=password_hash(secrets.token_urlsafe(32))))
        db.flush()
        replay=ResearchReplay(owner_id=owner_id,subject_id=subject_id,cursor=0)
        db.add(replay);db.flush()
    stop=min(replay.cursor+count,len(rows))
    inserted=0
    for index in range(replay.cursor,stop):
        fields=rows[index];elapsed=float(fields['Time [s]'])
        measurement_id=f'{replay.subject_id}:{index}'
        _,created=ingest(db,Reading(id=measurement_id,user_id=replay.subject_id,metric='heart_rate',value=float(fields['HR']),unit=manifest['unit'],
                         timestamp=ENCODING_EPOCH+timedelta(seconds=elapsed),origin='imported',quality='valid',
                         source='PhysioNet BIDMC 1.0.0 record 01; Earth ICU; elapsed time'),owner_id)
        inserted+=int(created)
        if not db.get(ResearchSample,measurement_id):
            db.add(ResearchSample(measurement_id=measurement_id,owner_id=owner_id,sample_index=index,
                                  elapsed_seconds=elapsed,source_fields=fields))
    replay.cursor=stop
    db.add(AuditEvent(actor=owner_id,action='research.replayed',detail={'dataset':manifest['id'],'cursor':stop,'inserted':inserted,'sha256':manifest['sha256']}))
    db.flush()
    return inserted


def status(db,owner_id):
    manifest,rows=load_source()
    replay=db.get(ResearchReplay,owner_id)
    points=[]
    if replay:
        records=db.execute(select(ResearchSample,Measurement).join(Measurement,Measurement.id==ResearchSample.measurement_id)
                           .where(ResearchSample.owner_id==owner_id,ResearchSample.sample_index<replay.cursor).order_by(ResearchSample.sample_index)).all()
        points=[{'id':m.id,'elapsed_seconds':s.elapsed_seconds,'original_time':s.source_fields['Time [s]'],
                 'value':m.value,'original_value':s.source_fields['HR'],'unit':m.unit,'source_fields':s.source_fields,
                 'origin':'real_research','quality':m.quality} for s,m in records]
    monitoring=analyze_metric(db,replay.subject_id,'heart_rate','imported',as_of=ENCODING_EPOCH+timedelta(seconds=points[-1]['elapsed_seconds'])) if points else None
    return {'mode':'real_research_replay','dataset':manifest,'cursor':replay.cursor if replay else 0,'total':len(rows),'points':points,
            'monitoring':monitoring,'summary':{'count':len(points),'latest':points[-1]['value'],'minimum':min(p['value'] for p in points),
                'maximum':max(p['value'] for p in points),'mean':mean(p['value'] for p in points)} if points else None,
            'limitations':'Eight minutes of Earth ICU heart rate; not resting heart rate or astronaut data. No personal baseline or multi-day coverage: longitudinal risk conclusions are unavailable.',
            'quality_note':'Valid means the numeric value passed ingestion validation; no independent sensor-quality or clinical review is claimed.'}
