def analyze_skill_gap(application_id, required_skills, user_skills):
    # Convert skills to lowercase for comparison
    required_map = {
        skill.strip().lower(): skill.strip()
        for skill in required_skills
    }

    user_map = {
        skill.strip().lower(): skill.strip()
        for skill in user_skills
    }

    required_set = set(required_map.keys())
    user_set = set(user_map.keys())

    # Skills present in both lists
    matched_keys = required_set.intersection(user_set)

    # Skills required by the job but missing from the user
    missing_keys = required_set.difference(user_set)

    # Skills the user has but are not required for this job
    extra_keys = user_set.difference(required_set)

    return {
        "application_id": application_id,

        "matched_skills": [
            required_map[skill] for skill in sorted(matched_keys)
        ],

        "missing_skills": [
            required_map[skill] for skill in sorted(missing_keys)
        ],

        "extra_skills": [
            user_map[skill] for skill in sorted(extra_keys)
        ],

        "skill_gap_count": len(missing_keys)
    }