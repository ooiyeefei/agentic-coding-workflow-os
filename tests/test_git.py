from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from atelier.git import (
    ConfirmationRequiredError,
    ConflictFile,
    ConflictHunk,
    RebaseReport,
    WorktreeError,
    analyze_rebase,
    cleanup_run_worktrees,
    create_worktree,
    remove_worktree,
)


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=True,
    )


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Temporary git repo with one commit on 'main'."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", str(repo), cwd=tmp_path)
    _git("config", "user.email", "test@atelier.test", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)

    (repo / "README.md").write_text("# Test repo\n")
    _git("add", ".", cwd=repo)
    _git("commit", "-m", "Initial commit", cwd=repo)
    return repo


@pytest.fixture()
def run_id(fixed_ulid_values: list[str]) -> str:
    return f"run_{fixed_ulid_values[0]}"


# ---------------------------------------------------------------------------
# Worktree lifecycle
# ---------------------------------------------------------------------------


class TestCreateWorktree:
    def test_creates_directory(
        self, git_repo: Path, run_id: str, tmp_path: Path
    ) -> None:
        wt = create_worktree(
            run_id, repo_root=git_repo, worktree_base=tmp_path / "wts"
        )
        assert wt.exists()
        assert wt.is_dir()
        assert (wt / "README.md").exists()

    def test_creates_branch(
        self, git_repo: Path, run_id: str, tmp_path: Path
    ) -> None:
        create_worktree(run_id, repo_root=git_repo, worktree_base=tmp_path / "wts")
        result = _git("branch", "--list", f"atelier/{run_id}", cwd=git_repo)
        assert run_id in result.stdout

    def test_returns_valid_git_dir(
        self, git_repo: Path, run_id: str, tmp_path: Path
    ) -> None:
        wt = create_worktree(
            run_id, repo_root=git_repo, worktree_base=tmp_path / "wts"
        )
        result = _git("rev-parse", "--is-inside-work-tree", cwd=wt)
        assert result.stdout.strip() == "true"

    def test_invalid_run_id_raises(self, git_repo: Path) -> None:
        with pytest.raises(ValueError, match="expected 'run' ID"):
            create_worktree("bad-id", repo_root=git_repo)

    def test_default_layout_under_worktrees_dir(
        self, git_repo: Path, run_id: str
    ) -> None:
        wt = create_worktree(run_id, repo_root=git_repo)
        expected = git_repo.parent / "worktrees" / run_id
        assert wt == expected
        assert wt.exists()
        remove_worktree(wt, confirm=True)


class TestRemoveWorktree:
    def test_no_confirm_raises(
        self, git_repo: Path, run_id: str, tmp_path: Path
    ) -> None:
        wt = create_worktree(
            run_id, repo_root=git_repo, worktree_base=tmp_path / "wts"
        )
        with pytest.raises(ConfirmationRequiredError):
            remove_worktree(wt, confirm=False)
        assert wt.exists()

    def test_confirmed_removes(
        self, git_repo: Path, run_id: str, tmp_path: Path
    ) -> None:
        wt = create_worktree(
            run_id, repo_root=git_repo, worktree_base=tmp_path / "wts"
        )
        assert wt.exists()
        remove_worktree(wt, confirm=True)
        assert not wt.exists()

    def test_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(WorktreeError, match="does not exist"):
            remove_worktree(tmp_path / "nope", confirm=True)


# ---------------------------------------------------------------------------
# Rebase analyzer
# ---------------------------------------------------------------------------


@pytest.fixture()
def clean_branch_repo(git_repo: Path) -> Path:
    """Feature branch that fast-forwards cleanly onto main."""
    _git("checkout", "-b", "feature-clean", cwd=git_repo)
    (git_repo / "new_file.txt").write_text("new content\n")
    _git("add", ".", cwd=git_repo)
    _git("commit", "-m", "Add new file on feature", cwd=git_repo)
    return git_repo


