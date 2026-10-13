# Feedback for Nebius Token Factory + NVIDIA Nemotron (submission form draft)

**Do not submit without owner approval.** Paste into the Devpost feedback field when ready.

## What worked

- OpenAI-compatible Token Factory API made integration straightforward (`/v1/chat/completions` + model list).
- `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` followed structured JSON tool-call / conclude loops reliably enough for a bounded multi-step investigator (with `response_format` fallback when needed).
- Low latency/cost for Nano supported iterative tool selection within a hard $0.10 evaluation budget (matched proof spent ~$0.006).
- Model listing endpoint helped confirm Nemotron availability before investigation runs.

## Friction

- Some Nemotron variants (e.g. Lightning in earlier experiments) spent tokens on chain-of-thought and returned unparseable investigation JSON; Nano was more reliable for schema-constrained agent loops.
- When `response_format=json_object` is rejected (400/422), a silent fallback without format is required — documenting which models support JSON mode would help hackathon builders.
- Pricing for cost estimation is easy to mis-cite across model SKUs; a stable per-model price endpoint would improve honest cost reporting.

## Suggestion

Ship a short “agent loop” cookbook: tool_call JSON → tool result → conclude, with recommended max_tokens for Nano vs Super/Ultra, and explicit guidance that reasoning-heavy models need larger budgets or a JSON repair turn.
