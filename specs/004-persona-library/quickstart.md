# Quickstart: Persona Library

## Verify the feature

1. Run `uv run pytest tests/test_personas.py -v`.
2. Run `uv run pytest tests/test_llm_adapter.py -v`.
3. Run `uv run ruff check spanweave/personas tests/test_personas.py tests/test_llm_adapter.py`.
4. Run `uv run pyright spanweave/personas`.

## Manual spot checks

1. Instantiate `Coder()` and confirm it records a compatible model without making a network request.
2. Instantiate `Reviewer()` and confirm it records a compatible model that satisfies `tool_use`, `code_execution`, and `structured_outputs`.
3. Read `.spanweave/defaults/personas/reviewer.md` and confirm the prompt mentions `execute`, `paste actual output`, and `incomplete without execution evidence`.
4. Compare `Reviewer().system_prompt` with `Reviewer(devil_advocate_mode=True).system_prompt` and confirm the second adds explicit "reasons to reject" instructions.
5. Inject a mock adapter, call `await persona.respond(fake_packet)`, and confirm the returned object includes persona identity plus normalized content/tool/usage/cost fields.
