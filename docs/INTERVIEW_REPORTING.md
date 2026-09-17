# Interview reporting

## Repository inspection before implementation

Canonical contract: `docs/MASTER_API_CONTRACT.md`. Branch inspected: `feature/person2-evaluation-report`; working tree initially clean.

1. `Interview` / `interviews` belongs to the canonical `applications.id`. Fields include personality, difficulty, question_target, mode, status, started_at, completed_at, created_at, summary, recommendation, visual_score, visual_summary.
2. `InterviewQuestion` / `interview_questions`: id, interview_id, question_number, question, topic, question_type, difficulty, expected_skills (JSON), reason, created_at. Unique session/question number.
3. `InterviewAnswer` / `interview_answers`: id, interview_id, question_id, answer_text, source (`typed`/`voice`), duration_seconds, created_at, audio_storage_key, audio_mime_type, audio_size_bytes. Replacement removes the evaluation; video answer replacement is rejected.
4. `InterviewAnswerEvaluation` / `interview_answer_evaluations`: id, answer_id (unique), overall_score, relevance_score, correctness_score, depth_score, clarity_score, evidence_score, confidence_score, confidence_rationale, strengths, weaknesses, missing_points, feedback, evaluated_at. Rubric scores are integers 0–100, currently non-null. Defaults from migration may have no confidence rationale.
5. `build_adaptation_context` in `interview_questions.py` uses this session's persisted scores, weaknesses, and missing points starting at question 3. Thresholds: 75/hard, 45/medium, below/easy. Immediate evaluation stays intact.
6. Communication is stored as clarity and supporting relevance/depth/evidence rubric values. There are no implemented standalone `/communication` or `/confidence` routes. Confidence in Gemini and its local heuristic is a language estimate; the heuristic uses hedges, decisive phrasing, specificity, length and optional duration. No separate persisted acoustic feature scores exist.
7. Video uses `POST /interviews/{id}/visual-frames`, not a raw video-upload endpoint. `InterviewVisualFrame` / `interview_visual_frames` stores interview_id, optional question_id, face_visible, multiple_people, looking_at_camera, engagement_score, attentiveness_score, composure_score, presentation_score, expression, observation, captured_at. JPEG frames are processed in memory, never persisted. `aggregate_visual_analysis` returns visual_score, frames_analyzed, face_visible_rate, eye_contact_rate, engagement, attentiveness, composure, presentation, common_expressions, observations. Completion persists that JSON on Interview. Video speech still submits a `voice` answer through audio transcription.
8. Audio route: `POST /interviews/{id}/questions/{question_id}/audio-answer`. Bounded format validation, private local storage, Gemini transcription, typed fallback, and separate evaluation. Only transcript, duration, and file metadata are stored: no extracted filler/pauses/silence/fluency signals.
9. Completion already existed, persisted summary/recommendation, and returned status, timestamps, counts, average_score, average_confidence, mode, visual_analysis. `/full` and paginated interview history exist. `/report` did not exist. No report model/table exists. The actual completion contract differs from the master's conceptual final report; existing fields are preserved and canonical fields added.
10. Frontend setup/history/review are under `/applications/[id]/interview`; active typed/audio and video pages are under `/interview-session/[interviewId]` and `/video-interview/[interviewId]`. Existing UI cards/buttons and chart primitives use CSS/SVG; no chart package exists. Detailed feedback was displayed during practice.
11. `get_gemini_service()` provides interview question/evaluation/summary methods with deterministic local fallbacks. Audio and vision have their own bounded Google GenAI calls. Application synthesis here is deterministic and makes no provider call.
12. Canonical `Application` has id, user_id, company, role, job_description and is_scratch, plus platform metadata. JWT `PremiumUser` enforces premium before reports execute. `_owned_application` / `_owned_interview` filter authenticated ownership and exclude scratch applications. No duplicate application models or IDs are introduced.
13. Single migration head: `0010_video_interview`, following `0009_interview_audio`. No schema change needed.
14. Existing backend PyMuPDF (`PyMuPDF==1.24.10`) is reused. No new dependencies.
15. Person 3 implemented routes are `GET /api/v1/career/roadmap/{application_id}` and `POST /api/v1/career/what-if/{application_id}`. `WhatIfRequest` is skill/target_level. Career reads canonical Application plus isolated Resume/AtsReport, and derives skill gaps, priorities, resources, and simulation output. No separate persisted career model is used by these routes. Frozen contracts and all payment code remain untouched.

