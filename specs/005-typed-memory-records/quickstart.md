# Quickstart: Typed Memory Records

## Verify the feature

1. Run `uv run pytest tests/test_memory.py -v`.
2. Run `uv run ruff check atelier/memory atelier/security tests/test_memory.py`.

## Manual spot checks

1. Create a `Decision` with a markdown body that includes headings, lists, and fenced code blocks, then write it to a temporary `.atelier/memory/` root.
2. Inspect the written file and confirm it uses YAML frontmatter followed by raw markdown body content.
3. Read the file back with `read_record(...)` and confirm the returned record matches the original fixture for every field in the non-secret round-trip case.
4. Write a `Decision` whose body contains `OPENAI_API_KEY=sk-xxx` and confirm the stored file contains a redaction marker instead of the raw token.
5. Create multiple records with different types and tags, run `list_records(type="Decision", tags=["safety-critical"])`, and confirm only the expected record is returned.
