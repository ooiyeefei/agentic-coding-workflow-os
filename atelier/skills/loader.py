from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

from atelier.skills.schema import Skill, SkillFrontmatter

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_DIR = REPO_ROOT / ".atelier" / "defaults" / "skills"
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(?P<meta>.*?)\r?\n---\r?\n", re.DOTALL)


class SkillNotFoundError(FileNotFoundError):
    def __init__(self, skill_name: str, skills_dir: Path) -> None:
        super().__init__(f"Skill '{skill_name}' was not found in {skills_dir}")
        self.skill_name = skill_name
        self.skills_dir = skills_dir


class SkillLoader:
    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = (skills_dir or DEFAULT_SKILLS_DIR).resolve()

    def get_skill(self, name: str) -> Skill:
        path = self.skills_dir / f"{name}.md"
        if not path.is_file():
            raise SkillNotFoundError(name, self.skills_dir)
        return self._load_from_path(path)

    def load_all(self) -> dict[str, Skill]:
        return {
            path.stem: self._load_from_path(path)
            for path in sorted(self.skills_dir.glob("*.md"))
            if path.is_file()
        }

    def _load_from_path(self, path: Path) -> Skill:
        raw_text = path.read_text(encoding="utf-8")
        metadata_text, content = self._split_frontmatter(raw_text, path)
        parsed_metadata = yaml.safe_load(metadata_text)
        if parsed_metadata is None:
            metadata: dict[str, object] = {}
        elif isinstance(parsed_metadata, dict):
            raw_metadata = cast(dict[object, object], parsed_metadata)
            metadata = {
                str(key): value
                for key, value in raw_metadata.items()
            }
        else:
            raise ValueError(f"{path} frontmatter must deserialize to a mapping")
        frontmatter = SkillFrontmatter.model_validate(metadata)
        return Skill(
            name=path.stem,
            path=str(path),
            content=content,
            **frontmatter.model_dump(),
        )

    def _split_frontmatter(self, text: str, path: Path) -> tuple[str, str]:
        match = _FRONTMATTER_RE.match(text)
        if match is None:
            raise ValueError(f"{path} is missing valid YAML frontmatter")
        return match.group("meta"), text[match.end() :]


def get_skill(name: str, skills_dir: Path | None = None) -> Skill:
    return SkillLoader(skills_dir=skills_dir).get_skill(name)
