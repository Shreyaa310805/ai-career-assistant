from app.data.mock_data import MOCK_APPLICATIONS

from app.services.skill_gap_service import analyze_skill_gap
from app.services.priority_service import calculate_priority
from app.services.recommendation_service import (
    get_learning_recommendations
)


class SkillData:
    def __init__(
        self,
        skill,
        job_importance,
        current_level
    ):
        self.skill = skill
        self.job_importance = job_importance
        self.current_level = current_level


class RecommendationSkill:
    def __init__(self, skill, priority):
        self.skill = skill
        self.priority = priority


def generate_career_roadmap(application_id):

    # 1. Get application data
    application = MOCK_APPLICATIONS.get(application_id)

    if not application:
        return None

    # -----------------------------------
    # 2. ISSUE-40: Skill Gap Analysis
    # -----------------------------------
    skill_gap_result = analyze_skill_gap(
        application_id=application_id,
        required_skills=application["required_skills"],
        user_skills=application["user_skills"]
    )

    # -----------------------------------
    # 3. ISSUE-41: Priority Scoring
    # -----------------------------------
    importance_map = {
        "fastapi": 0.9,
        "docker": 0.8,
        "aws": 0.7
    }

    priority_inputs = []

    for skill in skill_gap_result["missing_skills"]:

        priority_inputs.append(
            SkillData(
                skill=skill,
                job_importance=importance_map.get(
                    skill.lower(),
                    0.5
                ),
                current_level=0.0
            )
        )

    priority_result = calculate_priority(
        application_id=application_id,
        skills=priority_inputs
    )

    # -----------------------------------------
    # 4. Convert priority output into
    #    recommendation input
    # -----------------------------------------
    recommendation_inputs = []

    for skill_data in priority_result["prioritized_skills"]:

        recommendation_inputs.append(
            RecommendationSkill(
                skill=skill_data["skill"],
                priority=skill_data["priority"]
            )
        )

    # -----------------------------------------
    # 5. ISSUE-44: Priority-Aware Resources
    # -----------------------------------------
    recommendation_result = get_learning_recommendations(
        application_id=application_id,
        skills=recommendation_inputs
    )

    # -----------------------------------
    # 6. Return Complete Roadmap
    # -----------------------------------
    return {
        "application_id": application_id,
        "company": application["company"],
        "role": application["role"],
        "current_match_score": application[
            "current_match_score"
        ],

        "skill_gap": {
            "matched_skills": skill_gap_result[
                "matched_skills"
            ],
            "missing_skills": skill_gap_result[
                "missing_skills"
            ],
            "extra_skills": skill_gap_result[
                "extra_skills"
            ],
            "skill_gap_count": skill_gap_result[
                "skill_gap_count"
            ]
        },

        "prioritized_skills": priority_result[
            "prioritized_skills"
        ],

        "recommendations": recommendation_result[
            "recommendations"
        ]
    }