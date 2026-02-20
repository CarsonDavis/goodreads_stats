# Claude Code Instructions

## Package Management

Always use `uv` for Python operations. Never use naked `python` or `pip`.

```bash
# Correct
uv run python script.py
uv pip install package

# Incorrect
python script.py
pip install package
```

## Required Reading

**Before starting any task, you MUST read `docs/README.md`** to understand the project structure and data flow.

## Additional Context by Task

Read these files before working on specific areas:

| Task | Read First |
|------|------------|
| Data models or JSON structure | `docs/data-models.md`, `genres/models/book.py`, `genres/models/analytics.py` |
| Genre enrichment or API sources | `docs/genre-enrichment.md`, `genres/pipeline/enricher.py` |
| Local development or FastAPI | `docs/getting-started.md`, `local_server.py` |
| AWS Lambda functions | `docs/lambda-functions.md`, `cdk/lambda_code/` |
| System architecture | `docs/architecture.md` |
| REST API endpoints | `docs/api-reference.md` |
| Debugging issues | `docs/troubleshooting.md` |
| Frontend/dashboard | `dashboard/README.md` |
