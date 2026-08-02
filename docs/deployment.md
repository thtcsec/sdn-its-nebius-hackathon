# Deployment

## Local demo (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
.\scripts\dev.ps1
```

Open `http://127.0.0.1:8080/`.

OpenFlow backend (optional):

```powershell
$env:SDN_OF_BACKEND = "mock"   # default print-only
$env:SDN_OF_BACKEND = "queue"  # in-memory flow-mod log (dry-run)
$env:SDN_OF_BACKEND = "http"   # real OVS via WSL of_agent
$env:OF_AGENT_URL = "http://127.0.0.1:8089"
```

## Docker Compose

```bash
cd docker
docker compose up --build
```

Services mirror the architecture: **controller/API/dashboard** (Flask) and **telemetry** streamer.  
Compose is the portable demo path — it does **not** ship a privileged Mininet/OVS lab.

## Linux / Mininet + Ryu lab (real OpenFlow)

Full step-by-step: **[lab_checklist.md](lab_checklist.md)**.

Short version (WSL2 Ubuntu):

```bash
# Terminal A
ryu-manager src/sdn_its/controller/ryu_app.py

# Terminal B
sudo python -m sdn_its.simulation.topology

# Terminal C
export SDN_OF_BACKEND=ryu
python -m api.app
```

## Config

Controller port/host: `configs/controller.yaml`  
Simulation streamer: `configs/simulation.yaml`  
OpenFlow backend: env `SDN_OF_BACKEND` = `mock` | `queue` | `ryu`
