# Hackathon readiness audit

**Scope:** `D:\tu_projects\sdn-its-nebius-hackathon` only  
**Upstream research tree:** not modified  
**Last updated:** 2026-10-12 (judge-ready agent + offline benchmark)

---

## Implementation update (2026-10-12 evening) — judge agent + benchmark

### Current commit / branch

| Field | Value |
|-------|--------|
| Branch | `hackathon/nebius-nvidia` |
| Baseline verified before this pass | `29a2b97` |
| Branch tip after this pass | run `git rev-parse HEAD` |

### Newly added (this pass)

| Path | Role |
|------|------|
| `datasets/hackathon/incidents/*.json` | 7 public synthetic cyber–physical fixtures |
| `src/sdn_its/llm/agent.py` | Rule ⊕ Nemotron investigation agent |
| `src/sdn_its/llm/fixtures.py` / `audit_log.py` | Fixture load + audit history |
| `scripts/run_hackathon_benchmark.py` | Offline/real benchmark harness |
| `scripts/run_judge_demo.py` | Judge acceptance runner |
| `tests/test_hackathon_agent.py` | Integration/regression tests |
| `api/routes.py` | `/hackathon/incidents|run|audit` |
| `dashboard/templates/index.html` | Investigation board UI |
| `docs/JUDGE_DEMO.md` | Judge reproducibility |
| `docs/HACKATHON_CONTRIBUTIONS.md` | Research vs hackathon split |
| `docs/DEMO_VIDEO.md` | &lt;3 min script (not uploaded yet) |
| `artifacts/hackathon/benchmark_offline.json` | Tracked offline benchmark results |

### Tests

```text
62 passed, 6 warnings
```

Commands: `pytest -q` (full) · light venv also ran `run_judge_demo.py` exit 0.

### Offline benchmark (actual)

From `artifacts/hackathon/benchmark_offline.json`:

| Metric | Value |
|--------|-------|
| n_incidents | 7 |
| decision_agreement_rate | **0.571** |
| inappropriate_containment_rate | **0.0** |
| gate_fired_rate | 0.143 |
| abstention_or_fail_closed_rate | 0.429 |
| total_estimated_cost_usd | 0.0 (offline) |

**Honesty:** Agreement is **not** an accuracy win claim. Offline Nemotron path uses labeled `synthetic_offline` / `synthetic_malformed` outputs. Fail-closed cases (malformed + unavailable API) correctly reduce agreement.

### Real Nebius (re-verified this pass)

`scripts/verify_nebius_nemotron.py` → `evidence_class: real_api`, model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, HTTP 200.

### Demo readiness

| Acceptance | Status |
|------------|--------|
| Real Nemotron in documented runtime | **Pass** (verify + `.env`) |
| ≥4 scenarios E2E | **Pass** (7 fixtures; judge demo) |
| Reproducible honest benchmark | **Pass** (offline JSON tracked) |
| Judge without private RTSP/checkpoint | **Pass** (synthetic fixtures; light venv) |
| Unsafe rec cannot bypass gate | **Pass** (fixture 07 + tests) |
| Public repo + YouTube &lt;3 min | **Blocked** (still private; video not uploaded) |

### Remaining blockers

1. Repo still **private** — publish when competition rules require.
2. Demo video not recorded/uploaded (`docs/DEMO_VIDEO.md` script only).
3. Full `pip install -e ".[dev]"` clean venv (with torch) not timed in CI this pass — light path verified.
4. No claim that Nemotron improves over rules (agreement 57% offline).

### Reproduction

See [docs/JUDGE_DEMO.md](docs/JUDGE_DEMO.md).

```powershell
python scripts/run_judge_demo.py
python scripts/run_hackathon_benchmark.py --mode offline --allow-containment-in-demo
python scripts/verify_nebius_nemotron.py   # needs .env
pytest -q
```

### Next three actions

1. Record/upload &lt;3 min YouTube demo from `docs/DEMO_VIDEO.md`.
2. Confirm hackathon public-release checklist; flip repo visibility when allowed.
3. Optional: run `--mode real` benchmark subset and attach redacted cost table.

---

## Prior update (2026-10-12) — `.env` + real_api vertical slice

Preserved: commit `29a2b97` established repo-root dotenv loading, Nano model default, real Token Factory smoke + Flask investigate, 55 tests at that time.

### Audit hygiene

- Research tree untouched.
- No credentials committed/printed.
- Offline vs `real_api` evidence classes kept distinct.
