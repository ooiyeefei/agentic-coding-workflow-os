# Feature Specification: HTTP Daemon + SSE

**Feature Branch**: `014-http-daemon-sse`  
**Created**: 2026-04-22  
**Status**: Implemented  
**Input**: User description: "FastAPI daemon exposing runs, SSE events stream, approval gates for the plugin client"

## Clarifications

### Session 2026-04-22

- Q: Should the daemon use SSE or WebSockets for live run updates? → A: Use SSE because Phase 0 only needs unidirectional event delivery.
- Q: What CORS policy should the daemon enforce? → A: Allow only localhost loopback origins in Phase 0.
- Q: What authentication model should the local daemon use? → A: Require a shared secret header using `LOCAL_DAEMON_SECRET`, or auto-generate and persist one on first start.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create And Inspect Runs Over HTTP (Priority: P1)

As a non-CLI client, I can create a workflow run and fetch its current metadata over localhost HTTP, so future IDE and dashboard integrations can target the same control-plane state as the CLI.

**Why this priority**: Without a stable create/read HTTP contract, later clients still need to shell out to the CLI or read `.spanweave/` directly, which defeats the purpose of the daemon.

**Independent Test**: In a temporary repository, start the FastAPI app in-process, call `POST /runs`, and then call `GET /runs/<run_id>`. The responses should include a valid run ID, persisted run metadata, and evidence that the workflow advanced beyond bare creation.

**Acceptance Scenarios**:

1. **Given** a repo-local `.spanweave/` workspace, **When** a client sends `POST /runs` with an issue reference and workflow name, **Then** the daemon creates `.spanweave/runs/<run_id>/`, starts advancing the workflow in daemon mode, and returns the created run ID plus current metadata.
2. **Given** an existing run on disk, **When** a client sends `GET /runs/<run_id>`, **Then** the daemon returns the persisted run snapshot including status, current stage, waiting reason, and created stages.
3. **Given** a request without the shared secret header, **When** the client calls any daemon route, **Then** the daemon rejects the request instead of exposing run state.

---

### User Story 2 - Stream Audit Events Live With SSE (Priority: P2)

As a non-CLI client, I can subscribe to a run's audit stream over SSE, so future UI surfaces can render live progress without polling the filesystem.

**Why this priority**: Real-time visibility is the main future-facing value of the daemon, but it depends on the run API and local-only security boundary existing first.

**Independent Test**: Open `GET /runs/<run_id>/events` with an in-process HTTP client after `POST /runs`, and verify the SSE stream emits daemon-generated audit events as the workflow advances without using a real network socket.

**Acceptance Scenarios**:

1. **Given** a run with existing audit lines, **When** a client connects to `GET /runs/<run_id>/events`, **Then** the daemon emits those audit entries as SSE messages in order.
2. **Given** a connected SSE client, **When** a new audit event is appended to the run's `audit.jsonl`, **Then** the daemon emits the new event without requiring a reconnect.
3. **Given** a request from a non-local origin or client address, **When** the client attempts to subscribe to the SSE route, **Then** the daemon rejects the request.

---

### User Story 3 - Approve A Gated Stage Over HTTP (Priority: P3)

As a non-CLI client, I can approve a run that is waiting on a completed approval gate, so a future plugin can unblock human-gated workflow stages without invoking the CLI.

**Why this priority**: Approval is important for later control-plane integrations, but it is only meaningful once run creation and read models already exist.

**Independent Test**: Seed a run into `waiting_approval` state for a gate wait, call `POST /runs/<run_id>/approve`, and verify the run advances to the next stage or completes.

**Acceptance Scenarios**:

1. **Given** a run blocked on a completed approval gate, **When** a client sends `POST /runs/<run_id>/approve`, **Then** the daemon resumes the run and returns updated metadata.
2. **Given** a run that is not waiting on a completed approval gate, **When** a client sends `POST /runs/<run_id>/approve`, **Then** the daemon returns a clear conflict error instead of mutating the run.
3. **Given** a policy-blocked or nonexistent run, **When** a client sends `POST /runs/<run_id>/approve`, **Then** the daemon does not advance the run and reports the problem in HTTP error form.

### Edge Cases

