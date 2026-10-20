# Release candidate manifest — JunctionTrace

**Status authority:** [`SUBMISSION_READY.md`](SUBMISSION_READY.md)  
**Branch:** `hackathon/nebius-nvidia`  
**Application tree:** `47dc614d52ab89f37518821006d07bfb85bcd71e` — already committed and pushed. This file is **not** a pre-commit staging list.

**CI on `47dc614`:** https://github.com/thtcsec/sdn-its-nebius-hackathon/actions/runs/39440953197 — **78 passed**, credential-free. **CI did not run live Nemotron.**

Local light pytest (this packaging pass): **78 passed**. Docker smoke is re-run locally; local Docker ≠ public host.

## Product freeze

`api/`, `dashboard/`, `src/` match the application SHA. Do not change planner/inference in this pass.

Unrelated dirty file if present: `artifacts/hackathon/benchmark_offline.json` (timestamp/latency rerun). **Leave unstaged.**

## Do not add

- `artifacts/hackathon/benchmark_offline.json`
- `artifacts/demo_video/*.mp4` / `*.wav` / `real_app_raw_*` / `real_app_qa/`
- `deploy/judge/.env` / `.env.smoke` / `.tmp_judge_token.txt`
- Any `.env`, keys, or paid-host URLs

Canonical video remains **local / gitignored**: `junctiontrace_REAL_APP_DEMO.mp4` (75.567 s).

## Verdicts

| Gate | Verdict |
|------|---------|
| Engineering / host package | **GO** |
| Competition submission | **BLOCKED** until public repo, hosted demo URL, YouTube, Devpost |
