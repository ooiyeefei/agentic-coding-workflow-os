from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .store import InMemoryStore

TEMPLATES_DIR = Path(__file__).parent / "templates"


class NoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=280)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Note text is required.")
        return normalized


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Spanweave Demo App")
    app.state.settings = settings or Settings.from_env()
    app.state.store = InMemoryStore()
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    def current_user(request: Request) -> str | None:
        cookie_name = request.app.state.settings.session_cookie_name
        session_id = request.cookies.get(cookie_name)
        return request.app.state.store.get_user(session_id)

    def require_user(request: Request) -> str:
        user = current_user(request)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )
        return user

    def render_login(
        request: Request,
        error: str | None = None,
        status_code: int = status.HTTP_200_OK,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": error,
                "demo_user": request.app.state.settings.test_user,
            },
            status_code=status_code,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def home(request: Request) -> Response:
        destination = "/notes" if current_user(request) else "/login"
        return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login_page(request: Request) -> Response:
        if current_user(request):
            return RedirectResponse("/notes", status_code=status.HTTP_303_SEE_OTHER)
        return render_login(request)

    @app.post("/login", include_in_schema=False)
    async def login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
    ) -> Response:
        settings = request.app.state.settings
        if email != settings.test_user or password != settings.test_password:
            return render_login(
                request,
                error="Invalid email or password.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        session_id = request.app.state.store.create_session(email)
        response = RedirectResponse("/notes", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            settings.session_cookie_name,
            session_id,
            httponly=True,
            samesite="lax",
            max_age=3600,
        )
        return response

    @app.post("/logout", include_in_schema=False)
    async def logout(request: Request) -> Response:
        settings = request.app.state.settings
        session_id = request.cookies.get(settings.session_cookie_name)
        request.app.state.store.clear_session(session_id)
        response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(settings.session_cookie_name)
        return response

    @app.get("/notes", response_class=HTMLResponse, include_in_schema=False)
    async def notes_page(request: Request) -> Response:
        user = current_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        return templates.TemplateResponse(
            request,
            "notes.html",
            {"user": user},
        )

    @app.get("/api/notes")
    async def list_notes(request: Request) -> list[dict[str, str]]:
        user = require_user(request)
        return request.app.state.store.list_notes(user)

    @app.post("/api/notes", status_code=status.HTTP_201_CREATED)
    async def create_note(
        payload: NoteCreate,
        request: Request,
    ) -> dict[str, str]:
        user = require_user(request)
        return request.app.state.store.create_note(user, payload.text)

    @app.delete("/api/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_note(note_id: str, request: Request) -> Response:
        user = require_user(request)
        deleted = request.app.state.store.delete_note(user, note_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found.",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


app = create_app()
