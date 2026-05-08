# Data Model: HTTP Daemon + SSE

## DaemonConfig

- **Purpose**: Represents the repo-local configuration the FastAPI daemon uses to serve control-plane routes.
- **Fields**:
  - `repo_root`: Filesystem root containing `.spanweave/`
  - `shared_secret`: Resolved secret value for request authentication
  - `shared_secret_path`: Optional persisted secret file path when env configuration is absent
  - `user_workflows_dir`: Optional override for repo-local workflows used by tests
  - `defaults_workflows_dir`: Optional override for packaged default workflows
- **Validation rules**:
  - `repo_root` must resolve to a directory on the local filesystem.
  - `shared_secret` must be non-empty.
  - `shared_secret_path` is present only when the daemon generated or loaded a repo-local fallback secret.

## CreateRunRequest

- **Purpose**: Represents the HTTP payload accepted by `POST /runs`.
- **Fields**:
  - `issue_ref`: User- or client-supplied issue reference
  - `workflow`: Workflow name to start, defaulting to the Phase 0 default workflow
  - `context`: Optional extra context stored in workflow state
- **Validation rules**:
  - `issue_ref` must be non-empty after trimming whitespace.
  - `workflow` must be non-empty after trimming whitespace.

## RunSnapshot

- **Purpose**: Represents the persisted run metadata returned by daemon read and approval routes.
- **Fields**:
  - `run_id`
  - `issue_ref`
  - `workflow`
  - `status`
  - `current_stage`
  - `waiting_reason`
  - `last_transition`
  - `last_transition_reason`
  - `retry_count`
  - `run_path`
  - `stages`
- **Validation rules**:
  - The snapshot is derived from repo-local run files rather than process memory.
  - `stages` preserve on-disk stage ordering.

## AuditSSEEnvelope

- **Purpose**: Represents one audit log record serialized for the SSE stream.
- **Fields**:
  - `id`: Audit event identifier
  - `event`: SSE event name derived from the audit event type
  - `data`: JSON payload describing the audit event
- **Validation rules**:
  - `id` matches the underlying audit event's `event_id`.
  - `data` is valid JSON derived from the audit event payload.

## ApprovalResult

- **Purpose**: Represents the post-approval run snapshot returned by `POST /runs/<id>/approve`.
- **Fields**:
  - `run`: Updated `RunSnapshot`
  - `approved`: Boolean indicating whether the daemon accepted the approval request
- **Validation rules**:
  - `approved` is true only when the run was waiting on a completed gate and the workflow engine accepted the resume.
