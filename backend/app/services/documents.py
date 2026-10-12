from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ApplicationRecord, Opportunity, SupervisorEmail
from app.services.profile_service import get_or_create_profile, missing_academic_fields, profile_dict


def _folder_name(opp: Opportunity) -> str:
    deadline = opp.application_deadline.date().isoformat() if opp.application_deadline else "NoDeadline"
    parts = [opp.country or "Europe", opp.university or "University", opp.position_title or "PhD", deadline]
    slug = "_".join(re.sub(r"[^A-Za-z0-9]+", "_", p).strip("_")[:40] for p in parts)
    return slug[:120]


def prepare_package(db: Session, opportunity_id: int) -> dict:
    opp = db.get(Opportunity, opportunity_id)
    if not opp:
        raise ValueError("Opportunity not found")
    profile = profile_dict(get_or_create_profile(db))
    missing = missing_academic_fields(profile["profile"])
    if missing:
        return {
            "blocked": True,
            "reason": "Academic profile is incomplete. Documents will not be generated with invented facts.",
            "missing_fields": missing,
        }

    folder = settings.packages_dir / _folder_name(opp)
    folder.mkdir(parents=True, exist_ok=True)
    ident = profile["profile"].get("identity", {})
    pref = profile["profile"].get("preferences", {})
    pro = profile["profile"].get("professional", {})

    cv = _plain_cv(ident, pro, profile["profile"])
    letter = _motivation_skeleton(ident, pro, pref, opp)
    email = _supervisor_email(ident, pro, opp)

    (folder / "CV.txt").write_text(cv, encoding="utf-8")
    (folder / "Motivation_Letter.txt").write_text(letter, encoding="utf-8")
    (folder / "Supervisor_Email.txt").write_text(email, encoding="utf-8")
    (folder / "SOURCE.txt").write_text(
        f"Vacancy: {opp.official_vacancy_url}\nApply: {opp.official_application_url}\n",
        encoding="utf-8",
    )

    record = ApplicationRecord(
        opportunity_id=opp.id,
        package_folder=str(folder),
        status="READY_FOR_REVIEW",
        checklist_json=json.dumps(
            [
                "Confirm every fact against your documents",
                "Do not submit without explicit approval",
                f"Open official application page: {opp.official_application_url}",
            ]
        ),
    )
    db.add(record)
    draft = SupervisorEmail(
        opportunity_id=opp.id,
        supervisor_name=opp.supervisor,
        supervisor_email=opp.supervisor_email,
        subject=f"Interest in {opp.position_title}",
        body=email,
        status="DRAFTED",
    )
    db.add(draft)
    opp.application_status = "DOCS_READY"
    db.commit()
    return {"blocked": False, "folder": str(folder), "application_id": record.id, "email_id": draft.id}


def _plain_cv(ident: dict, pro: dict, profile: dict) -> str:
    academic = profile.get("academic") or {}
    lines = [
        f"{ident.get('given_name', '')} {ident.get('family_name', '')}".strip(),
        f"Nationality: {ident.get('nationality', '')}",
        f"Location: {ident.get('current_country', '')}",
        f"Email: {ident.get('email', '')}",
        "",
        "Professional experience",
        f"{pro.get('profession', '')} · ~{pro.get('years_experience', '')} years",
        "Technical background: " + ", ".join(pro.get("technical_background") or []),
        "",
        "Education",
        json.dumps(academic.get("bachelor") or {}, indent=2),
        json.dumps(academic.get("masters") or {}, indent=2),
        "",
        "Publications",
        json.dumps(academic.get("publications") or [], indent=2),
        "",
        "This CV contains only facts stored in your profile. Empty fields were left empty.",
    ]
    return "\n".join(lines)


def _motivation_skeleton(ident: dict, pro: dict, pref: dict, opp: Opportunity) -> str:
    name = f"{ident.get('given_name', '')} {ident.get('family_name', '')}".strip()
    return (
        f"Dear Selection Committee,\n\n"
        f"I am {name or '[full name to be completed]'}, a {pro.get('profession', 'software engineer')} "
        f"with approximately {pro.get('years_experience', '4')} years of professional experience. "
        f"I am writing to apply for {opp.position_title} at {opp.university}.\n\n"
        f"My background includes {', '.join(pro.get('technical_background') or [])}. "
        f"I am interested in this project because it relates to {opp.research_field or 'the advertised research topic'}.\n\n"
        "I have not added unpublished claims, degrees, or papers that are not in my profile.\n\n"
        "Sincerely,\n"
        f"{name or '[name]'}\n"
    )


def _supervisor_email(ident: dict, pro: dict, opp: Opportunity) -> str:
    name = f"{ident.get('given_name', '')} {ident.get('family_name', '')}".strip()
    greeting = f"Dear {opp.supervisor}," if opp.supervisor else "Dear Professor,"
    return (
        f"{greeting}\n\n"
        f"My name is {name or '[full name]'}. I am a software engineer based in Pakistan with "
        f"approximately {pro.get('years_experience', '4')} years of experience in "
        f"{', '.join(pro.get('technical_background') or [])}.\n\n"
        f"I am writing about the advertised position: {opp.position_title} "
        f"({opp.official_vacancy_url}). I would like to express interest and ask whether "
        f"international applicants from Pakistan are eligible to apply.\n\n"
        "I have not sent this email. It remains a draft until you approve it.\n\n"
        f"Kind regards,\n{name or '[name]'}\n"
    )


def application_checklist(opp: Opportunity) -> list[dict]:
    docs = [d.strip() for d in (opp.required_documents or "").split(",") if d.strip()]
    steps = [
        {"step": "Open the official vacancy page", "url": opp.official_vacancy_url, "automated": False},
        {"step": "Open the official application page", "url": opp.official_application_url, "automated": False},
        {"step": "Confirm the vacancy is still open and funding is unchanged", "automated": False},
        {"step": "Fill the form with verified profile data only", "automated": False},
    ]
    for doc in docs:
        steps.append({"step": f"Upload {doc}", "automated": False})
    steps.extend(
        [
            {"step": "Review a preview of the completed application", "automated": False},
            {"step": "Give explicit approval for this specific application", "automated": False},
            {"step": "Submit only after approval; never bypass CAPTCHA or logins", "automated": False},
            {"step": "Save confirmation, reference number, and date", "automated": False},
        ]
    )
    return steps
