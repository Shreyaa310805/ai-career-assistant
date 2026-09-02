from app.services.providers.official_provider import OfficialProvider
from app.services.providers.external_provider import ExternalProvider
from app.services.providers.gemini_provider import GeminiProvider


def get_learning_recommendations(application_id, skills):

    official_provider = OfficialProvider()
    external_provider = ExternalProvider()
    gemini_provider = GeminiProvider()

    recommendations = []

    for skill_data in skills:

        skill = skill_data.skill
        priority = skill_data.priority

        all_resources = []

        # 1. Official resources
        official_resources = official_provider.get_resources(
            skill,
            priority
        )
        all_resources.extend(official_resources)

        # 2. External API resources
        external_resources = external_provider.get_resources(
            skill,
            priority
        )
        all_resources.extend(external_resources)

        # 3. Gemini AI resources
        gemini_resources = gemini_provider.get_resources(
            skill,
            priority
        )
        all_resources.extend(gemini_resources)

        recommendations.append(
            {
                "skill": skill,
                "priority": priority,
                "resources": all_resources
            }
        )

    return {
        "application_id": application_id,
        "recommendations": recommendations
    }