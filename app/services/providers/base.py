from abc import ABC, abstractmethod


class RecommendationProvider(ABC):

    @abstractmethod
    def get_resources(
        self,
        skill: str,
        priority: str | None = None
    ) -> list:
        """
        Return learning resources for a skill.

        Every provider must return a list of resources
        in the same normalized format.
        """
        pass