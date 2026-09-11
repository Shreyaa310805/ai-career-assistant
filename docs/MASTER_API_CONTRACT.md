# AI Career Assistant — Master API Contract

> Single shared reference for all 4 team members.
>
> **Frozen:** Person 1 and Person 3 contracts. Do not change their existing request/response contracts.
> **Person 2:** Final shared interview contract.
> **Person 4:** Platform, authentication, application, and integration owner.

---

## 1. Product Workflow

```text
USER
↓ AUTHENTICATION (Register/Login)
↓ DASHBOARD
↓ CREATE APPLICATION (Company + Role)
↓ UPLOAD JD + RESUME
↓ RESUME + JD PARSING
↓ ATS ANALYSIS + JD↔RESUME MATCHING
↓ EXPLAINABLE SCREENING REPORT
↓ RESUME VERSIONING (V1, V2, V3...)
↓ VERSION COMPARISON / BEST VERSION
↓ CHOOSE INTERVIEW PERSONALITY
↓ VOICE MOCK INTERVIEW
↓ AI QUESTION
↓ TEXT→SPEECH
↓ USER SPEAKS
↓ SPEECH→TEXT
↓ ANSWER EVALUATION
↓ ADAPTIVE QUESTION ENGINE
↓ CONFIDENCE / COMMUNICATION TREND
↓ FINAL INTERVIEW REPORT
↓ FINAL DECISION / READINESS INSIGHT
↓ WHAT-IF SIMULATOR
↓ SKILL PRIORITIZATION
↓ LEARNING RESOURCES
↓ FINAL APPLICATION DASHBOARD
```

# 2. Person 1 — Resume & ATS

### Scope
- Resume upload/parsing
- JD parsing
- ATS compatibility
- JD ↔ Resume matching
- Explainable screening report
- Resume versioning
- Resume comparison
- Best-version selection

**These APIs are frozen. Do not change them.**

### Base Path
`/api/v1`

### Response Envelope
```json
{
  "success": true,
  "data": {},
  "error": null
}
```

## 2.1 Upload Resume

### `POST /resumes/upload`

**Content-Type:** `multipart/form-data`

Fields:
- `file` — PDF/DOCX, required, max 10 MB
- `application_id` — UUID, required

Response:
```json
{
  "success": true,
  "data": {
    "resume_id": "c39a8e2b-1234-4567-89ab-cdef01234567",
    "application_id": "a1111111-2222-3333-4444-555555555555",
    "version_number": 1,
    "file_url": "https://storage.example.com/resumes/...",
    "raw_text": "Extracted plain text content...",
    "parsed_data": {
      "candidate_name": "Jane Doe",
      "email": "jane@example.com",
      "phone": "+123456789",
      "skills": ["Python", "FastAPI", "React", "PostgreSQL"],
      "experience_years": 4.5,
      "work_history": [],
      "education": ["B.S. Computer Science"]
    }
  },
  "error": null
}
```

## 2.2 Analyze Resume Against JD

### `POST /resumes/analyze`

**Content-Type:** `multipart/form-data`

Fields:
- `jd_file` — PDF/DOCX/TXT, required
- `application_id` — UUID, required
- `resume_id` — UUID, required

Response:
```json
{
  "success": true,
  "data": {
    "report_id": "...",
    "application_id": "...",
    "resume_id": "...",
    "ats_score": 82.5,
    "match_score": 75.0,
    "matched_skills": ["Python", "FastAPI", "PostgreSQL"],
    "missing_skills": ["Docker", "AWS", "CI/CD"],
    "improvement_suggestions": [
      {
        "category": "Formatting & Keywords",
        "action": "Include missing infrastructure keywords like Docker and AWS.",
        "impact": "High"
      },
      {
        "category": "Experience Detail",
        "action": "Quantify outcomes in work history bullets using percentage metrics.",
        "impact": "Medium"
      }
    ]
  },
  "error": null
}
```

## 2.3 Resume Versions

### `GET /resumes/versions/{application_id}`

Response:
```json
{
  "success": true,
  "data": {
    "application_id": "...",
    "versions": [
      {
        "resume_id": "...",
        "application_id": "...",
        "version_number": 1,
        "file_url": "...",
        "is_best_version": false,
        "created_at": "...",
        "parsed_data": "{ ...ParsedResumeData... }",
        "latest_ats_report": {
          "report_id": "...",
          "ats_score": 82.5,
          "match_score": 75.0,
          "created_at": "..."
        }
      }
    ]
  },
  "error": null
}
```

