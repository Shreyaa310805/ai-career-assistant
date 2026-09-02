import requests

from app.core.config import YOUTUBE_API_KEY
from app.services.providers.base import RecommendationProvider


class ExternalProvider(RecommendationProvider):

    def get_resources(
        self,
        skill: str,
        priority: str | None = None
    ) -> list:

        # If the API key is missing, fail safely
        if not YOUTUBE_API_KEY:
            return []

        search_query = f"{skill} beginner tutorial"

        url = "https://www.googleapis.com/youtube/v3/search"

        params = {
            "part": "snippet",
            "q": search_query,
            "type": "video",
            "maxResults": 3,
            "key": YOUTUBE_API_KEY
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            resources = []

            for item in data.get("items", []):

                video_id = item.get(
                    "id",
                    {}
                ).get("videoId")

                snippet = item.get(
                    "snippet",
                    {}
                )

                if not video_id:
                    continue

                resources.append(
                    {
                        "title": snippet.get(
                            "title",
                            "Untitled Video"
                        ),
                        "type": "video",
                        "provider": snippet.get(
                            "channelTitle",
                            "YouTube"
                        ),
                        "difficulty": "beginner",
                        "url": (
                            f"https://www.youtube.com/"
                            f"watch?v={video_id}"
                        ),
                        "source": "external_api"
                    }
                )

            return resources

        except requests.RequestException as error:
            print(
                f"External recommendation API error: {error}"
            )

            return []