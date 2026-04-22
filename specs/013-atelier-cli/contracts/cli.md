# Contract: Atelier CLI

## Common behavior

- Root command: `atelier`
- Human-readable output remains the default for interactive use.
- Commands that support `--json` emit JSON only on stdout.
- User-facing errors exit non-zero and surface a concise message.

## `atelier init`

**Command**: `atelier init [--repo PATH] [--json]`

**Contract**:

- Creates missing repo-local directories under `.atelier/`.
- Writes the default `speckit-loop` workflow into `.atelier/workflows/` when missing.
- Succeeds idempotently when the workspace already exists.

**JSON shape**

```json
{
  "repo": "/path/to/repo",
  "atelier_root": "/path/to/repo/.atelier",
  "created_dirs": [".atelier/workflows"],
  "created_files": [".atelier/workflows/speckit-loop.yaml"],
  "changed": true
}
```

## `atelier run`

**Command**: `atelier run --issue <ISSUE_REF> [--repo PATH] [--workflow NAME] [--context TEXT] [--json]`

**Contract**:

- Creates a new run under `.atelier/runs/<run_id>/`.
- Loads the selected workflow, defaulting to `speckit-loop`.
- Returns the stored run snapshot immediately after creation.
- Human output prints the run ID, workflow, and current stage when present.

**JSON shape**

```json
{
  "run_id": "run_01...",
  "issue_ref": "issue #42",
  "workflow": "speckit-loop",
  "status": "running",
  "current_stage": "001-specify",
  "waiting_reason": null,
  "stages": [
    {
      "stage_id": "001-specify",
      "status": "running",
      "path": "/path/to/repo/.atelier/runs/run_01.../stages/001-specify"
    }
  ]
}
```

## `atelier run resume`

**Command**: `atelier run resume <RUN_ID> [--approve] [--json]`

**Contract**:

- Reads persisted run state for the specified run.
- Without `--approve`, reports the current stored state only.
- With `--approve`, advances a completed gate wait when the persisted state already allows that transition.

## `atelier run list`

**Command**: `atelier run list [--json]`

**Contract**:

- Reads run summaries from persisted `.atelier/runs/` state.
- Sorts runs newest-first using run IDs and filesystem state.
- Human output includes run ID, status, current stage, and issue reference.
- `--json` returns an array of run snapshot objects.

## `atelier run show`

**Command**: `atelier run show <RUN_ID> [--json]`

**Contract**:

- Returns a detailed persisted snapshot for a single run.
- Human output renders a stage tree or ordered stage list with completion/current/waiting state.
- `--json` returns the same snapshot object shape used by `atelier run`.

## `atelier grep`

**Command**: `atelier grep <PATTERN> [--repo PATH] [--ignore-case] [--json]`

**Contract**:

- Searches repo-local `.atelier/` text artifacts such as markdown, YAML, JSON, and JSONL files.
- Returns path and snippet context for every match.
- Human output prints `path:line` plus the matching line.

**JSON shape**

```json
{
  "pattern": "issue #42",
  "repo": "/path/to/repo",
  "match_count": 1,
  "matches": [
    {
      "path": ".atelier/runs/run_01.../run.md",
      "line": 2,
      "text": "issue_ref: issue #42"
    }
  ]
}
```

## `atelier cleanup`

**Command**: `atelier cleanup <RUN_ID> [--repo PATH] [--yes] [--json]`

**Contract**:

- Targets only worktrees associated with the specified run.
- Live deletion requires either an interactive confirmation prompt or `--yes`.
- Never removes unrelated worktrees.

**JSON shape**

```json
{
  "run_id": "run_01...",
  "removed_count": 1,
  "removed": [
    "/path/to/worktrees/run_01..."
  ],
  "repo": "/path/to/repo"
}
```

## `atelier daemon`

**Commands**:

- `atelier daemon start [--repo PATH] [--json]`
- `atelier daemon stop [--repo PATH] [--json]`
- `atelier daemon status [--repo PATH] [--json]`

**Contract**:

- Uses repo-scoped placeholder state so future surfaces can reuse the lifecycle commands.
- `start` is idempotent when the placeholder is already `running`.
- `status` reports whether the daemon placeholder is `running` or `stopped`.
- `stop` writes a stopped placeholder state.

**JSON shape**

```json
{
  "state": "running",
  "mode": "placeholder",
  "state_path": "/path/to/repo/.atelier/daemon/state.json",
  "note": "HTTP daemon arrives in W16. Current commands track placeholder daemon control state."
}
```
