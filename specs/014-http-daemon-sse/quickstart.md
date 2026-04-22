# Quickstart: HTTP Daemon + SSE

## Verify the feature

1. Run `uv run pytest tests/test_daemon.py -q`.
2. Run `uv run ruff check atelier/daemon tests/test_daemon.py`.

## Manual spot checks

1. Run `uv run python -m atelier.daemon --repo . --host 127.0.0.1 --port 8765` and confirm the listener binds to loopback.
2. Create the app in-process with a fixed secret and call `POST /runs` using `httpx.AsyncClient` plus `ASGITransport`.
3. Call `GET /runs/<run_id>` and confirm the returned status moves beyond bare creation as the run advances.
4. Open `GET /runs/<run_id>/events` and confirm the SSE stream emits daemon-generated audit events for the started run.
5. Start a run that waits on a gate, call `POST /runs/<run_id>/approve`, and confirm the run advances; also verify policy waits still return HTTP `409`.
6. Retry any route without `X-Atelier-Secret` or with a non-loopback client address and confirm the daemon rejects the request.