## 2.4 Compare Resume Versions

### `POST /resumes/compare`

Request:
```json
{
  "resume_id_v1": "UUID",
  "resume_id_v2": "UUID"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "resume_v1": {},
    "resume_v2": {},
    "diff": {
      "skills_gained": [],
      "skills_lost": [],
      "experience_years_delta": 0,
      "ats_score_delta": 0,
      "match_score_delta": 0,
      "education_gained": [],
      "education_lost": [],
      "work_history_count_delta": 0
    },
    "recommended_version": 2,
    "recommendation_reason": "..."
  },
  "error": null
}
```

## 2.5 Select Best Resume

### `PATCH /resumes/select-best`

Request:
```json
{
  "application_id": "UUID",
  "best_resume_id": "UUID"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "application_id": "UUID",
    "best_resume_id": "UUID",
    "version_number": 2,
    "updated_versions": 2
  },
  "error": null
}
```

### Person 1 Error Codes
`INVALID_REQUEST`, `APPLICATION_MISMATCH`, `RESUME_NOT_FOUND`, `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE`, `EXTRACTION_FAILED`, `VALIDATION_ERROR`, `STORAGE_ERROR`, `INTERNAL_ERROR`

---

# 3. Person 2 — AI Interview

### Scope
- Interview personality
- Question generation
- Voice interview
- Speech-to-text
- Answer evaluation
- Adaptive questioning
- Communication analysis
- Confidence trend
- Final interview report
- Typed-answer fallback

### Base Path
`/api/v1`

### Integration Rule

`application_id` must come from Person 4's real Applications table once integrated.

Person 2 must **not** create a second application ID or duplicate the application model.

Final integrated system:
- `interviews.application_id` → FK to `applications.id`
- JWT determines the authenticated user
- Application ownership must be verified
- Person 2 uses the application's JD/resume context internally
- Frontend must not ask for a duplicate application ID

## 3.1 Create Interview

### `POST /api/v1/interviews`

Request:
```json
{
  "application_id": "UUID",
  "personality": "technical",
  "difficulty": "medium"
}
```

Personality:
- `technical`
- `friendly`
- `strict`
- `behavioral`
- `mixed`

Difficulty:
- `easy`
- `medium`
- `hard`

Response: HTTP `201`
```json
{
  "success": true,
  "data": {
    "interview_id": "UUID",
    "application_id": "UUID",
    "personality": "technical",
    "difficulty": "medium",
    "status": "created",
    "question_count": 0,
    "started_at": null
  },
  "error": null
}
```

## 3.2 Get Interview

### `GET /api/v1/interviews/{interview_id}`

Returns the interview session representation above.

Missing interview → HTTP `404`.

## 3.3 Generate Question

### `POST /api/v1/interviews/{interview_id}/questions`

Request:
```json
{
  "mode": "adaptive"
}
```

Allowed mode:
- `adaptive`
- `standard`

Response:
```json
{
  "success": true,
  "data": {
    "question_id": "UUID",
    "interview_id": "UUID",
    "question_number": 1,
    "question": "Explain how you would design a scalable API.",
    "topic": "System Design",
    "question_type": "technical",
    "difficulty": "medium",
    "expected_skills": ["API Design", "Scalability"],
    "reason": "Relevant to the target role and current interview context."
  },
  "error": null
}
```

## 3.4 Submit Answer

### `POST /api/v1/interviews/{interview_id}/answers`

Request:
```json
{
  "question_id": "UUID",
  "answer_text": "My answer...",
  "source": "voice",
  "duration_seconds": 45
}
```

Allowed source:
- `typed`
- `voice`

`duration_seconds` is optional.

Response:
```json
{
  "success": true,
  "data": {
    "answer_id": "UUID",
    "question_id": "UUID",
    "answer_text": "My answer...",
    "source": "voice",
    "duration_seconds": 45,
    "submitted_at": "..."
  },
  "error": null
}
```

## 3.5 Evaluate Answer

### `POST /api/v1/interviews/{interview_id}/answers/{answer_id}/evaluate`