@pytest.fixture()
def conflicting_repo(git_repo: Path) -> Path:
    """Feature branch that conflicts with main on shared.txt."""
    (git_repo / "shared.txt").write_text("original\n")
    _git("add", ".", cwd=git_repo)
    _git("commit", "-m", "Add shared file", cwd=git_repo)

    _git("checkout", "-b", "feature-conflict", cwd=git_repo)
    (git_repo / "shared.txt").write_text("feature wants this\n")
    _git("add", ".", cwd=git_repo)
    _git("commit", "-m", "Feature changes shared", cwd=git_repo)

    _git("checkout", "main", cwd=git_repo)
    (git_repo / "shared.txt").write_text("main wants this\n")
    _git("add", ".", cwd=git_repo)
    _git("commit", "-m", "Main changes shared", cwd=git_repo)

    _git("checkout", "feature-conflict", cwd=git_repo)
    return git_repo


@pytest.fixture()
def repo_with_remote(tmp_path: Path) -> Path:
    """Local repo with 'origin' remote and a stale origin/main ref."""
    remote = tmp_path / "remote"
    _git("init", "-b", "main", "--bare", str(remote), cwd=tmp_path)

    local = tmp_path / "local"
    _git("clone", str(remote), str(local), cwd=tmp_path)
    _git("config", "user.email", "test@atelier.test", cwd=local)
    _git("config", "user.name", "Test", cwd=local)

    (local / "shared.txt").write_text("original\n")
    _git("add", ".", cwd=local)
    _git("commit", "-m", "Initial", cwd=local)
    _git("push", "origin", "main", cwd=local)

    _git("checkout", "-b", "feature", cwd=local)
    (local / "shared.txt").write_text("feature\n")
    _git("add", ".", cwd=local)
    _git("commit", "-m", "Feature change", cwd=local)

    # Push a new commit to remote via a temp clone — local won't see it
    temp = tmp_path / "temp"
    _git("clone", str(remote), str(temp), cwd=tmp_path)
    _git("config", "user.email", "test@atelier.test", cwd=temp)
    _git("config", "user.name", "Test", cwd=temp)
    (temp / "shared.txt").write_text("remote main\n")
    _git("add", ".", cwd=temp)
    _git("commit", "-m", "Remote main change", cwd=temp)
    _git("push", "origin", "main", cwd=temp)

    return local


class TestAnalyzeRebase:
    def test_clean_branch_returns_empty_report(self, clean_branch_repo: Path) -> None:
        report = analyze_rebase(clean_branch_repo, target="main")
        assert report.clean is True
        assert report.has_conflicts is False
        assert report.files_with_conflicts == []
        assert report.merge_tree_sha is not None

    def test_conflicting_branch_reports_files(self, conflicting_repo: Path) -> None:
        report = analyze_rebase(conflicting_repo, target="main")
        assert report.has_conflicts is True
        assert report.clean is False
        paths = [f.path for f in report.files_with_conflicts]
        assert "shared.txt" in paths

    def test_never_mutates_repo(self, conflicting_repo: Path) -> None:
        """Working tree, HEAD, and all refs must be identical before/after."""
        status_before = _git("status", "--porcelain", cwd=conflicting_repo).stdout
        head_before = _git("rev-parse", "HEAD", cwd=conflicting_repo).stdout
        refs_before = _git(
            "for-each-ref", "--format=%(refname) %(objectname)",
            cwd=conflicting_repo,
        ).stdout

        analyze_rebase(conflicting_repo, target="main")

        status_after = _git("status", "--porcelain", cwd=conflicting_repo).stdout
        head_after = _git("rev-parse", "HEAD", cwd=conflicting_repo).stdout
        refs_after = _git(
            "for-each-ref", "--format=%(refname) %(objectname)",
            cwd=conflicting_repo,
        ).stdout

        assert status_before == status_after
        assert head_before == head_after
        assert refs_before == refs_after

    def test_never_fetches_remote(self, repo_with_remote: Path) -> None:
        """analyze_rebase must not fetch — caller is responsible."""
        origin_ref = _git(
            "rev-parse", "refs/remotes/origin/main", cwd=repo_with_remote
        ).stdout.strip()

        git_dir = Path(
            _git("rev-parse", "--absolute-git-dir", cwd=repo_with_remote)
            .stdout.strip()
        )
        fetch_head = git_dir / "FETCH_HEAD"
        fetch_before = fetch_head.read_bytes() if fetch_head.exists() else None

        analyze_rebase(repo_with_remote, target="origin/main")

        origin_ref_after = _git(
            "rev-parse", "refs/remotes/origin/main", cwd=repo_with_remote
        ).stdout.strip()
        fetch_after = fetch_head.read_bytes() if fetch_head.exists() else None

        assert origin_ref == origin_ref_after, "origin/main ref was mutated"
        assert fetch_before == fetch_after, "FETCH_HEAD was mutated"

    def test_report_includes_resolution_commands(
        self, conflicting_repo: Path
    ) -> None:
        report = analyze_rebase(conflicting_repo, target="main")
        cmds = report.resolution_commands()
        assert any("git rebase" in c for c in cmds)
        assert any("shared.txt:" in c for c in cmds)

    def test_conflict_file_structure(self, conflicting_repo: Path) -> None:
        report = analyze_rebase(conflicting_repo, target="main")
        for conflict in report.files_with_conflicts:
            assert isinstance(conflict, ConflictFile)
            assert conflict.path
            assert conflict.conflict_type
            assert conflict.suggestion in ("manual", "prefer_ours", "prefer_theirs")

    def test_conflicting_branch_has_hunks_with_line_precision(
        self, conflicting_repo: Path
    ) -> None:
        report = analyze_rebase(conflicting_repo, target="main")
        for conflict in report.files_with_conflicts:
            assert len(conflict.hunks) > 0, f"no hunks for {conflict.path}"
            for hunk in conflict.hunks:
                assert isinstance(hunk, ConflictHunk)
                assert hunk.start_line >= 1
                assert hunk.end_line >= 1
                assert hunk.start_line < hunk.end_line

    def test_hunks_contain_branch_content(self, conflicting_repo: Path) -> None:
        report = analyze_rebase(conflicting_repo, target="main")
        shared = next(
            f for f in report.files_with_conflicts if f.path == "shared.txt"
        )
        hunk_text = " ".join(f"{h.ours} {h.theirs}" for h in shared.hunks)
        assert "feature wants this" in hunk_text
        assert "main wants this" in hunk_text

    def test_clean_branch_has_no_hunks(self, clean_branch_repo: Path) -> None:
        report = analyze_rebase(clean_branch_repo, target="main")
        assert all(len(f.hunks) == 0 for f in report.files_with_conflicts)


