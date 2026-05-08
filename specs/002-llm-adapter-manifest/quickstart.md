# Quickstart: LLM Adapter Manifest

1. `pytest tests/test_llm_adapter.py -q`
2. `python3 -m pytest tests/test_llm_adapter.py -q` if `pytest` is not on your PATH
3. `python3 - <<'PY'`
4. `from pathlib import Path`
5. `from spanweave.llm.capabilities import load_capability_manifests`
6. `print([manifest.model for manifest in load_capability_manifests(Path('.spanweave/defaults/models'))])`
7. `PY`

The test suite uses mocked SDK clients, so no live provider credentials are required to validate this slice locally.
