"""Reviewer — Stage 1 API.

POST a unified diff, get structured findings back. Provider is chosen by
REVIEWER_PROVIDER (mock by default, so the app runs without a key).
"""

from fastapi import FastAPI, HTTPException

from .config import settings
from .diff import parse_unified_diff
from .models import ReviewRequest, ReviewResponse
from .providers.base import ReviewProvider
from .providers.mock import MockProvider

app = FastAPI(title="Reviewer", version="0.1.0")


def get_provider() -> ReviewProvider:
    if settings.provider == "gemini":
        if not settings.gemini_api_key:
            raise HTTPException(
                status_code=500,
                detail="REVIEWER_PROVIDER=gemini but GEMINI_API_KEY is not set.",
            )
        from .providers.gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)

    return MockProvider()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "provider": settings.provider}


@app.post("/review", response_model=ReviewResponse)
async def review(request: ReviewRequest) -> ReviewResponse:
    if len(request.diff) > settings.max_diff_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Diff exceeds MAX_DIFF_CHARS ({settings.max_diff_chars}).",
        )

    files = parse_unified_diff(request.diff)
    if not files:
        raise HTTPException(
            status_code=422,
            detail="No added lines found. Send a unified diff with file headers.",
        )

    provider = get_provider()

    try:
        result = await provider.review(request, files)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - convert provider failures to 502
        raise HTTPException(
            status_code=502,
            detail=f"Provider '{provider.name}' failed: {exc}",
        ) from exc

    return ReviewResponse(
        summary=result.summary,
        findings=result.findings,
        provider=provider.name,
        model=provider.model,
        files_reviewed=len(files),
    )
