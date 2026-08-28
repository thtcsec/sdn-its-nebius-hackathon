#!/usr/bin/env python
"""Replace ops-console screenshots inside the IEDE DOCX (keep architecture.png)."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "Trinh Hoang Tu_3rd Version.docx"
OUT_DOCS = ROOT / "docs" / "IEDE_Project_Report_Prototype.docx"
IMG = ROOT / "assets" / "images" / "report"
ARCH = ROOT / "architecture.png"

# New screenshots to swap into document figure slots (section 4 Fig 1–6)
REPLACEMENTS = {
    "fig01": IMG / "fig01_console_overview.png",
    "fig02": IMG / "fig02_ddos_containment.png",
    "fig03": IMG / "fig03_settings_drawer.png",
    "fig04": IMG / "fig04_rush_hour_preserve.png",
    "fig05": IMG / "fig05_replay_timeline.png",
    "fig06": IMG / "fig06_topology_events.png",
}


def set_run_font(run, size=12, bold=False, italic=False):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def insert_paragraph_after(paragraph: Paragraph) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    return Paragraph(new_p, paragraph._parent)


def fill(para: Paragraph, text: str, *, size=12, bold=False, italic=False, center=False, indent=True):
    for r in list(para.runs):
        r._element.getparent().remove(r._element)
    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    para.paragraph_format.first_line_indent = Cm(0) if (center or not indent) else Cm(0.75)
    if center:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic)
    return para


def media_map(docx_path: Path) -> list[tuple[str, Path, int]]:
    """Return list of (name, extracted_path, size) for word/media/*."""
    tmp = ROOT / "tmp_docx_unpack"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(docx_path, "r") as zf:
        zf.extractall(tmp)
    media = tmp / "word" / "media"
    rows = []
    for p in sorted(media.glob("*")):
        rows.append((p.name, p, p.stat().st_size))
    return rows


def replace_media_blobs(docx_path: Path, mapping: dict[str, Path], out_path: Path) -> None:
    """
    Replace UI screenshot blobs by document order.

    Strategy: among image*.png in media, skip the architecture image (matched by
    near-equal size to architecture.png), then map the next 6 PNG/JPEG images in
    relationship discovery order to fig01..fig06.
    """
    tmp = ROOT / "tmp_docx_unpack"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(docx_path, "r") as zf:
        zf.extractall(tmp)

    media = tmp / "word" / "media"
    arch_size = ARCH.stat().st_size if ARCH.exists() else -1

    # Prefer document-order via document.xml.rels image targets
    rels = (tmp / "word" / "_rels" / "document.xml.rels").read_text(encoding="utf-8")
    import re

    targets = re.findall(r'Target="media/([^"]+)"', rels)
    # Keep unique order
    ordered = []
    for t in targets:
        if t not in ordered:
            ordered.append(t)

    ui_slots = []
    for name in ordered:
        path = media / name
        if not path.exists():
            continue
        # skip architecture (exact size match or name contains arch)
        if arch_size > 0 and abs(path.stat().st_size - arch_size) < 64:
            print(f"  skip architecture media: {name} ({path.stat().st_size})")
            continue
        # skip tiny icons if any
        if path.stat().st_size < 5_000:
            print(f"  skip tiny: {name}")
            continue
        ui_slots.append(path)

    figs = [REPLACEMENTS[f"fig0{i}"] for i in range(1, 7)]
    if len(ui_slots) < 6:
        raise SystemExit(f"expected >=6 UI images in docx, found {len(ui_slots)}: {[p.name for p in ui_slots]}")

    # First 6 non-architecture images in rels order ≈ Fig 1–6 from original report
    for slot, src in zip(ui_slots[:6], figs):
        if not src.exists():
            raise SystemExit(f"missing screenshot: {src}")
        shutil.copyfile(src, slot)
        print(f"  replaced {slot.name} <- {src.name} ({src.stat().st_size} bytes)")

    # Repack
    if out_path.exists():
        out_path.unlink()
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in tmp.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(tmp).as_posix())
    print(f"wrote {out_path}")


def ensure_camera_figures(docx_path: Path) -> None:
    """Insert fig07/fig08 under §4.7 / §4.8 if not already present as pictures nearby."""
    doc = Document(str(docx_path))
    text = "\n".join(p.text or "" for p in doc.paragraphs)
    h47 = None
    h48 = None
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t.startswith("4.7 Camera Context"):
            h47 = p
        if t.startswith("4.8 PacketIn Inject"):
            h48 = p

    def add_fig_after(anchor: Paragraph, img: Path, caption: str):
        # If next few paragraphs already contain this caption, skip
        # Insert picture + caption after anchor's following body paragraph if present
        pic_p = insert_paragraph_after(anchor)
        pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pic_p.paragraph_format.first_line_indent = Cm(0)
        run = pic_p.add_run()
        run.add_picture(str(img), width=Cm(15.5))
        cap = insert_paragraph_after(pic_p)
        fill(cap, caption, size=11, italic=True, center=True, indent=False)
        return cap

    if h47 is not None and "Figure 8. Camera context" not in text:
        # find body after heading
        body = None
        seen = False
        for p in doc.paragraphs:
            if p._p is h47._p:
                seen = True
                continue
            if seen and (p.text or "").strip():
                body = p
                break
        anchor = body or h47
        add_fig_after(
            anchor,
            IMG / "fig07_camera_tracks.png",
            "Figure 8. Camera context panel (August 2026 UI): Tracks / occ / q≈ / rel — "
            "not veh/h and not calibrated confidence. Synthetic rush scenario shown.",
        )

    # reload text after possible insert
    doc = Document(str(docx_path)) if False else doc  # keep same doc object if we inserted
    text2 = "\n".join(p.text or "" for p in doc.paragraphs)
    # re-find h48 after possible mutation
    h48 = None
    for p in doc.paragraphs:
        if (p.text or "").strip().startswith("4.8 PacketIn Inject"):
            h48 = p
            break
    if h48 is not None and "Figure 9. Fusion decision" not in text2:
        body = None
        seen = False
        for p in doc.paragraphs:
            if p._p is h48._p:
                seen = True
                continue
            if seen and (p.text or "").strip() and not (p.text or "").startswith("Figure 8"):
                body = p
                break
        anchor = body or h48
        add_fig_after(
            anchor,
            IMG / "fig08_fusion_camera.png",
            "Figure 9. Fusion decision with camera physical evidence (network × physical). "
            "PacketIn network inject is independent of Cam · * physical overrides.",
        )

    # Update §4 intro date note if needed
    for p in doc.paragraphs:
        if (p.text or "").startswith("This section documents the working prototype UI"):
            if "August 2026 UI screenshots" not in (p.text or ""):
                fill(
                    p,
                    "This section documents the working prototype UI at http://127.0.0.1:8080/. "
                    "Figures 1–6 and 8–9 were re-captured on 2 August 2026 from the current evidence console "
                    "(Tracks / context_reliability labels, Cam · synth controls, NET · NO EVIDENCE honesty strip).",
                )
            break

    # Appendix rows
    if doc.tables:
        t_last = doc.tables[-1]
        if (t_last.rows[0].cells[0].text or "").lower().startswith("figure"):
            blob = " ".join((r.cells[0].text or "") for r in t_last.rows)
            if "Fig. 8" not in blob:
                row = t_last.add_row()
                row.cells[0].text = ""
                row.cells[1].text = ""
                r0 = row.cells[0].paragraphs[0].add_run("Fig. 8")
                set_run_font(r0, size=11, bold=False)
                r1 = row.cells[1].paragraphs[0].add_run(
                    "A Cam modes · B Tracks/rel · C stream quality · D synthetic source"
                )
                set_run_font(r1, size=11)
            if "Fig. 9" not in blob:
                row = t_last.add_row()
                row.cells[0].text = ""
                row.cells[1].text = ""
                r0 = row.cells[0].paragraphs[0].add_run("Fig. 9")
                set_run_font(r0, size=11)
                r1 = row.cells[1].paragraphs[0].add_run(
                    "A Network evidence · B Physical tracks · C recommended_action · D explain"
                )
                set_run_font(r1, size=11)

    doc.save(str(docx_path))
    print(f"updated camera figures in {docx_path.name}")


def main() -> None:
    for k, p in REPLACEMENTS.items():
        if not p.exists():
            raise SystemExit(f"missing {p}")
    print("media before:")
    for name, path, size in media_map(DOC):
        print(f"  {name}: {size}")

    tmp_out = ROOT / "Trinh Hoang Tu_3rd Version.screens_tmp.docx"
    replace_media_blobs(DOC, REPLACEMENTS, tmp_out)
    shutil.move(tmp_out, DOC)
    ensure_camera_figures(DOC)
    shutil.copyfile(DOC, OUT_DOCS)
    print(f"copied -> {OUT_DOCS}")

    # verify open
    d = Document(str(DOC))
    imgs = sum(1 for r in d.part.rels.values() if "image" in r.reltype)
    print(f"verify open OK paras={len(d.paragraphs)} tables={len(d.tables)} images={imgs}")


if __name__ == "__main__":
    main()
