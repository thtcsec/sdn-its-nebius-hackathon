# Public-release checklist (do NOT flip visibility without approval)

Repository is currently **private**. Changing GitHub visibility requires an explicit human approval.

## Before requesting public

- [ ] `python scripts/scan_secrets_and_license.py` → `ok: true`
- [ ] `.env` not tracked (`git ls-files .env` empty)
- [ ] No RTSP URLs / `1.cameras.json` / private camera inventories in git
- [ ] No `*.pt` checkpoints required for judge path
- [ ] `docs/JUDGE_DEMO.md` current
- [ ] `docs/HACKATHON_CONTRIBUTIONS.md` separates research vs hackathon
- [ ] Held-out eval artifacts regenerated and reviewed for honesty notes
- [ ] Demo video (&lt;3 min) uploaded; URL recorded in `docs/DEMO_VIDEO.md`
- [ ] LICENSE present (MIT)
- [ ] README states mock OpenFlow default and no fabricated Nebius results
- [ ] Competition rules re-checked (eligibility, model disclosure, open-source requirements)

## Explicit non-actions

- Do **not** run `gh repo edit --visibility public` without approval.
- Do **not** commit `.env` or API keys.
- Do **not** enable real OpenFlow containment for demos (`of_backend: mock`).

## Suggested release command (after approval only)

```powershell
# ONLY after explicit approval:
# gh repo edit thtcsec/sdn-its-nebius-hackathon --visibility public
```
