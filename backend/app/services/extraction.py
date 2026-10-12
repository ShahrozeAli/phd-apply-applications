from __future__ import annotations

import re
from datetime import datetime
from email.utils import parseaddr

from dateutil import parser as dateparser

SALARY_RE = re.compile(
    r"(?:gross\s+monthly\s+salary|monthly\s+stipend|stipend|salary)[^\n]{0,80}?"
    r"(?:€|EUR|SEK|NOK|DKK|CHF|GBP)?\s*([0-9]{1,3}(?:[.,][0-9]{3})+(?:[.,][0-9]{2})?|[0-9]{3,5})"
    r"(?:\s*(?:to|-|–|—)\s*(?:€|EUR)?\s*([0-9]{1,3}(?:[.,][0-9]{3})+|[0-9]{3,5}))?",
    re.I,
)
EURO_RANGE_RE = re.compile(
    r"€\s*([0-9]{1,3}(?:[.,][0-9]{3})+)\s*(?:to|-|–|—)\s*€?\s*([0-9]{1,3}(?:[.,][0-9]{3})+)",
    re.I,
)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
DEADLINE_RE = re.compile(
    r"(?:application deadline|deadline|apply by|closes on|we accept applications until)[:\s]*"
    r"([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4}|[0-9]{1,2}\s+\w+\s+[0-9]{4}|\w+\s+[0-9]{1,2},?\s+[0-9]{4}|"
    r"[0-9]{1,2}\s+\w+\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})",
    re.I,
)


def excerpt(text: str, needle: str, radius: int = 180) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - radius)
    end = min(len(text), idx + len(needle) + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def parse_deadline(text: str) -> datetime | None:
    for match in DEADLINE_RE.finditer(text):
        try:
            value = dateparser.parse(match.group(1), dayfirst=True, fuzzy=False)
            if 2020 <= value.year <= 2035:
                return value.replace(tzinfo=None)
        except (ValueError, OverflowError, TypeError):
            continue
    return None


def parse_salary(text: str) -> dict:
    match = SALARY_RE.search(text) or EURO_RANGE_RE.search(text)
    if not match:
        return {"raw": "", "currency": "", "snippet": ""}
    groups = [g for g in match.groups() if g]
    raw = " - ".join(groups)
    currency = "EUR" if "€" in match.group(0) or "EUR" in match.group(0).upper() else ""
    return {"raw": raw, "currency": currency, "snippet": excerpt(text, match.group(0)[:40])}


def has_employment_contract(text: str) -> bool:
    patterns = [
        r"temporary contract",
        r"employment contract",
        r"doctoral studentship",
        r"collectiv(?:e|e labour) agreement",
        r"tv-l",
        r"scale p",
        r"full-time.{0,40}employment",
        r"employed as a doctoral",
        r"phd candidate is applicable",
        r"ufo profile phd",
    ]
    return any(re.search(p, text, re.I) for p in patterns)


def duration_text(text: str) -> str:
    match = re.search(r"(?:duration of|for the duration of|for)\s+(\d+)\s+years", text, re.I)
    if match:
        return f"{match.group(1)} years"
    match = re.search(r"(\d+)\s*-?\s*year (?:phd|doctoral|full-time)", text, re.I)
    if match:
        return f"{match.group(1)} years"
    return ""


def nationality_flags(text: str) -> dict:
    restricted = []
    if re.search(r"only (?:open to )?(?:eu|eea|european union) (?:citizens|nationals|applicants)", text, re.I):
        restricted.append("EU/EEA only (stated)")
    if re.search(r"german citizenship required|must be a german national", text, re.I):
        restricted.append("German nationality required (stated)")
    if re.search(r"not open to international applicants", text, re.I):
        restricted.append("International applicants excluded (stated)")
    welcomed = bool(
        re.search(
            r"international students? (?:are )?welcome|open to international|non-dutch applicants|30%\s*ruling",
            text,
            re.I,
        )
    )
    msca = bool(re.search(r"marie sk.?odowska-curie|msca doctoral", text, re.I))
    return {"restrictions": restricted, "positive_international_signal": welcomed, "msca": msca}


def extract_emails(text: str) -> list[str]:
    found = []
    for raw in EMAIL_RE.findall(text):
        _, addr = parseaddr(raw)
        addr = addr.lower()
        if addr and "example." not in addr and addr not in found:
            found.append(addr)
    return found[:5]


def required_degree(text: str) -> str:
    if re.search(r"m\.?sc|master(?:'s)? degree|university graduate|master degree or equivalent", text, re.I):
        return "Master's degree or equivalent (stated)"
    if re.search(r"bachelor.?s degree.{0,40}fast-track phd|bsc degree", text, re.I):
        return "Bachelor's may be considered for fast-track (stated)"
    return ""


def english_requirement(text: str) -> str:
    match = re.search(r"(ielts|toefl|cambridge|c1|professional command of english|fluent.{0,20}english)[^\n.]{0,80}", text, re.I)
    if match:
        return match.group(0).strip()
    return ""


def required_documents(text: str) -> str:
    docs = []
    mapping = {
        "cv": r"\bcv\b|curriculum vitae",
        "motivation letter": r"letter of motivation|motivation letter",
        "cover letter": r"cover letter",
        "transcripts": r"transcript",
        "references": r"references|recommendation",
        "research proposal": r"research proposal",
        "publication list": r"publication list",
    }
    for label, pattern in mapping.items():
        if re.search(pattern, text, re.I):
            docs.append(label)
    return ", ".join(docs)


def application_fee(text: str) -> str:
    if re.search(r"no application fee|application is free", text, re.I):
        return "None stated as free"
    if re.search(r"application fee.{0,20}€?\s*\d+", text, re.I):
        match = re.search(r"application fee[^\n.]{0,40}", text, re.I)
        return match.group(0) if match else "Fee mentioned"
    return "UNKNOWN"


def supervisor_name(text: str) -> str:
    match = re.search(
        r"(?:please contact|contact:|supervised by|research group of|assistant professor,)\s*"
        r"((?:dr\.?\s+|prof\.?\s+|professor\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
        text,
    )
    if match:
        return match.group(1).strip()
    return ""
