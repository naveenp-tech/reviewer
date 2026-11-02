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
- [x] Tests for the parser and the API
- [ ] Repo context retrieval
- [ ] Tool execution (linters/tests) in a sandbox
- [ ] Evaluation harness with labelled diffs
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

## Tests

```bash
python -m pytest -q
python -m ruff check .
```

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
└── test_api.py
```
