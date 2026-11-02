# Reviewer

An AI code-review service. You send a git diff; it returns **structured, validated
findings** — file, line, severity, category, message, suggested fix.

Stage 1 of a larger project. The point is not the chat interface; it is the
contract, the provider abstraction, and the tests.

## Status

- [x] Unified-diff parser with line numbers
- [x] Typed request/response schemas (Pydantic)
- [x] Provider abstraction + offline mock provider
- [x] Gemini provider with structured output
- [x] Tests for the parser, the API, and the eval matcher
- [x] Evaluation harness with 16 labelled diffs
- [ ] Repo context retrieval
- [ ] Tool execution (linters/tests) in a sandbox
- [ ] GitHub Action
- [ ] Observability (tokens, latency, cost)

## Run

```bash
cd ~/reviewer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000/docs> for the generated API documentation.

Check it is alive:

```bash
curl -s http://localhost:8000/health
# {"status":"ok","provider":"mock"}
```

## Review a diff

```bash
curl -s -X POST http://localhost:8000/review \
  -H 'content-type: application/json' \
  -d '{
    "language": "python",
    "diff": "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,3 @@\n import os\n+result = eval(user_input)\n print(result)\n"
  }'
```

With the default `mock` provider you get the security finding for `eval()`.
It is a deterministic heuristic, not a model call.

## Switch to Gemini

1. Create a free key at <https://aistudio.google.com/apikey>.
2. Put it in `.env` (never commit this file):

   ```bash
   REVIEWER_PROVIDER=gemini
   GEMINI_API_KEY=your-key-here
   GEMINI_MODEL=gemini-2.5-flash
   ```

3. Restart the server.

The model is forced to answer with the `LLMReview` schema, so the response is
validated JSON rather than free text.

## Evals

Quality is measured, not assumed. `evals/cases.json` holds 16 small diffs
(Python, JavaScript, Java) with known findings, plus one clean diff that must
produce no findings.

```bash
python -m evals.run --provider mock            # offline baseline
python -m evals.run --provider gemini          # real model
python -m evals.run --provider gemini --verbose
python -m evals.run --only py-eval,py-todo     # subset
python -m evals.run --json                     # evals/results/latest.json
```

Matching rules: same file + category, line within ±2. Severity is reported
separately. See `evals/README.md` for the full protocol and limitations.

Mock baseline (deliberately weak — it only spots `eval(` and `TODO`):

| Metric | Value |
|---|---|
| Cases | 16 |
| Expected findings | 15 |
| TP / FP / FN | 2 / 0 / 13 |
| Precision | 1.000 |
| Recall | 0.133 |
| F1 | 0.235 |
| Clean diff stayed silent | yes |

That is the number Gemini has to beat. Re-run the same command after switching
providers and compare, rather than judging a review by how plausible it reads.

## Tests

```bash
python -m pytest -q
python -m ruff check .
```

The suite also tests the eval matcher (`tests/test_evals.py`), so a bug in the
scoring cannot silently inflate the numbers.

## Design decisions

- **Provider protocol, not vendor lock-in.** `mock` and `gemini` implement the
  same interface; the endpoint does not import a vendor SDK directly.
- **Structured output.** The schema is the contract. If the model drifts, we
  get a validation error, not a silently wrong review.
- **Parse before you prompt.** Only added lines are sent, with their new-file
  line numbers. This cuts tokens and makes findings citable.
- **Fail loudly.** Provider errors become HTTP 502 with the provider name, not
  a 200 with empty findings.
- **Secrets.** `.env` is gitignored; `.env.example` documents the variables.

## Layout

```
app/
├── main.py          FastAPI endpoints
├── models.py        Pydantic contracts
├── diff.py          unified-diff parser
├── prompt.py        prompt construction
└── providers/
    ├── base.py      protocol
    ├── mock.py      offline deterministic provider
    └── gemini.py    structured-output Gemini provider
tests/
├── test_diff.py
├── test_api.py
└── test_evals.py
evals/
├── cases.json       labelled diffs
├── run.py           scorer CLI
└── README.md        matching rules and limitations
```
