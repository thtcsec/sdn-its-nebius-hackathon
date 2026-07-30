# Deployment

## Local demo (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
.\scripts\dev.ps1
```

Open `http://127.0.0.1:8080/`.

## Docker Compose

```bash
cd docker
docker compose up --build
```

Services mirror the architecture: **controller/API/dashboard** (Flask) and **telemetry** streamer.

## Linux / Mininet lab

- Run topology: `python -m sdn_its.simulation.topology`
- Ryu OpenFlow adapter is a documented stub (`sdn_its.controller.ryu_controller`); wire to real Ryu on WSL2/Linux.

## Config

Controller port/host: `configs/controller.yaml`  
Simulation streamer: `configs/simulation.yaml`
