"""Gemini provider.

Uses structured output: the model must answer with the LLMReview schema, so we
get validated JSON instead of prose we would have to parse.
"""

from google import genai
from google.genai import types

from ..diff import ChangedFile
from ..models import LLMReview, ReviewRequest
from ..prompt import SYSTEM_PROMPT, build_user_prompt


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = genai.Client(api_key=api_key)

    async def review(
        self, request: ReviewRequest, files: list[ChangedFile]
    ) -> LLMReview:
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=build_user_prompt(request, files),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=LLMReview,
                temperature=0.2,
            ),
        )

        if isinstance(response.parsed, LLMReview):
            return response.parsed

        # Fallback: some SDK versions return text even with a schema.
        return LLMReview.model_validate_json(response.text or '{"summary": "", "findings": []}')
