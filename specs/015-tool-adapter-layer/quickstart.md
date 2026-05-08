# Quickstart: Tool Adapter Layer

1. Ingest a tool transcript fixture into typed memory records.

```python
from pathlib import Path

from spanweave.adapters import ClaudeCodeAdapter
from spanweave.memory import write_record

adapter = ClaudeCodeAdapter(repo_root=Path.cwd())
records = adapter.ingest_transcript(
    Path("tests/fixtures/adapters/claude/projects/sample-project/session.jsonl")
)
for record in records:
    write_record(record)
```

2. Format a packet for a destination tool.

```python
from spanweave.adapters import CodexAdapter

adapter = CodexAdapter(repo_root=Path.cwd())
packet = adapter.format_context_packet(
    run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    role="coder",
    memory_records=records,
)
print(packet)
```

3. Run the focused adapter tests.

```bash
pytest tests/test_adapters.py -q
```
