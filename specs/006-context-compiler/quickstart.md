# Quickstart: Context Compiler

## Verify the feature

1. Run `pytest tests/test_compiler.py -v`.
2. Run `ruff check atelier/compiler tests/test_compiler.py`.

## Manual spot checks

1. Compile a fixture packet with must, should, and nice sources under an `8000` token budget and confirm the output is byte-for-byte stable across repeated runs.
2. Re-run the same fixture with a tighter budget and confirm nice-tier blocks disappear before should-tier blocks.
3. Re-run with a budget smaller than the must-tier packet and confirm `BudgetExceededError` is raised.
4. Compile fixture sources that reuse the same `source_id` and confirm the duplicate block appears only once.
5. Read the packet footer and confirm each included block has a provenance row listing source type, source id, and path.