## Endpoints and persistence

- `POST /api/v1/interviews/{interview_id}/complete`: preserves every previously implemented response field; adds canonical report fields and confidence observations.
- `GET /api/v1/interviews/{interview_id}/report`: one completed interview only; incomplete session returns 409.
- `GET /api/v1/applications/{application_id}/interview-report`: current completed-session set, including an empty report when none exist.
- `GET /api/v1/applications/{application_id}/interview-report/pdf`: in-memory PDF, `application/pdf`, attachment filename `SkillSync-interview-report-{application_id}.pdf`.
- Frontend: `/applications/{application_id}/interview/report`, linked from setup and session review.

JSON responses use `{ "success": true, "data": REPORT, "error": null }`. Reports require JWT and PREMIUM. Another owner's application/interview or nonexistent identifier returns 404; free accounts return 403; no token returns 401. Reports do not return storage keys, local paths, raw recordings, or internal provider metadata.

Reports compute from persisted evaluations, with no cache/table/migration or recomputation of original scores. Session report_id is the existing interview UUID, a stable derived report identifier, not a new application or persisted report ID. GET reports make no Gemini calls. Stored session prose is reused where available; application prose always has deterministic synthesis.

## Aggregation and confidence

- Include only status=`completed` sessions of the owned application. Abandoned/in-progress sessions contribute nothing, including skill names.
- Average each dimension over evaluated answers that actually contain that dimension; equal answer weight, not equal session weight. Nulls are excluded, never zero-filled. Python calculates deterministic means rounded to two decimals. Counts expose each metric's denominator.
- Attempted count is distinct answered questions; evaluated count is distinct evaluated questions. Per-question entries preserve every stored evaluated answer. The normal submission service keeps one current answer per question.
- Strengths and gaps are frequency-ranked recorded strings with stable first-occurrence ties. Areas to improve include weaknesses and missing_points. Focus areas include weak skills and recorded gaps, capped at 12.
- Readiness from overall score: >=75 Ready; >=45 Developing; otherwise Needs practice; no score Not assessed. This is practice guidance, not a hiring decision.
- `confidence_score` remains a language-based answer-confidence average for backward compatibility, including typed answers with a usable stored rationale. Empty/default rationales and the existing 'too short' unassessable rationale do not count. Original persisted values are untouched.
- `verbal_confidence` uses only evaluated `voice` answers with assessed language confidence. It is explicitly a transcript estimate with optional duration influence, **not** a measured acoustic assessment. No new signal extraction is invented.
- `visual_confidence` is separately identifiable observable composure from stored video frames. Across sessions it is frame-weighted; absent audio/typed visual observations never enter the denominator. `visual_analysis.visual_score` remains the teammate's existing multi-dimension on-camera-presence score, not a replacement for composure or answer score.
- Frame observations appear per question only for matching stored question_id and voice answers in video mode. Unassociated frames contribute only to session visual observations. No frames means null plus `not_assessed`; existing analysis semantics for measured frames with no visible face remain unchanged.
- Dates are completed-session completion timestamps. A completed legacy session missing a timestamp is still included but excluded from date-range computation.

## Exact JSON layout

Application REPORT keys and nested shapes (numbers below are illustrative; `null` means unmeasured):

