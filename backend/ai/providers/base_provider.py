from abc import ABC, abstractmethod


class AIProvider(ABC):
    """
    Base interface for every AI provider.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate text from a prompt.
        """
        pass