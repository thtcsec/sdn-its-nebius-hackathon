# SDN Lab Checklist (WSL2 / Ubuntu)

This is the **real OpenFlow path**. Windows native demo stays on `SDN_OF_BACKEND=mock` (or `queue` for dry-run logging).

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
| `ryu` | WSL2/Linux | Adapter + live datapaths / Ryu app |

See also: [deployment.md](deployment.md), `sdn_its.controller.of_backend`, `sdn_its.controller.ryu_app`.
