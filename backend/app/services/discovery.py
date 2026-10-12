from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import EXCLUDE_TITLE_HINTS, PHD_TITLE_HINTS, SEARCH_QUERIES, TARGET_FIELDS
from app.models import DiscoveryRun, Notification, Opportunity, OpportunityClaim, OpportunityEvent
from app.services.eligibility import assess_eligibility
from app.services.extraction import (
    application_fee,
    excerpt,
    extract_emails,
    parse_deadline,
    required_documents,
    supervisor_name,
)
from app.services.funding import classify_funding
from app.services.http_client import polite_get
from app.services.profile_service import get_or_create_profile, profile_dict
from app.services.ranking import primary_queue_ok, score_opportunity

PRIORITY_OFFICIAL_URLS = [
    "https://werkenbij.uva.nl/en/vacancies/phd-candidate-in-ai-and-hardware-security-netherlands-15552",
    "https://www.academictransfer.com/en/jobs/364643/phd-candidate-in-ai-and-hardware-security",
    "https://euraxess.ec.europa.eu/jobs/453839",
]

EURAXESS_SEARCH = (
    "https://euraxess.ec.europa.eu/jobs/search?keywords={q}"
    "&f%5B0%5D=researcher_profile%3Afirst_stage_researcher_r1"
)
ACADEMICTRANSFER_SEARCH = "https://www.academictransfer.com/en/search/?q={q}&on=phd"


