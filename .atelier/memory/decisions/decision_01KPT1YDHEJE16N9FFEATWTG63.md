---
id: decision_01KPT1YDHEJE16N9FFEATWTG63
type: Decision
version: 1
run_id: run_01KPT1YDEK0F9MYKW4R1VMY7XY
stage_id: stage_01KPT1YDHEJE16N9FFEATWTG62
timestamp: '2026-04-22T07:37:17.614680Z'
related_issues: []
related_adrs: []
tags:
- workflow-validation
- specify
confidence: 0.9
source: integration-harness
---
# Persist workflow evidence for 001-specify

The 001-specify stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
