#!/usr/bin/env python
"""Re-bind landscape screenshots into DOCX and fix drawing extents (no stretch)."""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "Trinh Hoang Tu_3rd Version.docx"
OUT_DOCS = ROOT / "docs" / "IEDE_Project_Report_Prototype.docx"
IMG = ROOT / "assets" / "images" / "report"
ARCH = ROOT / "architecture.png"

# Prefer richer chart plate for Fig 2 if present
FIG = {
    1: IMG / "fig01_console_overview.png",
    2: IMG / "fig02b_re_chart_ddos.png" if (IMG / "fig02b_re_chart_ddos.png").exists() else IMG / "fig02_ddos_containment.png",
    3: IMG / "fig03_settings_drawer.png",
    4: IMG / "fig04_rush_hour_preserve.png",
    5: IMG / "fig05_replay_timeline.png",
    6: IMG / "fig06_topology_events.png",
    7: ARCH,
    8: IMG / "fig07_camera_tracks.png",
    9: IMG / "fig08_fusion_camera.png",
}

# Max content width for A4 with 3.0/2.5 cm margins ≈ 15.5 cm
MAX_WIDTH_CM = 15.5
EMU_PER_CM = 360000


def unpack(docx: Path, tmp: Path) -> None:
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(docx) as zf:
        zf.extractall(tmp)


def pack(tmp: Path, docx: Path) -> None:
    if docx.exists():
        docx.unlink()
    with zipfile.ZipFile(docx, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in tmp.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(tmp).as_posix())


def target_emus(path: Path, max_w_cm: float = MAX_WIDTH_CM) -> tuple[int, int]:
    im = Image.open(path)
    w, h = im.size
    cx = int(max_w_cm * EMU_PER_CM)
    cy = int(cx * (h / w))
    return cx, cy


def replace_nearest_extent(xml: str, caption_pos: int, cx: int, cy: int) -> str:
    """Update the last wp:extent / a:ext before caption_pos."""
    window_start = max(0, caption_pos - 12000)
    head = xml[:window_start]
    mid = xml[window_start:caption_pos]
    tail = xml[caption_pos:]

    def _sub_last(fragment: str, tag: str) -> str:
        # replace last occurrence of <tag ... cx=".." cy=".."/>
        pat = re.compile(rf"(<{tag}\b[^>]*\bcx=\")\d+(\"\s+cy=\")\d+(\")")
        matches = list(pat.finditer(fragment))
        if not matches:
            return fragment
        m = matches[-1]
        return fragment[: m.start()] + m.group(1) + str(cx) + m.group(2) + str(cy) + m.group(3) + fragment[m.end() :]

    mid = _sub_last(mid, "wp:extent")
    mid = _sub_last(mid, "a:ext")
    return head + mid + tail


def main() -> None:
    for n, p in FIG.items():
        if not p.exists():
            raise SystemExit(f"missing Figure {n} file: {p}")

    tmp = ROOT / "tmp_docx_fix_aspect"
    unpack(DOC, tmp)
    xml_path = tmp / "word" / "document.xml"
    xml = xml_path.read_text(encoding="utf-8")
    rels = (tmp / "word" / "_rels" / "document.xml.rels").read_text(encoding="utf-8")
    rid_to = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="media/([^"]+)"', rels))

    for n, src in sorted(FIG.items()):
        m = re.search(rf"Figure\s+{n}\.", xml)
        if not m:
            print(f"  skip Figure {n}: caption missing")
            continue
        window = xml[max(0, m.start() - 12000) : m.start()]
        embeds = re.findall(r'r:embed="(rId\d+)"', window)
        if not embeds:
            print(f"  skip Figure {n}: no blip")
            continue
        rid = embeds[-1]
        media_name = rid_to[rid]
        dest = tmp / "word" / "media" / media_name
        # write PNG bytes; if container is jpeg, convert
        if dest.suffix.lower() in {".jpg", ".jpeg"}:
            Image.open(src).convert("RGB").save(dest, format="JPEG", quality=92)
        else:
            # force png content even if name is .png
            shutil.copyfile(src, dest)
        cx, cy = target_emus(src)
        xml = replace_nearest_extent(xml, m.start(), cx, cy)
        im = Image.open(src)
        print(f"  Figure {n}: {media_name} <- {src.name} ({im.size[0]}x{im.size[1]}) extent={cx}x{cy} EMU")

    xml_path.write_text(xml, encoding="utf-8")
    pack(tmp, DOC)
    shutil.copyfile(DOC, OUT_DOCS)
    print(f"wrote {DOC.name}")
    print(f"copied {OUT_DOCS}")


if __name__ == "__main__":
    main()
