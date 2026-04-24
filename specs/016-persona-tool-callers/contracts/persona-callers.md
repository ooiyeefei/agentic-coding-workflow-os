# Contract: Persona Callers

## AgentToolCaller.call

**Input**

- `persona_name`: persona identifier such as `coder`, `reviewer`, or `uat`
- `context`: stage context text
- `skill`: workflow skill name
- `run_id`: current run identifier

**Output**

- Returns `str`
- Returned string is a prompt for the target agent tool
- Returned string is not model-generated content
- Phase 0 also writes the same prompt to stdout

**Errors**

- Unknown persona names raise `ValueError`
- Unknown tool names raise `ValueError`
- Empty generated prompts raise `ValueError`

## DirectAPICaller.call

**Input**

- Same as `AgentToolCaller.call`

**Output**

- Returns `PersonaCallResult`
- `content` is the direct persona response content
- `metadata` preserves response metadata where available

**Errors**

- Propagates persona construction and LLM adapter errors from the existing direct path
