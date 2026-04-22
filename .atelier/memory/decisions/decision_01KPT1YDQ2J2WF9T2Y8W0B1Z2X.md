---
id: decision_01KPT1YDQ2J2WF9T2Y8W0B1Z2X
type: Decision
version: 1
run_id: run_01KPT1YDEK0F9MYKW4R1VMY7XY
stage_id: stage_01KPT1YDQ2J2WF9T2Y8W0B1Z2W
timestamp: '2026-04-22T07:37:17.794597Z'
related_issues: []
related_adrs: []
tags:
- workflow-validation
- implement
confidence: 0.9
source: integration-harness
---
# Persist workflow evidence for 005-implement

The 005-implement stage stores packet, transcript, and evidence artifacts directly on disk for replay and inspection.

* Good, because integration tests can assert on durable filesystem outputs
* Bad, because each workflow run leaves behind more generated artifacts
