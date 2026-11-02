"""Run the labelled review suite against a provider and report precision/recall.

Usage:
    python -m evals.run --provider mock
    python -m evals.run --provider gemini --verbose
    python -m evals.run --only py-eval,py-todo --json

Exit code is 0 when every case ran, even if quality is poor: the harness
measures a provider, it does not gate on a score. A provider error exits 1.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.config import load_settings
from app.diff import parse_unified_diff
from app.models import Finding, ReviewRequest
from app.providers.base import ReviewProvider
from app.providers.mock import MockProvider

CASES_PATH = Path(__file__).with_name("cases.json")
DEFAULT_JSON_PATH = Path(__file__).with_name("results") / "latest.json"
LINE_TOLERANCE = 2


@dataclass(frozen=True)
class ExpectedFinding:
    file: str
    line: int | None
    category: str
    severity: str
    note: str = ""


@dataclass(frozen=True)
class EvalCase:
    id: str
    language: str | None
    diff: str
    expected: list[ExpectedFinding]
    notes: str = ""


@dataclass
class CaseResult:
    case: EvalCase
    findings: list[Finding] = field(default_factory=list)
    matches: list[int | None] = field(default_factory=list)
    unmatched_findings: list[Finding] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None

    @property
    def true_positives(self) -> int:
        return sum(1 for match in self.matches if match is not None)

    @property
    def false_negatives(self) -> int:
        return len(self.case.expected) - self.true_positives

    @property
    def false_positives(self) -> int:
        return len(self.unmatched_findings)


def load_cases(path: Path) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON list of cases")

    cases: list[EvalCase] = []
    for item in raw:
        expected = [
            ExpectedFinding(
                file=entry["file"],
                line=entry.get("line"),
                category=entry["category"],
                severity=entry["severity"],
                note=entry.get("note", ""),
            )
            for entry in item.get("expected", [])
        ]
        cases.append(
            EvalCase(
                id=item["id"],
                language=item.get("language"),
                diff="\n".join(item["diff_lines"]) + "\n",
                expected=expected,
                notes=item.get("notes", ""),
            )
        )

    ids = [case.id for case in cases]
    duplicates = {case_id for case_id in ids if ids.count(case_id) > 1}
    if duplicates:
        raise ValueError(f"duplicate case ids: {sorted(duplicates)}")
    return cases


def lines_match(expected: int | None, actual: int | None, tolerance: int) -> bool:
    """Line numbers match within tolerance. A missing line only matches a missing line."""
    if expected is None or actual is None:
        return expected is None and actual is None
    return abs(expected - actual) <= tolerance


def match_findings(
    expected: list[ExpectedFinding],
    findings: list[Finding],
    tolerance: int,
) -> tuple[list[int | None], list[Finding]]:
    """Greedy one-to-one matching on file + category + line within tolerance.

    Severity is deliberately not part of matching: a correct finding with the
    wrong severity is still a detection, and severity agreement is reported
    separately. Extra findings are false positives.
    """
    unmatched = list(range(len(findings)))
    matches: list[int | None] = []

    for want in expected:
        chosen: int | None = None
        for index in unmatched:
            got = findings[index]
            if (
                got.file == want.file
                and got.category.value == want.category
                and lines_match(want.line, got.line, tolerance)
            ):
                chosen = index
                break

        if chosen is None:
            matches.append(None)
        else:
            unmatched.remove(chosen)
            matches.append(chosen)

    return matches, [findings[index] for index in unmatched]


async def run_case(provider: ReviewProvider, case: EvalCase, tolerance: int) -> CaseResult:
    started = time.perf_counter()
    result = CaseResult(case=case)

    try:
        request = ReviewRequest(diff=case.diff, language=case.language)
        files = parse_unified_diff(case.diff)
        review = await provider.review(request, files)
    except Exception as exc:  # noqa: BLE001 - a provider may fail in many ways
        result.error = f"{type(exc).__name__}: {exc}"
    else:
        result.findings = review.findings

    result.duration_ms = round((time.perf_counter() - started) * 1000)
    result.matches, result.unmatched_findings = match_findings(
        case.expected, result.findings, tolerance
    )
    return result


def build_provider(name: str) -> ReviewProvider:
    if name == "mock":
        return MockProvider()

    if name == "gemini":
        settings = load_settings()
        if not settings.gemini_api_key:
            raise SystemExit(
                "GEMINI_API_KEY is not set. Add it to ~/reviewer/.env (never commit it)."
            )
        from app.providers.gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)

    raise SystemExit(f"unknown provider: {name}")


def select_cases(cases: list[EvalCase], only: str | None) -> list[EvalCase]:
    if not only:
        return cases
    wanted = [token.strip() for token in only.split(",") if token.strip()]
    selected = [
        case for case in cases if any(token in case.id for token in wanted)
    ]
    if not selected:
        raise SystemExit(f"no case matches --only {only!r}")
    return selected


def ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def format_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def build_report(
    provider: ReviewProvider,
    results: list[CaseResult],
    tolerance: int,
    duration_ms: int,
) -> dict[str, object]:
    tp = sum(result.true_positives for result in results)
    fp = sum(result.false_positives for result in results)
    fn = sum(result.false_negatives for result in results)

    categories: dict[str, dict[str, int]] = {}
    for result in results:
        for want in result.case.expected:
            bucket = categories.setdefault(want.category, {"matched": 0, "expected": 0})
            bucket["expected"] += 1
        for index, want in enumerate(result.case.expected):
            if result.matches[index] is not None:
                categories[want.category]["matched"] += 1

    clean_total = sum(1 for result in results if not result.case.expected)
    clean_ok = sum(
        1
        for result in results
        if not result.case.expected and not result.findings and result.error is None
    )

    matched_pairs = [
        (result.case.expected[index], result.findings[match])
        for result in results
        for index, match in enumerate(result.matches)
        if match is not None
    ]
    severity_agreement = sum(
        1 for want, got in matched_pairs if got.severity.value == want.severity
    )

    return {
        "provider": provider.name,
        "model": provider.model,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_ms": duration_ms,
        "line_tolerance": tolerance,
        "totals": {
            "cases": len(results),
            "expected_findings": tp + fn,
            "found_findings": tp + fp,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn),
            "clean_cases": clean_total,
            "clean_cases_passed": clean_ok,
            "severity_agreement": ratio(severity_agreement, tp),
            "case_errors": sum(1 for result in results if result.error),
        },
        "categories": categories,
        "cases": [
            {
                "id": result.case.id,
                "language": result.case.language,
                "notes": result.case.notes,
                "duration_ms": result.duration_ms,
                "error": result.error,
                "expected": [want.__dict__ for want in result.case.expected],
                "findings": [
                    finding.model_dump(mode="json") for finding in result.findings
                ],
                "matched_expected": [
                    index for index, match in enumerate(result.matches) if match is not None
                ],
                "true_positives": result.true_positives,
                "false_positives": result.false_positives,
                "false_negatives": result.false_negatives,
            }
            for result in results
        ],
    }


def print_report(report: dict[str, object], results: list[CaseResult], verbose: bool) -> None:
    totals = report["totals"]
    assert isinstance(totals, dict)
    provider = report["provider"]
    model = report["model"] or "-"

    print(f"Reviewer eval — provider={provider} model={model}")
    print(
        f"cases: {totals['cases']} | expected findings: {totals['expected_findings']}"
        f" | line tolerance: ±{report['line_tolerance']}"
    )

    id_width = max([len("case"), *(len(result.case.id) for result in results)])
    print()
    header = (
        f"{'case'.ljust(id_width)}  {'expect':>6}  {'found':>5}"
        f"  {'tp':>3}  {'fp':>3}  {'fn':>3}  result"
    )
    print(header)
    for result in results:
        found = len(result.findings)
        if result.error:
            verdict = "ERROR"
        elif result.false_positives or result.false_negatives:
            verdict = "miss"
        else:
            verdict = "ok"
        print(
            f"{result.case.id.ljust(id_width)}  {len(result.case.expected):>6}"
            f"  {found:>5}  {result.true_positives:>3}"
            f"  {result.false_positives:>3}  {result.false_negatives:>3}  {verdict}"
        )

        if verbose:
            if result.case.notes:
                print(f"    note: {result.case.notes}")
            for index, want in enumerate(result.case.expected):
                match = result.matches[index]
                if match is None:
                    print(
                        f"    MISS  expected {want.file}:{want.line} [{want.category}]"
                        f" {want.note or want.severity}"
                    )
                else:
                    got = result.findings[match]
                    print(
                        f"    HIT   expected {want.file}:{want.line} [{want.category}]"
                        f" -> {got.severity.value}"
                    )
            for got in result.unmatched_findings:
                print(
                    f"    FP    {got.file}:{got.line} [{got.category.value}]"
                    f" {got.message}"
                )
            if result.error:
                print(f"    error: {result.error}")

    print()
    print("Overall")
    print(
        f"  TP {totals['true_positives']}  FP {totals['false_positives']}"
        f"  FN {totals['false_negatives']}"
    )
    print(f"  precision          {format_ratio(totals['precision'])}")
    print(f"  recall             {format_ratio(totals['recall'])}")
    print(f"  f1                 {format_ratio(totals['f1'])}")
    print(
        f"  clean cases        {totals['clean_cases_passed']}/{totals['clean_cases']} silent"
    )
    print(
        "  severity agreement "
        f"{format_ratio(totals['severity_agreement'])} (matched findings only)"
    )

    categories = report["categories"]
    assert isinstance(categories, dict)
    if categories:
        print()
        print("Recall by category (matched/expected)")
        for name in sorted(categories):
            bucket = categories[name]
            print(
                f"  {name.ljust(16)} {bucket['matched']}/{bucket['expected']}"
            )

    if totals["case_errors"]:
        print()
        print(f"{totals['case_errors']} case(s) failed to run — see errors above.")


async def run(args: argparse.Namespace) -> int:
    cases = select_cases(load_cases(CASES_PATH), args.only)
    provider = build_provider(args.provider)

    started = time.perf_counter()
    results = [await run_case(provider, case, args.tolerance) for case in cases]
    duration_ms = round((time.perf_counter() - started) * 1000)

    report = build_report(provider, results, args.tolerance, duration_ms)
    print_report(report, results, args.verbose)

    if args.json is not None:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {path}")

    return 1 if any(result.error for result in results) else 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run labelled diffs through a review provider and score the findings."
    )
    parser.add_argument(
        "--provider",
        default="mock",
        choices=["mock", "gemini"],
        help="provider to evaluate (default: mock)",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="comma-separated case id fragments, e.g. --only py-eval,java",
    )
    parser.add_argument(
        "--json",
        nargs="?",
        const=str(DEFAULT_JSON_PATH),
        default=None,
        help=f"write a JSON report (default path: {DEFAULT_JSON_PATH})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show each hit, miss and false positive",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=LINE_TOLERANCE,
        help=f"allowed line-number difference when matching (default: {LINE_TOLERANCE})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list case ids and exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.list:
        for case in load_cases(CASES_PATH):
            print(f"{case.id}\t{case.language or '-'}\t{len(case.expected)} expected")
        return 0

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
