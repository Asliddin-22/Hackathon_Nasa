from sqlalchemy import ForeignKey,JSON
from sqlalchemy.orm import Mapped,mapped_column
from ..database.db import Base


class ResearchReplay(Base):
    __tablename__='research_replays'
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    subject_id:Mapped[str]=mapped_column(ForeignKey('users.id'),unique=True)
    cursor:Mapped[int]=mapped_column(default=0)


class ResearchSample(Base):
    __tablename__='research_samples'
    measurement_id:Mapped[str]=mapped_column(ForeignKey('health_measurements.id'),primary_key=True)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    sample_index:Mapped[int]
    elapsed_seconds:Mapped[float]
    source_fields:Mapped[dict]=mapped_column(JSON)
