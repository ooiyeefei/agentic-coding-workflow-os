---
status: "accepted"
date: 2026-04-20
decision-makers: coder, reviewer
---

# Memory Backend

## Context and Problem Statement

The memory system uses the local filesystem as its primary storage backend, writing typed records as individual markdown files under `.spanweave/memory/`.

## Decision Drivers

* persistence
* safety-critical

## Considered Options

* Use filesystem-first storage
* Encode metadata as YAML frontmatter
* Redact secrets at write-time
* Use SQLite for record storage
* Use Redis for ephemeral caching

## Decision Outcome

Chosen option: "Use filesystem-first storage", because the memory system uses the local filesystem as its primary storage backend, writing typed records as individual markdown files under `.spanweave/memory/`.

### Consequences
* Good, because records are human-readable and reviewable with standard tools
* Good, because git tracks changes with full history and diff support
* Bad, because no built-in indexing for large record sets
* Good, because enables programmatic filtering without parsing prose
* Good, because prevents accidental secret leakage in git history
* Bad, because redaction is irreversible once written

## Pros and Cons of the Options

### Use filesystem-first storage

The memory system uses the local filesystem as its primary storage backend, writing typed records as individual markdown files under `.spanweave/memory/`.

* Good, because records are human-readable and reviewable with standard tools
* Good, because git tracks changes with full history and diff support
* Bad, because no built-in indexing for large record sets

### Encode metadata as YAML frontmatter

Every memory record carries structured YAML frontmatter for type, ID, timestamps, and tags, followed by a freeform markdown body.

* Good, because enables programmatic filtering without parsing prose
* Neutral, because requires a YAML parsing dependency

### Redact secrets at write-time

All records pass through the security redaction pipeline before reaching the filesystem, replacing detected secrets with `[REDACTED:<type>]` markers.

* Good, because prevents accidental secret leakage in git history
* Bad, because redaction is irreversible once written

### Use SQLite for record storage

SQLite would provide indexed queries and ACID transactions for the memory store.

* Good, because enables fast indexed queries across all record fields
* Bad, because records become opaque binary data inaccessible to standard text tools
* Bad, because complicates git-based workflows since the database file is not diffable

### Use Redis for ephemeral caching

Redis would serve as a low-latency cache layer in front of the primary record store.

* Good, because offers sub-millisecond reads for frequently accessed records
* Bad, because introduces a runtime infrastructure dependency
* Bad, because data loss occurs if the instance restarts without persistence configured