Response:
```json
{
  "success": true,
  "data": {
    "evaluation_id": "UUID",
    "answer_id": "UUID",
    "technical_correctness": 82,
    "relevance": 90,
    "reasoning": 78,
    "communication": 85,
    "overall_score": 84,
    "feedback": "Good answer with clear reasoning.",
    "strengths": ["Relevant", "Structured reasoning"],
    "weaknesses": ["Could provide more concrete examples"]
  },
  "error": null
}
```

## 3.6 Communication Analysis

### `GET /api/v1/interviews/{interview_id}/communication`

Response:
```json
{
  "success": true,
  "data": {
    "overall_communication": 84,
    "clarity": 86,
    "relevance": 90,
    "conciseness": 78,
    "reasoning_clarity": 82,
    "answers_analyzed": 5
  },
  "error": null
}
```

## 3.7 Confidence Trend

### `GET /api/v1/interviews/{interview_id}/confidence`

Response:
```json
{
  "success": true,
  "data": {
    "trend": [],
    "overall_confidence": 82,
    "trend_direction": "improving"
  },
  "error": null
}
```

## 3.8 Complete Interview

### `POST /api/v1/interviews/{interview_id}/complete`

Response:
```json
{
  "success": true,
  "data": {
    "report_id": "UUID",
    "interview_id": "UUID",
    "application_id": "UUID",
    "overall_score": 84,
    "technical_score": 86,
    "communication_score": 82,
    "reasoning_score": 84,
    "confidence_score": 80,
    "questions_attempted": 8,
    "strengths": [],
    "areas_to_improve": [],
    "readiness": "Ready",
    "summary": "..."
  },
  "error": null
}
```

## 3.9 Get Interview Report

### `GET /api/v1/interviews/{interview_id}/report`

Returns the final interview report.

## 3.10 Interview History

### `GET /api/v1/interviews/application/{application_id}`

Returns interview history for an application.

## 3.11 Voice Architecture

- Speech-to-text: Browser Web Speech API
- Text-to-speech: Browser SpeechSynthesis API
- Typed fallback: required if browser speech APIs or AI services fail
- AI-service failures → `502 AI_SERVICE_ERROR`

---

# 4. Person 3 — What-If & Career Intelligence

### Scope
- Skill-gap analysis
- Skill prioritization
- What-if simulations
- Estimated match improvement
- Learning resources
- Career roadmap

**These contracts are frozen. Do not change them.**

> The supplied Person 3 contract specifies request/response shapes and issue names, but does not specify literal HTTP endpoint paths. Do not invent or rename paths. Use the exact paths already implemented by Person 3.

## 4.1 Skill Gap Analysis — ISSUE-40

Request:
```json
{
  "application_id": "app_123",
  "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
  "user_skills": ["Python", "PostgreSQL", "Git"]
}
```

Response:
```json
{
  "application_id": "app_123",
  "matched_skills": ["Python", "PostgreSQL"],
  "missing_skills": ["FastAPI", "Docker", "AWS"],
  "partial_skills": ["Git"],
  "skill_gap_count": 3
}
```

## 4.2 Skill Priority — ISSUE-41

Request:
```json
{
  "application_id": "app_123",
  "skills": [
    {"skill": "FastAPI", "job_importance": 0.9, "current_level": 0.2},
    {"skill": "Docker", "job_importance": 0.8, "current_level": 0.0},
    {"skill": "AWS", "job_importance": 0.7, "current_level": 0.1}
  ]
}
```

Response contains:
```json
{
  "application_id": "app_123",
  "prioritized_skills": [
    {
      "skill": "FastAPI",
      "priority_score": 0.72,
      "priority": "HIGH",
      "reason": "..."
    }
  ]
}
```

## 4.3 What-If Simulation — ISSUE-42

Request:
```json
{
  "application_id": "app_123",
  "skill": "Docker",
  "target_level": 0.8
}
```

Response includes current/estimated match score, estimated improvement, impact, and message.

Example:
```json
{
  "application_id": "app_123",
  "skill": "Docker",
  "current_match_score": 62,
  "estimated_match_score": 70,
  "estimated_improvement": 8,
  "impact": "HIGH",
  "message": "..."
}
```

## 4.4 Estimated Match Improvement — ISSUE-43

Request:
```json
{
  "application_id": "app_123",
  "current_match_score": 62,
  "skills": [
    {"skill": "Docker", "target_level": 0.8},
    {"skill": "FastAPI", "target_level": 0.8}
  ]
}
```

