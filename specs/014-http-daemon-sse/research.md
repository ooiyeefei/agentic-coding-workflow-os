# Research: HTTP Daemon + SSE

## Decision 1: Use SSE instead of WebSockets for Phase 0 live updates

- **Decision**: Expose run events through Server-Sent Events rather than WebSockets.
- **Rationale**: The accepted clarification says Phase 0 only needs unidirectional event delivery. SSE keeps the contract simple, works over plain HTTP, and maps directly onto the append-only audit log model.
- **Alternatives considered**:
  - Use WebSockets: rejected because bidirectional control is unnecessary in this slice and would expand the daemon surface before any concrete consumer exists.
  - Use polling-only JSON endpoints: rejected because later clients need a live stream contract, and polling would duplicate audit-tail logic in every consumer.

## Decision 2: Authenticate requests with a shared secret header

- **Decision**: Require an `X-Spanweave-Secret` header on every daemon route and resolve its value from `LOCAL_DAEMON_SECRET`, or from a repo-local generated secret if the environment variable is absent.
- **Rationale**: The accepted clarification explicitly chooses a shared secret for the local-only daemon. A header-based check is easy for future plugin and dashboard clients to send, and a repo-local fallback avoids manual bootstrap friction.
- **Alternatives considered**:
  - No authentication because the daemon is local-only: rejected because localhost binding alone does not protect against every local process.
  - OS-user or session-bound auth: rejected because there is no Phase 0 consumer or daemon supervisor yet, so that complexity would not buy immediate value.

## Decision 3: Enforce loopback-only access in both transport and CORS

- **Decision**: Reject requests whose client address is not loopback, and configure CORS to allow only `localhost`, `127.0.0.1`, and `::1` origins.
- **Rationale**: The accepted clarification sets localhost-only access as a hard Phase 0 boundary. Enforcing it in the application keeps the invariant intact even if a future runner misconfigures the bind host.
- **Alternatives considered**:
  - Trust external process supervision to bind to localhost only: rejected because the acceptance criteria require the daemon itself to uphold the boundary.
  - Allow all origins and rely on the secret: rejected because permissive CORS weakens the local-only contract and broadens accidental browser exposure.

## Decision 4: Reuse existing run metadata and gate approval logic

- **Decision**: Build daemon responses from the existing run snapshot loader and reuse the workflow engine's gate-resume behavior for `POST /runs/<id>/approve`.
- **Rationale**: The daemon is a transport layer over the same filesystem state the CLI already owns. Reusing the same read and approval semantics avoids divergent behavior between HTTP and CLI clients.
- **Alternatives considered**:
  - Define a new daemon-only run metadata model and approval flow: rejected because it would duplicate business logic and create drift.
  - Shell out to the CLI from the daemon: rejected because the codebase already exposes the necessary Python APIs directly.

## Decision 5: Tail `audit.jsonl` by polling for appended lines

- **Decision**: Implement SSE streaming by polling `.spanweave/runs/<run_id>/audit.jsonl`, parsing appended JSONL lines into typed audit events, and emitting them as SSE messages with `id`, `event`, and JSON `data`.
- **Rationale**: The audit log is already the persisted event source of truth. Polling works in-process, needs no extra watcher dependency, and stays deterministic in CI.
- **Alternatives considered**:
  - Introduce filesystem notification dependencies: rejected because Phase 0 does not need OS-specific watcher complexity.
  - Read from the daily audit log instead of the per-run log: rejected because clients subscribe to one run and need only that run's events.

## Decision 6: Auto-advance daemon-started runs with a deterministic Phase 0 execution backend

- **Decision**: `POST /runs` creates the run record, schedules daemon-side workflow advancement, and emits audit events from that advancement so SSE subscribers observe real activity without out-of-band seeding.
- **Rationale**: The Phase 0 W16 scope explicitly defines `POST /runs` as a start endpoint and requires SSE clients to observe events as workflows advance. A deterministic built-in runner satisfies that contract before full external agent execution is wired in.
- **Alternatives considered**:
  - Keep `POST /runs` as a pure create call: rejected because it fails the W16 start contract and leaves SSE idle until external mutation occurs.
  - Omit `POST /runs` until a full execution backend exists: rejected because the acceptance criteria explicitly require run creation over HTTP.
