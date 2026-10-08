"""Read-only deterministic reports over canonical persisted interview evidence."""
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import quote_plus

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


def interview_improvement_roadmap(skill_evidence, focus_areas):
    """Create a report-local roadmap from completed interview evidence only."""
    steps = []
    included = set()
    weak_skills = (item for item in skill_evidence if item["status"] == "needs_improvement" and item["score"] is not None)
    for item in sorted(weak_skills, key=lambda item: (float(item["score"]), item["skill"].casefold())):
        skill = item["skill"]
        included.add(skill.casefold())
        score = float(item["score"])
        steps.append({
            "focus": skill,
            "priority": "High" if score < 50 else "Medium",
            "score": score,
            "reason": f"Interview answers associated with {skill} averaged {score:.0f}/100 for correctness.",
        })
    for focus in focus_areas:
        normalized = focus.strip().casefold()
        if not normalized or normalized in included:
            continue
        included.add(normalized)
        steps.append({
            "focus": focus,
            "priority": "Medium",
            "score": None,
            "reason": "This recurring improvement point was recorded in the interview evaluation feedback.",
        })
    return steps


_INTERVIEW_SKILL_RESOURCES = {
    "python": [
        {"title": "Python Official Tutorial", "provider": "Python", "difficulty": "beginner", "type": "documentation", "url": "https://docs.python.org/3/tutorial/"},
        {"title": "Python Practice Problems", "provider": "HackerRank", "difficulty": "intermediate", "type": "practice", "url": "https://www.hackerrank.com/domains/python"},
    ],
    "sql": [
        {"title": "SQL Tutorial", "provider": "PostgreSQL", "difficulty": "beginner", "type": "documentation", "url": "https://www.postgresql.org/docs/current/tutorial.html"},
        {"title": "SQL Practice", "provider": "HackerRank", "difficulty": "intermediate", "type": "practice", "url": "https://www.hackerrank.com/domains/sql"},
    ],
    "api design": [
        {"title": "Web API Design Guide", "provider": "Google Cloud", "difficulty": "intermediate", "type": "documentation", "url": "https://cloud.google.com/apis/design"},
    ],
}


def interview_skill_recommendations(skill_evidence):
    """Return learning resources only for assessed interview skill gaps."""
    recommendations = []
    for item in sorted(
        (item for item in skill_evidence if item["status"] == "needs_improvement" and item["score"] is not None),
        key=lambda item: (float(item["score"]), item["skill"].casefold()),
    ):
        skill = item["skill"]
        score = float(item["score"])
        resources = _INTERVIEW_SKILL_RESOURCES.get(skill.casefold())
        resources = list(resources) if resources else []
        if not resources:
            query = quote_plus(skill.strip())
            resources.append({
                "title": f"Practice {skill}", "provider": "Web search", "difficulty": "intermediate", "type": "practice",
                "url": f"https://www.google.com/search?q={query}+interview+practice",
            })
        query = quote_plus(f"{skill.strip()} tutorial")
        resources.append({
            "title": f"Popular YouTube tutorials: {skill.strip()}", "provider": "YouTube",
            "difficulty": "beginner", "type": "video",
            "url": f"https://www.youtube.com/results?search_query={query}",
        })
        recommendations.append({
            "skill": skill,
            "priority": "High" if score < 50 else "Medium",
            "score": score,
            "reason": f"Recommended from the interview evaluation score of {score:.0f}/100.",
            "resources": resources,
        })
    return recommendations


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
    focus_areas = ranked([*weak, *gaps])[:12]
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
        "recommended_focus_areas": focus_areas, "readiness": readiness(metrics["overall_score"]),
        "interview_improvement_roadmap": interview_improvement_roadmap(evidence, focus_areas),
        "interview_skill_recommendations": interview_skill_recommendations(evidence),
        "summary": f"{len(sessions)} completed sessions and {len(questions)} evaluated answers. {readiness(metrics['overall_score'])}. " + ("Focus next on " + "; ".join([*weak, *gaps][:3]) + "." if weak or gaps else ""),
    }


