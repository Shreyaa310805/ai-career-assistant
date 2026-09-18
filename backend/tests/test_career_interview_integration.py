from app.services.interview_reporting import interview_improvement_roadmap


def test_interview_roadmap_uses_only_assessed_interview_evidence_and_feedback():
    roadmap = interview_improvement_roadmap(
        [
            {"skill": "Python", "status": "needs_improvement", "score": 40},
            {"skill": "SQL", "status": "demonstrated", "score": 82},
            {"skill": "Docker", "status": "not_assessed", "score": None},
        ],
        ["Python", "Use more concrete examples"],
    )

    assert roadmap == [
        {
            "focus": "Python", "priority": "High", "score": 40.0,
            "reason": "Interview answers associated with Python averaged 40/100 for correctness.",
        },
        {
            "focus": "Use more concrete examples", "priority": "Medium", "score": None,
            "reason": "This recurring improvement point was recorded in the interview evaluation feedback.",
        },
    ]
