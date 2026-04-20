# Data Model: Swappability Demo

## SwapDemoConfig

- **Purpose**: Captures the user-selected runtime configuration for one W19 execution.
- **Fields**:
  - `mode`: `auto`, `live`, or `mock`
  - `claude_model`: manifest model name for the Claude side
  - `codex_model`: manifest model name for the Codex/OpenAI side
  - `output_root`: filesystem root for generated outputs
  - `run_unsupported_check`: whether to execute the incompatible-manifest proof
- **Validation rules**:
  - `mode` must be one of the supported values.
  - Requested models must exist in the shipped manifests for live runs.

## SwapDemoFixture

- **Purpose**: Represents the generated review target used by both backends.
- **Fields**:
  - `fixture_path`: path to the buggy Python source
  - `test_path`: path to the failing pytest file
  - `bug_summary`: short canonical description of the planted bug
  - `expected_failure_signal`: text snippet proving the off-by-one defect
- **Validation rules**:
  - The fixture and test files must be regenerated before each run.
  - The approved check must fail until the planted bug is fixed.

## SwapDemoBackend

- **Purpose**: Represents one backend target in the side-by-side run.
- **Fields**:
  - `label`: `claude` or `codex`
  - `provider`: `anthropic` or `openai`
  - `model`: manifest model name
  - `run_mode`: `live` or `mock`
  - `output_path`: markdown Evidence Pack destination
- **Validation rules**:
  - Successful review backends must satisfy `tool_use=True`.
  - `label` must map to a distinct output directory.

## ToolTranscriptEntry

- **Purpose**: Records one tool interaction during the review loop.
- **Fields**:
  - `tool_name`: canonical tool identifier
  - `arguments`: serialized tool arguments
  - `result`: serialized tool response
- **Validation rules**:
  - Entries preserve execution order.
  - Results must be printable into the final markdown artifact.

## SwapDemoRunResult

- **Purpose**: Represents the complete result of one backend execution.
- **Fields**:
  - `backend`: `SwapDemoBackend`
  - `response_content`: final reviewer markdown
  - `tool_transcript`: ordered list of `ToolTranscriptEntry`
  - `bug_detected`: whether the response explicitly identified the planted defect
  - `unsupported_error`: optional rendered `UnsupportedCapabilityError`
- **Validation rules**:
  - Successful runs must include a final response and at least one tool interaction.
  - `bug_detected` must be true for both successful Evidence Packs.

## EvidencePackDocument

- **Purpose**: The rendered markdown artifact for one backend.
- **Fields**:
  - `title`: human-readable heading
  - `summary_block`: backend identity, run mode, and result summary
  - `evidence_block`: executed check output and tool transcript
  - `review_block`: raw reviewer response
- **Validation rules**:
  - Markdown must be readable without external context.
  - The summary must state whether the planted bug was found.
