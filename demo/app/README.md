# Demo App
1. `cd demo/app && cp .env.example .env`
2. `uv sync`
3. `uv run uvicorn app.main:app --reload --port 8000 --env-file .env`
4. Open `http://127.0.0.1:8000/login`
5. Sign in with `demo@atelier.dev` / `demo1234` (or the values in `.env`)
6. Run tests with `uv run pytest`
