from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, default=0)
    missing_fields_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("unique_key", name="uq_opportunity_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unique_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), default="euraxess")
    position_title: Mapped[str] = mapped_column(String(500), nullable=False)
    university: Mapped[str] = mapped_column(String(300), default="")
    department: Mapped[str] = mapped_column(String(300), default="")
    country: Mapped[str] = mapped_column(String(120), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    research_field: Mapped[str] = mapped_column(String(300), default="")
    research_topic: Mapped[str] = mapped_column(Text, default="")
    supervisor: Mapped[str] = mapped_column(String(300), default="")
    supervisor_email: Mapped[str] = mapped_column(String(300), default="")
    official_vacancy_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    official_application_url: Mapped[str] = mapped_column(String(1000), default="")
    recruitment_reference: Mapped[str] = mapped_column(String(200), default="")
    funding_classification: Mapped[str] = mapped_column(String(40), default="UNVERIFIED")
    tuition_coverage: Mapped[str] = mapped_column(String(80), default="UNKNOWN")
    salary_or_stipend: Mapped[str] = mapped_column(String(300), default="")
    currency: Mapped[str] = mapped_column(String(16), default="")
    funding_duration: Mapped[str] = mapped_column(String(200), default="")
    contract_details: Mapped[str] = mapped_column(Text, default="")
    international_eligibility: Mapped[str] = mapped_column(String(80), default="UNSTATED")
    nationality_restrictions: Mapped[str] = mapped_column(Text, default="")
    required_qualifications: Mapped[str] = mapped_column(Text, default="")
    required_documents: Mapped[str] = mapped_column(Text, default="")
    english_requirement: Mapped[str] = mapped_column(Text, default="")
    application_fee: Mapped[str] = mapped_column(String(120), default="UNKNOWN")
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expected_start_date: Mapped[str] = mapped_column(String(120), default="")
    submission_method: Mapped[str] = mapped_column(String(200), default="")
    eligibility_status: Mapped[str] = mapped_column(String(40), default="NEEDS VERIFICATION")
    eligibility_reason: Mapped[str] = mapped_column(Text, default="")
    match_score: Mapped[float] = mapped_column(Float, default=0)
    score_breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    relevance_tags: Mapped[str] = mapped_column(Text, default="")
    vacancy_status: Mapped[str] = mapped_column(String(40), default="OPEN")
    application_status: Mapped[str] = mapped_column(String(40), default="DISCOVERED")
    user_decision: Mapped[str] = mapped_column(String(40), default="NONE")
    queued: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    date_discovered: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    date_last_verified: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_change_summary: Mapped[str] = mapped_column(Text, default="")

    claims: Mapped[list["OpportunityClaim"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")
    events: Mapped[list["OpportunityEvent"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")
    applications: Mapped[list["ApplicationRecord"]] = relationship(back_populates="opportunity")
    emails: Mapped[list["SupervisorEmail"]] = relationship(back_populates="opportunity")


class OpportunityClaim(Base):
    __tablename__ = "opportunity_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), index=True)
    claim_type: Mapped[str] = mapped_column(String(80))
    claim_value: Mapped[str] = mapped_column(Text)
    evidence_snippet: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(1000))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_inference: Mapped[bool] = mapped_column(Boolean, default=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    opportunity: Mapped[Opportunity] = relationship(back_populates="claims")


class OpportunityEvent(Base):
    __tablename__ = "opportunity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(80))
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    opportunity: Mapped[Opportunity] = relationship(back_populates="events")


class ApplicationRecord(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), index=True)
    package_folder: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(40), default="DRAFT")
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmation_reference: Mapped[str] = mapped_column(String(200), default="")
    confirmation_message: Mapped[str] = mapped_column(Text, default="")
    checklist_json: Mapped[str] = mapped_column(Text, default="[]")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    opportunity: Mapped[Opportunity] = relationship(back_populates="applications")


class SupervisorEmail(Base):
    __tablename__ = "supervisor_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), index=True)
    supervisor_name: Mapped[str] = mapped_column(String(300), default="")
    supervisor_email: Mapped[str] = mapped_column(String(300), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="DRAFTED")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    opportunity: Mapped[Opportunity] = relationship(back_populates="emails")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    opportunity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="RUNNING")
    source: Mapped[str] = mapped_column(String(80), default="all")
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    value: Mapped[str] = mapped_column(Text, default="")
