# Feedback for Nebius Token Factory + NVIDIA Nemotron (submission form draft)

**Do not submit without owner approval.** Paste into the Devpost feedback field when ready.  
Competition entry remains **BLOCKED** until public artifacts are complete (`SUBMISSION_READY.md`).

## What worked

- OpenAI-compatible Token Factory API made integration straightforward (`/v1/chat/completions` + model list).
- `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` followed structured JSON tool-call / conclude loops reliably enough for a bounded multi-step investigator (with `response_format` fallback when needed).
- Nano cost supported iterative tool selection inside a hard evaluation budget (matched live study spent **$0.011**; blind live arm C spent **$0.00345** on n=4).
- Model listing endpoint helped confirm Nemotron availability before investigation runs.
- Clear separation of live `real_api` vs deterministic planner/fallback kept honesty in demos.

## Friction

- Some Nemotron variants (e.g. Lightning in earlier experiments) spent tokens on chain-of-thought and returned unparseable investigation JSON; Nano was more reliable for schema-constrained agent loops.
- When `response_format=json_object` is rejected (400/422), a silent fallback without format is required — documenting which models support JSON mode would help hackathon builders.
- Pricing for cost estimation is easy to mis-cite across model SKUs; a stable per-model price endpoint would improve honest cost reporting.
- Blind live mean latency ~17 s per investigation — fine for advisory SOC workflows, not real-time control; builders need latency guidance for agent loops.
- Placeholder / incomplete conclude JSON still requires schema repair + fail-closed paths.

## Suggestion

Ship a short “agent loop” cookbook: tool_call JSON → tool result → conclude, with recommended max_tokens for Nano vs Super/Ultra, explicit JSON-mode support matrix, and guidance that reasoning-heavy models need larger budgets or a JSON repair turn.
