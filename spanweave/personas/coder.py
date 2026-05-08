from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import frontmatter
from pydantic import BaseModel, ConfigDict

from spanweave.llm.adapter import JsonValue
from spanweave.personas.base import DEFAULT_SKILLS_DIR, Persona


class SkillReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str
    source: Literal["catalog", "fallback"]
    description: str


_FALLBACK_SKILLS: tuple[tuple[str, str], ...] = (
    ("/speckit.specify", "Create or update the feature specification."),
    ("/speckit.clarify", "Resolve the highest-impact ambiguities in the active spec."),
    ("/speckit.plan", "Produce the implementation plan and design artifacts."),
    ("/speckit.tasks", "Turn the plan into dependency-ordered implementation tasks."),
    ("/speckit.implement", "Execute the planned implementation tasks."),
)


class Coder(Persona):
    prompt_filename = "coder.md"

    def __init__(
        self,
        *,
        skills_directory: str | Path = DEFAULT_SKILLS_DIR,
        **kwargs: Any,
    ) -> None:
        self.skills_directory = Path(skills_directory)
        self.skills = self._load_skills()
        super().__init__(**kwargs)

    def build_user_message(self, context_packet: Any) -> str:
        rendered_packet = self.render_context_packet(context_packet)
        recommended_command = self.recommend_next_command(context_packet)
        skill_lines = "\n".join(
            f"- {skill.command}: {skill.description}" for skill in self.skills
        )
        return (
            f"Context packet:\n{rendered_packet}\n\n"
            f"Available workflow skills:\n{skill_lines}\n\n"
            f"Recommended next command: {recommended_command}\n"
            "State the next command explicitly before you explain the action."
        )

    def response_metadata(self, context_packet: Any) -> dict[str, JsonValue]:
        return {
            "recommended_command": self.recommend_next_command(context_packet),
            "skills": [skill.model_dump(mode="json") for skill in self.skills],
        }

    def recommend_next_command(self, context_packet: Any) -> str:
        available_commands = {skill.command for skill in self.skills}
        rendered_packet = self.render_context_packet(context_packet).lower()
        candidates = self._candidate_commands(rendered_packet)
        for command in candidates:
            if command in available_commands:
                return command
        return self.skills[0].command

    def _candidate_commands(self, rendered_packet: str) -> list[str]:
        if "tasks.md" in rendered_packet or "# tasks:" in rendered_packet:
            return ["/speckit.implement"]
        if "plan.md" in rendered_packet or "# implementation plan:" in rendered_packet:
            return ["/speckit.tasks"]
        if (
            "## clarifications" in rendered_packet
            or "[needs clarification]" in rendered_packet
            or "/speckit.clarify" in rendered_packet
        ):
            return ["/speckit.plan"]
        if "spec.md" in rendered_packet or "# feature specification:" in rendered_packet:
            return ["/speckit.clarify"]
        return ["/speckit.specify"]

    def _load_skills(self) -> list[SkillReference]:
        discovered: list[SkillReference] = []
        if self.skills_directory.is_dir():
            for path in sorted(self.skills_directory.glob("*.md")):
                post = frontmatter.load(str(path))
                command = self._resolve_skill_command(path, post.metadata)
                if command is None or not command.startswith("/speckit."):
                    continue
                description = self._resolve_skill_description(post)
                discovered.append(
                    SkillReference(
                        command=command,
                        source="catalog",
                        description=description,
                    )
                )

        if discovered:
            return discovered

        return [
            SkillReference(command=command, source="fallback", description=description)
            for command, description in _FALLBACK_SKILLS
        ]

    def _resolve_skill_command(
        self,
        path: Path,
        metadata: dict[str, Any],
    ) -> str | None:
        candidates = [
            metadata.get("command"),
            metadata.get("name"),
            path.stem,
        ]
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            normalized = candidate.strip()
            if normalized.startswith("/speckit."):
                return normalized
            if normalized.startswith("speckit."):
                return f"/{normalized}"
            if normalized.startswith("speckit-"):
                return f"/{normalized.replace('-', '.', 1)}"
        return None

    def _resolve_skill_description(self, post: frontmatter.Post) -> str:
        description = post.metadata.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()

        for line in post.content.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped

        return "No description provided."