Response includes:
```json
{
  "application_id": "app_123",
  "current_match_score": 62,
  "estimated_match_score": 76,
  "improvement": 14,
  "skill_impacts": []
}
```

## 4.5 Learning Resources — ISSUE-44

Request:
```json
{
  "application_id": "app_123",
  "skills": ["FastAPI", "Docker"],
  "learning_preference": "course"
}
```

Response:
```json
{
  "application_id": "app_123",
  "recommendations": [
    {
      "skill": "FastAPI",
      "title": "FastAPI Tutorial",
      "type": "tutorial",
      "provider": "...",
      "url": "https://example.com/fastapi",
      "difficulty": "beginner"
    },
    {
      "skill": "Docker",
      "title": "Docker Fundamentals",
      "type": "course",
      "provider": "...",
      "url": "https://example.com/docker",
      "difficulty": "beginner"
    }
  ]
}
```

## 4.6 Career Roadmap — ISSUE-45

Response:
```json
{
  "application_id": "app_123",
  "current_match_score": 62,
  "skill_gap": {
    "matched": ["Python", "PostgreSQL"],
    "missing": ["FastAPI", "Docker", "AWS"]
  },
  "prioritized_skills": [
    {"skill": "FastAPI", "priority": "HIGH", "priority_score": 0.72},
    {"skill": "Docker", "priority": "HIGH", "priority_score": 0.64},
    {"skill": "AWS", "priority": "MEDIUM", "priority_score": 0.49}
  ],
  "recommendations": [
    {
      "skill": "FastAPI",
      "title": "FastAPI Tutorial",
      "type": "tutorial",
      "url": "https://example.com/fastapi"
    },
    {
      "skill": "Docker",
      "title": "Docker Fundamentals",
      "type": "course",
      "url": "https://example.com/docker"
    }
  ]
}
```

---

# 5. Person 4 — Platform / UX

### Scope
- Authentication
- User/application management
- Dashboard
- Common frontend shell
- Database foundation
- Application/file metadata
- Final module integration
- End-to-end application flow

### Base Path
`/api/v1`

### Authentication
JWT-based authentication. Password hashing uses bcrypt/passlib.

## 5.1 Authentication APIs

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`

---

# 6. Person 4 — Application APIs

## 6.1 Create Application

### `POST /applications`

Request:
```json
{
  "company_name": "Example Technologies",
  "job_title": "Software Engineer",
  "status": "active"
}
```

Response includes:
```json
{
  "id": "UUID",
  "user_id": "UUID",
  "company_name": "Example Technologies",
  "job_title": "Software Engineer",
  "status": "active",
  "created_at": "...",
  "updated_at": "..."
}
```

## 6.2 List Applications

### `GET /applications`

Returns the authenticated user's applications.

## 6.3 Get Application

### `GET /applications/{application_id}`

Returns one application after ownership verification.

## 6.4 Update Application

### `PATCH /applications/{application_id}`

Updates application metadata.

## 6.5 Delete Application

### `DELETE /applications/{application_id}`

Deletes the application after ownership verification.

---

# 7. Person 4 — Dashboard

### `GET /dashboard`

Returns dashboard information for the authenticated user.

---

# 8. Person 4 — Database Models

## Users

The platform requires a `users` table for authentication and ownership.

## Applications

```text
applications
-------------
id              UUID PRIMARY KEY
user_id         UUID FK → users.id
company_name
job_title
status
created_at
updated_at
```

The `application_id` generated here is the **single application ID used by all modules**.

---

# 9. Feature Access / Premium Rules

Product values below are **provisional and centrally configurable**. The UI calls the
billing catalog/entitlement APIs; it must not hard-code prices or allowances.
The database/API enum remains `FREE` / `PREMIUM`; the product label for PREMIUM is **Pro**.

| Feature | Free | Pro |
| --- | --- | --- |
| Quick-scan ATS, resume/JD match, basic breakdown and improvement insights | Yes | Yes |
| Lifetime interview trial | One session, up to configured question limit (default 3) | Existing trial may be resumed |
| Trial final report | Never available, including after upgrade | Never available |
| Paid interview sessions | No | One credit at session creation; subsequent questions/answers do not charge again |
| Paid-session report | No | Yes, while Pro access is active |
| Application tracker, resume versions/comparison, career intelligence | No | Yes |

Monthly default: 10 credits per paid monthly period. Yearly default: 120 credits
per paid yearly period, if a yearly provider plan is configured. These are configuration
defaults, not fixed product commitments. Yearly credits are granted for the annual period;
there is no separate monthly drip for annual billing in this implementation.
Renewal resets the allowance (no rollover). Cancellation at period end preserves access
until the paid expiry. Expired access is enforced on authenticated requests even without webhooks.
Backend guards return HTTP `403` for disallowed features or exhausted allowances.
See section 20 for the complete Person 4 contract. Person 1, 2, and 3 contracts remain unchanged.

---

# 10. Person 4 — Frontend Routes

```text
/
├── /login
├── /signup
├── /dashboard
├── /applications
├── /applications/new
├── /applications/[id]
└── /settings
```

The application workspace at `/applications/[id]` is the main integration point.

---

# 11. Common Application Workspace Integration

The central shared object is:

```text
application_id
```

Flow:

```text
Person 4
  ↓
