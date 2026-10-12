from __future__ import annotations

import re

from app.constants import EMPLOYED_PHD_COUNTRIES, LIVING_COST_ESTIMATES
from app.services.extraction import duration_text, excerpt, has_employment_contract, parse_salary


def _to_number(raw: str) -> float | None:
    cleaned = re.sub(r"[^\d]", "", raw.split("-")[0])
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def classify_funding(text: str, country: str, source_url: str) -> dict:
    salary = parse_salary(text)
    employed = has_employment_contract(text)
    duration = duration_text(text)
    country_key = (country or "").lower()
    tuition_explicit_waived = bool(
        re.search(r"tuition.{0,40}(waiv|cover|free|not charged)|no tuition", text, re.I)
    )
    tuition_charged = bool(re.search(r"tuition fee.{0,40}\d+", text, re.I))
    external_condition = bool(
        re.search(
            r"subject to.{0,40}funding|external funding|apply for a scholarship separately|"
            r"conditional on.{0,30}award|self-fund",
            text,
            re.I,
        )
    )
    fellowship_claim = bool(re.search(r"full financial coverage|fully funded|dedicated fellowship", text, re.I))

    claims = []
    classification = "UNVERIFIED"
    tuition = "UNKNOWN"
    notes = []

    if salary["raw"]:
        claims.append(
            {
                "claim_type": "salary_or_stipend",
                "claim_value": salary["raw"],
                "evidence_snippet": salary["snippet"],
                "source_url": source_url,
                "verified": True,
                "is_inference": False,
            }
        )
    if employed:
        claims.append(
            {
                "claim_type": "contract",
                "claim_value": "Employment or doctoral contract language present",
                "evidence_snippet": excerpt(text, "contract") or excerpt(text, "employment"),
                "source_url": source_url,
                "verified": True,
                "is_inference": False,
            }
        )
    if duration:
        claims.append(
            {
                "claim_type": "funding_duration",
                "claim_value": duration,
                "evidence_snippet": excerpt(text, duration.split()[0] + " years") or duration,
                "source_url": source_url,
                "verified": True,
                "is_inference": False,
            }
        )

    monthly = _to_number(salary["raw"]) if salary["raw"] else None
    living = LIVING_COST_ESTIMATES.get(country_key)
    living_ok = None
    if monthly and living:
        living_ok = monthly >= living[0]
        notes.append(
            f"Living-cost comparison is an ESTIMATE ({living[0]}-{living[1]} EUR/month band), not a vacancy fact."
        )

    if tuition_explicit_waived:
        tuition = "EXPLICITLY_WAIVED"
    elif tuition_charged:
        tuition = "FEES_STATED"
    elif employed and country_key in EMPLOYED_PHD_COUNTRIES:
        tuition = "INFERRED_EMPLOYMENT_NO_TUITION"
        notes.append(
            "Tuition waiver inferred from employed-PhD convention in this country; the listing did not state a waiver."
        )
        claims.append(
            {
                "claim_type": "tuition",
                "claim_value": tuition,
                "evidence_snippet": "Not stated on the listing; inferred from employed doctoral position practice.",
                "source_url": source_url,
                "verified": False,
                "is_inference": True,
            }
        )

    if external_condition and not (employed and monthly and monthly >= 2000):
        classification = "CONDITIONALLY FUNDED"
        notes.append("Listing mentions additional funding conditions or external awards.")
    elif fellowship_claim and monthly and monthly < 2000 and not employed:
        classification = "CONDITIONALLY FUNDED"
        notes.append(
            "Fellowship language is present, but the documented stipend is modest and/or the listing also points to extra funding routes."
        )
    elif employed and monthly and duration and tuition in ("EXPLICITLY_WAIVED", "INFERRED_EMPLOYMENT_NO_TUITION"):
        if living_ok is False:
            classification = "PARTIALLY FUNDED"
            notes.append("Documented salary appears below a conservative living-cost estimate for this country.")
        else:
            classification = "FULLY FUNDED"
    elif salary["raw"] and duration and tuition_explicit_waived:
        classification = "FULLY FUNDED"
    elif salary["raw"] and not duration:
        classification = "UNVERIFIED"
        notes.append("A stipend or salary is mentioned, but funding duration is not clearly specified.")
    elif "scholarship" in text.lower() and not salary["raw"]:
        classification = "UNVERIFIED"
        notes.append("The word scholarship appears, but no stipend or salary amount was extracted from the official text.")

    health = bool(re.search(r"health insurance|social security|holiday allowance", text, re.I))
    if health:
        claims.append(
            {
                "claim_type": "benefits",
                "claim_value": "Health insurance, social security, or standard employee allowances mentioned",
                "evidence_snippet": excerpt(text, "allowance") or excerpt(text, "insurance"),
                "source_url": source_url,
                "verified": True,
                "is_inference": False,
            }
        )

    return {
        "classification": classification,
        "tuition_coverage": tuition,
        "salary_or_stipend": salary["raw"],
        "currency": salary["currency"],
        "funding_duration": duration,
        "contract_details": "Employment-style doctoral contract indicated" if employed else "",
        "notes": " ".join(notes),
        "claims": claims,
    }
