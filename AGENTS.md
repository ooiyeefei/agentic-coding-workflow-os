# agentic-coding-workflow-os Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-20

## Active Technologies
- Python 3.11 + pydantic v2, python-frontmatter, pathlib, pytest, pytest-asyncio, Python standard library `subprocess`, `json`, `re`, `os` (008-uat-persona-integration)
- In-memory Pydantic models plus repo-local markdown/YAML files; subprocess evidence kept in memory for this slice (008-uat-persona-integration)
- Python 3.11 + pathlib, pydantic v2, python-ulid, pytest, pytest-asyncio, standard-library `fcntl`, existing `atelier.util.fs` helpers (007-rungraph-tree-ops)
- Filesystem-only state under `.atelier/runs/<run_id>/...` matching the roadmap's canonical storage layout (007-rungraph-tree-ops)
- Python 3.11 + Python `re` and `typing` from the standard library, plus `pytest` for validation (006-secret-redaction)
- N/A for the redaction function itself; transforms in-memory strings before persistence (006-secret-redaction)
- Python 3.11 + pydantic v2, pathlib, pytest (006-context-compiler)
- In-memory source models and markdown strings; optional filesystem paths only as provenance metadata (006-context-compiler)
- Python 3.11 + pydantic v2, python-frontmatter, pathlib, pyyaml, python-ulid, pytest (005-typed-memory-records)
- Markdown files with YAML frontmatter under `.atelier/memory/{decisions,findings,rejected_alternatives}/` (005-typed-memory-records)
- Python 3.11 + pydantic v2, pathlib, pytest (012-policy-engine)
- Filesystem JSONL audit logs under `.atelier/runs/` and `.atelier/audit/` (012-policy-engine)
- Python 3.11 + pydantic v2, python-frontmatter, pathlib, pyyaml, pytest, pytest-asyncio (004-persona-library)

## Project Structure

```text
src/
tests/
```

## Commands

cd src && pytest && ruff check .

## Code Style

Python 3.11: Follow standard conventions

## Recent Changes
- 008-uat-persona-integration: Added Python 3.11 + pydantic v2, python-frontmatter, pathlib, pytest, pytest-asyncio, Python standard library `subprocess`, `json`, `re`, `os`
- 007-rungraph-tree-ops: Added Python 3.11 + pathlib, pydantic v2, python-ulid, pytest, pytest-asyncio, standard-library `fcntl`, existing `atelier.util.fs` helpers
- 006-secret-redaction: Added Python 3.11 + Python `re` and `typing` from the standard library, plus `pytest` for validation
- 006-context-compiler: Added Python 3.11 + pydantic v2, pathlib, pytest
- 005-typed-memory-records: Added Python 3.11 + pydantic v2, python-frontmatter, pathlib, pyyaml, python-ulid, pytest
- 012-policy-engine: Added Python 3.11 + pydantic v2, pathlib, pytest
- 004-persona-library: Added Python 3.11 + pydantic v2, python-frontmatter, pathlib, pyyaml, pytest, pytest-asyncio

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
