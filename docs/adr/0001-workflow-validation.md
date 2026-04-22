---
status: "accepted"
date: 2026-04-22
decision-makers: integration-harness
---

# Workflow Validation

## Context and Problem Statement

The 001-specify stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

## Decision Drivers

* artifact-minimization
* clarify
* cleanup
* implement
* plan
* rebase-analyze
* specify
* tasks
* uat

## Considered Options

* Persist workflow evidence for 001-specify
* Persist workflow evidence for 002-clarify
* Persist workflow evidence for 003-plan
* Persist workflow evidence for 004-tasks
* Persist workflow evidence for 005-implement
* Persist workflow evidence for 006-uat
* Persist workflow evidence for 007-rebase-analyze
* Persist workflow evidence for 008-cleanup
* Keep workflow validation in memory only

## Decision Outcome

Chosen option: "Persist workflow evidence for 001-specify", because the 001-specify stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

### Consequences
* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

## Pros and Cons of the Options

### Persist workflow evidence for 001-specify

The 001-specify stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

### Persist workflow evidence for 002-clarify

The 002-clarify stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

### Persist workflow evidence for 003-plan

The 003-plan stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

### Persist workflow evidence for 004-tasks

The 004-tasks stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

### Persist workflow evidence for 005-implement

The 005-implement stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

### Persist workflow evidence for 006-uat

The 006-uat stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

### Persist workflow evidence for 007-rebase-analyze

The 007-rebase-analyze stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

### Persist workflow evidence for 008-cleanup

The 008-cleanup stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts

### Keep workflow validation in memory only

A purely in-memory validation path would avoid writing packets, transcripts, and evidence artifacts to the filesystem.

* Good, because temporary test state stays smaller and faster to clean up
* Bad, because replay, inspection, and ADR synthesis lose their durable inputs
