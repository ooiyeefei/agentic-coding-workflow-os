# Quickstart: Persona Tool Callers

## Verify Agent Tool Prompt Generation

```bash
pytest tests/test_persona_callers.py
```

Expected result: Codex and Claude Code caller tests return prompt strings with tool-specific context markers, persona instructions, skill, run ID, and stage context.

## Verify Backward Compatibility

```bash
pytest tests/test_personas.py tests/test_workflow.py
```

Expected result: existing persona response behavior and workflow dependency injection tests pass unchanged.

## Verify Targeted Slice

```bash
pytest tests/test_persona_callers.py tests/test_personas.py tests/test_workflow.py
```
