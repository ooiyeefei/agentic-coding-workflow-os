# Contract: spanweave.personas UAT API

## UAT Persona

- `UAT(...)`
- `await UAT.respond(context_packet) -> AgentResponse`

**Contract**:

- Persona initialization loads prompt metadata from `.spanweave/defaults/personas/uat.md`.
- Persona initialization routes through `route_persona_to_model(...)`.
- The persona requires a model capable of generating structured UAT guidance before execution.
- `respond(...)` always performs one adapter call before subprocess-backed UAT execution.
- `respond(...)` returns `AgentResponse` and stores the parsed `EvidencePack` in response metadata.

## UAT Runner

- `run_uat(request: UATRequest, *, test_plan: str | None = None) -> EvidencePack`

**Contract**:

- Resolves the skill path from the request or `SPANWEAVE_UAT_SKILL_PATH`.
- Fails clearly when the skill path is missing, unusable, or times out.
- Resolves credentials from request, environment, or repo-relative `.env.local`.
- Passes the target app path and credentials to the subprocess execution context.
- Captures stdout, stderr, and exit code separately.
- Redacts secrets before constructing `EvidencePack.execution`.
- Parses JSON or recognized line-oriented output into `EvidencePack.summary` and `EvidencePack.findings`.
