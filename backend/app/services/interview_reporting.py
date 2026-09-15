"""Read-only deterministic reports over canonical persisted interview evidence."""
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.interview import Interview, InterviewQuestion, InterviewAnswer, InterviewVisualFrame
from app.services.interview_visual import aggregate_visual_analysis

METRICS = ("overall_score", "correctness_score", "relevance_score", "depth_score", "clarity_score", "evidence_score", "confidence_score")


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def ranked(values):
    return [value for value, _ in Counter(v.strip() for v in values if v and v.strip()).most_common()]


def readiness(score):
    return "Not assessed" if score is None else "Ready" if score >= 75 else "Developing" if score >= 45 else "Needs practice"


def confidence(score, count, basis):
    return {"status": "assessed" if count else "not_assessed", "score": score, "observations_count": count, "basis": basis}


def sessions_query(application_id):
    return select(Interview).where(Interview.application_id == application_id, Interview.status == "completed").order_by(Interview.completed_at, Interview.id).options(
        selectinload(Interview.questions).selectinload(InterviewQuestion.answers).selectinload(InterviewAnswer.evaluation)
    )


def session_report(interview, db):
    frames = list(db.scalars(select(InterviewVisualFrame).where(InterviewVisualFrame.interview_id == interview.id)).all()) if interview.mode == "video" else []
    visual = aggregate_visual_analysis(frames)
    questions = []
    attempted = set()
    skill_names = {}
    for q in interview.questions:
        for skill in q.expected_skills or [q.topic]:
            if skill and skill.strip():
                skill_names.setdefault(skill.strip().casefold(), skill.strip())
        for a in sorted(q.answers, key=lambda a: (a.created_at, str(a.id))):
            if a.interview_id != interview.id:
                continue
            attempted.add(q.id)
            e = a.evaluation
            if not e:
                continue
            rationale = e.confidence_rationale or ""
            measured_confidence = e.confidence_score if rationale.strip() and "too short" not in rationale.lower() else None
            scores = {m: getattr(e, m, None) for m in METRICS}
            scores["confidence_score"] = measured_confidence
            qvisual = aggregate_visual_analysis([f for f in frames if f.question_id == q.id]) if a.source == "voice" else None
            questions.append({
                "interview_id": str(interview.id), "question_id": str(q.id), "answer_id": str(a.id),
                "question_number": q.question_number, "question": q.question, "topic": q.topic,
                "expected_skills": q.expected_skills or [], "source": a.source,
                "answer_modality": "video" if interview.mode == "video" and a.source == "voice" else "audio" if a.source == "voice" else "typed",
                "answer_text": a.answer_text, "scores": scores, "strengths": e.strengths or [],
                "weaknesses": e.weaknesses or [], "missing_points": e.missing_points or [], "feedback": e.feedback,
                "confidence_rationale": e.confidence_rationale, "visual_analysis": qvisual.model_dump() if qvisual else None,
            })
    metrics = {m: mean(q["scores"][m] for q in questions) for m in METRICS}
    verbal = [q["scores"]["confidence_score"] for q in questions if q["source"] == "voice" and q["scores"]["confidence_score"] is not None]
    strengths = ranked(s for q in questions for s in q["strengths"])
    gaps = ranked(s for q in questions for s in [*q["weaknesses"], *q["missing_points"]])
    score = metrics["overall_score"]
    return {
        "report_id": str(interview.id), "interview_id": str(interview.id), "application_id": str(interview.application_id),
        "personality": interview.personality, "difficulty": interview.difficulty, "mode": interview.mode,
        "completed_at": interview.completed_at, "started_at": interview.started_at,
        "overall_score": score, "technical_score": metrics["correctness_score"], "communication_score": metrics["clarity_score"],
        "reasoning_score": metrics["depth_score"], "confidence_score": metrics["confidence_score"], "relevance_score": metrics["relevance_score"],
        "questions_attempted": len(attempted), "questions_evaluated": len({q['question_id'] for q in questions}),
        "strengths": strengths, "areas_to_improve": gaps, "readiness": readiness(score),
        "summary": interview.summary or f"{len(questions)} evaluated answers. Overall performance: {score if score is not None else 'not assessed'}. {readiness(score)}.",
        "metrics": metrics, "per_question_analysis": questions,
        "verbal_confidence": confidence(mean(verbal), len(verbal), "Stored transcript-language estimate; duration may inform the evaluator. No acoustic signal extraction."),
        "visual_confidence": confidence(visual.composure if visual else None, len(frames), "Observable composure in sampled video frames; separate from answer confidence."),
        "visual_analysis": visual.model_dump() if visual else None, "skill_names": skill_names,
    }


