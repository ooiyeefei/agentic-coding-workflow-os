from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from atelier.llm import Message
from atelier.personas.base import AgentResponse, Persona
from atelier.personas.uat_runner import UATRequest, run_uat
from atelier.security import redact

UATRunner = Callable[..., Any]


class UAT(Persona):
    prompt_filename = "uat.md"

    def __init__(self, *, runner: UATRunner = run_uat, **kwargs: Any) -> None:
        self._runner = runner
        super().__init__(**kwargs)

    def build_user_message(self, context_packet: Any) -> str:
        request = self._coerce_request(context_packet)
        payload = self._redact_payload(
            request.model_dump(mode="json"),
            secrets=[request.test_user or "", request.test_password or ""],
        )
        rendered_packet = redact(
            self.render_context_packet(payload),
            secrets=[request.test_user or "", request.test_password or ""],
        )
        return (
            "UAT context packet:\n"
            f"{rendered_packet}\n\n"
            "Generate a concise UAT plan or checklist for this app. "
            "Do not claim execution results; "
            "the actual UAT run happens through an external subprocess."
        )

    async def respond(self, context_packet: Any) -> AgentResponse:
        request = self._coerce_request(context_packet)
        llm_response = await self.adapter.generate(
            messages=[
                self._system_message(),
                self._user_message(context_packet),
            ],
            required_capabilities=self.required_capabilities,
        )
        evidence_pack = self._runner(request, test_plan=llm_response.content)
        metadata = {
            "evidence_pack": evidence_pack.model_dump(mode="json"),
            "app_path": request.app_path,
        }
        response = self._build_agent_response(llm_response, metadata=metadata)
        response.content = "\n\n".join(
            part for part in (llm_response.content.strip(), evidence_pack.summary.strip()) if part
        )
        return response

    def _coerce_request(self, context_packet: Any) -> UATRequest:
        if isinstance(context_packet, UATRequest):
            return context_packet
        if isinstance(context_packet, BaseModel):
            return UATRequest.model_validate(context_packet.model_dump(mode="json"))
        if isinstance(context_packet, dict):
            return UATRequest.model_validate(context_packet)
        if isinstance(context_packet, str):
            return UATRequest(app_path=context_packet)
        return UATRequest(app_path=str(context_packet))

    def _redact_payload(self, value: Any, *, secrets: list[str]) -> Any:
        if isinstance(value, dict):
            return {
                key: self._redact_payload(item, secrets=secrets)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact_payload(item, secrets=secrets) for item in value]
        if isinstance(value, str):
            return redact(value, secrets=secrets)
        return value

    def _system_message(self) -> Any:
        return Message(role="system", content=self.system_prompt)

    def _user_message(self, context_packet: Any) -> Any:
        return Message(role="user", content=self.build_user_message(context_packet))
