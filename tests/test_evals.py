from app.models import Category, Finding, Severity
from evals.run import CASES_PATH, ExpectedFinding, lines_match, load_cases, match_findings


def finding(line: int | None, category: Category = Category.security) -> Finding:
    return Finding(
        file="app.py",
        line=line,
        severity=Severity.high,
        category=category,
        message="example",
    )


def expected(line: int | None, category: str = "security") -> ExpectedFinding:
    return ExpectedFinding(
        file="app.py", line=line, category=category, severity="critical"
    )


def test_lines_match_within_tolerance():
    assert lines_match(10, 10, 2)
    assert lines_match(10, 12, 2)
    assert not lines_match(10, 13, 2)


def test_missing_line_only_matches_missing_line():
    assert lines_match(None, None, 2)
    assert not lines_match(None, 10, 2)
    assert not lines_match(10, None, 2)


def test_match_ignores_severity_but_requires_file_and_category():
    matches, unmatched = match_findings([expected(3)], [finding(3)], tolerance=2)
    assert matches == [0]
    assert unmatched == []


def test_wrong_category_is_a_false_negative_and_false_positive():
    matches, unmatched = match_findings(
        [expected(3, "bug")], [finding(3, Category.security)], tolerance=2
    )
    assert matches == [None]
    assert unmatched == [finding(3, Category.security)]


def test_extra_findings_are_false_positives():
    matches, unmatched = match_findings(
        [expected(3)], [finding(3), finding(9, Category.bug)], tolerance=2
    )
    assert matches == [0]
    assert len(unmatched) == 1


def test_each_finding_matches_at_most_once():
    matches, unmatched = match_findings(
        [expected(3), expected(3)], [finding(3)], tolerance=2
    )
    assert matches == [0, None]
    assert unmatched == []


def test_load_cases_builds_a_valid_diff():
    cases = load_cases(CASES_PATH)
    assert len(cases) == 16
    assert cases[0].id == "py-eval"
    assert cases[0].diff.endswith("\n")
    assert cases[0].expected[0].category == "security"
    assert any(not case.expected for case in cases)
