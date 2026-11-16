import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import select
from simulator.astronaut_data import CREW, BASELINES, history
from ..config import DEMO_PASSWORD
from ..models.records import User, Mission, Measurement, Baseline, MedicalTest, Protocol
from .auth import password_hash

ROOT = Path(__file__).resolve().parents[3]

def seed(db):
    for path in (ROOT / 'medical_knowledge' / 'protocols').glob('*.json'):
        data = json.loads(path.read_text())
        if not db.get(Protocol, data['id']):
            db.add(Protocol(**data))
    db.commit()
    if db.scalar(select(User).limit(1)):
        return
    for index, (uid, name, _) in enumerate(CREW):
        db.add(User(id=uid, username='astronaut' if index == 0 else f'astronaut{index+1}', name=name,
                    role='astronaut', password_hash=password_hash(DEMO_PASSWORD)))
    db.add(User(id='doctor-01', username='doctor', name='Dr. Elena Park', role='doctor', password_hash=password_hash(DEMO_PASSWORD)))
    db.add(Mission(id='ares-01', profile='mars_transit', environment='Mars transit', gravity='Microgravity',
                   start_time=(datetime.now(timezone.utc) - timedelta(days=126)).isoformat(), online=True, delay_seconds=20))
    db.flush()
    for index, (uid, _, _) in enumerate(CREW):
        for reading in history(uid, index):
            db.add(Measurement(**reading))
        for metric, (value, unit) in BASELINES.items():
            db.add(Baseline(user_id=uid, metric=metric, value=value + (index * 2 if metric == 'resting_hr' else 0),
                            unit=unit, period='Synthetic preflight reference', origin='simulated'))
        for test_type, results in [('DXA', {'note': 'Synthetic preflight reference; no in-flight follow-up available.'}),
                                   ('Urinalysis', {'note': 'No current assessment. Urine testing and clinician review required.'}),
                                   ('OCT', {'note': 'Synthetic baseline exam. No current in-flight comparison.'})]:
            db.add(MedicalTest(id=f'{uid}-{test_type}', user_id=uid, test_type=test_type, results=results,
                              timestamp=(datetime.now(timezone.utc) - timedelta(days=130)).isoformat(), origin='simulated'))
    db.commit()
