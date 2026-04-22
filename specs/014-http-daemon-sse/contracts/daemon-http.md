# Contract: atelier.daemon HTTP API

## Security Boundary

- Every request requires the `X-Atelier-Secret` header.
- Requests are accepted only from loopback client addresses.
- CORS is limited to loopback origins (`localhost`, `127.0.0.1`, and `::1`).

## POST `/runs`

**Request body**:

```json
{
  "issue_ref": "42",
  "workflow": "speckit-loop",
  "context": "future plugin trigger"
}
```

**Contract**:

- Creates a new run under `.atelier/runs/<run_id>/`.
- Starts daemon-side workflow execution for the new run.
- Normalizes purely numeric issue references to the Phase 0 `issue #<n>` form.
- Returns HTTP `201` with the created run snapshot.
- Returns HTTP `404` if the requested workflow name does not exist.

## GET `/runs/{run_id}`

**Contract**:

- Reads the run snapshot from repo-local `.atelier/runs/<run_id>/` state.
- Returns HTTP `200` with the same metadata shape used by the CLI read model.
- Returns HTTP `404` when the run does not exist.
- Returns HTTP `400` when `run_id` is malformed.

## GET `/runs/{run_id}/events`

**Response content type**: `text/event-stream`

**SSE message contract**:

```text
id: evt_01ARZ3NDEKTSV4RRFFQ69G5F01
event: TOOL_CALL
data: {"event_id":"evt_01ARZ3NDEKTSV4RRFFQ69G5F01","event_type":"TOOL_CALL","run_id":"run_01ARZ3NDEKTSV4RRFFQ69G5F00",...}
```

**Contract**:

- Emits existing per-run audit events in log order.
- Continues tailing the run's `audit.jsonl` for appended events until the client disconnects.
- Accepts an optional `limit=<n>` query parameter to end the stream after `n` emitted events for deterministic local tests.
- Ignores blank lines in the audit log.
- Returns HTTP `404` when the run does not exist.

## POST `/runs/{run_id}/approve`

**Contract**:

- Resumes a run only when it is in `waiting_approval` state for `waiting_reason == "gate"`.
- Returns HTTP `200` with the updated run snapshot and `approved: true`.
- Returns HTTP `409` when the run is not eligible for gate approval.
- Returns HTTP `404` when the run does not exist.
