"""Provider contract.

Both the mock provider and Gemini implement this, so the API never depends on
one vendor. Swapping or adding a provider (OpenAI, Claude, Ollama) means
writing one class, not touching the endpoint.
"""

from typing import Protocol

from ..diff import ChangedFile
from ..models import LLMReview, ReviewRequest


class ReviewProvider(Protocol):
    name: str
    model: str | None

    async def review(
        self, request: ReviewRequest, files: list[ChangedFile]
    ) -> LLMReview: ...
