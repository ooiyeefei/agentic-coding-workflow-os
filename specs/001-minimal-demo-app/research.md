# Research: Minimal Demo App

## Decision: Use FastAPI instead of Next.js

- **Rationale**: FastAPI keeps the surface area smaller for a Phase 0 demo while still supporting both HTML pages and JSON endpoints from one process.
- **Alternatives considered**: Next.js would produce a richer UI but adds more files, more tooling, and more moving parts than this demo needs.

## Decision: Use server-rendered pages with light browser-side fetch calls

- **Rationale**: A login page and a notes page make the app easy to click through during a live demo without introducing a separate frontend build step.
- **Alternatives considered**: Pure API-only delivery would make UAT and the browser walkthrough less clear; a heavier frontend stack would add unnecessary complexity.

## Decision: Use an HTTP-only session cookie backed by in-memory session state

- **Rationale**: Session cookies are enough to demonstrate authentication and route protection, and avoiding JWT keeps the implementation easy to reason about.
- **Alternatives considered**: JWT-based auth is unnecessary for a single-process demo and would distract from the main workflow.

## Decision: Keep notes in in-memory storage keyed by signed-in user

- **Rationale**: Ephemeral state satisfies the demo while avoiding database setup or migrations.
- **Alternatives considered**: SQLite or file-backed storage would add persistence the feature does not require.

## Decision: Verify behavior with pytest and FastAPI TestClient

- **Rationale**: The stack gives fast local feedback and covers the exact login plus CRUD flow required by acceptance.
- **Alternatives considered**: Browser automation would be heavier than needed for this size of app.
