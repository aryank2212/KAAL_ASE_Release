from datetime import datetime
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Case(Base):
    __tablename__ = "cases"

    case_id: Mapped[PyUUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    legal_basis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SourceReference(Base):
    __tablename__ = "source_references"

    source_reference_id: Mapped[PyUUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(Uuid(), ForeignKey("cases.case_id"), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str | None] = mapped_column(Text)
    policy_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Profile(Base):
    __tablename__ = "profiles"

    profile_id: Mapped[PyUUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(Uuid(), ForeignKey("cases.case_id"), nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    known_locations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    social_profiles: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    images: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    documents: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    timeline: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    relationships: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    source_references: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, default="draft", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProfileVersion(Base):
    __tablename__ = "profile_versions"

    profile_version_id: Mapped[PyUUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    profile_id: Mapped[PyUUID] = mapped_column(Uuid(), ForeignKey("profiles.profile_id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[PyUUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(Uuid(), ForeignKey("cases.case_id"), nullable=False)
    source_reference_id: Mapped[PyUUID | None] = mapped_column(Uuid(), ForeignKey("source_references.source_reference_id"))
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    chain_of_custody: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    ingestion_status: Mapped[str] = mapped_column(Text, default="registered", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    ingestion_job_id: Mapped[PyUUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(Uuid(), ForeignKey("cases.case_id"), nullable=False)
    evidence_id: Mapped[PyUUID] = mapped_column(Uuid(), ForeignKey("evidence.evidence_id"), nullable=False)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="queued", nullable=False)
    priority: Mapped[str] = mapped_column(Text, default="normal", nullable=False)
    extractor: Mapped[str | None] = mapped_column(Text)
    extractor_version: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Observation(Base):
    __tablename__ = "observations"

    observation_id: Mapped[PyUUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(Uuid(), ForeignKey("cases.case_id"), nullable=False)
    evidence_id: Mapped[PyUUID | None] = mapped_column(Uuid(), ForeignKey("evidence.evidence_id"))
    source_reference_id: Mapped[PyUUID | None] = mapped_column(Uuid(), ForeignKey("source_references.source_reference_id"))
    observation_type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    extractor: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_version: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, default="candidate", nullable=False)
    supersedes_observation_id: Mapped[PyUUID | None] = mapped_column(Uuid(), ForeignKey("observations.observation_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[PyUUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    request_id: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(Text)
    case_id: Mapped[PyUUID | None] = mapped_column(Uuid(), ForeignKey("cases.case_id"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