def unique_key(url: str, institution: str, title: str, ref: str) -> str:
    basis = "|".join(
        [
            _canonical_url(url),
            (institution or "").strip().lower(),
            (title or "").strip().lower(),
            (ref or "").strip().lower(),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _canonical_url(url: str) -> str:
    return (url or "").split("?")[0].rstrip("/").lower()


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def looks_like_phd(title: str, text: str) -> bool:
    blob = f"{title} {text[:1500]}".lower()
    if any(h in blob for h in EXCLUDE_TITLE_HINTS) and "phd" not in title.lower():
        return False
    return any(h in blob for h in PHD_TITLE_HINTS)


def field_relevant(title: str, text: str) -> bool:
    blob = f"{title} {text[:4000]}".lower()
    return any(field in blob for field in TARGET_FIELDS)


def parse_euraxess_search(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        match = re.search(r"/jobs/(\d+)", href)
        if match:
            url = f"https://euraxess.ec.europa.eu/jobs/{match.group(1)}"
            if url not in urls:
                urls.append(url)
    return urls


def parse_academictransfer_search(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if re.search(r"/en/jobs/\d+/", href):
            url = urljoin("https://www.academictransfer.com", href).split("?")[0]
            if url not in urls:
                urls.append(url)
    return urls


def parse_listing_metadata(url: str, html: str, text: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    if not title:
        title = soup.title.get_text(" ", strip=True) if soup.title else url

    university = ""
    country = ""
    city = ""
    field = ""
    apply_url = ""
    ref = ""

    if "euraxess.ec.europa.eu" in url:
        def _after(label: str) -> str:
            node = soup.find(string=re.compile(rf"^{label}$", re.I))
            if node and node.parent and node.parent.find_next():
                return node.parent.find_next().get_text(" ", strip=True)
            return ""

        university = _after("Organisation/Company") or _after("Company/Institute")
        country = _after("Country")
        city = _after("City")
        field = _after("Research Field")
        deadline_raw = _after("Application Deadline")
        apply = soup.find("a", href=True, string=re.compile("apply", re.I))
        website_label = soup.find(string=re.compile(r"^Website$", re.I))
        if website_label and website_label.parent:
            nxt = website_label.parent.find_next("a")
            if nxt and nxt.get("href"):
                apply_url = nxt["href"]
        if apply and apply.get("href"):
            apply_url = apply["href"]
        ref = url.rstrip("/").split("/")[-1]
        extra = {
            "deadline_hint": deadline_raw,
        }
    else:
        extra = {}
        apply_url = url
        if "uva.nl" in url or "academictransfer.com" in url:
            university = "University of Amsterdam"
            country = "Netherlands"
            city = "Amsterdam"
            field = "Computer science"
            ref_match = re.search(r"(15552|\d{5,})", text)
            ref = ref_match.group(1) if ref_match else ""

    emails = extract_emails(text)
    supervisor = supervisor_name(text)
    deadline = parse_deadline(text)
    if not deadline and extra.get("deadline_hint"):
        deadline = parse_deadline("Application Deadline: " + extra["deadline_hint"])

    loc_match = re.search(r"Country\s*:\s*([A-Za-z ]+)", text)
    if loc_match and not country:
        country = loc_match.group(1).strip()
    city_match = re.search(r"City\s*:\s*([A-Za-z\- ]+)", text)
    if city_match and not city:
        city = city_match.group(1).strip()
    org_match = re.search(r"Organisation/Company\s*:\s*([^\n]+)", text)
    if org_match and not university:
        university = org_match.group(1).strip()[:300]

    return {
        "position_title": title[:500],
        "university": (university or "")[:300],
        "department": "",
        "country": (country or "")[:120],
        "city": (city or "")[:120],
        "research_field": (field or "")[:300],
        "research_topic": excerpt(text, "PhD")[:2000],
        "supervisor": supervisor,
        "supervisor_email": emails[0] if emails else "",
        "official_vacancy_url": url,
        "official_application_url": apply_url or url,
        "recruitment_reference": ref,
        "required_documents": required_documents(text),
        "application_fee": application_fee(text),
        "application_deadline": deadline,
        "submission_method": "Official portal / listed application URL",
        "raw_text": text[:50000],
    }


def harvest_urls() -> tuple[list[str], list[str]]:
    urls: list[str] = []
    errors: list[str] = []
    for url in PRIORITY_OFFICIAL_URLS:
        if url not in urls:
            urls.append(url)

    queries = SEARCH_QUERIES[:4]
    for query in queries:
        search_url = EURAXESS_SEARCH.format(q=quote_plus(query))
        try:
            html = polite_get(search_url).text
            for item in parse_euraxess_search(html)[: settings.discovery_max_detail_pages]:
                if item not in urls:
                    urls.append(item)
        except Exception as exc:
            errors.append(f"EURAXESS search failed for '{query}': {exc}")

        at_url = ACADEMICTRANSFER_SEARCH.format(q=quote_plus(query.split()[0] + " PhD computer science"))
        try:
            html = polite_get(at_url).text
            for item in parse_academictransfer_search(html)[:12]:
                if item not in urls:
                    urls.append(item)
        except Exception as exc:
            errors.append(f"AcademicTransfer search failed: {exc}")

    return urls[: settings.discovery_max_detail_pages + len(PRIORITY_OFFICIAL_URLS)], errors


def upsert_opportunity(db: Session, parsed: dict, profile: dict, source: str) -> tuple[Opportunity, bool]:
    key = unique_key(
        parsed["official_vacancy_url"],
        parsed["university"],
        parsed["position_title"],
        parsed["recruitment_reference"],
    )
    existing = db.query(Opportunity).filter(Opportunity.unique_key == key).first()
    if existing is None and parsed.get("recruitment_reference") and parsed.get("university"):
        existing = (
            db.query(Opportunity)
            .filter(
                Opportunity.recruitment_reference == parsed["recruitment_reference"],
                Opportunity.university == parsed["university"],
            )
            .first()
        )
    created = existing is None
    row = existing or Opportunity(unique_key=key, official_vacancy_url=parsed["official_vacancy_url"])
    if existing:
        _track_changes(db, existing, parsed)
    for field in (
        "position_title",
        "university",
        "department",
        "country",
        "city",
        "research_field",
        "research_topic",
        "supervisor",
        "supervisor_email",
        "official_vacancy_url",
        "official_application_url",
        "recruitment_reference",
        "required_documents",
        "application_fee",
        "application_deadline",
        "submission_method",
        "raw_text",
    ):
        setattr(row, field, parsed.get(field) or getattr(row, field, "") or (None if field == "application_deadline" else ""))

    row.source = source
    funding = classify_funding(parsed["raw_text"], parsed.get("country") or "", parsed["official_vacancy_url"])
    row.funding_classification = funding["classification"]
    row.tuition_coverage = funding["tuition_coverage"]
    row.salary_or_stipend = funding["salary_or_stipend"]
    row.currency = funding["currency"]
    row.funding_duration = funding["funding_duration"]
    row.contract_details = funding["contract_details"]
    row.notes = funding["notes"]

    eligibility = assess_eligibility(profile, parsed["raw_text"], parsed.get("country") or "")
    row.eligibility_status = eligibility["status"]
    row.eligibility_reason = eligibility["reason"]
    row.international_eligibility = eligibility["international_eligibility"]
    row.nationality_restrictions = eligibility["nationality_restrictions"]
    row.required_qualifications = eligibility["required_qualifications"]
    row.english_requirement = eligibility["english_requirement"]

    scored = score_opportunity(
        profile,
        {
            "eligibility_status": row.eligibility_status,
            "funding_classification": row.funding_classification,
            "international_eligibility": row.international_eligibility,
            "application_deadline": row.application_deadline,
            "application_fee": row.application_fee,
            "research_field": row.research_field,
        },
        parsed["raw_text"],
    )
    row.match_score = scored["score"]
    row.score_breakdown_json = json.dumps(scored["breakdown"])
    row.relevance_tags = ", ".join(scored["tags"])
    row.date_last_verified = datetime.utcnow()
    if row.application_deadline and row.application_deadline < datetime.utcnow():
        row.vacancy_status = "EXPIRED"
    else:
        row.vacancy_status = "OPEN"

    row.queued = primary_queue_ok(
        {
            "funding_classification": row.funding_classification,
            "eligibility_status": row.eligibility_status,
            "application_deadline": row.application_deadline,
        }
    )
    if row.queued and row.application_status == "DISCOVERED":
        row.application_status = "PRIMARY_QUEUE"

    if created:
        db.add(row)
        db.flush()
    db.query(OpportunityClaim).filter(OpportunityClaim.opportunity_id == row.id).delete()
    for claim in funding["claims"]:
        db.add(OpportunityClaim(opportunity_id=row.id, **claim))
    db.add(
        OpportunityClaim(
            opportunity_id=row.id,
            claim_type="source",
            claim_value="Official listing captured",
            evidence_snippet=parsed["position_title"],
            source_url=parsed["official_vacancy_url"],
            verified=True,
            is_inference=False,
        )
    )
    return row, created


def _track_changes(db: Session, existing: Opportunity, parsed: dict) -> None:
    watched = {
        "application_deadline": str(existing.application_deadline),
        "position_title": existing.position_title,
        "official_application_url": existing.official_application_url,
    }
    incoming = {
        "application_deadline": str(parsed.get("application_deadline")),
        "position_title": parsed.get("position_title") or "",
        "official_application_url": parsed.get("official_application_url") or "",
    }
    changes = []
    for field, old in watched.items():
        new = incoming[field]
        if old != new:
            db.add(
                OpportunityEvent(
                    opportunity_id=existing.id,
                    field_name=field,
                    old_value=old,
                    new_value=new,
                )
            )
            changes.append(field)
    if changes:
        existing.last_change_summary = "Updated: " + ", ".join(changes)


def run_discovery(db: Session, source: str = "all") -> dict:
    run = DiscoveryRun(source=source, status="RUNNING")
    db.add(run)
    db.commit()
    db.refresh(run)

    profile_row = get_or_create_profile(db)
    profile = profile_dict(profile_row)["profile"]
    found = 0
    created_n = 0
    updated_n = 0
    errors: list[str] = []

    urls, harvest_errors = harvest_urls()
    errors.extend(harvest_errors)

    for url in urls:
        try:
            response = polite_get(url)
            html = response.text
            text = _visible_text(html)
            title_guess = BeautifulSoup(html, "lxml").find("h1")
            title = title_guess.get_text(" ", strip=True) if title_guess else url
            if not looks_like_phd(title, text):
                continue
            if not field_relevant(title, text) and url not in PRIORITY_OFFICIAL_URLS:
                continue
            parsed = parse_listing_metadata(str(response.url), html, text)
            src = "euraxess"
            if "uva.nl" in url:
                src = "university_official"
            elif "academictransfer.com" in url:
                src = "academictransfer"
            row, created = upsert_opportunity(db, parsed, profile, src)
            found += 1
            if created:
                created_n += 1
                if row.queued and row.match_score >= 50:
                    db.add(
                        Notification(
                            kind="high_match",
                            title=f"High-match funded PhD: {row.position_title}",
                            body=f"{row.university} · {row.country} · score {row.match_score}",
                            opportunity_id=row.id,
                        )
                    )
            else:
                updated_n += 1
            db.commit()
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            db.rollback()

    _deadline_notifications(db)
    run.finished_at = datetime.utcnow()
    run.status = "COMPLETED" if not errors else "COMPLETED_WITH_ERRORS"
    run.found_count = found
    run.new_count = created_n
    run.updated_count = updated_n
    run.error_log = "\n".join(errors)[:8000]
    run.notes = f"Inspected {len(urls)} URLs from official portals."
    db.commit()
    return {
        "run_id": run.id,
        "found": found,
        "new": created_n,
        "updated": updated_n,
        "errors": errors,
        "inspected_urls": urls,
    }


def _deadline_notifications(db: Session) -> None:
    now = datetime.utcnow()
    rows = db.query(Opportunity).filter(Opportunity.application_deadline.isnot(None)).all()
    for row in rows:
        days = (row.application_deadline - now).days
        if days in (30, 14, 7, 3):
            db.add(
                Notification(
                    kind="deadline",
                    title=f"Deadline in {days} days: {row.position_title}",
                    body=row.official_vacancy_url,
                    opportunity_id=row.id,
                )
            )


def reassess_all(db: Session) -> int:
    profile = profile_dict(get_or_create_profile(db))["profile"]
    rows = db.query(Opportunity).all()
    for row in rows:
        parsed = {
            "official_vacancy_url": row.official_vacancy_url,
            "university": row.university,
            "position_title": row.position_title,
            "recruitment_reference": row.recruitment_reference,
            "department": row.department,
            "country": row.country,
            "city": row.city,
            "research_field": row.research_field,
            "research_topic": row.research_topic,
            "supervisor": row.supervisor,
            "supervisor_email": row.supervisor_email,
            "official_application_url": row.official_application_url,
            "required_documents": row.required_documents,
            "application_fee": row.application_fee,
            "application_deadline": row.application_deadline,
            "submission_method": row.submission_method,
            "raw_text": row.raw_text,
        }
        upsert_opportunity(db, parsed, profile, row.source)
    db.commit()
    return len(rows)
