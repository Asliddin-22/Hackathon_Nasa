from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database.db import Base, engine, SessionLocal
from .models import records  # register tables
from .models import knowledge
from .config import SEED_DEMO
from .services.seed import seed
from .api.core import router as core_router

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if SEED_DEMO:
        with SessionLocal() as db:
            seed(db)
            from .services.earth_sync import bootstrap
            bootstrap(db)
    with SessionLocal() as db:
        from .services.assistant_jobs import interrupt_pending
        interrupt_pending(db)
        db.commit()
    # Knowledge corruption must not prevent essential onboard monitoring.
    with SessionLocal() as db:
        try:
            from .services.knowledge import ingest_corpus
            ingest_corpus(db)
            db.commit()
        except Exception:
            db.rollback()
            import logging
            logging.getLogger(__name__).warning('Reference index unavailable; onboard monitoring remains active.')
    yield

app = FastAPI(title='GravityGuard', version='0.1.0', description='Synthetic-data hackathon prototype. No validated medical predictions.', lifespan=lifespan)
app.include_router(core_router)

from .api.analysis import router as analysis_router
app.include_router(analysis_router)

from .api.sync import router as sync_router
from .api.doctors import router as doctors_router
from .api.simulator import router as simulator_router
app.include_router(sync_router)
app.include_router(doctors_router)
app.include_router(simulator_router)
from .api.knowledge import router as knowledge_router
app.include_router(knowledge_router)
from .api.assistant import router as assistant_router
app.include_router(assistant_router)

# The built dashboard can be served onboard by the same process as the API.
# Vite remains the development server; production assets require npm run build.
from fastapi.staticfiles import StaticFiles
from .config import ROOT
frontend_dist = ROOT / 'frontend' / 'dist'
if (frontend_dist / 'index.html').exists():
    app.mount('/', StaticFiles(directory=frontend_dist, html=True), name='dashboard')