Creates Application
  ↓
application_id generated
  ↓
Person 1 uses application_id
  ↓
Person 3 uses application_id
  ↓
Person 2 uses application_id
```

There must be **one canonical application ID**.

---

# 12. Integration Rules

## Authentication
- JWT identifies the current user.
- Backend derives `user_id` from the token.
- Do not trust a client-supplied `user_id`.
- Every application/module request must enforce ownership where applicable.

## Application Ownership

```text
authenticated user
        ↓
application_id
        ↓
verify application.user_id == authenticated user
```

If ownership fails, return an appropriate authorization error.

## No Duplicate Application Models

Person 2 and Person 3 must not create separate application tables or application IDs.

Person 4 owns the canonical Applications table.

## Module Communication

Modules communicate through stable contracts.

Do not casually rename:
- fields
- endpoint paths
- response properties
- enums
- IDs

If a contract must change, discuss it with the affected module owner before changing it.

---

# 13. Database Ownership

### Person 4 owns
- `users`
- `applications`
- platform-level metadata

### Person 1 owns
Resume/ATS-related persistence.

### Person 2 owns
Interview-related persistence, including conceptually:
```text
interviews
interview_questions
interview_answers
evaluations
reports
```

### Person 3 owns
Career-intelligence-related persistence if required by its implementation.

---

# 14. Person 2 Interview Data Model

The final implementation should support:

```text
interviews
-----------
id
application_id → applications.id
personality
difficulty
status
started_at
completed_at
created_at
```

Questions:
```text
interview_questions
-------------------
id
interview_id
question_number
question
topic
question_type
difficulty
expected_skills
created_at
```

Answers:
```text
interview_answers
-----------------
id
interview_id
question_id
answer_text
source
duration_seconds
submitted_at
```

Evaluations:
```text
evaluations
-----------
id
answer_id
technical_correctness
relevance
reasoning
communication
overall_score
feedback
strengths
weaknesses
created_at
```

These represent the required final capability; exact internal schema can be refined as long as the API contract remains stable.

---

# 15. End-to-End Integration Sequence

## Step 1 — Authentication
Person 4:
`Register → Login → JWT`

## Step 2 — Create Application
Person 4:
`Company + Job Title + Status → application_id`

## Step 3 — Resume + JD
Person 1:
`application_id → Upload Resume → resume_id → Analyze JD + Resume → ATS + Match Report`

## Step 4 — Resume Versions
Person 1:
`V1 → V2 → V3 → Compare → Select Best Version`

## Step 5 — Career Intelligence
Person 3:
`application_id → Skill Gap → Priority → What-If → Learning Resources → Career Roadmap`

## Step 6 — AI Interview
Person 2:
`application_id → Personality + Difficulty → Create Interview → Generate Question → Answer → Evaluate → Adaptive Question → Communication + Confidence → Final Report`

## Step 7 — Final Dashboard
Person 4 integrates all module outputs into the application workspace.

---

# 16. Current Review / Demo Target

Main demonstrated flow:

```text
Login / Signup
↓
Dashboard
↓
Create Application
↓
Enter Company + Role
↓
Upload Resume + JD
↓
ATS Score
↓
Explainable Screening
↓
Resume Versions
↓
Required / Missing Skills
↓
Skill Priority
↓
What-If Simulator
↓
Learning Links
```

Person 2 is currently lower priority for this review.

Minimum interview demonstration:

```text
Choose Interview Personality
        +
