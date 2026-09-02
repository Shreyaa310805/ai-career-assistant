def calculate_priority(application_id, skills):
    prioritized_skills = []

    for skill_data in skills:
        skill_gap = 1 - skill_data.current_level

        priority_score = (
            skill_data.job_importance * skill_gap
        )

        priority_score = round(priority_score, 2)

        if priority_score >= 0.70:
            priority = "HIGH"
            reason = (
                "High job importance and low current skill level"
            )

        elif priority_score >= 0.40:
            priority = "MEDIUM"
            reason = (
                "Moderate skill gap or job importance"
            )

        else:
            priority = "LOW"
            reason = (
                "Lower job importance or smaller skill gap"
            )

        prioritized_skills.append(
            {
                "skill": skill_data.skill,
                "priority_score": priority_score,
                "priority": priority,
                "reason": reason
            }
        )

    # Highest priority skill comes first
    prioritized_skills.sort(
        key=lambda item: item["priority_score"],
        reverse=True
    )

    return {
        "application_id": application_id,
        "prioritized_skills": prioritized_skills
    }