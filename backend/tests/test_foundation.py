from datetime import datetime, timezone

def reading(**changes):
    return {'id': 'test-1', 'user_id': 'astro-01', 'metric': 'resting_hr', 'value': 75,
            'unit': 'bpm', 'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'Test simulator', 'origin': 'simulated', 'quality': 'valid', **changes}

def test_auth_and_isolation(client, astronaut, doctor):
    assert client.get('/api/astronauts/astro-01/health').status_code == 401
    assert client.get('/api/astronauts/astro-02/health', headers=astronaut).status_code == 403
    assert client.get('/api/astronauts/astro-01/health', headers=doctor).status_code == 403
    assert client.post('/api/auth/login', json={'username': 'doctor', 'password': 'wrong'}).status_code == 401

def test_seed_and_roundtrip(client, astronaut):
    data = client.get('/api/astronauts/astro-01/health', headers=astronaut).json()
    assert len(data['measurements']) == 300
    assert all(r['origin'] == 'simulated' for r in data['measurements'])
    payload = reading()
    assert client.post('/api/measurements', headers=astronaut, json=payload).json()['created']
    assert not client.post('/api/measurements', headers=astronaut, json=payload).json()['created']
    assert client.post('/api/measurements', headers=astronaut, json={**payload, 'value': 88}).status_code == 409
    history = client.get('/api/astronauts/astro-01/history', headers=astronaut).json()
    assert len(history) == 301

def test_invalid_readings(client, astronaut):
    for changes in [{'value': -1}, {'unit': 'ms'}, {'timestamp': '2026-01-01T00:00:00'},
                    {'origin': 'unknown'}, {'metric': 'bone_density'}, {'timestamp': '2099-01-01T00:00:00Z'}]:
        assert client.post('/api/measurements', headers=astronaut, json=reading(**changes)).status_code == 422

def test_logout_revokes_token(client, astronaut):
    assert client.post('/api/auth/logout', headers=astronaut).status_code == 200
    assert client.get('/api/auth/me', headers=astronaut).status_code == 401
