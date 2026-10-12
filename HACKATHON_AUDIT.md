# Hackathon readiness audit

**Scope:** `D:\tu_projects\sdn-its-nebius-hackathon` only  
**Upstream research tree:** not modified  
**Last updated:** 2026-10-12 (`.env` loader + real Nemotron vertical slice)

---

## Implementation update (2026-10-12) — real_api vertical slice verified

### Current commit and branch

| Field | Value |
|-------|--------|
| Branch | `hackathon/nebius-nvidia` |
| Branch tip | run `git rev-parse HEAD` |
| Feature focus | Repo-root `.env` loading + authenticated Nemotron Nano slice |
| Remote | `origin` → private `thtcsec/sdn-its-nebius-hackathon` |

### Exact newly implemented / updated files (this pass)

| Path | Role |
|------|------|
| `src/sdn_its/utils/env.py` | Central `python-dotenv` loader from `PROJECT_ROOT/.env` |
| `src/sdn_its/utils/__init__.py` | Export `ensure_repo_env` / `load_repo_env` |
| `src/sdn_its/llm/nebius_client.py` | Env-aware client, error classes, reasoning fallback |
| `src/sdn_its/llm/schema.py` | Brace-balanced JSON extraction after CoT |
| `src/sdn_its/llm/investigation.py` | Repair + Nano fallback; uses `ensure_repo_env` |
| `api/app.py` | `ensure_repo_env()` in `create_app` |
| `scripts/verify_nebius_nemotron.py` | Loads repo `.env`; redacted evidence |
| `scripts/run_nemotron_vertical_slice.py` | Same |
| `configs/nebius.yaml` / `.env.example` | Default model → Nano |
| `pyproject.toml` / `requirements.txt` | `python-dotenv>=1.0.0` |
| `tests/test_nebius_llm.py` | Env-root + classification tests |
| `artifacts/hackathon/real_api_evidence_redacted.json` | Commit-safe real_api evidence |

`.env` remains **gitignored and untracked** (key never committed/printed).

### Tests executed and results

```powershell
cd D:\tu_projects\sdn-its-nebius-hackathon
$env:CUDA_VISIBLE_DEVICES=""
$env:PYTHONPATH="$PWD\src;$PWD"
# Use a venv with deps (torch + python-dotenv)
pytest -q --tb=line
```

**Actual result:** `55 passed, 6 warnings` (exit 0).

### Verified external API calls (real, not mocked)

| Call | Evidence | Result |
|------|----------|--------|
| `GET /v1/models` (auth via `.env`) | `real_api` | HTTP 200; 25 models; Nano listed |
| `POST /v1/chat/completions` smoke | `real_api` | HTTP 200; model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| Vertical slice investigation | `real_api` | Validated JSON → safety gate → `OBSERVE_ONLY` (demo) |
| `POST /api/v1/hackathon/investigate` | `real_api` | HTTP 200; same model; policy observe |

**cwd independence:** verify script succeeded with `cwd=C:\Users\...\Temp` while loading `D:\tu_projects\sdn-its-nebius-hackathon\.env`.

**Model note:** `nvidia/Nemotron-3_5-Lightning` is listed but often emits CoT without JSON for investigation. Default investigation model is **`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`** (confirmed in authenticated catalog).

### Estimated cost incurred (this session, rough list prices)

| Source | USD (approx) |
|--------|----------------|
| Sum from last verify + slice + flask artifacts | **~$0.00047** |
| Earlier failed Lightning/schema attempts (extra tokens) | small additional (~$0.0005) |
| **Session total (order of magnitude)** | **≪ $0.01** |

### Remaining blockers

1. Classifier checkpoint still missing → console `DEGRADED` for TCN-GRU (orthogonal to LLM slice).
2. No LLM-vs-rule benchmark table yet.
3. Repo still private; no &lt;3 min YouTube demo.
4. Live camera RTSP still needs local inventory (not required for this LLM slice).
5. Fresh judge venv install (`pip install -e ".[dev]"`) not re-validated on a brand-new venv this pass (used sibling research venv + `PYTHONPATH`).

### Reproduction commands

```powershell
cd D:\tu_projects\sdn-its-nebius-hackathon
# Ensure repo-root .env exists (gitignored):
#   NEBIUS_API_KEY=...
#   NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1
#   NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B

pip install -e ".[dev]"   # includes python-dotenv
pytest -q

# Real Nebius (loads .env even if cwd differs)
python scripts/verify_nebius_nemotron.py
python scripts/run_nemotron_vertical_slice.py

# Flask path
python -c "from api.app import create_app; c=create_app().test_client(); print(c.post('/api/v1/hackathon/investigate', json={'network_prediction':'LOFT_LowRate_Attack','telemetry':{},'camera':{'physical_label':'stable'},'rule_fusion':{'recommended_action':'rate_limit'},'demo_mode':True,'apply_policy':True}).status_code)"
```

### Next three actions

1. Add rule-baseline vs Nemotron-gated comparison script with honest metrics.
2. Judge runbook: fresh venv + optional small checkpoint policy for console.
3. Record &lt;3 min demo once slice is scripted end-to-end on a clean machine.

### Submission readiness

**Not fully submission-ready**, but the **mandatory Nebius Nemotron vertical slice now has real_api execution evidence** (smoke + investigation + Flask). Remaining work is benchmark, packaging, and demo — not credential wiring.

Evidence labels:

| Class | Meaning |
|-------|---------|
| `real_api` | Authenticated Token Factory HTTP succeeded |
| `mocked_transport` | Unit-test injected session |
| `blocked_no_credentials` | Empty/missing key after env resolution |
| `validation_error` / `api_error` | Parse or provider failure (`error_class`: authentication / model_availability / billing / network / schema) |

---

## Prior updates (preserved)

### 2026-10-11 — vertical slice code landed; credentials blocked

See git history `e692329` and earlier audit sections in commit history. At that time `NEBIUS_API_KEY` was unset and only fail-closed behavior was proven.

### Audit hygiene

- Research repo not modified/pushed.
- No API keys printed or committed.
- No fabricated successful inference — `real_api` rows above are from live Token Factory responses.
