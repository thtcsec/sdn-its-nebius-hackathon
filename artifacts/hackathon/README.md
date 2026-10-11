# Hackathon evidence (Nebius × NVIDIA)

Non-secret runtime evidence from verification scripts lands here:

| File | Produced by | Notes |
|------|-------------|--------|
| `nebius_verify_last.json` | `scripts/verify_nebius_nemotron.py` | `evidence_class: real_api` only when a live key works |
| `vertical_slice_last.json` | `scripts/run_nemotron_vertical_slice.py` | Includes synthetic context fixture + policy status |

Do not commit API keys. Prefer committing redacted successful `real_api` evidence after a verified run.
