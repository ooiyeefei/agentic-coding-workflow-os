from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class CapabilityRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_use: bool | None = None
    parallel_tool_use: bool | None = None
    long_context: int | None = Field(default=None, ge=0)
    code_execution: bool | None = None
    structured_outputs: bool | None = None


class CapabilityOffers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_use: bool = False
    parallel_tool_use: bool = False
    long_context: int = Field(default=0, ge=0)
    code_execution: bool = False
    structured_outputs: bool = False

    def missing_capabilities(self, requirements: CapabilityRequirements) -> list[str]:
        missing: list[str] = []

        if requirements.tool_use and not self.tool_use:
            missing.append("tool_use")
        if requirements.parallel_tool_use and not self.parallel_tool_use:
            missing.append("parallel_tool_use")
        if requirements.code_execution and not self.code_execution:
            missing.append("code_execution")
        if requirements.structured_outputs and not self.structured_outputs:
            missing.append("structured_outputs")
        if requirements.long_context is not None and self.long_context < requirements.long_context:
            missing.append(f"long_context>={requirements.long_context}")

        return missing


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    offers: CapabilityOffers
    cost_per_mtok_in: float = Field(ge=0)
    cost_per_mtok_out: float = Field(ge=0)

    def supports(self, requirements: CapabilityRequirements | None = None) -> bool:
        return not self.missing_capabilities(requirements or CapabilityRequirements())

    def missing_capabilities(self, requirements: CapabilityRequirements) -> list[str]:
        return self.offers.missing_capabilities(requirements)


class UnsupportedCapabilityError(RuntimeError):
    def __init__(
        self,
        *,
        requirements: CapabilityRequirements,
        failures: dict[str, list[str]],
    ) -> None:
        self.requirements = requirements
        self.failures = failures

        rendered_requirements = _render_requirements(requirements)
        rendered_failures = "; ".join(
            f"{model}: missing {', '.join(missing)}" for model, missing in failures.items()
        )
        message = f"No model satisfies required capabilities ({rendered_requirements})"
        if rendered_failures:
            message = f"{message}. Evaluated {rendered_failures}."
        super().__init__(message)


def load_capability_manifest(path: str | Path) -> CapabilityManifest:
    manifest_path = Path(path)
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest {manifest_path} did not contain a YAML mapping")
    return CapabilityManifest.model_validate(payload)


def load_capability_manifests(directory: str | Path) -> list[CapabilityManifest]:
    manifest_dir = Path(directory)
    return [
        load_capability_manifest(path)
        for path in sorted(manifest_dir.glob("*.yaml"))
        if path.is_file()
    ]


def route_persona_to_model(
    persona_requires: CapabilityRequirements,
    available_models: Iterable[CapabilityManifest],
) -> CapabilityManifest:
    failures: dict[str, list[str]] = {}

    for manifest in available_models:
        missing = manifest.missing_capabilities(persona_requires)
        if not missing:
            return manifest
        failures[manifest.model] = missing

    raise UnsupportedCapabilityError(requirements=persona_requires, failures=failures)


def _render_requirements(requirements: CapabilityRequirements) -> str:
    parts: list[str] = []
    for field_name, value in requirements.model_dump(exclude_none=True).items():
        if field_name == "long_context":
            parts.append(f"{field_name}>={value}")
        else:
            parts.append(f"{field_name}={value}")
    return ", ".join(parts) if parts else "no explicit requirements"
