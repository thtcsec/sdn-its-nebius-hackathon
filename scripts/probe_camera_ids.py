#!/usr/bin/env python
"""Probe camera inventory IDs: DNS/TCP + optional ffprobe."""
from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "1.cameras.json"


def main() -> None:
    cams = json.loads(INV.read_text(encoding="utf-8"))
    print(f"inventory={len(cams)} file={INV}")
    working = []
    for i, c in enumerate(cams):
        cid = str(c.get("id") or "")
        url = str(c.get("streamUrl") or "")
        status = c.get("status")
        name = str(c.get("name") or "")[:48]
        host = port = None
        dns = tcp = probe = "—"
        if url.startswith("rtsp://"):
            p = urlparse(url)
            host, port = p.hostname, (p.port or 554)
            try:
                socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
                dns = "OK"
            except Exception as e:
                dns = f"FAIL:{type(e).__name__}"
            if dns == "OK":
                try:
                    s = socket.create_connection((host, port), timeout=4)
                    s.close()
                    tcp = "OK"
                except Exception as e:
                    tcp = f"FAIL:{type(e).__name__}"
            if tcp == "OK":
                try:
                    r = subprocess.run(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            "-rtsp_transport",
                            "tcp",
                            "-select_streams",
                            "v:0",
                            "-show_entries",
                            "stream=codec_name,width,height",
                            "-of",
                            "json",
                            url,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=12,
                    )
                    probe = "OK" if r.returncode == 0 else f"FAIL:{ (r.stderr or r.stdout)[:60]!r}"
                except Exception as e:
                    probe = f"FAIL:{type(e).__name__}"
        print(
            f"{i:02d} id={cid[:8]}… status={status} dns={dns} tcp={tcp} probe={probe} "
            f"host={host}:{port} name={name!r}"
        )
        if probe == "OK":
            working.append({"index": i, "id": cid, "host": host, "port": port, "name": name})

    print("\n=== WORKING (ffprobe OK) ===")
    if not working:
        print("(none)")
    for w in working:
        print(w)


if __name__ == "__main__":
    main()
