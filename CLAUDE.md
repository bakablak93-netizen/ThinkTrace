# CLAUDE.md

Guidance for working in this repo. Read README.md for the product description.

## Principles (non-negotiable)

1. **Deterministic core.** Parsing, step verification and error diagnosis are done by
   code (SymPy). The LLM never decides whether a step is correct or which bug it is.
2. **LLM is only for wording:** (a) phrasing a hint for a known bug id + hint level,
   (b) fallback analysis of an error not in the catalog, (c) report text.
3. **Every LLM call has an offline template fallback.** No API key or a network error
   means TemplateClient. The demo must work without internet.
4. **Never reveal the final answer on hint levels 1-3.** The guard in hints.py
   replaces any LLM output that contains the solution with a template hint.
5. **Privacy:** anonymous nickname only, minimal data, full delete endpoint.
   Diagnoses are probabilistic. Never conclude anything about a person's ability
   from a single error.
6. **Scope:** do not add features beyond the agreed spec without the team's consent.
   Small product that really works > many features.

## Commands

- Backend deps: `cd backend && pip install -r requirements.txt`
- Backend run: `cd backend && uvicorn thinktrace.api:create_app --factory --reload --port 8000`
- Tests: `cd backend && pytest -q` (run before claiming anything is done)
- Frontend: `cd frontend && npm install && npm run dev`
- Frontend type check + build: `cd frontend && npm run build`

## Conventions

- Python package lives in `backend/thinktrace/`. Tests are in `backend/tests/`.
- Storage: stdlib `sqlite3` (no ORM).
- Every diagnosis function is covered by tests, with at least 5 wrong-step examples per bug.
- i18n: ru is the reference language. kk/en use the same keys (missing key falls back to ru).
- Secrets only in `.env` (git-ignored). Keep `.env.example` in sync.
- Small commits with clear messages. Never fabricate test results or metrics.
