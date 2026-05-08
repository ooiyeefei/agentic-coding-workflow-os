# Evidence Pack

`Run:` `run_01ARZ3NDEKTSV4RRFFQ69G5F00`  
`Stage:` `001-review`  
`Schema:` `1.0`

> Verdict: **REJECTED**
> Confidence: **82%**
> Reviewer Persona: `reviewer.default`
> Timestamp: `2026-04-20T12:34:56Z`

## Findings

### RED

#### `finding-auth`

- File: `spanweave/workflow/stages.py:42`
- Description: Authentication flow breaks on invalid session reuse.
- Verification: Observed a failing pytest assertion in the review stage fixture.

### ORANGE

#### `finding-audit`

- File: `spanweave/audit/log.py:17`
- Description: Audit trace is missing a reference to the retry decision.
- Verification: Compared the emitted audit chain against the expected decision IDs.

### YELLOW

#### `finding-copy`

- File: `spanweave/evidence/templates/evidence.md.j2:1`
- Description: Evidence header wording is inconsistent with the rest of the run artifacts.
- Verification: Read the rendered markdown and compared it to the packet header style.

## Execution

### Command 1

- Command: `uv run pytest tests/test_evidence.py -v`
- Exit Code: `1`
- Linked Findings: `finding-auth`, `finding-audit`
#### Stdout

```text
============================= test session starts =============================
FAILED tests/test_evidence.py::test_generate_writes_both_files_and_round_trips
```

#### Stderr

```text
AssertionError: expected evidence file pair
```

### Command 2

- Command: `uv run ruff check spanweave/evidence tests/test_evidence.py`
- Exit Code: `0`
- Linked Findings: `finding-copy`
#### Stdout

```text
All checks passed!
```

#### Stderr

_No stderr captured._

## Audit Chain

- [`01ARZ3NDEKTSV4RRFFQ69G5F01`](../../audit.jsonl#01ARZ3NDEKTSV4RRFFQ69G5F01)
- [`01ARZ3NDEKTSV4RRFFQ69G5F02`](../../audit.jsonl#01ARZ3NDEKTSV4RRFFQ69G5F02)
