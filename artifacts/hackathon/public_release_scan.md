# Public-release scan results

**Date (UTC):** 2026-10-18  
**Working tree scan:** `python scripts/scan_secrets_and_license.py` → **`ok: true`**

| Check | Result |
|-------|--------|
| `.env` tracked in git | **No** |
| `deploy/judge/.env` tracked | **No** |
| `LICENSE` (MIT) present | **Yes** |
| Working-tree secret pattern findings | **None** |
| History: added `.env` blobs | **None found** (sampled) |

## Non-publishable / handle-with-care

| Item | Notes |
|------|-------|
| Local `.env` with Nebius key | Gitignored; never commit; rotate if exposed |
| Live camera / RTSP inventories | Gitignored; not part of judge path |
| `*.pt` checkpoints | Not required for JunctionTrace judge demo |
| Demo MP4/WebM under `artifacts/demo_video/` | Local only (gitignored); upload needs approval |
| Third-party endorsement claims | Product must not claim Tsinghua / NVIDIA / Nebius endorsement |

## Still requires owner approval

- Repository visibility → public  
- Paid host deploy (`deploy/judge`)  
- YouTube upload  
- Devpost submit  

See `docs/PUBLIC_RELEASE_CHECKLIST.md`.