Choose Difficulty
        ↓
Start Interview
        ↓
Interview Session Created
```

Full question-generation and voice flow can be integrated after the shared application structure is stable.

---

# 17. Development Rules

## Branching

Do not work directly on `main`.

Use feature branches:

```text
feature/person1-resume-ats
feature/person2-ai-interview
feature/person3-career-intelligence
feature/person4-platform
```

Merge through reviewed PRs.

## Development Independence

Each person can develop against sample/mock data while building their module.

Integration happens once module contracts and implementations are stable.

## Do Not Break Finished Modules

- Person 1 APIs are frozen.
- Person 3 APIs are frozen.
- Person 2 final contract should be used for integration.
- Person 4 owns the canonical application/auth platform.

---

# 18. Final Team Checklist

## Person 1
- [x] Resume upload
- [x] Resume parsing
- [x] JD parsing
- [x] ATS analysis
- [x] JD ↔ Resume matching
- [x] Explainable report
- [x] Resume versions
- [x] Version comparison
- [x] Best-version selection

## Person 2
- [x] Interview session contract
- [x] Personality selection
- [x] Difficulty selection
- [ ] Question generation
- [ ] Voice/STT
- [ ] TTS
- [ ] Answer submission
- [ ] Answer evaluation
- [ ] Adaptive questioning
- [ ] Communication analysis
- [ ] Confidence trend
- [ ] Final report
- [ ] Typed fallback

## Person 3
- [x] Skill-gap analysis
- [x] Skill prioritization
- [x] What-if simulation
- [x] Estimated match improvement
- [x] Learning recommendations
- [x] Career roadmap

## Person 4
- [ ] Register
- [ ] Login
- [ ] Logout
- [ ] JWT authentication
- [ ] User model
- [ ] Application model
- [ ] Dashboard
- [ ] Application CRUD
- [ ] Common navigation/layout
- [ ] File/application metadata
- [ ] Premium access control
- [ ] Integrate Person 1
- [ ] Integrate Person 2
- [ ] Integrate Person 3
- [ ] End-to-end application workspace

---

# 19. Golden Rules

1. **One application = one canonical `application_id`.**
2. **Person 4 owns the Applications table and authentication.**
3. **Person 1 contracts are frozen.**
4. **Person 3 contracts are frozen.**
5. **Person 2 uses the final interview contract above.**
6. **Do not invent new application IDs in module code.**
7. **Do not silently rename API fields or endpoints.**
8. **JWT/user ownership must be enforced server-side.**
9. **Premium access must be enforced server-side.**
10. **Use feature branches; do not develop directly on `main`.**
11. **Integrate modules through the shared application workspace.**
12. **If a contract change is necessary, coordinate with the module owner first.**


# 20. Person 4 - Payments / Subscriptions / Entitlements

## 20.1 Configuration and terminology

Base path: `/api/v1`. JWT bearer authentication is required except for the signed webhook.
Razorpay is **TEST-only**: the backend rejects keys that do not start with `rzp_test_`.
No endpoint accepts client-asserted amounts, credits, payment status, or Pro activation.
No payment credentials or card data are stored by the application.

Configuration is loaded from the root `.env` and then optional `backend/.env`; environment
variables take precedence. Docker Compose already passes the root `.env` to the backend.
Do not put secrets in frontend environment variables or source control.

| Variable | Meaning / provisional default |
| --- | --- |
| `RAZORPAY_KEY_ID` | TEST public checkout key |
| `RAZORPAY_KEY_SECRET` | Backend-only API/signature secret |
| `RAZORPAY_PLAN_ID` | Backward-compatible monthly provider plan fallback |
| `RAZORPAY_MONTHLY_PLAN_ID` | Preferred monthly plan ID; overrides fallback |
| `RAZORPAY_YEARLY_PLAN_ID` | Optional yearly plan ID; no invented fallback |
| `RAZORPAY_WEBHOOK_SECRET` | Independent backend-only webhook secret; optional locally |
| `PRO_MONTHLY_INTERVIEW_CREDITS` | 10, positive integer |
| `PRO_YEARLY_INTERVIEW_CREDITS` | 120, positive integer |
| `FREE_TRIAL_QUESTION_LIMIT` | 3, positive integer |

Prices/currency are fetched from the configured Razorpay Plan, the authoritative price
configuration. A plan must have interval `1` and period `monthly` or `yearly` as selected.
An absent yearly ID yields an unavailable catalog option and `503` on yearly checkout.
An absent webhook secret yields `503` on the webhook; it never disables signature validation.
Allowance changes apply at the next verified paid cycle, with the active allowance snapshotted
on the subscription. Trial limit changes apply to trial question generation.

## 20.2 Endpoint overview

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/billing/catalog` | User | Configured plan prices, intervals, availability, credit allowances |
| GET | `/billing/plan` | User | Current stored entitlements and subscription status |
| GET | `/billing/payments` | User | Up to 100 own audited purchases, newest first |
| POST | `/billing/checkout` | User | Create/reuse an unpaid Razorpay subscription; never activates Pro |
| POST | `/billing/verify` | User | Validate Checkout signature and verify provider payment/invoice |
| POST | `/billing/sync` | User | Fetch own subscription and paid invoices for callback/webhook recovery |
| POST | `/billing/cancel` | User | Cancel renewal; unpaid checkout cancellation is immediate |
| POST | `/billing/webhook` | Signed provider | Process subscription state/charges after HMAC verification |
| POST | `/practice/interviews` | User | Person 4 practice entry point using canonical application context |
| GET | `/practice/interviews` | User | Up to 100 owned sessions and usage costs, newest first |

