# SDN Lab Checklist (WSL2 / Ubuntu)

This is the **real OpenFlow path**. Windows default remains `SDN_OF_BACKEND=mock`
(in-memory / print only). Console **Lab mode** does not make OpenFlow real by itself —
set `SDN_OF_BACKEND=http` and run `scripts/wsl_of_agent.py` (or Ryu) for switch evidence.

Repo posture: [REPRODUCE.md](REPRODUCE.md) · [EVIDENCE.md](EVIDENCE.md).

## 0. Prerequisites

- Windows 11 + **WSL2 Ubuntu 22.04+** (or a native Linux box)
- 4+ GB RAM free for Mininet
- Project cloned into a path accessible from WSL (`/mnt/d/tu_projects/sdn-its-resilience-ai` OK)

```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch openvswitch-common python3-pip python3-venv
sudo service openvswitch-switch start
```

```bash
cd /mnt/d/tu_projects/sdn-its-resilience-ai   # adjust path
python3 -m venv .venv-lab
source .venv-lab/bin/activate
pip install -e ".[dev]"
pip install ryu eventlet==0.33.3   # pin eventlet if Ryu import fails
```

## 1. Start Ryu OpenFlow app

```bash
ryu-manager src/sdn_its/controller/ryu_app.py
# listens OF 1.3 on :6653
```

## 2. Launch ITS Mininet topology

```bash
# new terminal, same venv
sudo python -m sdn_its.simulation.topology
# or: sudo mn --custom ...  (uses ITSEdgeTopology when Mininet is available)
```

Expected: switches `s1..s4`, hosts `veh1..veh6`, `tmc`, `edge1/2`, remote controller `127.0.0.1:6653`.

## 3. Start resilience API with Ryu backend

```bash
export SDN_OF_BACKEND=ryu
python -m api.app
# http://127.0.0.1:8080/
```

On Windows PowerShell dry-run (no Mininet):

```powershell
$env:SDN_OF_BACKEND = "queue"
python -m api.app
```

`queue` records flow-mods in `RyuControllerAdapter.flow_log` without requiring OVS.

## 4. Inject attack traffic

```bash
python -m sdn_its.simulation.scapy_traffic --scenario ddos
# or loft / rush_hour
```

Watch Command Center: Detect → Contain (DROP/THROTTLE) → cooldown Rollback.

## 5. Verify OpenFlow side effects

```bash
sudo ovs-ofctl dump-flows s1
sudo ovs-ofctl dump-flows s4
```

API check:

```bash
curl http://127.0.0.1:8080/api/v1/status
# stats.of_backend should be ryu|queue|mock
```

## 6. Pass criteria (lab sign-off)

- [ ] Ryu sees switch features / datapaths
- [ ] DDoS inject raises anomaly / mitigation in console
- [ ] At least one DROP or meter-like rule visible via `ovs-ofctl` **or** queue log length increases
- [ ] Rush-hour scenario does **not** permanently drop legitimate flows (PRESERVE path)
- [ ] Rollback fires after cooldown

## Backend matrix

| `SDN_OF_BACKEND` | Where | Behavior |
|------------------|-------|----------|
| `mock` (default) | Windows demo | Print-only OpenFlow channel |
| `queue` | Windows / CI | In-memory flow-mod log |
| `http` / `wsl` | Windows API → WSL agent | **Real ovs-ofctl** on Mininet bridges |
| `ryu` | WSL2/Linux | Adapter + live datapaths / Ryu app |

## Recommended wired lab (light — no extra torch in WSL)

Disk/RAM impact: **~0 extra GB** if Mininet/OVS already installed; agent is a small Python script.
`.venv-lab` (os-ken) ≈ **100–150 MB** optional. Do **not** install CUDA torch in WSL (~2–3 GB) unless you need GPU infer there.

```powershell
# Terminal A — WSL root: agent + ITS topology (90s)
wsl -d Ubuntu -u root -- bash /mnt/d/tu_projects/sdn-its-resilience-ai/scripts/run_wsl_lab.sh 90

# Terminal B — Windows: API talks to WSL of_agent
$env:SDN_OF_BACKEND = "http"
$env:OF_AGENT_URL = "http://127.0.0.1:8089"
# Optional shared secret (match agent --token / OF_AGENT_TOKEN):
# $env:OF_AGENT_TOKEN = "lab-secret"
.\.venv\Scripts\python.exe -m api.app --port 8080
```

`wsl_of_agent` defaults to **`127.0.0.1:8089`**. Pass `--host 0.0.0.0` only if needed; prefer `--token` / `OF_AGENT_TOKEN` for `POST /flow_mod`.

Smoke (all in WSL):

```bash
wsl -d Ubuntu -u root -- bash /mnt/d/tu_projects/sdn-its-resilience-ai/scripts/smoke_wsl_lab.sh
```

See also: [deployment.md](deployment.md), `sdn_its.controller.of_backend`, `scripts/wsl_of_agent.py`.

## Minimum real experiments (to leave “toy” territory)

| Exp | Compare | Must measure | Status |
|-----|---------|--------------|--------|
| **A** Containment | none / permanent DROP / temporary DROP+rollback | attack/legit ICMP delivery, install_ms, recovery_ms, dump-flows verify | **Done** — `.\scripts\run_exp_a.ps1` → `artifacts/results/exp_a/` |
| **B/C** Fusion policy | camera×network matrix (rush / flood / mixed) | preserve vs temporary DROP decisions | **Done (rules)** — `scripts/exp_bc_camera_fusion.py` → `artifacts/results/exp_bc/` (not live FP-reduction claim) |
| **D** Tracker phases | graded camera/tracker × fusion | evidence grades / honesty fields | **Done (graded)** — `scripts/exp_d_camera_containment.py` → `artifacts/results/exp_d/` |
| Live false-block @ scale | RE-τ / classifier / fusion on city traces | false-block rate, PacketIn↓ | TODO |

Exp A metrics are **data-plane ICMP ratios** (honest proxy). PacketIn/s still needs Ryu. Console: `GET /api/v1/lab/evidence`.
