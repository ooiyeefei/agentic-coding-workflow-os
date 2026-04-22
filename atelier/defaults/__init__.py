from __future__ import annotations

from pathlib import Path

DEFAULTS_DIR = Path(__file__).resolve().parent
DEFAULT_MODELS_DIR = DEFAULTS_DIR / "models"
DEFAULT_PERSONAS_DIR = DEFAULTS_DIR / "personas"
DEFAULT_SKILLS_DIR = DEFAULTS_DIR / "skills"
DEFAULT_WORKFLOWS_DIR = DEFAULTS_DIR / "workflows"

__all__ = [
    "DEFAULTS_DIR",
    "DEFAULT_MODELS_DIR",
    "DEFAULT_PERSONAS_DIR",
    "DEFAULT_SKILLS_DIR",
    "DEFAULT_WORKFLOWS_DIR",
]
