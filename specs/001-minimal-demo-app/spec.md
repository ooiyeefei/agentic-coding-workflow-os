# Feature Specification: Minimal Demo App

**Feature Branch**: `feat/W22-demo-app`  
**Created**: 2026-04-19  
**Status**: Draft  
**Input**: User description: "minimal demo app with one auth flow and one protected CRUD endpoint"

## Clarifications

### Session 2026-04-19

- Q: What form should the demo take? → A: A single-service web app with a browser login page and a protected notes feature.
- Q: How should authentication work? → A: Email/password login creates a session cookie; token-based auth is out of scope.
- Q: How should demo state persist? → A: Sessions and notes live only in process memory and reset on restart.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign In To The Demo (Priority: P1)

As a demo operator, I can sign in with the provided test account so I can access the protected feature during a live walkthrough.

**Why this priority**: Without a working login flow, the protected API and the rest of the demo cannot be exercised.

**Independent Test**: Open the login page, submit the demo credentials, and confirm the app establishes a signed-in session and lands on the notes experience.

**Acceptance Scenarios**:

1. **Given** I am not authenticated, **When** I open the login page, **Then** I can see a form that asks for email and password.
2. **Given** I submit the correct demo credentials, **When** the login completes, **Then** I receive a session cookie and reach the authenticated notes experience.
3. **Given** I submit incorrect credentials, **When** the login attempt is processed, **Then** I remain unauthenticated and see a clear failure message.

---

### User Story 2 - Manage Notes Through A Protected API (Priority: P2)

As an authenticated user, I can list, create, and delete notes through a protected API so the demo includes a real feature with a small but complete CRUD loop.

**Why this priority**: The protected CRUD endpoint is the core feature that the future Coder and Reviewer demo loop will extend and critique.

**Independent Test**: Authenticate once, call the notes API to list notes, create a note, and delete that note while unauthenticated requests continue to fail.

**Acceptance Scenarios**:

1. **Given** I am not authenticated, **When** I request the notes API, **Then** the request is rejected with an unauthorized response.
2. **Given** I am authenticated, **When** I request my notes, **Then** I receive the current list of notes tied to my active session user.
3. **Given** I am authenticated, **When** I create a note with valid text, **Then** the API stores it and returns the created note.
4. **Given** I am authenticated, **When** I delete an existing note, **Then** the note is removed and no longer appears in later list responses.

---

### User Story 3 - Walk Through The Feature In A Browser (Priority: P3)

As a demo operator, I can use a minimal notes page in the browser so the workflow can be verified end-to-end without extra tooling.

**Why this priority**: A visible browser flow makes the dogfood demo easier to follow than API calls alone while keeping the surface area small.

**Independent Test**: Sign in through the browser, add a note from the page, observe it appear immediately, delete it from the page, and confirm the list updates.

**Acceptance Scenarios**:

1. **Given** I am signed in, **When** I open the notes page, **Then** I can see my notes and controls to add and delete them.
2. **Given** I add or delete a note from the page, **When** the request completes, **Then** the page updates to reflect the latest server state without manual reloading.

### Edge Cases

- Incorrect credentials must not create a session.
- Requests to protected note endpoints without a valid session cookie must return `401 Unauthorized`.
- Empty note text must be rejected without creating a note.
- Deleting an unknown note identifier must return a not-found error instead of silently succeeding.
- Restarting the app clears all sessions and notes because persistence is explicitly out of scope for this demo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a browser-accessible login page that accepts email and password.
- **FR-002**: The system MUST authenticate a single demo account using configured test credentials.
- **FR-003**: The system MUST establish an authenticated session using a cookie after successful login.
- **FR-004**: The system MUST provide a protected notes API that supports listing notes for the signed-in user.
- **FR-005**: The system MUST allow the signed-in user to create a note through the protected API.
- **FR-006**: The system MUST allow the signed-in user to delete an existing note through the protected API.
- **FR-007**: The system MUST reject unauthenticated access to the protected notes API with `401 Unauthorized`.
- **FR-008**: The system MUST keep demo sessions and notes in ephemeral application memory for the duration of a process run.
- **FR-009**: The system MUST include an automated test suite with at least four tests covering login and the protected CRUD happy path.
- **FR-010**: The system MUST include local run instructions and the demo credentials in a short README inside `demo/app/`.
- **FR-011**: The system MUST provide `.env.example` values for `TEST_USER` and `TEST_PASSWORD` so UAT can reuse the same credentials.

### Key Entities *(include if feature involves data)*

- **Demo Account**: The single allowed sign-in identity represented by an email and password pair used for local testing and UAT.
- **Session**: A server-side record that links a session identifier in a cookie to the signed-in demo account.
- **Note**: A user-owned item with a unique identifier and text content that can be listed, created, and deleted during a single app run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can start the app locally and reach the login page in under five minutes using the README steps.
- **SC-002**: Unauthenticated requests to the protected notes API are rejected with `401 Unauthorized` every time during automated tests.
- **SC-003**: After a successful sign-in, the demo user can complete a list-create-delete notes flow in one browser session without manual data setup.
- **SC-004**: The automated test suite passes locally and covers the full happy path from authentication through note deletion.

## Assumptions

- The demo only needs one hardcoded test account for Phase 0.
- Data durability across restarts is not required.
- Password reset, registration, and multi-user support are out of scope.
- The app only needs to run locally for demos and UAT, not in a production deployment.
