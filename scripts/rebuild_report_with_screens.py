#!/usr/bin/env python
"""Restore DOCX from backup, re-apply content patch, then bind screenshots to Figure captions."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "Trinh Hoang Tu_3rd Version.backup.docx"
DOC = ROOT / "Trinh Hoang Tu_3rd Version.docx"
OUT_DOCS = ROOT / "docs" / "IEDE_Project_Report_Prototype.docx"
IMG = ROOT / "assets" / "images" / "report"
ARCH = ROOT / "architecture.png"

FIG_FILES = {
    1: IMG / "fig01_console_overview.png",
    2: IMG / "fig02_ddos_containment.png",
    3: IMG / "fig03_settings_drawer.png",
    4: IMG / "fig04_rush_hour_preserve.png",
    5: IMG / "fig05_replay_timeline.png",
    6: IMG / "fig06_topology_events.png",
}


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


def bind_figures_by_caption(docx: Path) -> None:
    tmp = ROOT / "tmp_docx_bind"
    unpack(docx, tmp)
    xml_path = tmp / "word" / "document.xml"
    xml = xml_path.read_text(encoding="utf-8")
    rels_path = tmp / "word" / "_rels" / "document.xml.rels"
    rels = rels_path.read_text(encoding="utf-8")
    rid_to = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="media/([^"]+)"', rels))

    # Split into paragraphs roughly; find each "Figure N." and look backward for nearest blip
    # Work on raw XML: for each caption match, search preceding 5000 chars for last r:embed
    for n, src in FIG_FILES.items():
        if not src.exists():
            raise SystemExit(f"missing {src}")
        # Find caption text occurrence
        pat = re.compile(rf"Figure\s+{n}\.")
        m = pat.search(xml)
        if not m:
            print(f"  WARN: caption Figure {n}. not found")
            continue
        window = xml[max(0, m.start() - 8000) : m.start()]
        embeds = re.findall(r'r:embed="(rId\d+)"', window)
        if not embeds:
            print(f"  WARN: no blip before Figure {n}")
            continue
        rid = embeds[-1]
        media_name = rid_to.get(rid)
        if not media_name:
            print(f"  WARN: {rid} not in rels for Figure {n}")
            continue
        dest = tmp / "word" / "media" / media_name
        # If destination is jpeg but source png, still overwrite bytes — Word may complain.
        # Convert to match extension when needed.
        if dest.suffix.lower() in {".jpg", ".jpeg"} and src.suffix.lower() == ".png":
            from PIL import Image

            im = Image.open(src).convert("RGB")
            im.save(dest, format="JPEG", quality=92)
        else:
            # Always write as the container extension expects; if png->png copy
            if dest.suffix.lower() == ".png":
                shutil.copyfile(src, dest)
            else:
                shutil.copyfile(src, dest)
        print(f"  Figure {n}: {media_name} ({rid}) <- {src.name}")

    # Also ensure architecture media matches architecture.png if caption Figure 7 exists
    m7 = re.search(r"Figure\s+7\.", xml)
    if m7 and ARCH.exists():
        window = xml[max(0, m7.start() - 8000) : m7.start()]
        embeds = re.findall(r'r:embed="(rId\d+)"', window)
        if embeds:
            rid = embeds[-1]
            media_name = rid_to.get(rid)
            if media_name:
                dest = tmp / "word" / "media" / media_name
                shutil.copyfile(ARCH, dest)
                print(f"  Figure 7: {media_name} ({rid}) <- architecture.png")

    pack(tmp, docx)
    print(f"bound figures -> {docx.name}")


def main() -> None:
    if not BACKUP.exists():
        raise SystemExit(f"missing backup {BACKUP}")
    for p in FIG_FILES.values():
        if not p.exists():
            raise SystemExit(f"missing screenshot {p}")

    shutil.copyfile(BACKUP, DOC)
    print("restored from backup")

    rc = subprocess.call([sys.executable, str(ROOT / "scripts" / "patch_iede_report_docx.py")])
    if rc != 0:
        raise SystemExit(f"patch failed rc={rc}")

    bind_figures_by_caption(DOC)

    sys.path.insert(0, str(ROOT / "scripts"))
    from replace_report_screens_in_docx import ensure_camera_figures

    ensure_camera_figures(DOC)
    shutil.copyfile(DOC, OUT_DOCS)
    print(f"copied -> {OUT_DOCS}")


if __name__ == "__main__":
    main()
