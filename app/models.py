"""Request/response schemas.

These Pydantic models are the contract of the whole system:
- the API validates incoming data against them
- the model is forced to answer in this shape
- tests assert on them

Keeping model output typed is what turns an LLM call into an API.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Category(StrEnum):
    bug = "bug"
    security = "security"
    performance = "performance"
    style = "style"
    test = "test"
    maintainability = "maintainability"


class Finding(BaseModel):
    """A single review comment."""

    file: str = Field(description="Path of the reviewed file")
    line: int | None = Field(
        default=None, description="Line number in the new version of the file"
    )
    severity: Severity
    category: Category
    message: str = Field(description="What is wrong, concretely")
    suggestion: str | None = Field(
        default=None, description="Optional concrete fix, not vague advice"
    )


class LLMReview(BaseModel):
    """Exactly what the model is allowed to return."""

    summary: str = Field(description="One or two sentences about the diff overall")
    findings: list[Finding] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    diff: str = Field(min_length=1, max_length=200_000)
    language: str | None = Field(default=None, max_length=40)
    context: str | None = Field(
        default=None,
        max_length=4_000,
        description="Optional project conventions or information about the change",
    )


class ReviewResponse(LLMReview):
    """LLMReview plus server-side metadata."""

    provider: str
    model: str | None = None
    files_reviewed: int
