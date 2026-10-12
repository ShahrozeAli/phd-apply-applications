from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    ApplicationRecord,
    DiscoveryRun,
    Notification,
    Opportunity,
    OpportunityClaim,
    SupervisorEmail,
)
from app.services.discovery import reassess_all, run_discovery
from app.services.documents import application_checklist, prepare_package
from app.services.profile_service import get_or_create_profile, profile_dict, update_profile

router = APIRouter()


class ProfileUpdate(BaseModel):
    profile: dict


class DecisionIn(BaseModel):
    decision: str
    notes: str = ""


class ApprovalIn(BaseModel):
    approved: bool
    note: str = ""


def _opp_out(row: Opportunity) -> dict:
    return {
        "id": row.id,
        "position_title": row.position_title,
        "university": row.university,
        "department": row.department,
        "country": row.country,
        "city": row.city,
        "research_field": row.research_field,
        "research_topic": row.research_topic,
        "supervisor": row.supervisor,
        "supervisor_email": row.supervisor_email,
        "official_vacancy_url": row.official_vacancy_url,
        "official_application_url": row.official_application_url,
        "recruitment_reference": row.recruitment_reference,
        "funding_classification": row.funding_classification,
        "tuition_coverage": row.tuition_coverage,
        "salary_or_stipend": row.salary_or_stipend,
        "currency": row.currency,
        "funding_duration": row.funding_duration,
        "contract_details": row.contract_details,
        "international_eligibility": row.international_eligibility,
        "nationality_restrictions": row.nationality_restrictions,
        "required_qualifications": row.required_qualifications,
        "required_documents": row.required_documents,
        "english_requirement": row.english_requirement,
        "application_fee": row.application_fee,
        "application_deadline": row.application_deadline.isoformat() if row.application_deadline else None,
        "submission_method": row.submission_method,
        "eligibility_status": row.eligibility_status,
        "eligibility_reason": row.eligibility_reason,
        "match_score": row.match_score,
        "score_breakdown": json.loads(row.score_breakdown_json or "{}"),
        "relevance_tags": row.relevance_tags,
        "vacancy_status": row.vacancy_status,
        "application_status": row.application_status,
        "user_decision": row.user_decision,
        "queued": row.queued,
        "notes": row.notes,
        "date_discovered": row.date_discovered.isoformat() if row.date_discovered else None,
        "date_last_verified": row.date_last_verified.isoformat() if row.date_last_verified else None,
        "last_change_summary": row.last_change_summary,
        "source": row.source,
    }


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    return profile_dict(get_or_create_profile(db))


@router.put("/profile")
def put_profile(body: ProfileUpdate, db: Session = Depends(get_db)):
    return profile_dict(update_profile(db, body.profile))


@router.post("/discovery/run")
def discover(db: Session = Depends(get_db)):
    return run_discovery(db)


