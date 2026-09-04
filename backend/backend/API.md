# API Contract

Base URL: `http://localhost:8000/api/v1`

Authentication is a JWT bearer token from `/auth/register` or `/auth/login`:

```
Authorization: Bearer <access_token>
```

## Access levels

| Level | Meaning |
| --- | --- |
| **Public** | No token required. |
| **User** | Any authenticated account, FREE or PREMIUM. |
| **Premium** | `users.plan == PREMIUM`, enforced by `require_premium` in `app/api/deps.py`. Returns `403` otherwise. |

Access is always decided server-side from the stored plan. A client never asserts its own plan.

## Response envelopes

Two conventions exist, both stable:

1. **Envelope** — used by `/resumes/*` and `/quick-scan/*`:
   ```json
   { "success": true, "data": { }, "error": null }
   ```
   On failure: `{"success": false, "data": null, "error": {"code": "...", "message": "...", "details": null}}`.
2. **Direct schema** — used by `/auth`, `/applications`, `/billing`, `/career`, `/access`.
   Errors use FastAPI's `{"detail": "..."}`.

> **The `/resumes/*` contract is frozen.** Paths, multipart field names, response field names and error
> codes must not change. New fields may only be added as optional. The shared implementation lives in
> `app/services/resumes/pipeline.py` so other surfaces can reuse the pipeline without touching these routes.

---

## Authentication — `/auth`

| Method | Path | Access | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/auth/register` | Public | `{name, email, password}` | `201` `TokenResponse` |
| POST | `/auth/login` | Public | `{email, password}` | `200` `TokenResponse` |
| POST | `/auth/logout` | User | — | `204` (token jti revoked) |
| GET | `/auth/me` | User | — | `200` `UserResponse` |

`TokenResponse` = `{access_token, token_type, user}`.
`UserResponse` = `{id, name, email, plan, created_at}`.

Errors: `409` duplicate email, `401` bad credentials or invalid/revoked token.

## Billing — `/billing`

Simulated provider. **No card data is accepted, transmitted or stored.**

| Method | Path | Access | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/billing/plan` | User | — | `200` `{plan, premium_since, price_cents, currency, provider, payments[]}` |
| POST | `/billing/checkout` | User | `{plan: "PREMIUM"}` | `201` `{user, payment, already_premium}` |

`checkout` is idempotent: calling it on a PREMIUM account returns `already_premium: true` with
`payment: null` and records no second transaction. Buying `FREE` returns `422`.

## Quick scan — `/quick-scan`

The FREE-tier ATS surface. Runs the same pipeline as `/resumes` against a server-managed scratch
application that is never listed by the tracker. Available to FREE and PREMIUM.

| Method | Path | Access | Request (multipart unless noted) | Response `data` |
| --- | --- | --- | --- | --- |
| POST | `/quick-scan/resume` | User | `file` (.pdf/.docx) | `{resume_id, application_id, version_number, parsed_data}` |
| POST | `/quick-scan/analyze` | User | `resume_id`, and one of `jd_file` (.pdf/.docx/.txt) or `jd_text` | `AnalyzeResumeResponse` |
| GET | `/quick-scan/latest` | User | — | `{resume, report}` — either may be `null` |

Errors: `400` `APPLICATION_MISMATCH` when `resume_id` is not from this caller's quick scan,
`404` `RESUME_NOT_FOUND`, `413` `FILE_TOO_LARGE`, `415` `UNSUPPORTED_FILE_TYPE`.

## Resume & ATS — `/resumes` *(frozen)*

All routes require a bearer token **and** an application owned by the caller.

| Method | Path | Access | Request | Response `data` |
| --- | --- | --- | --- | --- |
| POST | `/resumes/upload` | User | multipart `file`, `application_id` | `{resume_id, application_id, version_number, parsed_data}` |
| POST | `/resumes/analyze` | User | multipart `application_id`, `resume_id`, `jd_file` \| `jd_text` | `AnalyzeResumeResponse` |
| GET | `/resumes/versions/{application_id}` | User | — | `{application_id, versions[]}` |
| POST | `/resumes/compare` | User | `{resume_id_v1, resume_id_v2}` | `{resume_v1, resume_v2, diff, recommended_version, recommendation_reason}` |
| PATCH | `/resumes/select-best` | User | `{application_id, best_resume_id}` | `{application_id, best_resume_id, version_number, updated_versions}` |

`AnalyzeResumeResponse`:

