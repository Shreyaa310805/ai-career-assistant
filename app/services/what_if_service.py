def simulate_what_if(
    application_id,
    skill,
    current_match_score,
    job_importance,
    current_level,
    target_level
):
    # If the target level is not higher,
    # learning produces no improvement
    skill_improvement = max(
        target_level - current_level,
        0
    )

    # Calculate estimated score improvement
    estimated_improvement = (
        job_importance
        * skill_improvement
        * 20
    )

    estimated_improvement = round(
        estimated_improvement,
        2
    )

    # Match score cannot exceed 100
    estimated_match_score = min(
        current_match_score + estimated_improvement,
        100
    )

    estimated_match_score = round(
        estimated_match_score,
        2
    )

    # Calculate impact level
    if estimated_improvement >= 10:
        impact = "HIGH"
    elif estimated_improvement >= 5:
        impact = "MEDIUM"
    else:
        impact = "LOW"

    # Create a readable explanation
    if estimated_improvement == 0:
        message = (
            f"Improving {skill} to the selected level "
            "does not produce an estimated match improvement."
        )
    elif impact == "HIGH":
        message = (
            f"Improving {skill} could significantly improve "
            "your match for this role."
        )
    elif impact == "MEDIUM":
        message = (
            f"Improving {skill} could moderately improve "
            "your match for this role."
        )
    else:
        message = (
            f"Improving {skill} could provide a small improvement "
            "to your match for this role."
        )

    return {
        "application_id": application_id,
        "skill": skill,
        "current_level": current_level,
        "target_level": target_level,
        "current_match_score": current_match_score,
        "estimated_match_score": estimated_match_score,
        "estimated_improvement": estimated_improvement,
        "impact": impact,
        "message": message
    }