# Quickstart: UAT Persona Integration

## Validate The Slice

1. Set the feature context when invoking Spec Kit scripts from the `acw-w18` branch:

```bash
export SPECIFY_FEATURE=008-uat-persona-integration
```

2. Run the focused tests:

```bash
pytest tests/test_uat.py -q
```

3. Example Python invocation with an explicit skill path override:

```python
import asyncio

from atelier.personas.uat import UAT


async def main() -> None:
    persona = UAT()
    result = await persona.respond(
        {
            "app_path": "demo/app",
            "skill_path": "/tmp/mock-uat-skill.sh",
            "test_user": "demo@atelier.dev",
            "test_password": "demo1234",
        }
    )
    print(result.metadata["evidence_pack"]["summary"])


asyncio.run(main())
```

4. When using the repo-local demo app without explicit credentials, make sure either `TEST_USER` and `TEST_PASSWORD` are exported or `../../.env.local` exists for the workspace where UAT runs.