```jsonc
{
  "report_id": "uuid", "application_id": "uuid", "resume_id": "uuid",
  "ats_score": 0.0,        // resume quality blended with keyword coverage against THIS jd
  "match_score": 0.0,      // fit against this JD
  "matched_skills": ["..."], "missing_skills": ["..."],
  "improvement_suggestions": [{ "category": "...", "action": "...", "impact": "High|Medium|Low" }],
  "jd_details": { "role_title": "...", "required_skills": [], "preferred_skills": [],
                  "min_experience_years": 0.0, "responsibilities": [] },
  // Optional, added later. Absent on reports created before they existed.
  "ats_breakdown":   { "jd_keyword_coverage": 45.0, "contact_completeness": 10.0, "section_coverage": 15.0,
                       "quantified_impact": 15.0, "length_check": 10.0, "work_history_structure": 5.0 },
  "match_breakdown": { "required_skill_match_pct": 0.0, "preferred_skill_match_pct": 0.0,
                       "experience_match_pct": 0.0 }
}
```

`ResumeDetails` (the only resume projection any route returns) is `{skills, experience_years, work_history, education}`.
`file_url` in a version summary is an opaque `resume://<resume_id>` reference, never a storage path.

## Applications — `/applications` *(Premium)*

| Method | Path | Access | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/applications` | Premium | — | `200` `ApplicationResponse[]` |
| POST | `/applications` | Premium | `ApplicationCreate` | `201` `ApplicationResponse` |
| GET | `/applications/{id}` | Premium | — | `200` `ApplicationResponse` |
| PATCH | `/applications/{id}` | Premium | `ApplicationUpdate` | `200` `ApplicationResponse` |
| DELETE | `/applications/{id}` | Premium | — | `204` |
| GET | `/dashboard/summary` | Premium | — | `200` `DashboardSummary` |
| GET | `/applications/{id}/integrations/ats` | User | — | `200` `{application_id, feature, allowed}` |
| GET | `/applications/{id}/integrations/{feature}` | Premium | — | `200` same shape |

`ApplicationCreate` = `{company, role, status?, location?, job_url?, job_description?, applied_at?}`.
`status` ∈ `SAVED | APPLIED | INTERVIEWING | SELECTED | OFFER | OFFER_DECLINED | REJECTED`.
`{feature}` ∈ `interviews | skill-gap | learning | roadmap | what-if | versions`.

A non-owner receives `404`, never `403` — the API does not disclose that another user's application exists.
The FREE-tier scratch application is excluded from every query on these routes.

## Career intelligence — `/career` *(Premium)*

Derived from the caller's stored resume and its latest ATS report. Never from fixtures.

| Method | Path | Access | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/career/roadmap/{application_id}` | Premium | — | `200` roadmap (below) |
| POST | `/career/what-if/{application_id}` | Premium | `{skill, target_level: 0..1}` | `200` projection |

```jsonc
// GET /career/roadmap/{application_id}
{
  "application_id": "uuid", "company": "...", "role": "...", "current_match_score": 0,
  "skill_gap": { "matched_skills": [], "missing_skills": [], "extra_skills": [], "skill_gap_count": 0 },
  "prioritized_skills": [{ "skill": "...", "priority": "High|Medium|Low",
                           "priority_score": 0.0, "reason": "..." }],
  "recommendations": [{ "skill": "...", "priority": "...",
                        "resources": [{ "title", "provider", "difficulty", "type", "url" }] }]
}
```

Errors: `404` application not found or not owned, `409` no resume uploaded / no ATS analysis yet,
`422` (what-if) the skill is not in the current missing-skills set.

## Access probes — `/access`

| Method | Path | Access |
| --- | --- | --- |
| GET | `/access/ats-score` | User |
| GET | `/access/premium` | Premium |

## Health

`GET /health` (unprefixed) → `{"status": "ok"}`.

---

## Adding an endpoint

1. Reuse `app/services/resumes/pipeline.py` for anything resume- or scoring-related; do not re-implement
   extraction, scoring, storage or versioning.
2. Take `CurrentUser` or `PremiumUser` from `app/api/deps.py` — never read a plan from the request.
3. Confirm ownership before touching an application-scoped record, and return `404` (not `403`) for
   records belonging to another user.
4. Project resume data through `public_resume_details()`. Never return `raw_text`, `candidate_name`,
   `email`, `phone`, or `Resume.file_url`.
5. Match the envelope convention of the router you are extending.
