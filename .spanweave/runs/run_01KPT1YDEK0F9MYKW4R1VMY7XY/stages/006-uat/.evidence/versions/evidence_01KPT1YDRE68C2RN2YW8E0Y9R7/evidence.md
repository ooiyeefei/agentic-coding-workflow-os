# Evidence Pack

`Run:` `run_01KPT1YDEK0F9MYKW4R1VMY7XY`  
`Stage:` `006-uat`  
`Schema:` `1.0`

> Verdict: **APPROVED**
> Confidence: **100%**
> Reviewer Persona: `uat.integration`
> Timestamp: `2026-04-22T07:37:17.837853Z`

## Findings

### RED

_None._

### ORANGE

_None._

### YELLOW

_None._

## Execution

### Command 1

- Command: `mock-uat /home/fei/fei/code/hackathon/acw-w24/demo/app`
- Exit Code: `0`
- Linked Findings: _None_

#### Stdout

```text
1. Open /login.
2. Submit invalid credentials enough times to trigger the limiter.
3. Confirm the visible wait message and Retry-After guidance.
```

#### Stderr

_No stderr captured._

## Audit Chain

- [`01KPT1YDRD89RGTD01E0EXDKCT`](../../audit.jsonl#01KPT1YDRD89RGTD01E0EXDKCT)
