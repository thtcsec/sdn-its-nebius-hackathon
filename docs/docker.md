# Docker — what compose runs (and what it does not)

## Official project (unchanged)

**Title:** AI-Assisted Resilience for SDN-Enabled Intelligent Transportation Systems  
**Subtitle:** A Lightweight Framework for V2X Network Reliability, Edge Telemetry, and Safety-Aware Mitigation  
**Category:** Transportation · AI · Internet Security · IoT · Cloud/Edge Computing  

See [IEDE_Report_Summary.md](IEDE_Report_Summary.md). Docker is only a **runtime packaging** of the prototype console — it does not redefine the research title.

## Quick start

From the **repo root**:

```bash
docker compose up -d --build
# http://127.0.0.1:8080/
# Host publish is loopback-only: 127.0.0.1:8080→container (see docker-compose.yml)
```

With camera inventory mounted:

```bash
docker compose -f docker-compose.yml -f docker/docker-compose.cameras.yml up -d --build
```

## What `docker compose up` starts

| Service | Role |
|---------|------|
| `controller` | Flask API + evidence console (`:8080`) |
| `telemetry` | Synthetic traffic feeder → controller |

That is the **ops/demo loop**, not every research artifact in the repo.

## What compose does **not** replace

| Piece | How you run it |
|-------|----------------|
| Train / evaluate / reproduce tables | Host: `pip install -e .` + `reproduce.ps1` / scripts |
| YOLO on **RTX** | Host GPU: `.\scripts\dev.ps1` (Docker default image is CPU) |
| Exp A Mininet / OVS / OpenFlow verify | WSL/Linux lab (`scripts/run_exp_a.ps1`) |
| Jupyter notebooks | Host or optional profile (not default) |
| Full dataset download | Host: `scripts/download_dataset.py` |

So: **compose ≠ cả dự án IEDE**. Compose = console + feeder để demo nhanh. Lab evidence (Exp A, training, CUDA detect) vẫn chạy trên host/WSL như checklist.

## Optional: camera extras in image

```bash
docker build -f docker/Dockerfile --build-arg INSTALL_CAMERA=1 -t sdn-its-console .
```

Still CPU unless you add NVIDIA Container Toolkit + GPU compose device reservations.
