#!/usr/bin/env python
"""Verify 5th Edition captions and normalize figure extents."""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from docx import Document
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "Trinh Hoang Tu_5th Version.docx"
SLIDES = ROOT / "assets" / "images" / "slides"
EMU = 360000


def emus(path: Path, max_w: float = 15.0) -> tuple[int, int]:
    im = Image.open(path)
    w, h = im.size
    cx = int(max_w * EMU)
    cy = int(cx * (h / w))
    return cx, cy


def main() -> None:
    doc = Document(str(DOCX))
    print("=== key lines ===")
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        if (
            t.startswith("Figure")
            or "August" in t
            or "5th" in t
            or t.startswith("Captures")
            or "allow-listed" in t
            or "live-night" in t
            or "labeled-video false-positive" in t
        ):
            print("-", t[:180])

    pairs = [
        ("Figure 7.1.", SLIDES / "slide_01_console_overview.jpg"),
        ("Figure 7.2.", SLIDES / "slide_05_re_chart_ddos.jpg"),
        ("Figure 7.3.", SLIDES / "slide_06_rush_hour_network.jpg"),
        ("Figure 7.4.", SLIDES / "slide_04_ddos_containment.jpg"),
        ("Figure 7.6.", SLIDES / "slide_02_live_cameras.jpg"),
        ("Figure 7.7.", SLIDES / "slide_03_fusion_rush_preserve.jpg"),
    ]

    tmp = ROOT / "tmp_docx_v5_ext"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    with zipfile.ZipFile(DOCX) as z:
        z.extractall(tmp)
    xml_path = tmp / "word" / "document.xml"
    xml = xml_path.read_text(encoding="utf-8")
    changed = False

    def sub_last(fragment: str, cx: int, cy: int) -> str:
        nonlocal changed
        for tag in ("wp:extent", "a:ext"):
            pat = re.compile(rf'(<{tag}\b[^>]*\bcx=")\d+("\s+cy=")\d+(")')
            ms = list(pat.finditer(fragment))
            if not ms:
                continue
            m = ms[-1]
            fragment = (
                fragment[: m.start()]
                + m.group(1)
                + str(cx)
                + m.group(2)
                + str(cy)
                + m.group(3)
                + fragment[m.end() :]
            )
            changed = True
        return fragment

    for cap, img in pairs:
        pos = xml.find(cap)
        print(f"cap {cap!r} pos={pos}")
        if pos < 0 or not img.exists():
            continue
        cx, cy = emus(img)
        ws = max(0, pos - 14000)
        head, mid, tail = xml[:ws], xml[ws:pos], xml[pos:]
        mid2 = sub_last(mid, cx, cy)
        xml = head + mid2 + tail
        print(f"  extent -> {cx}x{cy}")

    # also update Captures line if still old
    doc2 = Document(str(DOCX))
    for p in doc2.paragraphs:
        if p.text.strip() == "Captures use the August 2026 console.":
            p.runs[0].text = (
                "Captures include the August 2026 console and refreshed 28 August 2026 "
                "live-night camera panels when RTSP hosts resolve."
            )
            doc2.save(str(DOCX))
            print("updated Captures line")
            # re-extract after save
            if tmp.exists():
                shutil.rmtree(tmp)
            tmp.mkdir()
            with zipfile.ZipFile(DOCX) as z:
                z.extractall(tmp)
            xml = (tmp / "word" / "document.xml").read_text(encoding="utf-8")
            break

    xml_path.write_text(xml, encoding="utf-8")
    if changed:
        DOCX.unlink()
        with zipfile.ZipFile(DOCX, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for f in tmp.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(tmp).as_posix())
        print("repacked with extents")
    else:
        print("extents already ok / no regex hits")
    shutil.rmtree(tmp, ignore_errors=True)
    print("size_kb", DOCX.stat().st_size // 1024)


if __name__ == "__main__":
    main()
