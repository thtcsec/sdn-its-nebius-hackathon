# Deployment

## Local demo (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
.\scripts\dev.ps1
```

Open `http://127.0.0.1:8080/`.

Controller **binds to `127.0.0.1` by default** (`configs/controller.yaml`).  
For a LAN demo only:

```powershell
$env:SDN_BIND_HOST = "0.0.0.0"   # or SDN_BIND_LAN=1
$env:SDN_API_TOKEN = "replace-me"  # recommended when LAN-bound
python -m api.app --host 0.0.0.0 --port 8080
```

Mutating calls then need `Authorization: Bearer <token>` or `X-API-Token`.

OpenFlow backend (optional):

```powershell
$env:SDN_OF_BACKEND = "mock"   # default print-only
$env:SDN_OF_BACKEND = "queue"  # in-memory flow-mod log (dry-run)
$env:SDN_OF_BACKEND = "http"   # real OVS via WSL of_agent
$env:OF_AGENT_URL = "http://127.0.0.1:8089"
$env:OF_AGENT_TOKEN = "optional-shared-secret"
```

Webhooks: blocked for private/metadata hosts by default (SSRF guard).  
Set `SDN_WEBHOOK_ALLOW_PRIVATE=1` only for trusted LAN sinks.

## Docker Compose

```bash
docker compose up -d --build
# → http://127.0.0.1:8080/  (host port published on loopback only)
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
OpenFlow backend: env `SDN_OF_BACKEND` = `mock` | `queue` | `ryu` | `http`
