from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.app.database.db import Base
from backend.app.models.records import Measurement, Protocol
from backend.app.services.seed import seed
from backend.app.services.ingestion import Reading, ingest


def test_sqlite_survives_reopen(tmp_path):
    url = f'sqlite:///{tmp_path / "health.db"}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db)
        reading=Reading(id='persisted',user_id='astro-01',metric='resting_hr',value=71,unit='bpm',
                        timestamp=datetime.now(timezone.utc),source='Synthetic persistence test',origin='simulated')
        ingest(db,reading,'astro-01')
        db.commit()
    engine.dispose()
    engine = create_engine(url)
    with Session(engine) as db:
        assert db.get(Measurement,'persisted').value == 71
        protocol=db.get(Protocol,'demo-measurement-review')
        assert protocol.approval_status=='demo_only_not_clinically_approved'
    engine.dispose()
