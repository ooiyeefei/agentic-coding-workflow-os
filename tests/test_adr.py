from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from spanweave.adr.numbering import next_adr_number
from spanweave.adr.slug import slugify
from spanweave.adr.synthesis import synthesize_adr
from spanweave.memory import Decision, RejectedAlternative, write_record
from ulid import ULID

_GOLDEN_DIR = Path(__file__).parent / "golden"


class _DeterministicULIDFactory:
    def __init__(self, values: list[str]) -> None:
        self._values: Iterator[str] = iter(values)

    def __call__(self) -> str:
        return next(self._values)

    @staticmethod
    def parse(value: str) -> ULID:
        return ULID.parse(value)


_TIMESTAMP = datetime(2026, 4, 20, 0, 0, tzinfo=UTC)


def _make_fixture_records(
    run_id: str,
    ulids: list[str],
) -> tuple[list[Decision], list[RejectedAlternative]]:
    stage_id = f"stage_{ulids[0]}"

    decisions = [
        Decision(
            id=f"decision_{ulids[1]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=_TIMESTAMP,
            tags=["memory-backend", "persistence", "safety-critical"],
            confidence=0.92,
            source="coder",
            body=(
                "# Use filesystem-first storage\n"
                "\n"
                "The memory system uses the local filesystem as its primary"
                " storage backend, writing typed records as individual"
                " markdown files under `.spanweave/memory/`.\n"
                "\n"
                "* Good, because records are human-readable and reviewable"
                " with standard tools\n"
                "* Good, because git tracks changes with full history and"
                " diff support\n"
                "* Bad, because no built-in indexing for large record sets\n"
            ),
        ),
        Decision(
            id=f"decision_{ulids[2]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=_TIMESTAMP,
            tags=["memory-backend", "persistence"],
            confidence=0.88,
            source="coder",
            body=(
                "# Encode metadata as YAML frontmatter\n"
                "\n"
                "Every memory record carries structured YAML frontmatter"
                " for type, ID, timestamps, and tags, followed by a"
                " freeform markdown body.\n"
                "\n"
                "* Good, because enables programmatic filtering without"
                " parsing prose\n"
                "* Neutral, because requires a YAML parsing dependency\n"
            ),
        ),
        Decision(
            id=f"decision_{ulids[3]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=_TIMESTAMP,
            tags=["memory-backend", "safety-critical"],
            confidence=0.85,
            source="reviewer",
            body=(
                "# Redact secrets at write-time\n"
                "\n"
                "All records pass through the security redaction pipeline"
                " before reaching the filesystem, replacing detected secrets"
                " with `[REDACTED:<type>]` markers.\n"
                "\n"
                "* Good, because prevents accidental secret leakage in git"
                " history\n"
                "* Bad, because redaction is irreversible once written\n"
            ),
        ),
    ]

    rejected = [
        RejectedAlternative(
            id=f"rejected_alternative_{ulids[4]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=_TIMESTAMP,
            tags=["memory-backend", "persistence"],
            confidence=0.6,
            source="coder",
            body=(
                "# Use SQLite for record storage\n"
                "\n"
                "SQLite would provide indexed queries and ACID transactions"
                " for the memory store.\n"
                "\n"
                "* Good, because enables fast indexed queries across all"
                " record fields\n"
                "* Bad, because records become opaque binary data"
                " inaccessible to standard text tools\n"
                "* Bad, because complicates git-based workflows since"
                " the database file is not diffable\n"
            ),
        ),
        RejectedAlternative(
            id=f"rejected_alternative_{ulids[5]}",
            run_id=run_id,
            stage_id=stage_id,
            timestamp=_TIMESTAMP,
            tags=["memory-backend", "persistence"],
            confidence=0.4,
            source="reviewer",
            body=(
                "# Use Redis for ephemeral caching\n"
                "\n"
                "Redis would serve as a low-latency cache layer in front of"
                " the primary record store.\n"
                "\n"
                "* Good, because offers sub-millisecond reads for frequently"
                " accessed records\n"
                "* Bad, because introduces a runtime infrastructure"
                " dependency\n"
                "* Bad, because data loss occurs if the instance restarts"
                " without persistence configured\n"
            ),
        ),
    ]

    return decisions, rejected


