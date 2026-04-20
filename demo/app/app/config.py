from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    test_user: str
    test_password: str
    session_cookie_name: str = "atelier_demo_session"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            test_user=os.getenv("TEST_USER", "demo@atelier.dev"),
            test_password=os.getenv("TEST_PASSWORD", "demo1234"),
        )
