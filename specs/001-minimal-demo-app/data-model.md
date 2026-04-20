# Data Model: Minimal Demo App

## DemoAccount

- **Purpose**: Represents the one allowed user identity for local demo login.
- **Fields**:
  - `email`: unique login identifier
  - `password`: configured secret used only for credential comparison

## SessionRecord

- **Purpose**: Tracks the current authenticated browser session.
- **Fields**:
  - `session_id`: opaque unique identifier stored in a cookie
  - `user_email`: owner of the session
- **Lifecycle**:
  - Created after successful login
  - Read on protected requests
  - Removed on logout or process restart

## NoteRecord

- **Purpose**: Represents one note owned by the signed-in user.
- **Fields**:
  - `id`: opaque unique identifier
  - `text`: short note content
- **Lifecycle**:
  - Created from the notes page or API
  - Listed in the protected notes API
  - Deleted by note identifier

## Relationships

- One `DemoAccount` can own many `NoteRecord` items.
- One `DemoAccount` can have zero or more active `SessionRecord` items during the life of a process.
