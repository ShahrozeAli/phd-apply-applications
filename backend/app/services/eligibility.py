from __future__ import annotations

from app.services.extraction import english_requirement, nationality_flags, required_degree
from app.services.profile_service import missing_academic_fields


def assess_eligibility(profile: dict, text: str, country: str) -> dict:
    missing = missing_academic_fields(profile)
    flags = nationality_flags(text)
    degree = required_degree(text)
    english = english_requirement(text)
    reasons = []
    status = "NEEDS VERIFICATION"

    if flags["restrictions"]:
        status = "NOT ELIGIBLE"
        reasons.append("Nationality restriction stated: " + "; ".join(flags["restrictions"]))
        return {
            "status": status,
            "reason": " ".join(reasons),
            "international_eligibility": "RESTRICTED",
            "nationality_restrictions": "; ".join(flags["restrictions"]),
            "required_qualifications": degree,
            "english_requirement": english,
        }

    international = "UNSTATED"
    if flags["positive_international_signal"]:
        international = "POSITIVE_SIGNAL"
        reasons.append("Listing contains a positive signal for non-local applicants; this is not a formal eligibility guarantee.")
    else:
        reasons.append(
            "The listing does not explicitly confirm that applicants from Pakistan are eligible. Do not treat this as acceptance."
        )

    if flags["msca"]:
        reasons.append(
            "MSCA mobility rules may apply (residence in the host country). This must be checked on the official MSCA/doctoral-network page."
        )
        international = "MSCA_MOBILITY_CHECK"

    if degree:
        reasons.append(f"Degree requirement extracted: {degree}.")
        masters = (profile.get("academic") or {}).get("masters") or {}
        highest = (profile.get("academic") or {}).get("highest_completed_degree")
        if not highest and masters.get("status") in (None, "", "unknown"):
            reasons.append("Your highest degree and Master's status are not configured, so academic eligibility cannot be confirmed.")
            status = "NEEDS VERIFICATION"

    if english:
        reasons.append(f"English requirement extracted: {english}.")
        eng = (profile.get("academic") or {}).get("english") or {}
        if not eng.get("test_type") and not eng.get("overall_score") and not eng.get("medium_of_instruction_waiver"):
            reasons.append("Your English proficiency evidence is not configured.")
            status = "NEEDS VERIFICATION"

    if missing:
        labels = ", ".join(item["label"] for item in missing[:6])
        reasons.append(f"Profile incomplete ({len(missing)} fields). Still needed before a final eligibility decision: {labels}.")
        status = "NEEDS VERIFICATION"
    elif status != "NOT ELIGIBLE":
        if international in ("POSITIVE_SIGNAL",) and degree:
            status = "LIKELY ELIGIBLE"
            reasons.append("Profile fields are present and no nationality ban was found; remaining fit still depends on supervisor review.")
        else:
            status = "NEEDS VERIFICATION"
            reasons.append("No nationality ban found, but international eligibility is not explicitly guaranteed on the listing.")

    return {
        "status": status,
        "reason": " ".join(reasons),
        "international_eligibility": international,
        "nationality_restrictions": "; ".join(flags["restrictions"]),
        "required_qualifications": degree,
        "english_requirement": english,
    }
