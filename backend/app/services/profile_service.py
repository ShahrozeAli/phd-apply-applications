from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import REQUIRED_PROFILE_FIELDS
from app.models import Profile


def _get(data: dict, dotted: str):
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def missing_academic_fields(payload: dict) -> list[dict]:
    missing = []
    for path, label in REQUIRED_PROFILE_FIELDS:
        value = _get(payload, path)
        empty = value in (None, "", [], {}, "unknown")
        if path == "academic.masters.degree_title":
            status = _get(payload, "academic.masters.status")
            if status in (None, "", "unknown", "not started"):
                continue
        if path in ("academic.masters.thesis_title", "academic.masters.thesis_abstract"):
            status = _get(payload, "academic.masters.status")
            if status in (None, "", "unknown", "not started"):
                continue
        if empty:
            missing.append({"path": path, "label": label})
    return missing


def completeness(payload: dict) -> float:
    missing = missing_academic_fields(payload)
    total = len(REQUIRED_PROFILE_FIELDS)
    return round(100 * (total - len(missing)) / total, 1) if total else 0


def load_yaml_profile() -> dict:
    path: Path = settings.profile_yaml
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_yaml_profile(payload: dict) -> None:
    with settings.profile_yaml.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def get_or_create_profile(db: Session) -> Profile:
    row = db.query(Profile).first()
    if row:
        return row
    payload = load_yaml_profile()
    row = Profile(
        payload_json=json.dumps(payload, ensure_ascii=False),
        completeness_score=completeness(payload),
        missing_fields_json=json.dumps(missing_academic_fields(payload), ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def profile_dict(row: Profile) -> dict:
    payload = json.loads(row.payload_json)
    return {
        "id": row.id,
        "profile": payload,
        "completeness_score": row.completeness_score,
        "missing_fields": json.loads(row.missing_fields_json or "[]"),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "eligibility_ready": len(json.loads(row.missing_fields_json or "[]")) == 0,
    }


def update_profile(db: Session, incoming: dict) -> Profile:
    row = get_or_create_profile(db)
    current = json.loads(row.payload_json)
    merged = deepcopy(current)
    _deep_merge(merged, incoming)
    row.payload_json = json.dumps(merged, ensure_ascii=False)
    row.completeness_score = completeness(merged)
    row.missing_fields_json = json.dumps(missing_academic_fields(merged), ensure_ascii=False)
    save_yaml_profile(merged)
    db.commit()
    db.refresh(row)
    return row


def _deep_merge(base: dict, incoming: dict) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
