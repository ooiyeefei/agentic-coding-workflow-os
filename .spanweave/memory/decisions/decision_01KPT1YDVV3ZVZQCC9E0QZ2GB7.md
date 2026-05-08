---
id: decision_01KPT1YDVV3ZVZQCC9E0QZ2GB7
type: Decision
version: 1
run_id: run_01KPT1YDEK0F9MYKW4R1VMY7XY
stage_id: stage_01KPT1YDVV3ZVZQCC9E0QZ2GB6
timestamp: '2026-04-22T07:37:17.947668Z'
related_issues: []
related_adrs: []
tags:
- workflow-validation
- rebase-analyze
confidence: 0.9
source: integration-harness
---
# Persist workflow evidence for 007-rebase-analyze

The 007-rebase-analyze stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
