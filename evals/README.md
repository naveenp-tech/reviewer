# Evaluation harness

This suite scores a provider against labelled unified diffs. It is **not** a test of
`pytest`; it is a measurement of the review quality.

## Rules

- A finding matches an expected finding if `file` and `category` are the same,
  and the line number is within **±2**. `severity` is reported separately and not
  used for matching.
- A case with `expected: []` must produce **no findings** to count as a clean
  pass (precision anchor).
- `diff_lines` in `cases.json` are joined with `\n` and a trailing newline so the
  diff is identical to what you would `POST` to `/review`.
- The mock provider only catches `eval(` and `TODO`, so recall will be low by
  design — that is the baseline to beat with a real model.
- The runner never gates on a score: exit code `0` means every case executed;
  any provider exception gives exit code `1`.

## Run

```bash
cd ~/reviewer
.venv/bin/python -m evals.run --provider mock
.venv/bin/python -m evals.run --provider mock --verbose
.venv/bin/python -m evals.run --only py-eval,py-todo
.venv/bin/python -m evals.run --provider mock --json
.venv/bin/python -m evals.run --list
```

After adding `GEMINI_API_KEY` to `.env`:

```bash
.venv/bin/python -m evals.run --provider gemini
```

The JSON report is written to `evals/results/latest.json` by default.

## Limitations

- Only added lines are visible to the reviewer (by construction). A bug that
  lives purely in removed or unchanged code will not be caught.
- Matching is greedy and case-insensitive to category/file as strings; it does
  not do fuzzy text similarity.
- Severity agreement is tracked only for matched findings.
- The suite is small on purpose. Expand it when you add retrieval/tools; the
  schema is stable so old results stay comparable.
- A model may raise a legitimate finding the harness did not label — those are
  counted as false positives until you add them to `cases.json`.
