# Quickstart: Council Tiebreaker

## Verify the feature

1. Run `uv run pytest tests/test_council.py -v`.
2. Run `uv run ruff check atelier/council atelier/memory tests/test_council.py`.
3. If council-specific memory helpers were added, run `uv run pyright atelier/council atelier/memory`.

## Manual spot checks

1. Inject three mock adapters that vote `COMPATIBLE_WITH_CODER`, `COMPATIBLE_WITH_CODER`, and `NEITHER`; confirm `await tiebreak(...)` returns `COMPATIBLE_WITH_CODER`.
2. Inject three mock adapters that vote `COMPATIBLE_WITH_CODER`, `COMPATIBLE_WITH_REVIEWER`, and `NEITHER`; confirm `await tiebreak(...)` returns `HUMAN_REQUIRED`.
3. Confirm the three mock voter calls overlap in time instead of running strictly one after another.
4. Inspect the generated `.atelier/memory/council_reports/*.md` file and confirm it includes the selected models, full vote breakdown, and final verdict.
5. Configure one manifest without `tool_use=True` and confirm `UnsupportedCapabilityError` is raised before any provider call happens.
