from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from ..database.db import Base

class KnowledgeDocument(Base):
    __tablename__ = 'knowledge_documents'
    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    url: Mapped[str]
    publisher: Mapped[str]
    system: Mapped[str]
    category: Mapped[str]
    content_hash: Mapped[str]
    metadata_hash: Mapped[str]
    provenance: Mapped[dict] = mapped_column(JSON)

class KnowledgeChunk(Base):
    __tablename__ = 'knowledge_chunks'
    id: Mapped[str] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('knowledge_documents.id'), index=True)
    heading: Mapped[str]
    text: Mapped[str]
    ordinal: Mapped[int]

class AssistantMessage(Base):
    __tablename__ = 'assistant_messages'
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    question: Mapped[str]
    request_hash: Mapped[str]
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]

class AssistantThread(Base):
    __tablename__ = 'assistant_threads'
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    created_at: Mapped[str]

class AssistantTurn(Base):
    __tablename__ = 'assistant_turns'
    message_id: Mapped[str] = mapped_column(ForeignKey('assistant_messages.id'),primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey('assistant_threads.id'),index=True)
    parent_message_id: Mapped[str | None] = mapped_column(ForeignKey('assistant_messages.id'),nullable=True)

class AssistantJob(Base):
    __tablename__ = 'assistant_jobs'
    message_id: Mapped[str] = mapped_column(ForeignKey('assistant_messages.id'),primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'),index=True)
    status: Mapped[str]
    request: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[str]

class GroundAssistantMessage(Base):
    __tablename__ = 'ground_assistant_messages'
    message_id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[str]
    received_at: Mapped[str]
