# Research: Persona Library

## Decision 1: Use markdown frontmatter as the shipped persona definition format

- **Decision**: Store each persona prompt as a markdown file with YAML frontmatter for `name`, `required_capabilities`, and prompt-level metadata.
- **Rationale**: This keeps persona defaults filesystem-first, editable, and version-controlled while letting Python load both structured metadata and rich prompt text from one source of truth.
- **Alternatives considered**:
  - Hardcode prompts and requirements in Python: rejected because it hides persona behavior in source code and makes prompt iteration awkward.
  - Split prompt text and metadata into separate files: rejected because it increases drift risk between required capabilities and the prompt that explains them.

## Decision 2: Route at initialization but build adapters lazily

- **Decision**: Resolve the compatible manifest during persona initialization, but defer provider adapter construction until `respond(...)` unless a caller injects an adapter explicitly.
- **Rationale**: This satisfies the acceptance criteria that `Coder()` and `Reviewer()` route via W02 while keeping initialization deterministic and test-friendly without requiring live API credentials.
- **Alternatives considered**:
  - Instantiate provider clients in `__init__`: rejected because it couples persona construction to environment secrets and makes unit tests noisier.
  - Delay both routing and adapter creation until `respond(...)`: rejected because it hides routing failures until later and weakens the persona object's declared identity.

## Decision 3: Preserve Reviewer's strict capability requirements and update shipped manifests instead of downgrading the persona

- **Decision**: Keep Reviewer's declared routing requirements as `tool_use=True`, `code_execution=True`, and `structured_outputs=True`, and update default manifest metadata so at least one shipped model satisfies them.
- **Rationale**: The feature brief treats capability gating as a core architectural property, and downgrading Reviewer's requirements would make the abstraction dishonest. The smaller adjacent change is to correct the manifest layer so W04 can actually prove the routing story.
- **Alternatives considered**:
  - Drop `code_execution` and `structured_outputs` from Reviewer: rejected because it would directly contradict the clarified feature contract.
  - Encode these as comments in the prompt only: rejected because prompt-only declarations are not enforceable by W02's matcher.

## Decision 4: Let Coder consume a skill catalog when present and a fixed fallback sequence when absent

- **Decision**: Implement Coder skill discovery against `.spanweave/defaults/skills/*.md` and fall back to a hardcoded Speckit progression when the W05 catalog has not landed.
- **Rationale**: W04 depends conceptually on W05 but cannot block on it. The fallback preserves useful behavior on `main` while still allowing W05 to become the source of truth later.
- **Alternatives considered**:
  - Hard fail if the skills directory is missing: rejected because W05 is a parallel dependency and the user explicitly wants W04 implemented now.
  - Ignore skills entirely and let Coder free-form everything: rejected because the feature brief explicitly says Coder should know which `/speckit.*` command comes next.

## Decision 5: Model persona output as a thin wrapper over W02's normalized response

- **Decision**: Define `AgentResponse` as a structured persona-level object that carries persona metadata plus normalized response content, tool calls, usage, and cost fields from W02.
- **Rationale**: This gives the workflow engine one persona-facing contract while reusing the normalized provider output that already exists in W02.
- **Alternatives considered**:
  - Return raw W02 `Response` objects directly: rejected because downstream code also needs persona identity and selected adapter information.
  - Build a large evidence-pack-like schema now: rejected because Evidence Pack work is owned by W08 and would expand W04 beyond scope.

## Decision 6: Implement devil's-advocate mode as prompt post-processing

- **Decision**: Keep a single base `reviewer.md` prompt and append a concise "reasons to reject" section requirement only when `devil_advocate_mode=True`.
- **Rationale**: One prompt source avoids divergence in the execution-mandatory protocol while making the flag behavior easy to test with a simple diff.
- **Alternatives considered**:
  - Separate prompt files for default and devil's-advocate Reviewer: rejected because duplicated prompts will drift.
  - Always include rejection scaffolding: rejected because the roadmap explicitly makes devil's-advocate mode opt-in.
