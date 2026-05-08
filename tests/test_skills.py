from __future__ import annotations

from pathlib import Path

import pytest
from spanweave.skills.loader import (
    DEFAULT_SKILLS_DIR,
    SkillLoader,
    SkillNotFoundError,
    get_skill,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TIROS_COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
REBASE_PROMPT_BLOCK = (
    "First, git add . to add ALL updates and commit changes we have, then run git fetch "
    "origin and git rebase origin/main. If there is any conflict, please do not decide for "
    "me first, analyse thru all conflicts if any, report back with what are the conflicts "
    "and resolution suggestions. After rebasing, push with git push --force-with-lease "
    "<feature-branch-name>."
)
REBASE_EXECUTION_SEQUENCE = (
    "Run `git add .` to stage all updates in the worktree.",
    "Create a commit that snapshots the current branch before rebasing.",
    "Run `git fetch origin` and `git rebase origin/main`.",
    "If conflicts appear, stop the rebase flow and inspect every conflicted file.",
    "Write `conflict_report.md` with each conflict, the competing changes, and concrete "
    "resolution suggestions.",
    "Wait for the human to choose the resolution approach before continuing the rebase.",
    "After the rebase completes successfully, stop and request explicit human approval for "
    "the push.",
    "Only after that approval is granted, push with `git push --force-with-lease "
    "<feature-branch-name>`.",
)
SHIPPED_SKILLS = (
    "speckit.specify",
    "speckit.clarify",
    "speckit.plan",
    "speckit.tasks",
    "speckit.implement",
    "rebase-before-pr",
    "cleanup-worktree",
    "uat-test",
    "security-best-practice",
)
TIROS_SKILL_SOURCES = {
    "speckit.specify": TIROS_COMMANDS_DIR / "speckit.specify.md",
    "speckit.clarify": TIROS_COMMANDS_DIR / "speckit.clarify.md",
    "speckit.plan": TIROS_COMMANDS_DIR / "speckit.plan.md",
    "speckit.tasks": TIROS_COMMANDS_DIR / "speckit.tasks.md",
    "speckit.implement": TIROS_COMMANDS_DIR / "speckit.implement.md",
}


def assert_occurs_in_order(text: str, snippets: tuple[str, ...]) -> None:
    cursor = -1
    for snippet in snippets:
        next_cursor = text.find(snippet, cursor + 1)
        assert next_cursor != -1, f"Missing snippet: {snippet}"
        cursor = next_cursor


def test_loads_all_shipped_skills() -> None:
    loader = SkillLoader()

    loaded = loader.load_all()

    assert set(loaded) == set(SHIPPED_SKILLS)
    for name in SHIPPED_SKILLS:
        skill = loaded[name]
        assert skill.name == name
        assert skill.version == "1.0.0"
        assert skill.inputs
        assert skill.expected_artifacts
        assert skill.success_checks
        assert skill.next_transition
        assert len(skill.content.strip()) > 100
        assert Path(skill.path).parent == DEFAULT_SKILLS_DIR


def test_get_skill_returns_rebase_before_pr() -> None:
    skill = get_skill("rebase-before-pr")

    assert skill.name == "rebase-before-pr"
    assert REBASE_PROMPT_BLOCK in skill.content
    assert_occurs_in_order(skill.content, REBASE_EXECUTION_SEQUENCE)
    assert (
        "Do not auto-push after a clean rebase; approval is required before the final push."
        in skill.content
    )


def test_get_skill_returns_security_best_practice() -> None:
    skill = get_skill("security-best-practice")

    assert skill.name == "security-best-practice"
    assert "Map trust boundaries" in skill.content
    assert "exact safe primitive" in skill.content
    assert "rules, skills" in skill.content
    assert "MCP config" in skill.content
    assert "negative tests" in skill.content


def test_get_skill_raises_for_missing_skill() -> None:
    with pytest.raises(SkillNotFoundError):
        get_skill("nonexistent")


@pytest.mark.parametrize(("skill_name", "source_path"), sorted(TIROS_SKILL_SOURCES.items()))
def test_imported_speckit_skills_preserve_tiros_content(skill_name: str, source_path: Path) -> None:
    skill = get_skill(skill_name)
    source_text = source_path.read_text(encoding="utf-8")

    assert skill.content == source_text