def report_pdf(report):
    """Build a paginated, reader-friendly interview report with native PDF charts."""
    import fitz

    doc = fitz.open()
    width, height = 595, 842
    margin = 42
    ink = (0.12, 0.16, 0.24)
    muted = (0.39, 0.44, 0.53)
    brand = (0.29, 0.27, 0.88)
    brand_light = (0.93, 0.93, 1.0)
    line = (0.87, 0.89, 0.92)
    green = (0.12, 0.55, 0.38)
    amber = (0.72, 0.43, 0.08)
    red = (0.72, 0.22, 0.25)
    page = None
    y = 0

    def new_page():
        nonlocal page, y
        page = doc.new_page(width=width, height=height)
        page.draw_rect(fitz.Rect(0, 0, width, height), color=None, fill=(1, 1, 1))
        page.draw_rect(fitz.Rect(0, 0, width, 7), color=None, fill=brand)
        page.insert_text((margin, 31), "SKILLSYNC  /  INTERVIEW REPORT", fontsize=8,
                         fontname="hebo", color=muted)
        y = 55

    def ensure_space(amount):
        nonlocal y
        if page is None:
            new_page()
        if y + amount > height - 52:
            new_page()

    def write(text, size=9.5, color=ink, bold=False, italic=False, indent=0, after=5):
        nonlocal y
        font = "hebo" if bold else "heit" if italic else "helv"
        available = width - margin * 2 - indent
        line_height = size * 1.45
        paragraphs = str(text or "").splitlines() or [""]
        for paragraph in paragraphs:
            words = paragraph.split()
            lines = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if current and fitz.get_text_length(candidate, fontname=font, fontsize=size) > available:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
            for text_line in lines:
                ensure_space(line_height)
                page.insert_text((margin + indent, y + size), text_line, fontsize=size,
                                 fontname=font, color=color)
                y += line_height
        y += after

    def section(title):
        nonlocal y
        ensure_space(34)
        rect = fitz.Rect(margin, y, width - margin, y + 25)
        page.draw_rect(rect, color=None, fill=brand_light)
        page.insert_text((margin + 10, y + 17), title, fontsize=10,
                         fontname="hebo", color=brand)
        y += 34

    def score_color(value):
        return green if value >= 75 else amber if value >= 50 else red

    def bars(title, rows):
        nonlocal y
        section(title)
        label_width = 130
        bar_x = margin + label_width
        bar_width = width - margin * 2 - label_width - 48
        for label, value in rows:
            ensure_space(27)
            page.insert_text((margin, y + 10), label, fontsize=8.5, fontname="helv", color=ink)
            track = fitz.Rect(bar_x, y + 1, bar_x + bar_width, y + 11)
            page.draw_rect(track, color=None, fill=(0.93, 0.94, 0.96))
            if value is not None:
                score = max(0.0, min(100.0, float(value)))
                filled = fitz.Rect(bar_x, y + 1, bar_x + bar_width * score / 100, y + 11)
                page.draw_rect(filled, color=None, fill=score_color(score))
                page.insert_text((bar_x + bar_width + 8, y + 10), f"{score:.0f}", fontsize=8,
                                 fontname="hebo", color=ink)
            else:
                page.insert_text((bar_x + bar_width + 5, y + 10), "N/A", fontsize=7.5,
                                 fontname="helv", color=muted)
            y += 25
        y += 5

    def trend_chart():
        nonlocal y
        questions = report.get("per_question_analysis", [])
        valid = [q for q in questions if q.get("scores", {}).get("overall_score") is not None]
        section("Score by question")
        if not valid:
            write("Scores will appear here after evaluated answers are available.", color=muted)
            return
        chart_height = 144
        ensure_space(chart_height + 22)
        left, top = margin + 35, y + 8
        chart_width = width - margin * 2 - 55
        plot_height = 102
        for mark in (0, 50, 100):
            line_y = top + plot_height * (100 - mark) / 100
            page.draw_line((left, line_y), (left + chart_width, line_y), color=line, width=0.7)
            page.insert_text((margin, line_y + 3), str(mark), fontsize=7, fontname="helv", color=muted)
        session_order = {session.get("interview_id"): i + 1 for i, session in enumerate(report.get("sessions", []))}
        points = []
        for i, question in enumerate(valid):
            x = left + (chart_width * i / max(len(valid) - 1, 1))
            value = max(0.0, min(100.0, float(question["scores"]["overall_score"])))
            point_y = top + plot_height * (100 - value) / 100
            points.append((x, point_y))
            if i:
                page.draw_line(points[i - 1], points[i], color=brand, width=2)
            page.draw_circle((x, point_y), 3, color=brand, fill=brand)
            if len(valid) <= 12 or i % max(1, len(valid) // 8) == 0:
                sid = session_order.get(question.get("interview_id"), 1)
                label = f"S{sid} Q{question.get('question_number', i + 1)}"
                page.insert_text((x - 14, top + plot_height + 16), label, fontsize=6.5,
                                 fontname="helv", color=muted)
        y += chart_height

    def bullet(text, color=ink):
        write(f"•  {text}", size=9, color=color, indent=4, after=3)

    # Opening summary
    new_page()
    write("Interview performance", size=23, color=ink, bold=True, after=3)
    write(f"{report.get('role', 'Role')}  |  {report.get('company', 'Company')}",
          size=12, color=brand, bold=True, after=5)
    generated = report.get("generated_at")
    if generated:
        if hasattr(generated, "strftime"):
            generated = generated.strftime("%B %d, %Y")
        else:
            generated = str(generated)[:10]
        write(f"Prepared {generated}", size=8.5, color=muted, after=14)

    score = report.get("metrics", {}).get("overall_score")
    card_gap = 8
    card_width = (width - margin * 2 - card_gap * 3) / 4
    cards = [
        ("Overall score", f"{score:.0f} / 100" if score is not None else "Not assessed"),
        ("Readiness", str(report.get("readiness", "Not assessed"))),
        ("Sessions", str(report.get("completed_session_count", 0))),
        ("Answers evaluated", str(report.get("total_questions_evaluated", 0))),
    ]
    ensure_space(64)
    for index, (label, value) in enumerate(cards):
        x = margin + index * (card_width + card_gap)
        rect = fitz.Rect(x, y, x + card_width, y + 56)
        page.draw_rect(rect, color=line, fill=(0.98, 0.985, 1), width=0.8)
        page.insert_text((x + 9, y + 18), label, fontsize=7, fontname="helv", color=muted)
        page.insert_textbox(fitz.Rect(x + 8, y + 25, x + card_width - 6, y + 49), value,
                            fontsize=10 if index != 1 else 8.5, fontname="hebo", color=ink)
    y += 72

    metrics = report.get("metrics", {})
    dimension_rows = [
        ("Correctness", metrics.get("correctness_score")),
        ("Relevance", metrics.get("relevance_score")),
        ("Depth", metrics.get("depth_score")),
        ("Clarity", metrics.get("clarity_score")),
        ("Evidence", metrics.get("evidence_score")),
        ("Language confidence", metrics.get("confidence_score")),
    ]
    bars("Average by dimension", dimension_rows)
    confidence_rows = []
    for key, label in (("verbal_confidence", "Verbal confidence"), ("visual_confidence", "On-camera presence")):
        item = report.get(key, {})
        confidence_rows.append((label, item.get("score")))
    bars("Confidence and on-camera presence", confidence_rows)
    trend_chart()

    section("Your performance at a glance")
    write(report.get("summary", "Your results are based on completed interview answers."), size=9.5, after=8)
    if report.get("date_range", {}).get("from"):
        start = str(report["date_range"]["from"])[:10]
        end = str(report["date_range"].get("to") or report["date_range"]["from"])[:10]
        write(f"Sessions covered: {start} to {end}", size=8.5, color=muted)

    # Consolidated observations and practice plan
    strengths = report.get("strengths", [])
    improvements = report.get("areas_to_improve", [])
    if strengths:
        section("Strengths")
        for item in strengths[:12]:
            bullet(item, green)
    if improvements:
        section("Areas to work on")
        for item in improvements[:12]:
            bullet(item, amber)

    roadmap = report.get("interview_improvement_roadmap", [])
    if roadmap:
        section("Your practice plan")
        for index, step in enumerate(roadmap, start=1):
            ensure_space(58)
            page.draw_circle((margin + 9, y + 7), 9, color=brand_light, fill=brand_light)
            page.insert_text((margin + 6, y + 10), str(index), fontsize=7.5, fontname="hebo", color=brand)
            priority_color = red if step.get("priority") == "High" else amber
            write(f"{step.get('focus', 'Practice area')}  ·  {step.get('priority', 'Medium')} priority", size=9.5,
                  bold=True, color=priority_color, indent=26, after=2)
            write(step.get("reason", ""), size=8.5, color=muted, indent=26, after=7)

    evidence = [item for item in report.get("skill_evidence", []) if item.get("score") is not None]
    if evidence:
        bars("Skill evidence", [(item["skill"], item["score"]) for item in evidence[:12]])

    recommendations = report.get("interview_skill_recommendations", [])
    if recommendations:
        section("Suggested learning resources")
        for recommendation in recommendations:
            write(f"{recommendation['skill']}  ·  {recommendation['priority']} priority", size=9.5,
                  bold=True, after=2)
            write(recommendation.get("reason", ""), size=8.5, color=muted, indent=8, after=3)
            for resource in recommendation.get("resources", []):
                ensure_space(18)
                label = f"{resource.get('title', 'Open resource')}  ({resource.get('provider', 'Resource')})"
                x = margin + 10
                text_width = min(fitz.get_text_length(label, fontname="helv", fontsize=8.5), width - margin * 2 - 14)
                page.insert_text((x, y + 9), label, fontsize=8.5, fontname="helv", color=brand)
                if resource.get("url"):
                    page.insert_link({"kind": fitz.LINK_URI,
                                      "from": fitz.Rect(x, y, x + text_width, y + 13),
                                      "uri": resource["url"]})
                y += 15
            y += 5

    questions = report.get("per_question_analysis", [])
    if questions:
        section("Question-by-question feedback")
        for q in questions:
            ensure_space(34)
            label = (f"Question {q.get('question_number', '?')}  ·  {q.get('topic', 'Interview')}  ·  "
                     f"{q.get('answer_modality', 'text').title()}")
            score_value = q.get("scores", {}).get("overall_score")
            suffix = f"  ·  {score_value:.0f}/100" if score_value is not None else ""
            rect = fitz.Rect(margin, y, width - margin, y + 22)
            page.draw_rect(rect, color=None, fill=brand_light)
            page.insert_text((margin + 8, y + 15), label + suffix, fontsize=8.5,
                             fontname="hebo", color=brand)
            y += 29
            write(q.get("question", ""), size=9.5, bold=True, after=5)
            if q.get("answer_text"):
                write("Your answer", size=8, bold=True, color=muted, after=2)
                write(q["answer_text"], size=8.5, color=ink, indent=8, after=5)
            if q.get("feedback"):
                write("Feedback", size=8, bold=True, color=muted, after=2)
                write(q["feedback"], size=8.5, indent=8, after=5)
            if q.get("confidence_rationale"):
                write("Confidence: " + q["confidence_rationale"], size=8, color=muted, indent=8, after=4)
            if q.get("strengths"):
                write("Strengths: " + "; ".join(q["strengths"]), size=8.5, color=green, indent=8, after=3)
            concerns = [*q.get("weaknesses", []), *q.get("missing_points", [])]
            if concerns:
                write("To improve: " + "; ".join(concerns), size=8.5, color=amber, indent=8, after=3)
            if q.get("visual_analysis"):
                observations = q["visual_analysis"].get("observations", [])
                if observations:
                    write("On-camera observations: " + "; ".join(observations), size=8, color=muted, indent=8, after=3)
            y += 7

    # Consistent footer and page numbering after all pages have been laid out.
    total_pages = len(doc)
    for number, current in enumerate(doc, start=1):
        current.draw_line((margin, height - 36), (width - margin, height - 36), color=line, width=0.7)
        current.insert_text((margin, height - 20), "SkillSync  ·  Interview results", fontsize=7.5,
                            fontname="helv", color=muted)
        current.insert_text((width - margin - 55, height - 20), f"Page {number} of {total_pages}",
                            fontsize=7.5, fontname="helv", color=muted)
    result = doc.tobytes()
    doc.close()
    return result
