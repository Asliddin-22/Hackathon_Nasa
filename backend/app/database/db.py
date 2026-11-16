from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from ..config import DATABASE_URL

class Base(DeclarativeBase):
    pass

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def configure_sqlite(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA busy_timeout=10000')
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as db:
        yield db


def get_session_factory():
    """Short-lived worker sessions; injectable for isolated API tests."""
    return SessionLocal


def begin_write(db):
    """Reserve SQLite's writer before reads in a short mutating transaction.

    In particular, sync savepoints must have a real outer transaction; legacy
    sqlite transaction control otherwise lets RELEASE commit intermediate work.
    Never call this helper across a provider/network operation.
    """
    if db.new or db.dirty or db.deleted:
        raise RuntimeError('Begin write before mutating session state')
    db.commit()  # Authentication may have opened a read-only session transaction.
    if db.get_bind().dialect.name=='sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')


# Additive columns for databases created before a column existed. create_all()
# adds tables but never alters existing ones; this keeps old demo databases usable.
ADDITIVE_COLUMNS = {'health_measurements': {'device_id': 'VARCHAR'}}

def ensure_additive_columns(bind):
    if bind.dialect.name != 'sqlite':
        return
    with bind.begin() as connection:
        for table, columns in ADDITIVE_COLUMNS.items():
            existing = {row[1] for row in connection.exec_driver_sql(f'PRAGMA table_info({table})')}
            if not existing:
                continue
            for column, kind in columns.items():
                if column not in existing:
                    connection.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {column} {kind}')
