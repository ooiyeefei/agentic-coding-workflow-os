from __future__ import annotations

import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .errors import RebaseAnalysisError

_CONFLICT_RE = re.compile(r"^CONFLICT \(([^)]+)\):", re.MULTILINE)
_CONFLICT_IN_RE = re.compile(r"Merge conflict in (.+)")


class ConflictHunk(BaseModel):
    """One ours/theirs pair extracted from conflict markers with line positions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    ours: str
    theirs: str


class ConflictFile(BaseModel):
    """A single file with merge conflicts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    conflict_type: str = Field(default="content", min_length=1)
    suggestion: str = Field(default="manual")
    hunks: list[ConflictHunk] = Field(
        default_factory=lambda: list[ConflictHunk]()
    )


class RebaseReport(BaseModel):
    """Result of a mutation-free rebase conflict analysis."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1)
    files_with_conflicts: list[ConflictFile] = Field(
        default_factory=lambda: list[ConflictFile]()
    )
    merge_tree_sha: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_conflicts(self) -> bool:
        return len(self.files_with_conflicts) > 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def clean(self) -> bool:
        return not self.has_conflicts

    def resolution_commands(self) -> list[str]:
        """Human-readable commands to resolve (never auto-applied)."""
        if self.clean:
            return [f"git rebase {self.target}"]
        cmds = [
            f"git rebase {self.target}",
            "# Resolve the following conflicts:",
        ]
        for f in self.files_with_conflicts:
            if f.hunks:
                ranges = ", ".join(
                    f"L{h.start_line}-{h.end_line}" for h in f.hunks
                )
                cmds.append(
                    f"#   {f.path}:{f.hunks[0].start_line} "
                    f"({f.conflict_type}, {ranges}) — {f.suggestion}"
                )
            else:
                cmds.append(f"#   {f.path} ({f.conflict_type}) — {f.suggestion}")
        cmds.append("# Then: git add <resolved-files> && git rebase --continue")
        return cmds


def _parse_merge_tree_output(
    stdout: str,
    returncode: int,
) -> tuple[str | None, list[ConflictFile]]:
    lines = stdout.strip().splitlines()
    if not lines:
        return None, []

    tree_sha = lines[0].strip()
    if returncode == 0:
        return tree_sha, []

    conflicts: list[ConflictFile] = []
    for line in lines[1:]:
        type_match = _CONFLICT_RE.match(line)
        if not type_match:
            continue

        conflict_type = type_match.group(1)

        in_match = _CONFLICT_IN_RE.search(line)
        if in_match:
            file_path = in_match.group(1).strip()
        else:
            tokens = line[type_match.end() :].split()
            file_path = tokens[0] if tokens else "unknown"

        conflicts.append(
            ConflictFile(
                path=file_path,
                conflict_type=conflict_type,
                suggestion="manual",
            )
        )

    return tree_sha, conflicts


def _parse_conflict_hunks(content: str) -> list[ConflictHunk]:
    """Parse conflict markers into hunks with 1-indexed line positions."""
    hunks: list[ConflictHunk] = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].startswith("<<<<<<<"):
            start_line = i + 1
            ours_lines: list[str] = []
            theirs_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("======="):
                ours_lines.append(lines[i])
                i += 1
            i += 1
            while i < len(lines) and not lines[i].startswith(">>>>>>>"):
                theirs_lines.append(lines[i])
                i += 1
            end_line = i + 1
            hunks.append(
                ConflictHunk(
                    start_line=start_line,
                    end_line=end_line,
                    ours="\n".join(ours_lines),
                    theirs="\n".join(theirs_lines),
                )
            )
        i += 1
    return hunks


def _extract_hunks(tree_sha: str, file_path: str, cwd: Path) -> list[ConflictHunk]:
    """Read the merged blob from the object store and parse conflict markers."""
    result = subprocess.run(
        ["git", "show", f"{tree_sha}:{file_path}"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        return []
    return _parse_conflict_hunks(result.stdout)


def _repo_state_snapshot(cwd: Path) -> tuple[str, str, str]:
    """Capture working-tree status, HEAD, and all refs for mutation detection."""
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=cwd,
    ).stdout

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd,
    ).stdout.strip()

    refs = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname) %(objectname)"],
        capture_output=True,
        text=True,
        cwd=cwd,
    ).stdout

    return status, head, refs


def analyze_rebase(
    worktree_path: Path,
    target: str = "origin/main",
) -> RebaseReport:
    """Analyze rebase conflicts without mutating any repository state.

    Uses ``git merge-tree --write-tree`` to simulate the merge.  The working
    tree, index, local branches, and remote-tracking refs are never modified.

    The caller is responsible for ensuring *target* is up-to-date (e.g. by
    running ``git fetch`` before calling this function).
    """
    cwd = Path(worktree_path)

    state_before = _repo_state_snapshot(cwd)

    result = subprocess.run(
        ["git", "merge-tree", "--write-tree", target, "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )

    if result.returncode > 1:
        raise RebaseAnalysisError(f"git merge-tree failed: {result.stderr.strip()}")

    tree_sha, conflicts = _parse_merge_tree_output(result.stdout, result.returncode)

    if tree_sha and conflicts:
        enriched: list[ConflictFile] = []
        for cf in conflicts:
            hunks = _extract_hunks(tree_sha, cf.path, cwd)
            enriched.append(
                ConflictFile(
                    path=cf.path,
                    conflict_type=cf.conflict_type,
                    suggestion=cf.suggestion,
                    hunks=hunks,
                )
            )
        conflicts = enriched

    state_after = _repo_state_snapshot(cwd)
    if state_before != state_after:
        raise RebaseAnalysisError(
            "analyze_rebase mutated repository state — this is a bug"
        )

    return RebaseReport(
        target=target,
        files_with_conflicts=conflicts,
        merge_tree_sha=tree_sha,
    )


__all__ = ["ConflictFile", "ConflictHunk", "RebaseReport", "analyze_rebase"]
