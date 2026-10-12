# Fully Funded PhD Application Bot

Personal assistant for discovering, verifying, ranking, and preparing applications to **fully funded European PhD positions**. It does not invent academic facts, submit forms, or send email without your approval.

This repository is a Stage 1–4 MVP: editable profile, official-source discovery, conservative funding classification, eligibility flags, ranking, and a tracking dashboard.

## Academic information you still need to provide

Do not ask the bot to evaluate final eligibility until these are filled in the dashboard or `config/profile.yaml`.

1. Legal family name and contact email
2. Highest completed degree (title, field, institution, country, year)
3. Bachelor GPA/CGPA **and the scale** (for example 3.7/4.0 or 3.6/4.00)
4. Master's status: completed, in progress, or not started
5. Master's title, field, institution, dates, GPA/scale if you have a Master's
6. Master's thesis title and abstract, if any
7. English evidence: IELTS/TOEFL/Cambridge scores **or** a documented medium-of-instruction waiver
8. Research experience (project, dates, supervisor, outcomes) — leave empty if none
9. Publication list with full citations — leave empty if none
10. Intended PhD research interests (not only the default field list)
11. Names and institutional emails of referees (stored only; never contacted automatically)
12. Which original documents you already have (transcripts, degree scans, passport)

Known and already stored: Pakistani nationality, based in Pakistan, software engineer (~4 years), JavaScript/web/healthcare/IoT background, Europe, fully funded, prefer no application fee.

## Architecture

```
Dashboard (React)  →  FastAPI  →  SQLite or PostgreSQL
                         ├── profile + completeness
                         ├── discovery (EURAXESS, AcademicTransfer, official pages)
                         ├── funding classifier (evidence-backed)
                         ├── eligibility + ranking
                         └── document drafts (facts only)
APScheduler refreshes discovery daily.
Playwright application-filling is intentionally not enabled yet.
```

Modules are separated: discovery, funding, eligibility, ranking, documents, approvals.

## Database (main tables)

- `profiles` — JSON profile, completeness, missing fields
- `opportunities` — vacancy fields, funding class, eligibility, score, status
- `opportunity_claims` — each important claim with source URL and verified/inference flag
- `opportunity_events` — deadline/title/URL changes
- `applications` — packages and approval state
- `supervisor_emails` — drafted / approved / not sent
- `notifications`, `discovery_runs`, `app_settings`

Duplicate key: SHA-256 of canonical URL + institution + title + recruitment reference. A second listing with the same university + vacancy ID is merged.

## Local setup

```powershell
cd "D:\Cursor Bots\phd-apply-applications"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
copy .env.example .env
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

In another terminal:

```powershell
cd "D:\Cursor Bots\phd-apply-applications\frontend"
npm install
npm run dev
```

Open http://localhost:5173. Use **Search Opportunities → Run discovery now**.

Optional Postgres: `docker compose up db` and set `DATABASE_URL` in `.env`.

## Funding rules (enforced)

- `FULLY FUNDED` only if a stipend/salary is extracted **and** duration is stated **and** tuition is explicit or inferred from an employed-PhD contract in countries where that is standard. Inferences are stored as `is_inference=true`.
- A page that only says “scholarship” without amounts is `UNVERIFIED`.
- Extra award conditions → `CONDITIONALLY FUNDED`.
- Only `FULLY FUNDED` items enter the primary queue.

## What is automated vs what needs you

Automated: search official listings, extract fields, classify funding, flag eligibility gaps, score, draft documents from profile facts, track deadlines, remind.

Requires you: completing academic data, approving/rejecting opportunities, sending supervisor email, solving CAPTCHAs, logging into university portals, final submission, interviews.

Hard rules: no CAPTCHA bypass, no storing portal passwords in this MVP, no submit/send without per-application approval.

## Later stages

5 Document polish with an optional LLM  
6 Richer tracker states (interview/offer)  
7 Playwright form assistance with a preview + approval gate  
8 Email notifications  
9 Broader official sources (DAAD, university APIs)  
10 Hardened deployment