@router.get("/discovery/runs")
def discovery_runs(db: Session = Depends(get_db)):
    rows = db.query(DiscoveryRun).order_by(desc(DiscoveryRun.started_at)).limit(20).all()
    return [
        {
            "id": r.id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "found_count": r.found_count,
            "new_count": r.new_count,
            "updated_count": r.updated_count,
            "error_log": r.error_log,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.get("/opportunities")
def list_opportunities(
    funding: str | None = None,
    eligibility: str | None = None,
    country: str | None = None,
    queued: bool | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Opportunity)
    if funding:
        q = q.filter(Opportunity.funding_classification == funding)
    if eligibility:
        q = q.filter(Opportunity.eligibility_status == eligibility)
    if country:
        q = q.filter(Opportunity.country == country)
    if queued is True:
        q = q.filter(Opportunity.queued.is_(True))
    if status:
        q = q.filter(Opportunity.application_status == status)
    rows = q.order_by(desc(Opportunity.match_score), Opportunity.application_deadline).all()
    return [_opp_out(r) for r in rows]


@router.get("/opportunities/{opp_id}")
def opportunity_detail(opp_id: int, db: Session = Depends(get_db)):
    row = db.get(Opportunity, opp_id)
    if not row:
        raise HTTPException(404, "Not found")
    claims = [
        {
            "claim_type": c.claim_type,
            "claim_value": c.claim_value,
            "evidence_snippet": c.evidence_snippet,
            "source_url": c.source_url,
            "verified": c.verified,
            "is_inference": c.is_inference,
        }
        for c in row.claims
    ]
    return {**_opp_out(row), "claims": claims, "checklist": application_checklist(row)}


@router.post("/opportunities/{opp_id}/decision")
def decide(opp_id: int, body: DecisionIn, db: Session = Depends(get_db)):
    row = db.get(Opportunity, opp_id)
    if not row:
        raise HTTPException(404, "Not found")
    if body.decision not in {"APPROVE", "REJECT", "SAVE", "PRIORITIZE"}:
        raise HTTPException(400, "Invalid decision")
    row.user_decision = body.decision
    if body.notes:
        row.notes = (row.notes + "\n" + body.notes).strip()
    if body.decision == "REJECT":
        row.queued = False
        row.application_status = "REJECTED_BY_USER"
    elif body.decision in {"APPROVE", "PRIORITIZE"} and row.funding_classification == "FULLY FUNDED":
        row.queued = True
        row.application_status = "USER_PRIORITY" if body.decision == "PRIORITIZE" else "APPROVED_FOR_PREP"
    db.commit()
    return _opp_out(row)


@router.post("/opportunities/{opp_id}/prepare-documents")
def prepare_docs(opp_id: int, db: Session = Depends(get_db)):
    try:
        return prepare_package(db, opp_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    rows = db.query(Opportunity).all()
    apps = db.query(ApplicationRecord).all()
    emails = db.query(SupervisorEmail).all()
    now = datetime.utcnow()
    return {
        "total_discovered": len(rows),
        "fully_funded_verified": sum(1 for r in rows if r.funding_classification == "FULLY FUNDED"),
        "profile_matches": sum(1 for r in rows if r.eligibility_status in {"ELIGIBLE", "LIKELY ELIGIBLE"}),
        "ready_for_review": sum(1 for a in apps if a.status == "READY_FOR_REVIEW"),
        "awaiting_approval": sum(1 for a in apps if a.status in {"READY_FOR_REVIEW", "AWAITING_APPROVAL"}),
        "submitted": sum(1 for a in apps if a.status == "SUBMITTED"),
        "upcoming_deadlines": sum(
            1
            for r in rows
            if r.application_deadline and 0 <= (r.application_deadline - now).days <= 30
        ),
        "missing_documents": sum(1 for r in rows if not r.required_documents),
        "supervisor_emails_awaiting": sum(1 for e in emails if e.status == "DRAFTED"),
        "interviews": sum(1 for r in rows if r.application_status == "INTERVIEW"),
        "rejections": sum(1 for r in rows if r.application_status == "REJECTED"),
        "offers": sum(1 for r in rows if r.application_status == "OFFER"),
        "primary_queue": sum(1 for r in rows if r.queued),
    }


@router.get("/notifications")
def notifications(db: Session = Depends(get_db)):
    rows = db.query(Notification).order_by(desc(Notification.created_at)).limit(50).all()
    return [
        {
            "id": n.id,
            "kind": n.kind,
            "title": n.title,
            "body": n.body,
            "opportunity_id": n.opportunity_id,
            "read": n.read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


@router.post("/notifications/{nid}/read")
def read_notification(nid: int, db: Session = Depends(get_db)):
    row = db.get(Notification, nid)
    if not row:
        raise HTTPException(404, "Not found")
    row.read = True
    db.commit()
    return {"ok": True}


@router.get("/approvals")
def approvals(db: Session = Depends(get_db)):
    apps = db.query(ApplicationRecord).filter(ApplicationRecord.status.in_(["READY_FOR_REVIEW", "AWAITING_APPROVAL"])).all()
    emails = db.query(SupervisorEmail).filter(SupervisorEmail.status == "DRAFTED").all()
    return {
        "applications": [
            {
                "id": a.id,
                "opportunity_id": a.opportunity_id,
                "status": a.status,
                "package_folder": a.package_folder,
                "checklist": json.loads(a.checklist_json or "[]"),
            }
            for a in apps
        ],
        "emails": [
            {
                "id": e.id,
                "opportunity_id": e.opportunity_id,
                "supervisor_name": e.supervisor_name,
                "supervisor_email": e.supervisor_email,
                "subject": e.subject,
                "body": e.body,
                "status": e.status,
            }
            for e in emails
        ],
    }


@router.post("/approvals/applications/{app_id}")
def approve_application(app_id: int, body: ApprovalIn, db: Session = Depends(get_db)):
    row = db.get(ApplicationRecord, app_id)
    if not row:
        raise HTTPException(404, "Not found")
    if not body.approved:
        row.status = "REJECTED_BY_USER"
        db.commit()
        return {"status": row.status, "submitted": False}
    row.status = "APPROVED_NOT_SUBMITTED"
    row.approved_at = datetime.utcnow()
    db.commit()
    return {
        "status": row.status,
        "submitted": False,
        "message": "Approval recorded. The bot will not submit this application automatically. Complete submission on the official portal after you confirm the preview.",
    }


@router.post("/approvals/emails/{email_id}")
def approve_email(email_id: int, body: ApprovalIn, db: Session = Depends(get_db)):
    row = db.get(SupervisorEmail, email_id)
    if not row:
        raise HTTPException(404, "Not found")
    if not body.approved:
        row.status = "REJECTED_BY_USER"
    else:
        row.status = "APPROVED_NOT_SENT"
        row.approved_at = datetime.utcnow()
    db.commit()
    return {
        "status": row.status,
        "sent": False,
        "message": "Email drafts are never sent unless you separately enable a narrow email automation workflow.",
    }


@router.post("/reassess")
def reassess(db: Session = Depends(get_db)):
    count = reassess_all(db)
    return {"reassessed": count}


@router.get("/settings")
def get_settings():
    from app.config import settings as cfg

    return {
        "llm_provider": cfg.llm_provider,
        "daily_discovery_hour": cfg.daily_discovery_hour,
        "auto_submit_applications": False,
        "auto_send_emails": False,
        "database_backend": "sqlite" if cfg.database_url.startswith("sqlite") else "postgresql",
    }
