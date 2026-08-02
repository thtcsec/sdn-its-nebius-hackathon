"""Load a small allow-listed camera set from configs/cameras.yaml + inventory JSON.

Secrets stay in the inventory file (gitignored). No per-camera env vars required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import CameraHealth

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CFG = ROOT / "configs" / "cameras.yaml"


def load_camera_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or Path(os_environ_cfg() or DEFAULT_CFG)
    if not cfg_path.is_file():
        return {"enabled": False, "select": [], "inventory": None}
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    data["_config_path"] = str(cfg_path)
    return data


def os_environ_cfg() -> str | None:
    import os

    return os.environ.get("SDN_CAMERAS_CONFIG")  # optional single override path


def resolve_inventory(cfg: dict[str, Any]) -> Path | None:
    inv = cfg.get("inventory")
    if not inv:
        return None
    p = Path(inv)
    if not p.is_absolute():
        p = ROOT / p
    return p if p.is_file() else None


def load_selected_cameras(cfg: dict[str, Any] | None = None) -> tuple[list[CameraHealth], dict[str, Any]]:
    """Return CameraHealth list (≤ max_cameras) and load meta for /api/v1/camera."""
    cfg = cfg or load_camera_config()
    meta: dict[str, Any] = {
        "config_path": cfg.get("_config_path"),
        "inventory": cfg.get("inventory"),
        "enabled": bool(cfg.get("enabled", True)),
        "selected_ids": [],
        "missing_ids": [],
        "physical_mode": cfg.get("physical_mode", "synthetic"),
        "sample_frames": bool(cfg.get("sample_frames", False)),
        "note": "Allow-list only — full inventory is not loaded into the app.",
    }
    if not cfg.get("enabled", True):
        return [], meta

    inv_path = resolve_inventory(cfg)
    if inv_path is None:
        meta["error"] = f"inventory not found: {cfg.get('inventory')}"
        return [], meta

    try:
        inventory = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        meta["error"] = str(exc)
        return [], meta

    by_id = {str(row.get("id")): row for row in inventory if isinstance(row, dict)}
    select = list(cfg.get("select") or [])
    max_n = int(cfg.get("max_cameras") or 3)
    cameras: list[CameraHealth] = []

    for entry in select[:max_n]:
        if isinstance(entry, str):
            cam_id, role, prio = entry, "secondary", "NORMAL"
        else:
            cam_id = str(entry.get("id") or "")
            role = str(entry.get("role") or "secondary")
            prio = str(entry.get("network_priority") or ("HIGH" if role == "primary" else "NORMAL"))
        row = by_id.get(cam_id)
        if not row:
            meta["missing_ids"].append(cam_id)
            continue
        url = row.get("streamUrl") or row.get("rtsp") or row.get("url")
        short = cam_id.split("-")[0] if cam_id else f"cam{len(cameras)}"
        camera_id = f"cam-{short}"
        health = CameraHealth(
            camera_id=camera_id,
            label=str(row.get("name") or camera_id),
            junction=str(row.get("address") or row.get("name") or "")[:80],
            rtsp_url=str(url) if url else None,
            connected=False,
            codec=None,
            resolution=None,
            fps_cfg=None,
            network_priority=prio,
            mode="rtsp_health" if url else "disabled",
            last_error=None,
            inventory_id=cam_id,
            role=role,
        )
        cameras.append(health)
        meta["selected_ids"].append(
            {
                "inventory_id": cam_id,
                "camera_id": camera_id,
                "name": health.label,
                "role": role,
                "has_rtsp": bool(url),
            }
        )

    meta["loaded"] = len(cameras)
    meta["inventory_total"] = len(by_id)
    return cameras, meta
