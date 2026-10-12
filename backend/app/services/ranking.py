from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.constants import TARGET_FIELDS


def field_relevance(text: str, research_field: str, interests: list[str]) -> tuple[float, list[str]]:
    blob = f"{text} {research_field}".lower()
    tags = [field for field in TARGET_FIELDS if field in blob]
    for interest in interests:
        if interest and interest.lower() in blob and interest.lower() not in tags:
            tags.append(interest.lower())
    score = min(20, len(set(tags)) * 4)
    if any(k in blob for k in ("software", "web", "javascript", "health", "iot", "informatic")):
        score = min(20, score + 4)
    return score, tags[:12]


def score_opportunity(profile: dict, opp: dict, text: str) -> dict:
    interests = profile.get("preferences", {}).get("research_interests") or []
    relevance, tags = field_relevance(text, opp.get("research_field") or "", interests)

    academic = 8
    if opp.get("eligibility_status") == "ELIGIBLE":
        academic = 25
    elif opp.get("eligibility_status") == "LIKELY ELIGIBLE":
        academic = 18
    elif opp.get("eligibility_status") == "NEEDS VERIFICATION":
        academic = 10
    elif opp.get("eligibility_status") == "NOT ELIGIBLE":
        academic = 0

    funding = {
        "FULLY FUNDED": 20,
        "CONDITIONALLY FUNDED": 8,
        "PARTIALLY FUNDED": 5,
        "UNVERIFIED": 4,
    }.get(opp.get("funding_classification"), 0)

    interest_score = 8
    if tags:
        interest_score = min(15, 7 + 2 * len(tags))
    preferred = [t.lower() for t in (profile.get("preferences", {}).get("target_fields") or [])]
    if any(p in " ".join(tags) for p in preferred if p):
        interest_score = min(15, interest_score + 3)

    intl = {
        "POSITIVE_SIGNAL": 8,
        "MSCA_MOBILITY_CHECK": 6,
        "UNSTATED": 4,
        "RESTRICTED": 0,
    }.get(opp.get("international_eligibility"), 4)
    if opp.get("application_fee") not in ("UNKNOWN", "") and "fee" in (opp.get("application_fee") or "").lower() and "free" not in (opp.get("application_fee") or "").lower():
        intl = max(0, intl - 3)

    feasibility = 4
    deadline = opp.get("application_deadline")
    if isinstance(deadline, datetime):
        remaining = deadline - datetime.utcnow()
        if remaining < timedelta(days=0):
            feasibility = 0
        elif remaining <= timedelta(days=7):
            feasibility = 5
        elif remaining <= timedelta(days=30):
            feasibility = 8
        else:
            feasibility = 10
    if (opp.get("application_fee") or "").lower().startswith("none"):
        feasibility = min(10, feasibility + 1)

    total = academic + relevance + funding + interest_score + intl + feasibility
    breakdown = {
        "academic_eligibility": academic,
        "background_relevance": relevance,
        "funding_completeness": funding,
        "research_interest_fit": interest_score,
        "international_eligibility": intl,
        "application_feasibility": feasibility,
        "total": total,
    }
    return {"score": min(100, total), "breakdown": breakdown, "tags": tags}


def primary_queue_ok(opp: dict) -> bool:
    if opp.get("funding_classification") != "FULLY FUNDED":
        return False
    if opp.get("eligibility_status") == "NOT ELIGIBLE":
        return False
    deadline = opp.get("application_deadline")
    if isinstance(deadline, datetime) and deadline < datetime.utcnow():
        return False
    return True
