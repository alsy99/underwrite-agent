import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class CaseRecord(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    vertical: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    case_file_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documents: Mapped[list["DocumentRecord"]] = relationship(back_populates="case")
    audit_events: Mapped[list["AuditEventRecord"]] = relationship(back_populates="case")


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    doc_type: Mapped[str] = mapped_column(String(64), default="unknown")
    storage_key: Mapped[str] = mapped_column(String(1024))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["CaseRecord"] = relationship(back_populates="documents")
    chunks: Mapped[list["ChunkRecord"]] = relationship(back_populates="document")


class ChunkRecord(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    document: Mapped["DocumentRecord"] = relationship(back_populates="chunks")


class PolicyDocumentRecord(Base):
    __tablename__ = "policy_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    policy_version: Mapped[str] = mapped_column(String(64))
    effective_date: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["PolicyChunkRecord"]] = relationship(back_populates="policy")


class PolicyChunkRecord(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    policy_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("policy_documents.id"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    policy: Mapped["PolicyDocumentRecord"] = relationship(back_populates="chunks")


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    inputs_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outputs_json: Mapped[dict] = mapped_column("outputs", JSONB, default=dict)
    citations_json: Mapped[list] = mapped_column("citations", JSONB, default=list)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    case: Mapped["CaseRecord"] = relationship(back_populates="audit_events")
