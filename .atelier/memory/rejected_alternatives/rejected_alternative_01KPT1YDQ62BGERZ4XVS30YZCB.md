---
id: rejected_alternative_01KPT1YDQ62BGERZ4XVS30YZCB
type: RejectedAlternative
version: 1
run_id: run_01KPT1YDEK0F9MYKW4R1VMY7XY
stage_id: stage_01KPT1YDQ2J2WF9T2Y8W0B1Z2W
timestamp: '2026-04-22T07:37:17.798549Z'
related_issues: []
related_adrs: []
tags:
- workflow-validation
- artifact-minimization
confidence: 0.6
source: integration-harness
---
# Keep workflow validation in memory only

A purely in-memory validation path would avoid writing packets, transcripts, and evidence artifacts to the filesystem.

* Good, because temporary test state stays smaller and faster to clean up
* Bad, because replay, inspection, and ADR synthesis lose their durable inputs
