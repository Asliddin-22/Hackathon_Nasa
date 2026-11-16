import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "gravityguard.db"}')
DEMO_PASSWORD = os.getenv('DEMO_PASSWORD', 'demo-orbit-2026')
SEED_DEMO = os.getenv('SEED_DEMO', 'true').lower() == 'true'
