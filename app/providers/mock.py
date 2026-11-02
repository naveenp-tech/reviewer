"""Offline provider used for tests and for running without an API key.

It is deliberately simple and NOT an LLM: two deterministic heuristics. That
makes the API testable without network access or cost. Its findings say
"mock", so nobody can mistake it for a real review.
"""

from ..diff import ChangedFile
from ..models import Category, Finding, LLMReview, ReviewRequest, Severity


class MockProvider:
    name = "mock"
    model = None

    async def review(
        self, request: ReviewRequest, files: list[ChangedFile]
    ) -> LLMReview:
        findings: list[Finding] = []

        for changed in files:
            for line_no, text in changed.added:
                lowered = text.lower()

                if "eval(" in lowered:
                    findings.append(
                        Finding(
                            file=changed.path,
                            line=line_no,
                            severity=Severity.critical,
                            category=Category.security,
                            message="eval() executes arbitrary code and is unsafe here.",
                            suggestion="Use a safe parser or explicit logic instead of eval().",
                        )
                    )
                elif "todo" in lowered:
                    findings.append(
                        Finding(
                            file=changed.path,
                            line=line_no,
                            severity=Severity.info,
                            category=Category.maintainability,
                            message="TODO left in newly added code.",
                            suggestion="Link it to an issue or resolve it before merging.",
                        )
                    )

        return LLMReview(
            summary=(
                f"Mock review of {len(files)} file(s). "
                "Heuristic checks only — no model was called."
            ),
            findings=findings,
        )