def test_synthesize_adr_renders_madr3_golden_file(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    decisions, rejected = _make_fixture_records(fixed_run_id, fixed_ulid_values)
    for rec in [*decisions, *rejected]:
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    assert len(paths) == 1
    assert paths[0].name == "0001-memory-backend.md"
    assert paths[0].exists()

    actual = paths[0].read_text(encoding="utf-8")
    golden_path = _GOLDEN_DIR / "0001-memory-backend.md"

    if not golden_path.exists():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(actual, encoding="utf-8")
        pytest.fail(
            f"Golden file did not exist — created at {golden_path}. "
            "Review it and re-run the test."
        )

    expected = golden_path.read_text(encoding="utf-8")
    assert actual == expected, (
        "Rendered ADR does not match golden file.\n"
        f"Actual:\n{actual}\n\nExpected:\n{expected}"
    )


def test_synthesize_adr_uses_decision_makers_field(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """MADR 3.0 requires `decision-makers`, not `deciders`."""
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    decisions, rejected = _make_fixture_records(fixed_run_id, fixed_ulid_values)
    for rec in [*decisions, *rejected]:
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    content = paths[0].read_text(encoding="utf-8")
    assert "decision-makers:" in content
    assert "deciders:" not in content


def test_synthesize_adr_consequences_polarity(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Consequences must use only Good/Bad polarity."""
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    decisions, rejected = _make_fixture_records(fixed_run_id, fixed_ulid_values)
    for rec in [*decisions, *rejected]:
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    content = paths[0].read_text(encoding="utf-8")

    consequences_start = content.index("### Consequences")
    next_section = content.index("\n## ", consequences_start)
    consequences_block = content[consequences_start:next_section]

    assert "* Good, because" in consequences_block
    assert "* Bad, because" in consequences_block
    assert "* Neutral, because" not in consequences_block


def test_synthesize_adr_pros_cons_supports_neutral(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """Pros and Cons section supports Good/Neutral/Bad polarity."""
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    decisions, rejected = _make_fixture_records(fixed_run_id, fixed_ulid_values)
    for rec in [*decisions, *rejected]:
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    content = paths[0].read_text(encoding="utf-8")
    pros_cons_start = content.index("## Pros and Cons")
    pros_cons_block = content[pros_cons_start:]

    assert "* Good, because" in pros_cons_block
    assert "* Bad, because" in pros_cons_block
    assert "* Neutral, because" in pros_cons_block


def test_auto_numbering_increments_correctly(tmp_path: Path) -> None:
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)

    assert next_adr_number(adr_dir) == 1

    (adr_dir / "0001-first.md").write_text("# First\n", encoding="utf-8")
    assert next_adr_number(adr_dir) == 2

    (adr_dir / "0011-eleventh.md").write_text("# Eleventh\n", encoding="utf-8")
    assert next_adr_number(adr_dir) == 12


def test_auto_numbering_nonexistent_directory(tmp_path: Path) -> None:
    assert next_adr_number(tmp_path / "nonexistent") == 1


def test_slugify_ascii_title() -> None:
    assert slugify("Memory Backend") == "memory-backend"


def test_slugify_unicode_title() -> None:
    assert slugify("Über Straße Design") == "uber-strae-design"
    assert slugify("café résumé") == "cafe-resume"


def test_slugify_special_characters() -> None:
    assert slugify("Use C++ for Performance!") == "use-c-for-performance"
    assert slugify("--leading--trailing--") == "leading-trailing"


def test_synthesize_no_decisions_returns_empty(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    assert paths == []
    assert not adr_output.exists()


def test_consequences_only_reflect_accepted_option_tradeoffs(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """RED regression: consequences must come from accepted decisions only."""
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    decisions, rejected = _make_fixture_records(fixed_run_id, fixed_ulid_values)
    for rec in [*decisions, *rejected]:
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    content = paths[0].read_text(encoding="utf-8")
    consequences_start = content.index("### Consequences")
    next_section = content.index("\n## ", consequences_start)
    consequences_block = content[consequences_start:next_section]

    assert "no built-in indexing" in consequences_block
    assert "redaction is irreversible" in consequences_block

    assert "runtime infrastructure dependency" not in consequences_block
    assert "data loss occurs" not in consequences_block
    assert "opaque binary data" not in consequences_block


def test_tag_reordering_produces_single_adr(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """ORANGE regression: same tags in different order must group together."""
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    stage_id = f"stage_{fixed_ulid_values[0]}"
    d1 = Decision(
        id=f"decision_{fixed_ulid_values[1]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=_TIMESTAMP,
        tags=["memory-backend", "persistence"],
        confidence=0.9,
        source="coder",
        body="# Option A\n\nDescription A.\n\n* Good, because reason A\n",
    )
    d2 = Decision(
        id=f"decision_{fixed_ulid_values[2]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=_TIMESTAMP,
        tags=["persistence", "memory-backend"],
        confidence=0.8,
        source="coder",
        body="# Option B\n\nDescription B.\n\n* Good, because reason B\n",
    )

    for rec in (d1, d2):
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    assert len(paths) == 1, (
        f"Expected 1 ADR but got {len(paths)}: {[p.name for p in paths]}"
    )


def test_different_driver_tags_same_topic_produce_single_adr(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """ORANGE regression: records sharing a topic but with different driver tags
    must still group together.  The shared tag 'topic-zeta' has frequency 2;
    the unique driver tags each have frequency 1."""
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    stage_id = f"stage_{fixed_ulid_values[0]}"
    d1 = Decision(
        id=f"decision_{fixed_ulid_values[1]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=_TIMESTAMP,
        tags=["alpha-driver", "topic-zeta"],
        confidence=0.9,
        source="coder",
        body="# Option A\n\nDescription A.\n\n* Good, because reason A\n",
    )
    d2 = Decision(
        id=f"decision_{fixed_ulid_values[2]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=_TIMESTAMP,
        tags=["beta-driver", "topic-zeta"],
        confidence=0.8,
        source="coder",
        body="# Option B\n\nDescription B.\n\n* Good, because reason B\n",
    )

    for rec in (d1, d2):
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    assert len(paths) == 1, (
        f"Expected 1 ADR but got {len(paths)}: {[p.name for p in paths]}"
    )
    assert "topic-zeta" in paths[0].name


def test_rejected_only_topic_does_not_crash(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    """RED regression: a topic with only RejectedAlternatives and no Decision
    must be silently skipped, not crash on max() of an empty sequence."""
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"

    stage_id = f"stage_{fixed_ulid_values[0]}"

    decision = Decision(
        id=f"decision_{fixed_ulid_values[1]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=_TIMESTAMP,
        tags=["topic-alpha"],
        confidence=0.9,
        source="coder",
        body="# Chosen A\n\nRationale.\n\n* Good, because reason\n",
    )
    orphan_rejected = RejectedAlternative(
        id=f"rejected_alternative_{fixed_ulid_values[2]}",
        run_id=fixed_run_id,
        stage_id=stage_id,
        timestamp=_TIMESTAMP,
        tags=["topic-beta"],
        confidence=0.5,
        source="coder",
        body="# Orphan B\n\nWas rejected.\n\n* Bad, because reason\n",
    )

    for rec in (decision, orphan_rejected):
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    assert len(paths) == 1
    assert "topic-alpha" in paths[0].name


def test_slugify_non_latin_produces_stable_hash() -> None:
    """YELLOW regression: non-Latin titles produce a deterministic hash slug."""
    slug_tokyo = slugify("東京")
    assert slug_tokyo.startswith("adr-")
    assert len(slug_tokyo) == 12  # "adr-" + 8 hex chars
    assert slugify("東京") == slug_tokyo

    slug_arabic = slugify("العربية")
    assert slug_arabic.startswith("adr-")
    assert slug_arabic != slug_tokyo


def test_synthesize_appends_after_existing_adrs(
    tmp_path: Path,
    fixed_run_id: str,
    fixed_ulid_values: list[str],
) -> None:
    memory_root = tmp_path / ".spanweave" / "memory"
    adr_output = tmp_path / "docs" / "adr"
    adr_output.mkdir(parents=True)
    (adr_output / "0011-existing.md").write_text("# Existing\n", encoding="utf-8")

    decisions, rejected = _make_fixture_records(fixed_run_id, fixed_ulid_values)
    for rec in [*decisions, *rejected]:
        write_record(rec, memory_root)

    paths = synthesize_adr(
        fixed_run_id,
        memory_root=memory_root,
        adr_output_dir=adr_output,
    )

    assert len(paths) == 1
    assert paths[0].name == "0012-memory-backend.md"
