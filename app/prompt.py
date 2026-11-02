"""Prompt construction, kept separate so it can be tested and iterated on."""

from .diff import ChangedFile
from .models import ReviewRequest

SYSTEM_PROMPT = """\
You are a senior software engineer performing a focused code review of a git diff.

Rules:
- Review ONLY the added lines shown. Do not comment on removed or unchanged code.
- Report concrete problems: bugs, security issues, performance, missing tests,
  and maintainability concerns that a reviewer would actually raise.
- Do not invent problems. If the change is fine, return an empty findings list.
- Cite the file path and, when possible, the new-file line number shown.
- Keep messages specific and short; put the fix in "suggestion" when useful.
- Never include secrets, credentials, or personal data in your output.
"""


def build_user_prompt(request: ReviewRequest, files: list[ChangedFile]) -> str:
    parts = [
        f"Language: {request.language or 'unknown'}",
        f"Files changed: {len(files)}",
    ]

    if request.context:
        parts.append("Project context:\n" + request.context.strip())

    for changed in files:
        lines = "\n".join(
            f"{line_no:>5} + {text}" for line_no, text in changed.added
        )
        parts.append(f"File: {changed.path}\n{lines}")

    return "\n\n".join(parts)