```json
{
  "application_id": "UUID", "company": "Acme", "role": "Engineer",
  "generated_at": "ISO-8601", "completed_session_count": 1,
  "total_questions_attempted": 1, "total_questions_evaluated": 1,
  "date_range": {"from": "ISO-8601 or null", "to": "ISO-8601 or null"},
  "metrics": {"overall_score": 80, "correctness_score": 80, "relevance_score": 80, "depth_score": 80, "clarity_score": 80, "evidence_score": 80, "confidence_score": 70},
  "metric_observation_counts": {"overall_score": 1, "correctness_score": 1, "relevance_score": 1, "depth_score": 1, "clarity_score": 1, "evidence_score": 1, "confidence_score": 1},
  "verbal_confidence": {"status": "not_assessed", "score": null, "observations_count": 0, "basis": "Stored transcript-language confidence estimates for voice answers only."},
  "visual_confidence": {"status": "not_assessed", "score": null, "observations_count": 0, "basis": "Frame-weighted observable composure; no missing frames imputed."},
  "sessions": [], "per_question_analysis": [],
  "strengths": ["Clear example"], "areas_to_improve": ["More depth"],
  "skill_evidence": [{"skill": "Python", "status": "demonstrated", "score": 80, "evidence": [{"interview_id": "UUID", "question_id": "UUID", "score": 80, "reason": "Recorded evaluator feedback"}]}],
  "demonstrated_skills": ["Python"], "skills_needing_improvement": [],
  "assessed_skills": ["Python"], "recommended_focus_areas": ["More depth"],
  "interview_improvement_roadmap": [{"focus": "More depth", "priority": "Medium", "score": null, "reason": "This recurring improvement point was recorded in the interview evaluation feedback."}],
  "interview_skill_recommendations": [{"skill": "Python", "priority": "Medium", "score": 60, "reason": "Recommended from the interview evaluation score of 60/100.", "resources": [{"title": "Python Official Tutorial", "provider": "Python", "difficulty": "beginner", "type": "documentation", "url": "https://docs.python.org/3/tutorial/"}]}],
  "readiness": "Ready", "summary": "Deterministic synthesis"
}
```

Each `sessions` entry is the session REPORT below (no `skill_names` internal helper):

```json
{
  "report_id": "interview UUID", "interview_id": "UUID", "application_id": "UUID",
  "personality": "technical", "difficulty": "medium", "mode": "text",
  "completed_at": "ISO-8601 or null", "started_at": "ISO-8601 or null",
  "overall_score": 80, "technical_score": 80, "communication_score": 80,
  "reasoning_score": 80, "confidence_score": 70, "relevance_score": 80,
  "questions_attempted": 1, "questions_evaluated": 1,
  "strengths": [], "areas_to_improve": [], "readiness": "Ready", "summary": "Session synthesis",
  "metrics": {"overall_score": 80, "correctness_score": 80, "relevance_score": 80, "depth_score": 80, "clarity_score": 80, "evidence_score": 80, "confidence_score": 70},
  "per_question_analysis": [],
  "verbal_confidence": {"status": "not_assessed", "score": null, "observations_count": 0, "basis": "Stored transcript-language estimate; duration may inform the evaluator. No acoustic signal extraction."},
  "visual_confidence": {"status": "not_assessed", "score": null, "observations_count": 0, "basis": "Observable composure in sampled video frames; separate from answer confidence."},
  "visual_analysis": null
}
```

Each `per_question_analysis` entry (same layout within session and application):

```json
{
  "interview_id": "UUID", "question_id": "UUID", "answer_id": "UUID", "question_number": 1,
  "question": "Explain Python APIs.", "topic": "Python", "expected_skills": ["Python"],
  "source": "typed", "answer_modality": "typed", "answer_text": "Transcript or typed text",
  "scores": {"overall_score": 80, "correctness_score": 80, "relevance_score": 80, "depth_score": 80, "clarity_score": 80, "evidence_score": 80, "confidence_score": 70},
  "strengths": [], "weaknesses": [], "missing_points": [], "feedback": "Recorded feedback",
  "confidence_rationale": "Stored rationale", "visual_analysis": null
}
```

`source` remains canonical `typed`/`voice`; `answer_modality` is `typed`/`audio`/`video`. When assessed, `visual_analysis` is exactly the existing visual shape:

```json
{"visual_score": 85, "frames_analyzed": 3, "face_visible_rate": 1.0, "eye_contact_rate": 1.0, "engagement": 80.0, "attentiveness": 80.0, "composure": 90.0, "presentation": 80.0, "common_expressions": ["neutral"], "observations": ["Face centered."]}
```

Complete response retains interview_id, status, completed_at, question_count, answered_count, average_score, average_confidence, summary, recommendation, mode, visual_analysis. Added: report_id, application_id, overall_score, technical_score, communication_score, reasoning_score, confidence_score, relevance_score, questions_attempted, questions_evaluated, strengths, areas_to_improve, readiness, per_question_analysis, verbal_confidence, visual_confidence. Legacy average_confidence remains unchanged; consumers should use the new identified observations for modality-aware interpretation.

## Person 3 handoff

Consume `data.skill_evidence`, `demonstrated_skills`, `skills_needing_improvement`, `assessed_skills`, and `recommended_focus_areas` from the additive application JSON endpoint. No Person 3 API is called or modified. `interview_improvement_roadmap` and `interview_skill_recommendations` are interview-report-only outputs; they must not modify the separate resume/JD/ATS career roadmap.