def application_report(application, db):
    sessions = [session_report(i, db) for i in db.scalars(sessions_query(application.id)).all()]
    questions = [q for s in sessions for q in s["per_question_analysis"]]
    metrics = {m: mean(q["scores"][m] for q in questions) for m in METRICS}
    skills = {}
    for session in sessions:
        for key, name in session.pop("skill_names").items():
            skills.setdefault(key, {"skill": name, "status": "not_assessed", "score": None, "evidence": []})
    for q in questions:
        for name in dict.fromkeys(s.strip().casefold() for s in (q["expected_skills"] or [q["topic"]]) if s and s.strip()):
            item = skills[name]
            item["evidence"].append({"interview_id": q["interview_id"], "question_id": q["question_id"], "score": q["scores"]["correctness_score"], "reason": q["feedback"]})
    for item in skills.values():
        item["score"] = mean(e["score"] for e in item["evidence"])
        if item["score"] is not None:
            item["status"] = "demonstrated" if item["score"] >= 75 else "needs_improvement"
    evidence = sorted(skills.values(), key=lambda s: s["skill"].casefold())
    strengths = ranked(v for q in questions for v in q["strengths"])
    gaps = ranked(v for q in questions for v in [*q["weaknesses"], *q["missing_points"]])
    weak = [s["skill"] for s in evidence if s["status"] == "needs_improvement"]
    verbal = [q["scores"]["confidence_score"] for q in questions if q["source"] == "voice" and q["scores"]["confidence_score"] is not None]
    visuals = [s["visual_confidence"] for s in sessions if s["visual_confidence"]["score"] is not None]
    frame_count = sum(v["observations_count"] for v in visuals)
    visual_score = round(sum(v["score"] * v["observations_count"] for v in visuals) / frame_count, 2) if frame_count else None
    dates = [s["completed_at"] for s in sessions if s["completed_at"]]
    return {
        "application_id": str(application.id), "company": application.company, "role": application.role,
        "generated_at": datetime.now(timezone.utc), "completed_session_count": len(sessions),
        "total_questions_attempted": sum(s["questions_attempted"] for s in sessions), "total_questions_evaluated": sum(s["questions_evaluated"] for s in sessions),
        "date_range": {"from": min(dates) if dates else None, "to": max(dates) if dates else None},
        "metrics": metrics, "metric_observation_counts": {m: sum(q["scores"][m] is not None for q in questions) for m in METRICS},
        "verbal_confidence": confidence(mean(verbal), len(verbal), "Stored transcript-language confidence estimates for voice answers only."),
        "visual_confidence": confidence(visual_score, frame_count, "Frame-weighted observable composure; no missing frames imputed."),
        "sessions": sessions, "per_question_analysis": questions, "strengths": strengths, "areas_to_improve": gaps,
        "skill_evidence": evidence, "demonstrated_skills": [s["skill"] for s in evidence if s["status"] == "demonstrated"],
        "skills_needing_improvement": weak, "assessed_skills": [s["skill"] for s in evidence if s["status"] != "not_assessed"],
        "recommended_focus_areas": ranked([*weak, *gaps])[:12], "readiness": readiness(metrics["overall_score"]),
        "summary": f"{len(sessions)} completed sessions and {len(questions)} evaluated answers. {readiness(metrics['overall_score'])}. " + ("Focus next on " + "; ".join([*weak, *gaps][:3]) + "." if weak or gaps else ""),
    }


def report_pdf(report):
    """Use existing PyMuPDF, wrap text and paginate without writing files."""
    import fitz
    from textwrap import wrap
    doc = fitz.open()
    page = None
    y = 800

    def write(text, size=11):
        nonlocal page, y
        for paragraph in str(text).splitlines() or [""]:
            for line in wrap(paragraph, width=85 if size == 11 else 65, break_long_words=True) or [""]:
                if y + size * 1.5 > 780:
                    page = doc.new_page(width=595, height=842)
                    y = 45
                page.insert_text((40, y), line, fontsize=size)
                y += size * 1.5
        y += 5

    write("SkillSync - Application Interview Report", 16)
    write(f"{report['company']} | {report['role']}\nReport date: {report['generated_at'].isoformat()}")
    write(f"{report['completed_session_count']} completed sessions | {report['total_questions_attempted']} attempted | {report['total_questions_evaluated']} evaluated")
    write(f"Overall: {report['metrics']['overall_score']} | Readiness: {report['readiness']}")
    for name, value in report['metrics'].items():
        write(f"{name}: {value if value is not None else 'Not assessed'}")
    for key in ('verbal_confidence', 'visual_confidence'):
        write(f"{key}: {report[key]['score']} ({report[key]['status']})")
    for session in report['sessions']:
        write(f"Session {session['interview_id']}: {session['personality']} / {session['difficulty']} | {session['overall_score']} | {session['questions_attempted']} attempted | {session['completed_at']}")
    for title, key in [('Strengths', 'strengths'), ('Areas to improve', 'areas_to_improve'), ('Recommended focus', 'recommended_focus_areas')]:
        write(title, 14)
        for value in report[key]:
            write(value)
    write('Skill evidence', 14)
    for skill in report['skill_evidence']:
        write(f"{skill['skill']}: {skill['status']} | {skill['score']}")
    write('Per-question evaluation', 14)
    for q in report['per_question_analysis']:
        write(f"Session {q['interview_id']} / Question {q['question_number']} ({q['answer_modality']}): {q['question']}")
        write(f"Scores: {q['scores']}\n{q['feedback']}")
        write('Strengths: ' + '; '.join(q['strengths']) + '\nImprove: ' + '; '.join(q['weaknesses']))
        if q['visual_analysis']:
            write('Video observations: ' + '; '.join(q['visual_analysis']['observations']))
    write(report['summary'])
    result = doc.tobytes()
    doc.close()
    return result
