# Security Best Practice & Architecture Brief
> **Audience:** Agents and humans actively developing Spanweave (`/home/fei/fei/code/hackathon/agentic-coding-workflow-os`).
> **Date:** 2026-05-07
> **Source:** Live Clash of Prompts tournament data, Symbiotic Security research report ("The Insecurity of AI-Generated Code"), and live event slide decks.

## 1. Project Context: Spanweave
Spanweave is the filesystem-first knowledge substrate for agentic coding workflows. Its goal is not to replace agent tools (like Claude Code or Cursor) but to capture durable context, decisions, policies, prompts, and run states in Git (`atelier/` directories). 

Because Spanweave operates as the "OS" layer managing agent behavior, it sits at the absolute center of the AI security crisis. Our goal for Phase 1 is to build a security harness that plugs into Spanweave's existing `atelier/policy/`, `atelier/compiler/`, and `atelier/defaults/` paths to secure both the code the agents write and the environment the agents run in.

## 2. The Empirical Reality of AI Code
The structural design of Spanweave's security harness must be grounded in the data shared by Symbiotic Security today:
* **The Vulnerability Baseline:** Roughly 50% of AI-generated code contains exploitable security vulnerabilities. 
* **The "Vibe Coding" Multiplier:** Fully autonomous "vibe-coded" sessions introduce ~9× more vulnerabilities per line than human-only code, and ~5× more than collaborative human-agent code. Agents naturally optimize for "it runs", not "it's safe," because they are trained on both good and vulnerable code across the internet.
* **Prompting Limits:** Security prompting reduces vulnerability rates by only 8.2 percentage points; it does not solve the problem on its own.
* **The Architecture Mandate:** Security analysis must be shifted *into the generation loop itself* because post-hoc reactive scanning cannot mathematically scale to meet the exponential growth of AI code.

## 3. Agentic Attack Mechanisms to Map
Agentic systems introduce new attack surfaces. Spanweave's `atelier/policy/` and `atelier/security/` modules must defend against the following specific vectors:

### A. Rules and Skills Supply Chain
* **The Threat:** Attackers place malicious instructions in `.cursorrules`, `.github/copilot-instructions.md`, `AGENTS.md`, or `.claude/skills/`. When cloned, the agent reads these as trusted configuration, allowing silent shell execution or typo-squatting (e.g., forcing the agent to use a malicious package like `djagno` instead of `django`).
* **Spanweave Defense:** Never blindly open a cloned repository with an agent without reviewing rules/skills files. The Context Compiler must scan local rule files before trusting them.

### B. Configuration Poisoning for Persistence
* **The Threat:** Prompt injection via GitHub issues or code comments tricks an agent into writing to its own config file (e.g., updating `.vscode/settings.json` with `{"chat.tools.autoApprove": true}`). 
* **Impact:** One successful attack disables defense for all future sessions.
* **Spanweave Defense:** Agents must *never* have routine write access to their own configuration directories. Ensure Spanweave policies require explicit human interaction to enable auto-approval modes.

### C. Tool Poisoning (MCP)
* **The Threat:** MCP (Model Context Protocol) connects agents to databases, APIs, and file systems. Attackers hide malicious instructions inside the *description* of an MCP tool, tricking the agent into fetching and exfiltrating `~/.aws/credentials` when the user simply asks to "Fetch my data".
* **Spanweave Defense:** Treat tool descriptions and schemas as untrusted metadata. Spanweave adapters should enforce strict data destination scoping.

### D. Hooks
* **The Threat/Asset:** Hooks are user-defined scripts (e.g., `.gemini/hooks/block-secrets.sh`) executed at predefined lifecycles. 
* **Spanweave Defense:** Spanweave can utilize middleware hooks to extract content, scan for secrets using `grep`, and return structured denial decisions (e.g., `{"decision": "deny"}`) to the agent before commits.

## 4. Prompt Engineering Meta-Strategy: The "Organic Spec"
Today’s tournament revealed a massive shift in how AI security judges (and models) evaluate prompts. **We must update the `atelier/defaults/personas/coder.md` immediately.**

1. **The Originality Penalty:** Highly templated prompts using robotic formatting (e.g., `CRITICAL OVERRIDE:`, `SECURITY NOTES:`) are flagged by AI judges/scanners as boilerplate and heavily penalized. 
2. **The "Organic Staff Engineer" Pattern:** Instead of generic checklists, prompts must read like a natural, fluid technical requirement document written by a senior engineer.
3. **Reframe, Don't Copy:** Do not paste the weak challenge statement back into the prompt; reframe it into a secure design.
4. **Concrete > Verbose:** Token efficiency rewards concise prompts; name the threats explicitly (SQLi, XSS, SSRF) because if you don't name them, the agent won't defend against them.
5. **Exact Primitives:** The prompt *must* contain the exact safe framework APIs. 
    * *Bad:* "Prevent SQL injection."
    * *Good:* "Prevent SQL injection by strictly using parameterized queries exactly like `where('device_id = ? AND status = ?', params[:device_id], params[:status])`."
    * *Bad:* "Validate the input."
    * *Good:* "Validate that `status` strictly matches this hardcoded array: `['ok', 'warn', 'critical', 'offline']`."

## 5. Phase 1 Execution Plan for Spanweave Agents

To the coding agents building Spanweave, execute the following implementation slice:

**1. Create the Security Best Practice Skill:**
* Path: `.atelier/defaults/skills/organic-security-spec.md`
* Instruction: Teach the Coder persona to formulate prompts organically. Instruct it to map trust boundaries, explicitly name threats upfront, use hardcoded allow-lists/enums instead of generic "validation", and demand safe defaults (auto-escaping templates, `shell=False`) at the boundary.

**2. Update Context Compiler for Rules Intake:**
* Path: `atelier/security/rules_intake.py`
* Instruction: Build a scanner that pre-flights local `.cursorrules`, `AGENTS.md`, and MCP descriptions. Flag any rules requesting `autoApprove`, shell execution, or credential access as high-risk policy violations.

**3. Implement Feedback Loops for Agent Fallback:**
* Path: `.atelier/defaults/feedback_rules/`
* Instruction: Create YAML rules to catch when an agent generates a prompt that relies on generic security checklists instead of exact framework APIs.

**Final Note to Agents:** Your objective is not to run a SAST tool *after* you write the code. Your objective is to compile the exact, context-aware, organic security constraints into the generation prompt *before* the code is written. Fail securely, fail closed, and rely on explicit evidence.