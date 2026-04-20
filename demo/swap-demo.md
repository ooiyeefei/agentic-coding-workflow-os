# W19 Swappability Demo

Atelier is not vendor-locked. This script runs the same Reviewer prompt, the same tool contract, and the same buggy Python fixture against two backends: Claude first, then Codex on OpenAI. Both Evidence Packs show the same failing pytest and both identify the same defect: an off-by-one loop bound in `rolling_window_average` that skips the last valid window.

The wording differs because the model differs, but the interface does not. Same review flow, same artifacts, different brains. Then the guardrail beat: I point the runner at a manifest without tool support, and it fails fast with `UnsupportedCapabilityError` instead of pretending the swap is safe. That is the moat: configurable models, one protocol, and an honest capability gate.