- If `LOCAL_DAEMON_SECRET` is absent, the daemon should generate one stable secret for the repo on first start instead of requiring manual setup.
- Requests from non-loopback client addresses must be rejected even if they present a valid secret header.
- Requests with `Origin` headers outside loopback hosts must not receive CORS permission.
- `GET /runs/<run_id>/events` should keep waiting on an empty audit log and emit events only when valid JSONL lines appear.
- Blank lines in `audit.jsonl` should be ignored rather than emitted as malformed SSE messages.
- Invalid or unreadable run metadata should produce an HTTP error instead of a Python traceback.
- `POST /runs/<run_id>/approve` should remain limited to completed gate waits in Phase 0 and must not silently resume policy or council waits.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a FastAPI application in `spanweave/daemon/server.py`.
- **FR-002**: The system MUST expose HTTP routes in `spanweave/daemon/routes.py` for `POST /runs`, `GET /runs/<id>`, `GET /runs/<id>/events`, and `POST /runs/<id>/approve`.
- **FR-003**: `POST /runs` MUST create a new run using the existing filesystem-backed workflow engine, trigger daemon-side execution for that run, and return the created run ID plus persisted run metadata.
- **FR-004**: `GET /runs/<id>` MUST return the same run metadata model that Phase 0 CLI inspection uses, derived from repo-local `.spanweave/runs/<id>/` state.
- **FR-005**: `GET /runs/<id>/events` MUST stream audit events from `.spanweave/runs/<id>/audit.jsonl` as SSE, including new events appended after the connection opens.
- **FR-006**: SSE messages MUST include the audit event identifier, event type, and serialized payload so clients can consume them without reading the filesystem directly.
- **FR-007**: `POST /runs/<id>/approve` MUST unblock runs waiting on a completed approval gate and return the updated run metadata.
- **FR-008**: `POST /runs/<id>/approve` MUST reject runs that are not in `waiting_approval` state or are waiting for a reason other than `gate`.
- **FR-009**: Every daemon route MUST require a shared secret header whose value comes from `LOCAL_DAEMON_SECRET` or a repo-local generated secret persisted on first start.
- **FR-010**: Every daemon route MUST reject non-loopback client addresses instead of trusting the secret header alone.
- **FR-011**: The FastAPI app MUST configure CORS so only localhost loopback origins are allowed in Phase 0.
- **FR-012**: The daemon implementation MUST remain testable in-process with `httpx.AsyncClient` and MUST not require binding an external network port in CI.
- **FR-013**: `tests/test_daemon.py` MUST cover run creation, run inspection, daemon-generated SSE event streaming, approval success, rejected approval conflicts, and the local auth boundary.

### Key Entities *(include if feature involves data)*

- **Daemon Config**: Repo-root, workflow lookup paths, localhost-only policy, and shared secret state used by the FastAPI app.
- **Create Run Request**: The HTTP payload containing the issue reference, workflow name, and optional run context for `POST /runs`.
- **Run Snapshot**: The persisted run metadata returned by `POST /runs`, `GET /runs/<id>`, and `POST /runs/<id>/approve`.
- **SSE Audit Event**: One audit log entry represented as an SSE message with `id`, `event`, and JSON `data`.
- **Daemon Secret Record**: The environment-provided or repo-local generated shared secret used for Phase 0 request authentication.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `POST /runs` returns HTTP 201 with a valid `run_id`, persisted run metadata, and a run that advances beyond bare creation in an in-process AsyncClient test.
- **SC-002**: `GET /runs/<id>` returns HTTP 200 with the expected run status, current stage, and stage list for a seeded run.
- **SC-003**: `GET /runs/<id>/events` emits daemon-generated audit events over SSE within one local polling interval in an in-process test.
- **SC-004**: `POST /runs/<id>/approve` advances a run waiting on a completed gate and returns updated metadata without requiring CLI invocation.
- **SC-005**: Requests missing the shared secret or originating from a non-loopback client are rejected by the daemon.
- **SC-006**: The daemon test suite passes in CI without binding a real network port.

## Assumptions

- Phase 0 daemon consumers run on the same machine as the repository workspace and can reach only a localhost listener.
- Existing CLI run metadata and workflow-state files remain the source of truth; the daemon is an alternate transport, not a new persistence layer.
- Phase 0 does not require bidirectional socket control, so SSE is sufficient for live event delivery.
- A shared secret header is acceptable for local-only daemon access until later phases define stronger client identity.
- The daemon's default execution backend is a deterministic Phase 0 runner that advances workflows and writes audit events without depending on a live external agent runtime.