class TestRebaseReportModel:
    def test_clean_report(self) -> None:
        report = RebaseReport(target="main")
        assert report.clean is True
        assert report.has_conflicts is False
        assert report.resolution_commands() == ["git rebase main"]

    def test_conflicting_report(self) -> None:
        report = RebaseReport(
            target="origin/main",
            files_with_conflicts=[
                ConflictFile(path="a.txt"),
                ConflictFile(
                    path="b.txt",
                    conflict_type="rename/delete",
                    hunks=[ConflictHunk(
                        start_line=5, end_line=11, ours="left", theirs="right",
                    )],
                ),
            ],
        )
        assert report.has_conflicts is True
        assert report.clean is False
        assert len(report.resolution_commands()) > 2
        assert report.files_with_conflicts[1].hunks[0].ours == "left"
        assert report.files_with_conflicts[1].hunks[0].start_line == 5
        assert report.files_with_conflicts[1].hunks[0].end_line == 11


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_no_confirm_raises(
        self, git_repo: Path, run_id: str
    ) -> None:
        with pytest.raises(ConfirmationRequiredError):
            cleanup_run_worktrees(run_id, confirm=False, repo_root=git_repo)

    def test_removes_matching_worktrees(
        self, git_repo: Path, fixed_ulid_values: list[str], tmp_path: Path
    ) -> None:
        rid = f"run_{fixed_ulid_values[1]}"
        wt = create_worktree(
            rid, repo_root=git_repo, worktree_base=tmp_path / "wts"
        )
        assert wt.exists()

        removed = cleanup_run_worktrees(rid, confirm=True, repo_root=git_repo)
        assert len(removed) == 1
        assert not wt.exists()

    def test_leaves_other_worktrees(
        self, git_repo: Path, fixed_ulid_values: list[str], tmp_path: Path
    ) -> None:
        rid1 = f"run_{fixed_ulid_values[2]}"
        rid2 = f"run_{fixed_ulid_values[3]}"

        wt1 = create_worktree(
            rid1, repo_root=git_repo, worktree_base=tmp_path / "wts"
        )
        wt2 = create_worktree(
            rid2, repo_root=git_repo, worktree_base=tmp_path / "wts"
        )

        cleanup_run_worktrees(rid1, confirm=True, repo_root=git_repo)
        assert not wt1.exists()
        assert wt2.exists()
