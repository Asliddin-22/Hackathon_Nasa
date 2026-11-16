import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database.db import Base, get_db, get_session_factory
from backend.app.services.seed import seed
from backend.app.services.earth_sync import bootstrap

@pytest.fixture
def client():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        seed(db)
        bootstrap(db)
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_session_factory] = lambda:sessions
    # Deliberately do not run lifespan: tests own an isolated database.
    client = TestClient(app)
    client.sessions = sessions
    yield client
    app.dependency_overrides.clear()
    engine.dispose()

@pytest.fixture
def astronaut(client):
    data = client.post('/api/auth/login', json={'username': 'astronaut', 'password': 'demo-orbit-2026'}).json()
    return {'Authorization': f'Bearer {data["token"]}'}

@pytest.fixture
def doctor(client):
    data = client.post('/api/auth/login', json={'username': 'doctor', 'password': 'demo-orbit-2026'}).json()
    return {'Authorization': f'Bearer {data["token"]}'}
