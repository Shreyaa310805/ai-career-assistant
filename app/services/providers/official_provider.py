from app.services.providers.base import RecommendationProvider
from app.data.mock_data import LEARNING_RESOURCES


class OfficialProvider(RecommendationProvider):

    def get_resources(
        self,
        skill: str,
        priority: str | None = None
    ) -> list:

        normalized_skill = skill.strip().lower()

        resources = LEARNING_RESOURCES.get(
            normalized_skill,
            []
        )

        normalized_resources = []

        for resource in resources:
            normalized_resources.append(
                {
                    "title": resource["title"],
                    "type": resource["type"],
                    "provider": resource["provider"],
                    "difficulty": resource["difficulty"],
                    "url": resource["url"],
                    "source": "official"
                }
            )

        return normalized_resources