Existing Person 2 interview request/response payloads remain unchanged. Person 4 adds
entitlement enforcement to those routes and supports the optional `Idempotency-Key` UUID
header on interview creation. The required `application_id` on `POST /interviews` is preserved.
The practice entry point creates a private scratch Application in the canonical Applications
table; it does not add an application model or expose scratch entries in the tracker.

## 20.3 Catalog and entitlements

`GET /billing/catalog`:
```json
{
  "plans": [
    {"interval": "monthly", "available": true, "credits": 10, "amount": 19900, "currency": "INR"},
    {"interval": "yearly", "available": false, "credits": 120, "amount": null, "currency": null}
  ],
  "trial_question_limit": 3
}
```
Amounts and allowances above are examples. `amount` uses currency minor units.

`GET /billing/plan`, and successful verify/sync/cancel, return:
```json
{
  "plan": "PREMIUM", "credits": 9, "credit_limit": 10,
  "trial_available": false, "trial_question_limit": 3, "interval": "monthly",
  "pro_until": "2026-10-10T12:00:00Z",
  "subscription_id": "sub_example", "subscription_status": "active",
  "cancel_at_cycle_end": false, "webhook_configured": false,
  "provider": "razorpay", "test_mode": true, "configured": true
}
```
`pro_until`, `subscription_id`, and `subscription_status` may be null. `configured` indicates
TEST API credentials, not webhook readiness. Catalog availability also requires a provider plan.
The payment-history response retains the purchase fields `id`, `plan`, `amount_cents`, `currency`,
`provider`, `status`, `created_at`; `amount_cents` is the historical field name for minor units.

## 20.4 Checkout and verification

`POST /billing/checkout` request: `{"plan":"PREMIUM","interval":"monthly"}`.
Both fields have the shown defaults. `interval` also accepts `yearly`.
`201` response: `{already_premium:false,key_id,subscription_id,amount,currency}`.
An already-Pro account receives `{already_premium:true}` and no provider purchase is made.
Repeated requests reuse the open subscription. Switching intervals while another subscription
is open returns `409`; cancel the unfinished subscription first. Active plan changes/proration
are not implemented.

Pass the returned public key and `subscription_id` to Razorpay Standard Checkout.
Post its callback unchanged to `/billing/verify`:
```json
{
  "razorpay_subscription_id": "sub_example",
  "razorpay_payment_id": "pay_example",
  "razorpay_signature": "64-character hexadecimal signature"
}
```
The server verifies HMAC-SHA256 over `payment_id|stored_subscription_id`, using the API secret,
then fetches the subscription, captured payment, and paid invoice. Ownership, purchased plan,
invoice subscription, and invoice payment must agree. Mere mandate authorization is insufficient.
A verified paid period activates Pro and grants its configured allowance. `409` means payment
capture/paid-period confirmation is still pending. Refresh via `/billing/sync` after capture.

