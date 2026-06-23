CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('system_admin', 'case_manager', 'analyst', 'reviewer', 'auditor')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    legal_basis TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'paused', 'closed', 'archived')),
    retention_until DATE,
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE case_members (
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    case_role TEXT NOT NULL CHECK (case_role IN ('owner', 'analyst', 'reviewer', 'auditor')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (case_id, user_id)
);

CREATE TABLE source_references (
    source_reference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    publisher TEXT,
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    collector_user_id UUID REFERENCES users(user_id),
    content_hash TEXT,
    attribution TEXT,
    policy_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    name TEXT,
    aliases JSONB NOT NULL DEFAULT '[]',
    known_locations JSONB NOT NULL DEFAULT '[]',
    social_profiles JSONB NOT NULL DEFAULT '[]',
    images JSONB NOT NULL DEFAULT '[]',
    documents JSONB NOT NULL DEFAULT '[]',
    timeline JSONB NOT NULL DEFAULT '[]',
    relationships JSONB NOT NULL DEFAULT '[]',
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    risk_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    source_references JSONB NOT NULL DEFAULT '[]',
    review_status TEXT NOT NULL DEFAULT 'draft' CHECK (review_status IN ('draft', 'candidate', 'reviewed', 'rejected')),
    version INTEGER NOT NULL DEFAULT 1,
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE profile_versions (
    profile_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    profile_snapshot JSONB NOT NULL,
    change_reason TEXT,
    changed_by UUID REFERENCES users(user_id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (profile_id, version)
);

CREATE TABLE evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    source_reference_id UUID REFERENCES source_references(source_reference_id),
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes BIGINT,
    chain_of_custody JSONB NOT NULL DEFAULT '[]',
    ingestion_status TEXT NOT NULL DEFAULT 'registered' CHECK (ingestion_status IN ('registered', 'queued', 'processing', 'complete', 'failed')),
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (case_id, sha256)
);

CREATE TABLE ingestion_jobs (
    ingestion_job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    evidence_id UUID NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'complete', 'failed', 'cancelled')),
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
    extractor TEXT,
    extractor_version TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE TABLE observations (
    observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    evidence_id UUID REFERENCES evidence(evidence_id) ON DELETE SET NULL,
    source_reference_id UUID REFERENCES source_references(source_reference_id),
    observation_type TEXT NOT NULL,
    value JSONB NOT NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    extractor TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'candidate' CHECK (review_status IN ('candidate', 'accepted', 'rejected', 'superseded')),
    supersedes_observation_id UUID REFERENCES observations(observation_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE timeline_events (
    timeline_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    profile_id UUID REFERENCES profiles(profile_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    event_time TIMESTAMPTZ,
    event_time_end TIMESTAMPTZ,
    location JSONB,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    source_reference_id UUID REFERENCES source_references(source_reference_id),
    review_status TEXT NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    subject_type TEXT NOT NULL,
    subject_id UUID NOT NULL,
    predicate TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id UUID NOT NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    source_reference_id UUID REFERENCES source_references(source_reference_id),
    review_status TEXT NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE analysis_runs (
    analysis_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    analysis_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_template_id TEXT NOT NULL,
    input_refs JSONB NOT NULL DEFAULT '[]',
    output JSONB NOT NULL,
    confidence NUMERIC(5,4),
    review_status TEXT NOT NULL DEFAULT 'draft' CHECK (review_status IN ('draft', 'approved', 'rejected')),
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_events (
    audit_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id TEXT,
    actor_user_id UUID REFERENCES users(user_id),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    case_id UUID REFERENCES cases(case_id),
    source_ip INET,
    user_agent TEXT,
    before_hash TEXT,
    after_hash TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_profiles_case_id ON profiles(case_id);
CREATE INDEX idx_evidence_case_id ON evidence(case_id);
CREATE INDEX idx_ingestion_jobs_evidence_id ON ingestion_jobs(evidence_id);
CREATE INDEX idx_ingestion_jobs_status ON ingestion_jobs(status);
CREATE INDEX idx_observations_case_id ON observations(case_id);
CREATE INDEX idx_observations_type ON observations(observation_type);
CREATE INDEX idx_timeline_case_time ON timeline_events(case_id, event_time);
CREATE INDEX idx_relationships_case_id ON relationships(case_id);
CREATE INDEX idx_audit_case_created ON audit_events(case_id, created_at);
CREATE INDEX idx_source_case_id ON source_references(case_id);