Skill identities are trimmed and case-folded for merging, with first observed spelling preserved. Use expected_skills; use topic only if no expected_skills exist. Correctness scores from associated evaluated questions are the skill proxy; no individual per-skill score was measured. Evidence reason is recorded evaluator feedback, with interview/question provenance. >=75 is demonstrated, below75 needs_improvement. A known skill from an unanswered/unevaluated completed-session question has null score, empty evidence, and not_assessed. Skills never mentioned by completed-session questions are omitted, **not missing**. Person 3 can join its own required-skill set and treat absent evidence as not_assessed. A low score is not proof that a skill is absent.

## PDF and frontend

PyMuPDF generates wrapped multipage output entirely in memory; no PDF or media artifact is committed. Includes heading, company/role/date, scores/readiness, sessions, strengths, gaps, skill statuses, focus, question scores/feedback/video observations and overall summary. Uses standard built-in PDF fonts; complex international scripts may require a future font-embedding enhancement. No chart dependency was added; frontend score bars are accessible CSS meters. Long answers and skill evidence are collapsible. The PDF omits raw recordings and full transcripts, retaining question evaluation summaries.

Practice pages still submit/evaluate immediately for adaptation, but show a saved confirmation rather than detailed per-answer feedback. Completing typed/audio/video opens the existing session review. Setup and session review link to the consolidated report. Application reports handle empty/loading/error/missing metrics and authenticated PDF download.

## Manual test procedure

1. Login with a PREMIUM user.
2. Open/create a canonical application with company and role.
3. Complete a Technical interview using typed/audio answers.
4. Confirm completion opens the session summary and review; feedback was saved internally during practice.
5. Complete another Behavioral or Mixed interview, preferably video with available Gemini vision.
6. Open Application report from interview setup or session review.
7. Verify both completed sessions appear; an unfinished third session must not contribute.
8. Compare aggregate dimensions to the arithmetic mean of stored evaluated answer scores, excluding unevaluated answers.
9. Check frequency-ranked strengths/weaknesses and next focus areas.
10. Check skill provenance; untested/unevaluated skills must never become missing skills.
11. Check video observations appear only where stored; audio visual confidence must be not assessed. Verbal confidence must remain identifiable as a transcript estimate.
12. Download PDF; confirm application/pdf and a UUID-specific filename.
13. Open PDF and verify wrapping, multipage content, and readable evaluation summaries.
14. GET application report JSON with JWT and inspect the machine-readable handoff arrays; do not call frozen Person 3 APIs.
15. Try another owner's application (404), nonexistent application (404), free user (403), and no JWT (401).

## Validation

Focused reporting tests cover session and application aggregation, multiple/incomplete/unevaluated sessions, skill semantics, modalities, absent camera data, ownership/premium/nonexistence, and PDF parsing/pagination. Existing Person 2 interview/audio/video tests were run: 71 passed; two pre-existing failures are strength-list truncation expectations in `test_fallback_evaluation_links_behavioral_collaboration_components_to_feedback_event` and `test_fallback_evaluation_handles_friendly_decision_tradeoff_components`. The evaluator was not changed. Frontend typecheck and production build pass. No migration introduced; one existing Alembic head remains.

Final combined reporting + Person 2 run: **80 passed, 2 pre-existing failures** (9 reporting cases pass). Additional auth/application/billing run: **11 passed**. Commands from repository root:

```powershell
& .venv/Scripts/python.exe -m pytest backend/tests/test_interview_reporting.py backend/tests/test_interviews.py backend/tests/test_interview_audio.py backend/tests/test_video_interview.py -q
& .venv/Scripts/python.exe -m pytest backend/tests/test_auth.py backend/tests/test_applications.py backend/tests/test_billing.py -q
```

From frontend: `npm.cmd run build` and `node_modules/.bin/tsc.cmd --noEmit --incremental false`. From backend: `../.venv/Scripts/python.exe -m alembic heads` -> `0010_video_interview (head)`. No live database migration/current check was required or performed because no migration was introduced. Live Gemini, camera/microphone UX, and opening the PDF in a desktop viewer remain manual checks; automated tests parse PDF bytes and exercise the existing mocked audio/video integration.
