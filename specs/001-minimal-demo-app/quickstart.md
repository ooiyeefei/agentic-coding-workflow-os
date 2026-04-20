# Quickstart: Minimal Demo App

1. `cd demo/app`
2. `cp .env.example .env`
3. `uv sync`
4. `uv run uvicorn app.main:app --reload --port 8000 --env-file .env`
5. Open `http://127.0.0.1:8000/login`
6. Sign in with the values from `.env.example`
7. Add and delete notes from the notes page
8. Run tests with `uv run pytest`
