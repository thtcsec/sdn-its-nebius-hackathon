"""Load a small allow-listed camera set from configs/cameras.yaml + inventory JSON.

No site names or inventory UUIDs are baked into application code.
Committed config uses select_mode=first_n; optional cameras.local.yaml for explicit IDs.
Console labels are always cam1..camN when anonymize_labels is true.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import CameraHealth

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CFG = ROOT / "configs" / "cameras.yaml"
LOCAL_CFG = ROOT / "configs" / "cameras.local.yaml"


def load_camera_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or Path(os_environ_cfg() or DEFAULT_CFG)
    if not cfg_path.is_file():
        return {"enabled": False, "select": [], "inventory": None}
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    data["_config_path"] = str(cfg_path)
    # Merge optional local override (explicit select list, never committed)
    local_path = LOCAL_CFG
    if local_path.is_file():
        try:
            local = yaml.safe_load(local_path.read_text(encoding="utf-8")) or {}
            if local.get("select"):
                data["select"] = local["select"]
                data["select_mode"] = str(local.get("select_mode") or "explicit")
            data["_local_override"] = str(local_path)
        except (OSError, yaml.YAMLError):
            pass
    return data


def os_environ_cfg() -> str | None:
    import os

    return os.environ.get("SDN_CAMERAS_CONFIG")


def resolve_inventory(cfg: dict[str, Any]) -> Path | None:
    inv = cfg.get("inventory")
    if not inv:
        return None
    p = Path(inv)
    if not p.is_absolute():
        p = ROOT / p
    return p if p.is_file() else None


def _rows_with_stream(inventory: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in inventory:
        if not isinstance(row, dict):
            continue
        url = row.get("streamUrl") or row.get("rtsp") or row.get("url")
        if url:
            out.append(row)
    return out


def _host_resolves(url: str, timeout_s: float = 1.5) -> bool:
    """Cheap DNS check so first_n skips dead DDNS entries when possible."""
    import socket
    from urllib.parse import urlparse

    try:
        host = urlparse(str(url)).hostname
        if not host:
            return False
        socket.setdefaulttimeout(timeout_s)
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


def _build_select_entries(cfg: dict[str, Any], inventory: list[Any]) -> list[dict[str, Any]]:
    """Resolve which inventory rows to load — never hardcode UUIDs in Python."""
    mode = str(cfg.get("select_mode") or "first_n").lower()
    max_n = int(cfg.get("max_cameras") or 3)
    select = list(cfg.get("select") or [])

    if mode == "explicit" and select:
        return select[:max_n]

    # first_n: prefer rows whose RTSP host resolves (dead DDNS otherwise fills the panel
    # with stale daytime JPEGs). Fall back to inventory order if none resolve.
    rows = _rows_with_stream(inventory)
    reachable = [r for r in rows if _host_resolves(str(r.get("streamUrl") or r.get("rtsp") or r.get("url") or ""))]
    chosen = (reachable or rows)[:max_n]
    entries: list[dict[str, Any]] = []
    for i, row in enumerate(chosen):
        entries.append(
            {
                "id": str(row.get("id") or ""),
                "role": "primary" if i == 0 else "secondary",
                "network_priority": "HIGH" if i == 0 else "NORMAL",
            }
        )
    return entries


def load_selected_cameras(cfg: dict[str, Any] | None = None) -> tuple[list[CameraHealth], dict[str, Any]]:
    """Return CameraHealth list (≤ max_cameras) and load meta for /api/v1/camera."""
    cfg = cfg or load_camera_config()
    anonymize = bool(cfg.get("anonymize_labels", True))
    meta: dict[str, Any] = {
        "config_path": cfg.get("_config_path"),
        "local_override": cfg.get("_local_override"),
        "inventory": cfg.get("inventory"),
        "enabled": bool(cfg.get("enabled", True)),
        "select_mode": cfg.get("select_mode", "first_n"),
        "selected_ids": [],
        "missing_ids": [],
        "physical_mode": cfg.get("physical_mode", "synthetic"),
        "sample_frames": bool(cfg.get("sample_frames", False)),
        "anonymize_labels": anonymize,
        "note": "Cameras loaded from inventory; labels are cam1..camN (no place names in UI).",
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
    if not isinstance(inventory, list):
        meta["error"] = "inventory must be a JSON list"
        return [], meta

    by_id = {str(row.get("id")): row for row in inventory if isinstance(row, dict)}
    select = _build_select_entries(cfg, inventory)
    max_n = int(cfg.get("max_cameras") or 3)
    cameras: list[CameraHealth] = []

    for idx, entry in enumerate(select[:max_n], start=1):
        if isinstance(entry, str):
            inv_id, role, prio = entry, ("primary" if idx == 1 else "secondary"), (
                "HIGH" if idx == 1 else "NORMAL"
            )
        else:
            inv_id = str(entry.get("id") or "")
            role = str(entry.get("role") or ("primary" if idx == 1 else "secondary"))
            prio = str(
                entry.get("network_priority") or ("HIGH" if role == "primary" else "NORMAL")
            )
        row = by_id.get(inv_id)
        if not row:
            meta["missing_ids"].append(inv_id)
            continue
        url = row.get("streamUrl") or row.get("rtsp") or row.get("url")
        camera_id = f"cam{idx}"
        label = camera_id if anonymize else str(row.get("name") or camera_id)
        health = CameraHealth(
            camera_id=camera_id,
            label=label,
            junction="" if anonymize else str(row.get("address") or row.get("name") or "")[:80],
            rtsp_url=str(url) if url else None,
            connected=False,
            codec=None,
            resolution=None,
            fps_cfg=None,
            network_priority=prio,
            mode="rtsp_health" if url else "disabled",
            last_error=None,
            inventory_id=inv_id,  # in-memory only; redacted in CameraHealth.to_dict
            role=role,
        )
        cameras.append(health)
        meta["selected_ids"].append(
            {
                "slot": idx,
                "camera_id": camera_id,
                "name": label,
                "role": role,
                "has_rtsp": bool(url),
            }
        )

    meta["loaded"] = len(cameras)
    meta["inventory_total"] = len(by_id)
    return cameras, meta
