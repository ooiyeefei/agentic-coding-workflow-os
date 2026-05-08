from __future__ import annotations

from textwrap import dedent
from typing import Any

import pytest
from pydantic import ValidationError
from spanweave.compiler import (
    AcceptanceGate,
    BudgetExceededError,
    ExactCommands,
    IssueText,
    Objective,
    RepoRule,
    SampleDoc,
    WorktreeRef,
    compile_packet,
    estimate_tokens,
)


def test_compile_packet_within_budget_is_deterministic() -> None:
    objective = Objective(content="Build the Context Compiler for Spanweave.")
    sources = make_sources()

    first_packet = compile_packet(objective, sources, budget_tokens=8000)
    second_packet = compile_packet(objective, sources, budget_tokens=8000)

    assert first_packet == second_packet
    assert first_packet.body == expected_full_packet()
    assert first_packet.estimated_tokens == estimate_tokens(expected_full_packet())
    assert first_packet.provenance == [
        ("objective", "objective", None),
        ("repo_rule", "agents-md", "/repo/AGENTS.md"),
        ("issue_text", "issue-7", None),
        ("sample_doc", "sample-packet", "docs/sample.md"),
        ("exact_commands", "commands", None),
        ("acceptance_gate", "gate-tests", "tests/test_compiler.py"),
    ]
    assert "Duplicate Issue" not in first_packet.body


def test_compile_packet_drops_nice_tier_first() -> None:
    packet = compile_packet(
        "Build the Context Compiler for Spanweave.",
        make_sources(),
        budget_tokens=estimate_tokens(expected_packet_without_nice()),
    )

    assert packet.body == expected_packet_without_nice()
    assert packet.provenance == [
        ("objective", "objective", None),
        ("repo_rule", "agents-md", "/repo/AGENTS.md"),
        ("issue_text", "issue-7", None),
        ("sample_doc", "sample-packet", "docs/sample.md"),
    ]


def test_compile_packet_drops_should_after_nice() -> None:
    packet = compile_packet(
        "Build the Context Compiler for Spanweave.",
        make_sources(),
        budget_tokens=estimate_tokens(expected_packet_with_must_only()),
    )

    assert packet.body == expected_packet_with_must_only()
    assert packet.provenance == [
        ("objective", "objective", None),
        ("repo_rule", "agents-md", "/repo/AGENTS.md"),
    ]


def test_compile_packet_raises_when_must_tier_exceeds_budget() -> None:
    budget_tokens = estimate_tokens(expected_packet_with_must_only()) - 1

    with pytest.raises(BudgetExceededError):
        compile_packet(
            "Build the Context Compiler for Spanweave.",
            make_sources(),
            budget_tokens=budget_tokens,
        )


def test_compile_packet_rejects_unordered_sources() -> None:
    unordered_sources: Any = set(make_sources()[:2])

    with pytest.raises(TypeError, match="ordered sequence"):
        compile_packet(
            "Build the Context Compiler for Spanweave.",
            unordered_sources,
            budget_tokens=8000,
        )


def test_specialized_source_models_enforce_canonical_source_type() -> None:
    invalid_source_type: Any = "repo_rule"

    with pytest.raises(ValidationError):
        IssueText(
            source_type=invalid_source_type,
            source_id="issue-7",
            priority="should",
            title="Issue Brief",
            content="Assemble prioritized context into one packet.",
        )


def make_sources() -> list[
    RepoRule | IssueText | SampleDoc | ExactCommands | AcceptanceGate | WorktreeRef
]:
    return [
        RepoRule(
            source_id="agents-md",
            priority="must",
            title="Repository Rules",
            content="Honor project coding and testing guidance.",
            path="/repo/AGENTS.md",
        ),
        IssueText(
            source_id="issue-7",
            priority="should",
            title="Issue Brief",
            content="Assemble prioritized context into one packet.",
        ),
        SampleDoc(
            source_id="sample-packet",
            priority="should",
            title="Sample Packet",
            content="Preserve deterministic markdown ordering.",
            path="docs/sample.md",
        ),
        ExactCommands(
            source_id="commands",
            priority="nice",
            title="Exact Commands",
            content="- `pytest tests/test_compiler.py -v`",
        ),
        AcceptanceGate(
            source_id="gate-tests",
            priority="nice",
            title="Acceptance Gate",
            content="All compiler scenarios pass.",
            path="tests/test_compiler.py",
        ),
        WorktreeRef(
            source_id="issue-7",
            priority="nice",
            title="Duplicate Issue",
            content="This duplicate should never appear.",
            path="worktree/duplicate.md",
        ),
    ]


def expected_full_packet() -> str:
    return dedent(
        """\
        # Context Packet

        ## Objective
        _Source: objective | objective | -_

        Build the Context Compiler for Spanweave.

        ## Repository Rules
        _Source: repo_rule | agents-md | /repo/AGENTS.md_

        Honor project coding and testing guidance.

        ## Issue Brief
        _Source: issue_text | issue-7 | -_

        Assemble prioritized context into one packet.

        ## Sample Packet
        _Source: sample_doc | sample-packet | docs/sample.md_

        Preserve deterministic markdown ordering.

        ## Exact Commands
        _Source: exact_commands | commands | -_

        - `pytest tests/test_compiler.py -v`

        ## Acceptance Gate
        _Source: acceptance_gate | gate-tests | tests/test_compiler.py_

        All compiler scenarios pass.

        ## Provenance

        | source_type | source_id | path |
        | --- | --- | --- |
        | objective | objective | - |
        | repo_rule | agents-md | /repo/AGENTS.md |
        | issue_text | issue-7 | - |
        | sample_doc | sample-packet | docs/sample.md |
        | exact_commands | commands | - |
        | acceptance_gate | gate-tests | tests/test_compiler.py |
        """
    )


def expected_packet_without_nice() -> str:
    return dedent(
        """\
        # Context Packet

        ## Objective
        _Source: objective | objective | -_

        Build the Context Compiler for Spanweave.

        ## Repository Rules
        _Source: repo_rule | agents-md | /repo/AGENTS.md_

        Honor project coding and testing guidance.

        ## Issue Brief
        _Source: issue_text | issue-7 | -_

        Assemble prioritized context into one packet.

        ## Sample Packet
        _Source: sample_doc | sample-packet | docs/sample.md_

        Preserve deterministic markdown ordering.

        ## Provenance

        | source_type | source_id | path |
        | --- | --- | --- |
        | objective | objective | - |
        | repo_rule | agents-md | /repo/AGENTS.md |
        | issue_text | issue-7 | - |
        | sample_doc | sample-packet | docs/sample.md |
        """
    )


def expected_packet_with_must_only() -> str:
    return dedent(
        """\
        # Context Packet

        ## Objective
        _Source: objective | objective | -_

        Build the Context Compiler for Spanweave.

        ## Repository Rules
        _Source: repo_rule | agents-md | /repo/AGENTS.md_

        Honor project coding and testing guidance.

        ## Provenance

        | source_type | source_id | path |
        | --- | --- | --- |
        | objective | objective | - |
        | repo_rule | agents-md | /repo/AGENTS.md |
        """
    )
