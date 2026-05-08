from __future__ import annotations

from typing import Any

from spanweave.llm.adapter import JsonValue
from spanweave.personas.base import AgentResponse, Persona


class Reviewer(Persona):
    prompt_filename = "reviewer.md"

    def __init__(self, *, devil_advocate_mode: bool = False, **kwargs: Any) -> None:
        self.devil_advocate_mode = devil_advocate_mode
        super().__init__(**kwargs)

    def render_system_prompt(self) -> str:
        if not self.devil_advocate_mode:
            return super().render_system_prompt()

        return (
            f"{super().render_system_prompt()}\n\n"
            "## Reasons To Reject\n"
            "Even when your final verdict is APPROVE, include a `Reasons to Reject` section "
            "that makes the strongest concrete case against shipping the change. Keep the "
            "section evidence-based and tie every rejection reason to an observed risk, a "
            "missing check, or an unresolved edge case."
        )

    def build_user_message(self, context_packet: Any) -> str:
        rendered_packet = self.render_context_packet(context_packet)
        return f"Review context packet:\n{rendered_packet}"

    def response_metadata(self, context_packet: Any) -> dict[str, JsonValue]:
        return {"devil_advocate_mode": self.devil_advocate_mode}

    async def review(self, context_packet: Any) -> AgentResponse:
        return await self.respond(context_packet)
