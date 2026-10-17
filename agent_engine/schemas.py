from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

MIN_CONFIDENCE = Decimal("0.80")
MAX_EVENT_MESSAGE = 300


def truncate_message(text: str, limit: int = MAX_EVENT_MESSAGE) -> str:
    """Event messages are at most `limit` characters; longer text is cut and ends with '...'."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


PER_COMPANY_CAP = 14

Orgnr = Annotated[str, StringConstraints(pattern=r"^[0-9]{9}$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def exact_number(value):
    if isinstance(value, (Decimal, int, str)):
        return value
    raise ValueError("amounts must be Decimal, int or numeric text")


Amount = Annotated[Decimal, BeforeValidator(exact_number)]


class FactKey(StrEnum):
    PRODUCTS = "products"
    MISSION = "mission"
    CUSTOMERS = "customers"
    MARKETS = "markets"
    SCALE = "scale"
    HISTORY = "history"
    LEADERSHIP = "leadership"
    OTHER_KEY_FACT = "other_key_fact"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PASS1_RUNNING = "pass1_running"
    PASS1_COMPLETE = "pass1_complete"
    PASS2_RUNNING = "pass2_running"
    PUBLISHED = "published"
    REGISTRY_ONLY = "registry_only"
    NOT_FOUND = "not_found"
    REGISTRY_UNAVAILABLE = "registry_unavailable"
    NOT_PROCESSED_BUDGET = "not_processed_budget"
    FAILED = "failed"


class Flag(StrEnum):
    WEBSITE_UNREACHABLE = "website_unreachable"
    TIME_LIMIT_REGISTRY_ONLY = "time_limit_registry_only"
    REQUEST_BRAKE = "request_brake"
    LLM_SKIPPED = "llm_skipped"
    FINANCIALS_UNAVAILABLE = "financials_unavailable"
    NOT_PROCESSED_BUDGET = "not_processed_budget"
    CONFLICTS_WITH_REGISTRY = "conflicts_with_registry"
    TIME_RELATIVE = "time_relative"
    SELF_REPORTED = "self_reported"
    QUOTE_TRANSLATED = "quote_translated"
    QUOTE_NOT_FOUND = "quote_not_found"


class RejectionReason(StrEnum):
    SCHEMA_INVALID = "schema_invalid"
    IDENTITY_FAILED = "identity_failed"
    QUOTE_NOT_FOUND = "quote_not_found"
    QUOTE_TRANSLATED = "quote_translated"
    VALUE_UNSUPPORTED = "value_unsupported"
    DIGIT_UNSUPPORTED = "digit_unsupported"
    NAME_UNSUPPORTED = "name_unsupported"
    MONEY_BLOCKED = "money_blocked"
    BELOW_THRESHOLD = "below_threshold"
    LLM_INVALID_JSON = "llm_invalid_json"
    FETCH_FAILED = "fetch_failed"
    CONFLICTS_WITH_REGISTRY = "conflicts_with_registry"


JobMode = Literal["daily_test", "baseline_batch", "pilot"]
JobStatus = Literal[
    "queued", "pass1_running", "pass1_complete", "pass2_running", "completed",
    "stopped_budget", "stopped_time", "stopped_storage", "failed", "cancelled",
]
StopReason = Literal[
    "none", "completed", "request_brake", "soft_cap_only", "time_hard_stop", "kill_switch",
    "daily_request_limit", "daily_cost_limit", "baseline_request_cap", "baseline_cost_limit",
    "operator_interrupt", "storage_failure",
]
ValidationStage = Literal["fetch", "schema", "identity", "quote", "value", "money", "registry_clash", "confidence"]
ValidationDecision = Literal["publish", "reject", "abstain"]
MoneyDecision = Literal["not_money", "harmless_passed", "blocked", "registry_source"]
FactMethod = Literal["registry", "llm_verified", "structured_fallback"]
FactTag = Literal["time_relative", "self_reported"]
FinancialMetric = Literal["revenue", "operating_result", "net_result", "total_assets", "equity"]
FinancialMethod = Literal["registry", "structured_fallback", "unavailable"]
VerificationStatus = Literal["verified", "abstained", "unavailable"]
RegistryStatus = Literal["active", "deleted", "bankrupt", "dissolved", "unknown"]
RoleType = Literal["board_member", "chair", "deputy_chair", "ceo", "other"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fact(Strict):
    key: FactKey
    value: str = Field(min_length=1, max_length=300)
    value_no: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1, max_length=600)
    source_url: str


class Extraction(Strict):
    facts: list[Fact] = Field(default_factory=list, max_length=20)


class PublishedFact(Strict):
    fact_id: UUID
    orgnr: Orgnr
    key: FactKey
    value: str
    value_no: str
    quote: str | None = None
    registry_json_path: str | None = None
    method: FactMethod
    source_id: UUID
    source_url: str
    retrieved_at: datetime
    sha256: Sha256
    as_of: datetime
    tags: list[FactTag] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)
    identity_score: Decimal
    q: Decimal
    v: Decimal
    g: Decimal
    s: Decimal
    f: Decimal
    confidence: Decimal
    publication_status: Literal["published", "superseded"] = "published"
    validation_id: UUID
    created_at: datetime

    @model_validator(mode="after")
    def publication_rules(self):
        if self.publication_status == "published" and self.confidence < MIN_CONFIDENCE:
            raise ValueError("published facts need a confidence of at least 0.80")
        if self.method == "registry" and (self.quote is not None or self.registry_json_path is None):
            raise ValueError("registry facts need a JSON path and no quote")
        if self.method == "llm_verified" and not self.quote:
            raise ValueError("AI facts need an exact quote")
        return self


class RejectionRecord(Strict):
    rejection_id: UUID
    job_id: UUID
    orgnr: Orgnr
    candidate_id: UUID | None = None
    source_id: UUID | None = None
    source_url: str | None = None
    rejected_value: str | None = Field(default=None, max_length=300)
    validation_stage: ValidationStage
    reason_code: RejectionReason
    diagnostic: dict[str, Any] = Field(default_factory=dict)
    rejected_at: datetime


class VChecks(Strict):
    key_words_ok: bool
    digits_ok: bool
    names_ok: bool


class ValidationResult(Strict):
    validation_id: UUID
    candidate_id: UUID
    schema_ok: bool
    g_identity_ok: bool
    q_raw: Decimal = Field(ge=0, le=1)
    q: Decimal = Field(ge=0, le=1)
    q_language_mismatch: bool = False
    quote_start: int | None = Field(default=None, ge=0)
    quote_end: int | None = Field(default=None, ge=0)
    v: Decimal = Field(ge=0, le=1)
    v_checks: VChecks
    money_filter: MoneyDecision
    registry_clash: bool = False
    confidence: Decimal = Field(ge=0, le=1)
    decision: ValidationDecision
    first_failed_stage: ValidationStage | None = None
    reason_code: RejectionReason | None = None
    repair_attempted: bool = False
    decided_at: datetime

    @model_validator(mode="after")
    def check_result(self):
        if (self.quote_start is None) != (self.quote_end is None):
            raise ValueError("quote_start and quote_end must be set together")
        if (self.q > 0) != (self.quote_start is not None):
            raise ValueError("quote_start and quote_end are None when Q is 0 and set otherwise")
        if self.quote_start is not None and self.quote_end <= self.quote_start:
            raise ValueError("quote_end must be greater than quote_start")
        if self.decision == "reject" and (self.first_failed_stage is None or self.reason_code is None):
            raise ValueError("a rejected result needs first_failed_stage and reason_code")
        return self


class FinancialRecord(Strict):
    financial_id: UUID
    orgnr: Orgnr
    metric: FinancialMetric
    fiscal_year: int = Field(ge=1900, le=2100)
    period_start: str | None = None
    period_end: str | None = None
    amount: Amount | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    unit_scale: Literal[1, 1000, 1000000] | None = None
    amount_as_printed: str | None = None
    amount_base: Amount | None = None
    method: FinancialMethod
    source_url: str
    source_ref: str
    org_match: bool
    unit_verified: bool
    retrieved_at: datetime
    sha256: Sha256 | None = None
    unavailable_reason: str | None = None
    verification_status: VerificationStatus

    @model_validator(mode="after")
    def money_rules(self):
        if self.amount is None:
            if self.unavailable_reason is None:
                raise ValueError("a missing amount needs an unavailable_reason")
        else:
            parts = (self.currency, self.unit_scale, self.amount_as_printed, self.amount_base)
            if any(part is None for part in parts):
                raise ValueError("an amount needs currency, unit_scale, printed text and amount_base")
            if self.amount_base != self.amount * self.unit_scale:
                raise ValueError("amount_base must equal amount x unit_scale")
        plan_b_published = self.method == "structured_fallback" and self.verification_status == "verified"
        if plan_b_published and not (self.org_match and self.unit_verified):
            raise ValueError("Plan B values need a matching org number and a verified unit")
        return self


class Company(Strict):
    orgnr: Orgnr
    is_subunit: bool = False
    parent_orgnr: Orgnr | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    active_status: RegistryStatus | None = None


class CompanyRole(Strict):
    name: str
    role: RoleType


class Dossier(Strict):
    dossier_id: str
    orgnr: Orgnr
    legal_name: str | None = None
    org_form: str | None = None
    registry_status: RegistryStatus
    website_url: str | None = None
    website_official_domain: str | None = None
    processing_status: ProcessingStatus
    flags: list[Flag] = Field(default_factory=list)
    verified_fact_count: int = Field(0, ge=0)
    registry_fields: dict[str, Any] | None = None
    roles: list[CompanyRole] = Field(default_factory=list)
    financial_summary: list[FinancialRecord] = Field(default_factory=list)
    published_fact_ids: list[str] = Field(default_factory=list)
    data_freshness: datetime
    created_at: datetime
    updated_at: datetime
    job_id: UUID
    schema_version: Literal["1.0"] = "1.0"

    @model_validator(mode="after")
    def one_dossier_per_company(self):
        if self.dossier_id != self.orgnr:
            raise ValueError("dossier_id must equal orgnr")
        return self


def latest_retrieval(times: Iterable[datetime]) -> datetime:
    """data_freshness of a dossier: the latest Retrieval Date of any input."""
    return max(times)


def count_verified_facts(facts: Iterable[PublishedFact]) -> int:
    """verified_fact_count counts published AI facts only; registry fields are reported apart."""
    return sum(1 for fact in facts if fact.method == "llm_verified" and fact.publication_status == "published")


class BudgetLedger(Strict):
    job_id: UUID
    total_outbound_requests: int = Field(0, ge=0, le=2000)
    requests_by_kind: dict[str, int] = Field(default_factory=dict)
    soft_cap: int = 1700
    brake: int = 1950
    brake_tripped: bool = False
    soft_cap_reached: bool = False
    per_company_requests: dict[str, int] = Field(default_factory=dict)
    plan_b_used_count: int = Field(0, ge=0)
    llm_calls: int = Field(0, ge=0)
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    tokens_estimated: bool = False
    estimated_cost_usd: Decimal = Decimal("0")
    cost_limit_usd: Decimal = Decimal("10")
    elapsed_seconds: int = Field(0, ge=0)
    kill_switch_tripped: bool = False
    kill_switch_projection_min: Decimal | None = None
    version: int = Field(1, ge=1)
    updated_at: datetime

    @field_validator("per_company_requests")
    @classmethod
    def within_company_cap(cls, value: dict[str, int]) -> dict[str, int]:
        if any(count > PER_COMPANY_CAP for count in value.values()):
            raise ValueError(f"no company may use more than {PER_COMPANY_CAP} requests")
        return value


class ProcessingJob(Strict):
    job_id: UUID
    idempotency_key: str | None = None
    request_hash: Sha256
    mode: JobMode
    status: JobStatus = "queued"
    current_pass: Literal[0, 1, 2] = 0
    submitted_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    input_count: int = Field(ge=0)
    rejected_input_count: int = Field(0, ge=0)
    completed_count: int = Field(0, ge=0)
    failed_count: int = Field(0, ge=0)
    registry_only_count: int = Field(0, ge=0)
    stop_reason: StopReason | None = None
    config_hash: Sha256
    code_version: str = Field(min_length=7)
    checkpoint_ref: str | None = None
    batch_index: int | None = Field(default=None, ge=1, le=10)
    batch_count: int | None = Field(default=None, ge=1, le=10)
    label: str | None = None


class JobCompany(Strict):
    job_id: UUID
    orgnr: Orgnr
    status: ProcessingStatus = ProcessingStatus.PENDING
    pass1_status: Literal["pending", "complete", "not_found", "failed", "not_processed_budget"] = "pending"
    pass2_status: Literal[
        "pending", "complete", "skipped_no_website", "failed", "time_limit", "request_brake", "not_started"
    ] = "pending"
    flags: list[Flag] = Field(default_factory=list)
    requests_used: int = Field(0, ge=0, le=PER_COMPANY_CAP)
    llm_calls_used: int = Field(0, ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_class: str | None = None


class RequestCounts(Strict):
    total: int = Field(ge=0, le=2000)
    by_kind: dict[str, int] = Field(default_factory=dict)


class RunFlags(Strict):
    soft_cap_reached: bool
    brake_tripped: bool
    kill_switch_tripped: bool
    plan_a_outage_detected: bool


class RunReport(Strict):
    job_id: UUID
    report_version: Literal["1.0"] = "1.0"
    mode: JobMode
    started_at: datetime
    ended_at: datetime
    duration_seconds: int = Field(ge=0)
    company_count: int = Field(ge=0)
    outcomes: dict[str, int]
    requests: RequestCounts
    llm_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    tokens_estimated: bool
    estimated_cost_usd: Decimal
    cost_limit_usd: Decimal
    time_limit_min: int | None = None
    stop_reason: StopReason
    flags: RunFlags
    plan_b_used_count: int = Field(ge=0)
    rejections_by_reason: dict[RejectionReason, int] = Field(default_factory=dict)
    checkpoint: dict[str, Any] | None = None
    config_hash: Sha256
    code_version: str = Field(min_length=7)
