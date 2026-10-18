# Public-release checklist (do NOT flip visibility without approval)

Repository is currently **private**. Changing GitHub visibility requires explicit human approval.

## Automated scans (run before asking)

```bash
python scripts/scan_secrets_and_license.py
git ls-files .env deploy/judge/.env   # must be empty
git log -p --all -S 'NEBIUS_API' -- '*.env' '*.md' '*.json' | Select-Object -First 40
```

Record results in `artifacts/hackathon/secret_license_scan.json` and `artifacts/hackathon/public_release_scan.md`.

## Before requesting public

- [ ] Secret/license scan `ok: true` (working tree)
- [ ] Git history review for leaked keys (see scan report)
- [ ] `.env` / `deploy/judge/.env` not tracked
- [ ] No RTSP URLs / `1.cameras.json` / private camera inventories in git
- [ ] No required `*.pt` checkpoints for judge path
- [ ] Screenshots in `artifacts/hackathon/product_screens/` contain no tokens/keys
- [ ] `docs/HACKATHON_CONTRIBUTIONS.md` separates research vs hackathon
- [ ] `SUBMISSION_DEVPOST.md` reviewed
- [ ] Demo video recorded locally; YouTube URL only after approval
- [ ] Hosted judge URL only after approved deploy (`docs/JUDGE_HOSTING.md`)
- [ ] LICENSE (MIT) present
- [ ] README matches reality: mock OF, synthetic camera, no fabricated Nebius accuracy
- [ ] Competition rules re-checked the day of submit

## Assets that may be non-publishable

| Asset | Risk | Action |
|-------|------|--------|
| `.env` / API keys | Secret | Never commit; rotate if ever leaked |
| Live camera inventories / RTSP | Privacy / ToS | Keep gitignored |
| Model checkpoints `*.pt` | Size / license | Not required for judge path |
| Third-party academic branding misuse | Legal | JunctionTrace must not claim Tsinghua/NVIDIA/Nebius endorsement |
| IEDE / prior research IP | Attribution | Keep `/research` clearly labeled; cite baseline honestly |

## Explicit non-actions

- Do **not** `gh repo edit --visibility public` without approval.
- Do **not** deploy paid infra / upload YouTube / submit Devpost without approval.
- Do **not** enable real OpenFlow containment for demos.
