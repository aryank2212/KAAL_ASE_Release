from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    legal_basis: str | None = None


class CaseRead(CaseCreate):
    model_config = ConfigDict(from_attributes=True)

    case_id: UUID
    status: str


class ProfileCreate(BaseModel):
    name: str | None = None
    aliases: list[str] = Field(default_factory=list)


class ProfilePatch(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    known_locations: list[dict] | None = None
    social_profiles: list[dict] | None = None
    images: list[dict] | None = None
    documents: list[dict] | None = None
    timeline: list[dict] | None = None
    relationships: list[dict] | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    source_references: list[dict] | None = None
    review_status: str | None = None
    change_reason: str | None = None


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: UUID
    case_id: UUID
    name: str | None
    aliases: list
    known_locations: list
    social_profiles: list
    images: list
    documents: list
    timeline: list
    relationships: list
    confidence_score: float
    risk_score: float
    source_references: list
    review_status: str
    version: int


class EvidenceCreate(BaseModel):
    filename: str
    media_type: str
    storage_uri: str
    sha256: str
    source_reference_id: UUID | None = None
    size_bytes: int | None = Field(default=None, ge=0)


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: UUID
    case_id: UUID
    source_reference_id: UUID | None
    filename: str
    media_type: str
    storage_uri: str
    sha256: str
    size_bytes: int | None
    ingestion_status: str


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ingestion_job_id: UUID
    case_id: UUID
    evidence_id: UUID
    job_type: str
    status: str
    priority: str
    extractor: str | None
    extractor_version: str | None
    error_message: str | None


class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_id: UUID
    case_id: UUID
    evidence_id: UUID | None
    source_reference_id: UUID | None
    observation_type: str
    value: dict
    confidence: float
    extractor: str
    extractor_version: str
    review_status: str


class SearchRequest(BaseModel):
    case_id: UUID
    query: str
    modes: list[str] = Field(default_factory=lambda: ["natural_language"])
    filters: dict = Field(default_factory=dict)


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=1)
    max_length: int = Field(default=200, ge=50, le=1000)


class SummarizeResponse(BaseModel):
    title: str
    summary: str
    key_facts: list[str]


class ExtractEntitiesRequest(BaseModel):
    text: str = Field(min_length=1)
    evidence_id: UUID | None = None


class EntityItem(BaseModel):
    type: str = "unknown"
    name: str = ""
    confidence: float = 0.5
    context: str | None = None


class EntityExtractionResponse(BaseModel):
    entities: list[EntityItem]


class DetectInconsistenciesRequest(BaseModel):
    text: str = Field(min_length=1)


class InconsistencyItem(BaseModel):
    description: str = ""
    severity: str = "medium"
    text_snippet: str | None = None


class InconsistenciesResponse(BaseModel):
    inconsistencies: list[InconsistencyItem]


class GenerateLeadsRequest(BaseModel):
    case_id: UUID
    context: dict = Field(default_factory=dict)


class LeadItem(BaseModel):
    title: str = ""
    description: str = ""
    priority: str = "medium"
    rationale: str = ""


class LeadsResponse(BaseModel):
    leads: list[LeadItem]


class SentimentRequest(BaseModel):
    text: str = Field(min_length=1)


class SentimentResponse(BaseModel):
    sentiment: str
    confidence: float = Field(ge=0, le=1)
    key_emotional_indicators: list[str]


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1)


class ClassifyResponse(BaseModel):
    category: str
    subcategory: str
    confidence: float = Field(ge=0, le=1)
    tags: list[str]