`POST /billing/sync` accepts no payload and never trusts browser payment claims. It retrieves
provider state and paid invoices using backend API credentials. This supports local recovery
without public webhooks, including a renewal triggered in Razorpay's TEST dashboard.
It does not itself charge, simulate payment, or renew a subscription.

## 20.5 Webhooks, renewal, and cancellation

`POST /billing/webhook` requires `X-Razorpay-Signature`, validated over the exact raw body with
the independent webhook secret. Missing configuration: `503`; bad signature/malformed event: `400`.
Events handled: `subscription.charged`, `subscription.cancelled`, `subscription.completed`,
`subscription.pending`, `subscription.halted`, `subscription.activated`, `subscription.authenticated`.
Other events and subscriptions outside this application are acknowledged without mutation.
Successful response: `{"received":true}`.

State is fetched from Razorpay after signature validation to avoid trusting out-of-order event
snapshots. Only a larger verified `paid_count` replenishes credits. Duplicate payment IDs are
stored once; verification and webhooks share the same transition. Replayed events cannot refill
a spent balance. Pending/halted status grants no new credits; previously paid access lasts only
until its stored expiry. A terminal provider subscription revokes its access. Old terminal events
cannot revoke a newer open subscription on the same account.

`POST /billing/cancel` has no payload. For a paid subscription it requests provider
`cancel_at_cycle_end=1`, records the pending cancellation, and preserves current credits/access.
Repeated cancellation is idempotent. An unpaid created/authenticated subscription is cancelled
immediately. Final provider cancellation, or paid-period expiry checked on requests, removes Pro
access and remaining credits. Cancellation does not restore the lifetime trial.

## 20.6 Interview usage and report guard

`POST /practice/interviews` request: `{personality,difficulty}`, using existing Person 2 enum values;
defaults are `technical` and `medium`. Response is the existing Person 2 `InterviewData` envelope.
Pass an optional UUID `Idempotency-Key` header and reuse it only for retries of the same start.
Reusing a key with different preferences yields `409`.

A Free start atomically marks the lifetime trial used. A Pro start atomically decrements one
credit and writes an `interview_usage` entry in the same transaction as the interview. Failure
rolls back the debit. Trial starts cost zero credits. Existing sessions, Q2/Q3, answers, evaluations,
report reads, and idempotent start retries do not consume additional credits.
The configured trial limit is checked before AI generation; excess questions return `403`.

`GET /practice/interviews` returns `{success:true,data:[{session:InterviewData,is_trial,
credits_charged}],error:null}`. Legacy sessions with no usage record show zero charged credits.

`GET /interviews/{id}/report` requires active Pro and a non-trial owned session. Trial reports
remain `403` after upgrade. The current integrated report read model returns
`{success:true,data:{interview_id,evaluated_answers,overall_score,evaluations:[]},error:null}`,
using existing persisted rubric evaluations; empty sessions have `overall_score:null`.
This payment integration does not modify Person 2's AI algorithms or implement the separate
voice/confidence/completion analysis described in its full contract above.

## 20.7 Persistence and errors

Migrations: `0007_subscriptions` after `0006_interview_answers`, then
`0008_subscription_allowance`.
New user fields: `interview_credits`, `trial_used`, `pro_until`. New interview field: `is_trial`.
New tables: `subscriptions`, `subscription_charges`, `interview_usage`.
The subscription stores interval, paid-count high-water mark, allowance snapshot and cancellation
intent. Unique indexes enforce one open subscription per user, one charge per provider payment,
and one interview usage per user/request key. PostgreSQL user-row locks serialize debit and
renewal transactions. Historical mock purchases remain auditable and legacy Pro accounts retain
existing access with an initial configured monthly credit allowance.

Errors use `{detail:"..."}`: `401` unauthenticated, `403` entitlement denied, `404` wrong owner/not
found, `409` payment pending or idempotency/interval conflict, `422` invalid request, `503` missing
configuration, `502` provider request failure. Raw provider errors/secrets are not echoed.

## 20.8 Frontend and local verification

`/upgrade`: configured prices, monthly/yearly availability, real TEST Checkout, Pro balance,
paid expiry, cancellation and provider-backed refresh.
`/interview`: trial/Pro practice, session resumption, credits and report gate.
Application interview pages share the same practice component.

See `docs/PAYMENTS_TESTING.md` for local testing, webhook activation and yearly setup.
No commit or push is required by this implementation.
