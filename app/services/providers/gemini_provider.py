from app.services.providers.base import RecommendationProvider


class GeminiProvider(RecommendationProvider):

    def get_resources(
        self,
        skill: str,
        priority: str | None = None
    ) -> list:

        # Gemini AI integration will be added later.
        return []