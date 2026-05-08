from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    test_user: str
    test_password: str
    session_cookie_name: str = "spanweave_demo_session"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            test_user=os.getenv("TEST_USER", "demo@spanweave.dev"),
            test_password=os.getenv("TEST_PASSWORD", "demo1234"),
        )
