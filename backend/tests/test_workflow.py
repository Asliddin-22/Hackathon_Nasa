from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import select
from backend.app.models.records import SyncEvent, Review
from backend.app.services.earth_sync import queue_snapshot


def make_due(client):
    with client.sessions() as db:
        for event in db.scalars(select(SyncEvent).where(SyncEvent.status == 'queued')):
            event.available_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.commit()


def test_offline_roundtrip_and_stale_ground(client, astronaut, doctor):
    original = client.get('/api/doctors/crew', headers=doctor).json()[0]
    client.patch('/api/mission/context', headers=astronaut, json={'online': False})
    report = client.post('/api/symptoms', headers=astronaut, json={'description': 'Synthetic dizziness', 'severity': 5}).json()
    alert_id = report['alert']['id']
    make_due(client)
    assert client.post('/api/sync', headers=astronaut).json()['status'] == 'offline'
    ground = client.get('/api/doctors/crew', headers=doctor).json()[0]
    assert ground['captured_at'] == original['captured_at']
    assert alert_id not in {a['id'] for a in ground['snapshot']['alerts']}
    review = {'id': str(uuid.uuid4()), 'user_id': 'astro-01', 'alert_id': alert_id,
              'assessment': 'Demo review of reported dizziness', 'feedback': 'Please send the context and collection times for the repeat measurements.'}
    assert client.post('/api/doctor-reviews', headers=doctor, json=review).status_code == 409
    client.patch('/api/mission/context', headers=astronaut, json={'online': True, 'delay_seconds': 0})
    assert client.post('/api/sync', headers=astronaut).json()['delivered'] >= 1
    result = client.post('/api/doctor-reviews', headers=doctor, json=review)
    assert result.status_code == 201
    assert client.post('/api/doctor-reviews', headers=doctor, json=review).json()['id'] == review['id']
    assert client.get('/api/astronauts/astro-01/health', headers=astronaut).json()['reviews'] == []
    assert client.post(f'/api/doctor-reviews/{review["id"]}/acknowledge', headers=astronaut).status_code == 409
    client.post('/api/sync', headers=doctor)
    onboard = client.get('/api/astronauts/astro-01/health', headers=astronaut).json()
    assert onboard['reviews'][0]['feedback'] == review['feedback']
    response = client.post(f'/api/doctor-reviews/{review["id"]}/acknowledge', headers=astronaut)
    assert response.json()['acknowledged_at']
    assert not client.get('/api/doctors/reviews', headers=doctor).json()[0]['acknowledged_at']
    client.post('/api/sync', headers=astronaut)
    ground = client.get('/api/doctors/crew', headers=doctor).json()[0]
    assert ground['snapshot']['reviews'][0]['acknowledged_at']
    assert client.post('/api/sync', headers=astronaut).json()['delivered'] == 0


def test_delay_and_encryption(client, astronaut, doctor):
    report = client.post('/api/symptoms', headers=astronaut, json={'description': 'Private synthetic symptom', 'severity': 3}).json()
    assert client.post('/api/sync', headers=astronaut).json()['delivered'] == 0
    with client.sessions() as db:
        event = db.scalar(select(SyncEvent).where(SyncEvent.status == 'queued'))
        assert set(event.payload) == {'ciphertext'}
        assert 'Private synthetic symptom' not in str(event.payload)
    make_due(client)
    assert client.post('/api/sync', headers=doctor).json()['delivered'] == 1
    assert client.get('/api/doctors/crew', headers=astronaut).status_code == 403
    assert client.post('/api/doctor-reviews', headers=astronaut, json={}).status_code == 403


def test_failed_message_retries(client, astronaut):
    with client.sessions() as db:
        event = queue_snapshot(db, 'astro-01', immediate=True)
        event.payload = {'ciphertext': 'tampered'}
        db.commit()
        event_id = event.id
    assert client.post('/api/sync', headers=astronaut).json()['delivered'] == 0
    with client.sessions() as db:
        event = db.get(SyncEvent, event_id)
        assert event.status == 'queued' and event.retry_count == 1


def test_simulator_is_persisted(client, astronaut):
    assert client.post('/api/simulator/tick', headers=astronaut, json={'scenario': 'trend'}).json()['inserted'] == 4
    assert len(client.get('/api/astronauts/astro-01/history', headers=astronaut).json()) == 184
