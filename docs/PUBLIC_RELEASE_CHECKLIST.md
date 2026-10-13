# Public-release checklist (do NOT flip visibility without approval)

Repository is currently **private**. Changing GitHub visibility requires an explicit human approval.

## Before requesting public

- [ ] `python scripts/scan_secrets_and_license.py` → `ok: true`
- [ ] `.env` not tracked (`git ls-files .env` empty)
- [ ] No RTSP URLs / `1.cameras.json` / private camera inventories in git
- [ ] No `*.pt` checkpoints required for judge path
- [ ] `docs/JUDGE_DEMO.md` current (multi-step + ablation commands)
- [ ] `docs/HACKATHON_CONTRIBUTIONS.md` separates research vs hackathon
- [ ] `COMPETITION_DELTA_REPORT.md` present with honest metrics
- [ ] Held-out + ablation artifacts regenerated; honesty notes reviewed
- [ ] Multi-step demo traces in `artifacts/hackathon/multistep_demo_traces.json`
- [ ] Demo video (&lt;3 min) uploaded; URL recorded in `docs/DEMO_VIDEO.md`
- [ ] Hosted working demo URL prepared (or clear local judge path + credentials note)
- [ ] `WINNING_EVIDENCE.md` remote SHA matches GitHub tip
- [ ] Matched live proof artifact present (`matched_nemotron_proof.json`) — never pitch offline 92% as Nemotron
- [ ] Devpost feedback draft reviewed (`docs/NEBIUS_NVIDIA_FEEDBACK.md`)
- [ ] LICENSE present (MIT) and visible on GitHub About after public flip
- [ ] README status table matches reality; mock OF; no fabricated Nebius results
- [ ] Competition rules re-checked (public repo, YouTube, Token Factory runtime, track, pre-existing explanation, feedback form)

## Explicit non-actions

- Do **not** run `gh repo edit --visibility public` without approval.
- Do **not** commit `.env` or API keys.
- Do **not** enable real OpenFlow containment for demos (`of_backend: mock`).

## Suggested release command (after approval only)

```powershell
# ONLY after explicit approval:
# gh repo edit thtcsec/sdn-its-nebius-hackathon --visibility public
```
