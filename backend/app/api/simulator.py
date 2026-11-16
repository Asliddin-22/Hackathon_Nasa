"""Synthetic G2 watch simulator. Every reading it produces is labeled simulated and
travels through the common ingestion + monitoring path used by all sources."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from simulator.scenarios import SCENARIOS, LEGACY_ALIASES, SIMULATED_SYMPTOM, DEVICE_ID, SOURCE, WATCH_BASELINES, sample, sleep_hours, day_start_steps
from ..config import SEED_DEMO
from ..database.db import get_db, begin_write
from ..models.records import Measurement, Baseline, SimulatorState, AuditEvent, now
from ..services.auth import astronaut
from ..services.ingestion import Reading, METRICS, ingest_batch_and_monitor
from ..services.symptoms import record_symptom

router = APIRouter(prefix='/api/simulator')
ScenarioName = Literal['normal', 'elevated_resting_hr', 'reduced_sleep', 'activity_recovery',
                       'reported_symptom', 'concerning_trend', 'nominal', 'trend']


class Tick(BaseModel):
    scenario: ScenarioName | None = None


class ScenarioChange(BaseModel):
    scenario: ScenarioName


def _require_demo():
    if not SEED_DEMO:
        raise HTTPException(403, 'Simulator is disabled')


def _state(db, user_id):
    state = db.get(SimulatorState, user_id)
    if not state:
        state = SimulatorState(user_id=user_id, scenario='normal', step=0, started_at=now(), updated_at=now())
        db.add(state)
        db.flush()
    return state


def _set_scenario(db, state, scenario, actor):
    scenario = LEGACY_ALIASES.get(scenario, scenario)
    if state.scenario != scenario:
        state.scenario, state.step, state.started_at, state.updated_at = scenario, 0, now(), now()
        db.add(AuditEvent(actor=actor, action='simulator.scenario', detail={'scenario': scenario}))
    return state


def _describe(state):
    return {'scenario': state.scenario, 'label': SCENARIOS[state.scenario]['label'], 'step': state.step,
            'started_at': state.started_at, 'updated_at': state.updated_at, 'device_id': DEVICE_ID,
            'provenance': 'simulated',
            'scenarios': [{'id': key, **value} for key, value in SCENARIOS.items()]}


@router.get('/state')
def get_state(user=Depends(astronaut), db: Session = Depends(get_db)):
    _require_demo()
    state = db.get(SimulatorState, user.id) or SimulatorState(user_id=user.id, scenario='normal', step=0, started_at=now(), updated_at=now())
    return _describe(state)


@router.post('/scenario')
def change_scenario(data: ScenarioChange, user=Depends(astronaut), db: Session = Depends(get_db)):
    _require_demo()
    begin_write(db)
    state = _set_scenario(db, _state(db, user.id), data.scenario, user.id)
    db.commit()
    return _describe(state)


@router.post('/tick')
def tick(data: Tick, user=Depends(astronaut), db: Session = Depends(get_db)):
    _require_demo()
    begin_write(db)
    state = _state(db, user.id)
    if data.scenario:
        _set_scenario(db, state, data.scenario, user.id)
    scenario, step = state.scenario, state.step
    base = {b.metric: b.value for b in db.scalars(select(Baseline).where(Baseline.user_id == user.id, Baseline.origin == 'simulated'))}
    for metric, (value, _) in WATCH_BASELINES.items():
        base.setdefault(metric, value)
    timestamp = datetime.now(timezone.utc)
    today = timestamp.date().isoformat()
    latest_steps = db.scalar(select(Measurement).where(Measurement.user_id == user.id, Measurement.metric == 'steps',
                                                      Measurement.origin == 'simulated').order_by(Measurement.timestamp.desc()).limit(1))
    steps_so_far = latest_steps.value if latest_steps and latest_steps.timestamp[:10] == today else day_start_steps(base['steps'], timestamp)
    values = sample(scenario, base, step, steps_so_far, timestamp)
    recent_sleep = db.scalar(select(Measurement.id).where(Measurement.user_id == user.id, Measurement.metric == 'sleep_hours',
                                                          Measurement.origin == 'simulated',
                                                          Measurement.timestamp >= (timestamp - timedelta(hours=20)).isoformat()).limit(1))
    if (scenario == 'reduced_sleep' and step == 0) or not recent_sleep:
        values['sleep_hours'] = sleep_hours(scenario, base['sleep_hours'], step)
    readings = [Reading(id=f'sim-{uuid.uuid4()}', metric=metric, value=value, unit=METRICS[metric][0], timestamp=timestamp,
                        source=SOURCE, device_id=DEVICE_ID, origin='simulated') for metric, value in values.items()]
    result = ingest_batch_and_monitor(db, readings, user.id, user.id, queue=False)
    symptom = None
    if scenario == 'reported_symptom' and step == 0:
        report, _, _ = record_symptom(db, user.id, SIMULATED_SYMPTOM[0], SIMULATED_SYMPTOM[1], False, 'simulated', user.id, queue=False)
        symptom = report.id
    from ..services.earth_sync import queue_snapshot
    event = queue_snapshot(db, user.id)
    state.step, state.updated_at = step + 1, now()
    db.commit()
    return {'inserted': len(result['created']), 'scenario': scenario, 'label': SCENARIOS[scenario]['label'], 'step': step,
            'readings': {r.metric: r.value for r in result['created']}, 'assessments': result['assessments'],
            'watch_alerts': result['watch_alerts'], 'symptom_id': symptom, 'sync_event_id': event.id, 'origin': 'simulated'}
