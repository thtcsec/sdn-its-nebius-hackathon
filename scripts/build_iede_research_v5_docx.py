#!/usr/bin/env python
"""Build Trinh Hoang Tu_5th Version.docx by carefully patching the 4th Edition.

Preserves styles/fonts; only updates text in existing runs and swaps figure
bytes with corrected drawing extents (no stretch).
"""

from __future__ import annotations

import io
import re
import shutil
import zipfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Trinh Hoang Tu_4th Version.docx"
OUT = ROOT / "Trinh Hoang Tu_5th Version.docx"
OUT_DOCS = ROOT / "docs" / "IEDE_Project_Report_Prototype.docx"
SLIDES = ROOT / "assets" / "images" / "slides"
COMPRESSED = ROOT / "assets" / "images" / "report" / "compressed"

EMU_PER_CM = 360000
MAX_W_CM = 15.0


def set_run_text_keep_font(run, text: str) -> None:
    """Replace run text without clearing rPr (font/size/bold)."""
    run.text = text
    # ensure Times New Roman remains if present
    if run._element.rPr is not None and run._element.rPr.rFonts is not None:
        run._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        run._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")


def replace_paragraph_text(paragraph, new_text: str) -> bool:
    """Put all text into the first run; clear other runs' text (keep formatting)."""
    runs = paragraph.runs
    if not runs:
        run = paragraph.add_run(new_text)
        set_run_text_keep_font(run, new_text)
        return True
    set_run_text_keep_font(runs[0], new_text)
    for r in runs[1:]:
        r.text = ""
    return True


def patch_texts(doc: Document) -> list[str]:
    log: list[str] = []

    replacements: list[tuple[str, str]] = [
        (
            "August, 2026",
            "August 28, 2026 · 5th Edition",
        ),
        (
            "Captures use the August 2026 console.",
            "Captures include the August 2026 console and refreshed 28 August 2026 "
            "live-night camera panels when RTSP hosts resolve.",
        ),
        (
            "Figure 7.1. Nominal monitoring view with evidence strip (MODEL / OF·mock / NET state) and KPI cards.",
            "Figure 7.1. Nominal monitoring view with evidence strip (MODEL / OF·mock / NET·NO EVIDENCE on Windows) and KPI cards.",
        ),
        (
            "Figure 7.2. PacketIn flood scenario: reconstruction-error chart, network inject controls, and intended mitigation panel.",
            "Figure 7.2. PacketIn flood inject: reconstruction-error rise and intended mitigation panel (mock OpenFlow on Windows).",
        ),
        (
            "Figure 7.3. Rush-hour network-label scenario emphasizing GT/PRED/MATCH honesty and preserve-oriented policy.",
            "Figure 7.3. Rush-hour network-label path with GT/PRED/MATCH honesty and preserve-oriented policy.",
        ),
        (
            "Figure 7.6. Live RTSP frames with YOLO object boxes (cars/motorcycles/persons). Object detection supporting fusion — not unusual-event AI.",
            "Figure 7.6. Live RTSP night frames (28 Aug 2026) with YOLO boxes. Object tracks support fusion only — not unusual-event AI or veh/h census.",
        ),
        (
            "Figure 7.7. Annotated live frame close-up used as physical-context evidence for fusion discussions.",
            "Figure 7.7. Fusion decision panel with live/scripted physical evidence and recommended action (preserve vs temporary contain).",
        ),
    ]

    # Longer paragraph rewrites (exact old → new)
    long_map = {
        # §3.7
        (
            "When physical_mode=rtsp_detector, RTSP frames are scored by YOLOv8 with an IoU tracker [15]. "
            "Exported fields emphasize visible_vehicle_tracks and context_reliability (heuristic composite). "
            "Occupancy and queue proxies are zone estimates, not surveyed meters. Object detection is not "
            "unusual-event or accident AI."
        ): (
            "When physical_mode=rtsp_detector, allow-listed RTSP frames are scored by YOLOv8 with an IoU "
            "tracker [15]. Hosts that fail DNS/TCP fall back to the last cached JPEG and/or scripted "
            "Cam·scenario buttons so demos remain reproducible. Exported fields emphasize "
            "visible_vehicle_tracks and context_reliability (heuristic composite). Occupancy and queue "
            "proxies are zone estimates, not surveyed meters. Object detection is not unusual-event or "
            "accident AI."
        ),
        # abstract camera sentence (partial replace inside abstract)
        (
            "while camera-fusion experiments currently provide scripted policy-validation evidence rather "
            "than labeled-video performance claims."
        ): (
            "while camera-fusion experiments provide scripted policy-validation evidence and, when RTSP "
            "hosts resolve, live object-track observation; labeled-video false-positive reduction is not claimed."
        ),
        # §6.5 intro if exact
        (
            "Experiments B/C validate explainable fusion rules on scripted physical contexts. Pass "
            "indicates policy wiring, not labeled-video false-positive reduction."
        ): (
            "Experiments B/C validate explainable fusion rules on scripted physical contexts; the "
            "operations console can additionally show live RTSP detector tracks when streams are "
            "reachable. Pass on B/C indicates policy wiring, not labeled-video false-positive reduction."
        ),
        # limitations bullet
        (
            "Camera fusion Exp B/C/D scripted pass ≠ labeled-video FP reduction."
        ): (
            "Camera fusion Exp B/C/D scripted pass ≠ labeled-video FP reduction; live RTSP tracks ≠ surveyed traffic counts."
        ),
    }

    for p in doc.paragraphs:
        t = p.text
        if not t.strip():
            continue
        for old, new in replacements:
            if t.strip() == old:
                replace_paragraph_text(p, new)
                log.append(f"caption/date: {old[:48]}…")
                break
        t = p.text
        for old, new in long_map.items():
            if old in t:
                replace_paragraph_text(p, t.replace(old, new))
                log.append(f"body: {old[:48]}…")
                break

    # Appendix D table: enrich D-live claim
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if cells and cells[0] == "D-live":
                # Camera source | Context modified | OpenFlow | Claim allowed
                if len(row.cells) >= 5:
                    # keep structure; update claim cell
                    for para in row.cells[4].paragraphs:
                        if para.runs:
                            set_run_text_keep_font(
                                para.runs[0],
                                "live detector/context availability (when RTSP resolves)",
                            )
                            for r in para.runs[1:]:
                                r.text = ""
                        elif para.text:
                            replace_paragraph_text(
                                para,
                                "live detector/context availability (when RTSP resolves)",
                            )
                    log.append("Appendix D D-live claim updated")
    return log


def target_emus(path: Path, max_w_cm: float = MAX_W_CM) -> tuple[int, int]:
    im = Image.open(path)
    w, h = im.size
    cx = int(max_w_cm * EMU_PER_CM)
    cy = int(cx * (h / w))
    return cx, cy


def jpeg_bytes(path: Path, max_side: int = 2200, quality: int = 85) -> bytes:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def replace_media_and_extents(docx: Path) -> list[str]:
    """Swap demo figures; fix extents so aspect stays correct."""
    log: list[str] = []
    # rId → new image path (from document.xml.rels mapping established earlier)
    # image4=rId12 Fig7.1, image5=rId13 Fig7.2, image6=rId14 Fig7.3,
    # image7=rId15 Fig7.4 keep or refresh, image8=rId16 Fig7.5 keep,
    # image9=rId17 Fig7.6 cameras, image10=rId18 Fig7.7 fusion
    mapping = {
        "word/media/image4.jpg": SLIDES / "slide_01_console_overview.jpg",
        "word/media/image5.jpg": SLIDES / "slide_05_re_chart_ddos.jpg",
        "word/media/image6.jpg": SLIDES / "slide_06_rush_hour_network.jpg",
        "word/media/image7.jpg": SLIDES / "slide_04_ddos_containment.jpg",
        # keep topology if no better; optional refresh with overview crop skipped
        "word/media/image9.jpg": SLIDES / "slide_02_live_cameras.jpg",
        "word/media/image10.jpg": SLIDES / "slide_03_fusion_rush_preserve.jpg",
    }
    if (COMPRESSED / "architecture.jpg").exists():
        mapping["word/media/image3.jpg"] = COMPRESSED / "architecture.jpg"

    tmp = ROOT / "tmp_docx_v5"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(docx) as zf:
        zf.extractall(tmp)

    # replace bytes
    for media, src in mapping.items():
        if not src.exists():
            log.append(f"missing {src.name}")
            continue
        dest = tmp / media
        if not dest.exists():
            log.append(f"no media slot {media}")
            continue
        data = jpeg_bytes(src)
        dest.write_bytes(data)
        log.append(f"replaced {media} ← {src.name} ({len(data)//1024} KB)")

    # fix extents for replaced figures using caption anchors
    doc_xml = (tmp / "word" / "document.xml").read_text(encoding="utf-8")
    caption_targets = {
        "Figure 7.1.": mapping["word/media/image4.jpg"],
        "Figure 7.2.": mapping["word/media/image5.jpg"],
        "Figure 7.3.": mapping["word/media/image6.jpg"],
        "Figure 7.4.": mapping["word/media/image7.jpg"],
        "Figure 7.6.": mapping["word/media/image9.jpg"],
        "Figure 7.7.": mapping["word/media/image10.jpg"],
    }
    if "word/media/image3.jpg" in mapping:
        caption_targets["Figure 3.1."] = mapping["word/media/image3.jpg"]

    def sub_last_extent(fragment: str, cx: int, cy: int) -> str:
        for tag in ("wp:extent", "a:ext"):
            pat = re.compile(rf"(<{tag}\b[^>]*\bcx=\")\d+(\"\s+cy=\")\d+(\")")
            matches = list(pat.finditer(fragment))
            if matches:
                m = matches[-1]
                fragment = (
                    fragment[: m.start()]
                    + m.group(1)
                    + str(cx)
                    + m.group(2)
                    + str(cy)
                    + m.group(3)
                    + fragment[m.end() :]
                )
        return fragment

    for caption, img_path in caption_targets.items():
        pos = doc_xml.find(caption)
        if pos < 0:
            # captions may already be updated — try shorter keys
            log.append(f"caption not found for extent: {caption}")
            continue
        if not img_path.exists():
            continue
        # Fig 7.6 was tall; new live panel is landscape — use full width
        max_w = 15.0 if "7.6" in caption or "7.7" in caption or "3.1" in caption else 15.0
        cx, cy = target_emus(img_path, max_w_cm=max_w)
        window_start = max(0, pos - 14000)
        head, mid, tail = doc_xml[:window_start], doc_xml[window_start:pos], doc_xml[pos:]
        mid2 = sub_last_extent(mid, cx, cy)
        if mid2 != mid:
            log.append(f"extent {caption} → {cx}x{cy} EMU")
        doc_xml = head + mid2 + tail

    (tmp / "word" / "document.xml").write_text(doc_xml, encoding="utf-8")

    # pack
    if docx.exists():
        docx.unlink()
    with zipfile.ZipFile(docx, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in tmp.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(tmp).as_posix())
    shutil.rmtree(tmp, ignore_errors=True)
    return log


def verify(docx: Path) -> None:
    doc = Document(str(docx))
    text = "\n".join(p.text for p in doc.paragraphs)
    checks = {
        "5th Edition": "5th Edition" in text,
        "Prototype-Backed": "Prototype-Backed" in text,
        "no @Grab": "@Grab" not in text,
        "Grab intern": "Software Engineering Intern, Grab" in text
        or "Software Engineering Intern, Grab" in "\n".join(
            "|".join(c.text for c in row.cells) for t in doc.tables[:1] for row in t.rows
        ),
        "live night fig": "28 Aug 2026" in text or "live-night" in text,
        "Times body": doc.styles["Normal"].font.name == "Times New Roman",
    }
    print("verify:", checks)
    print("paragraphs", len(doc.paragraphs), "tables", len(doc.tables))
    assert checks["5th Edition"] and checks["Prototype-Backed"] and checks["no @Grab"]


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing source: {SRC}")
    shutil.copyfile(SRC, OUT)
    print(f"copied → {OUT.name}")

    doc = Document(str(OUT))
    log = patch_texts(doc)
    doc.save(str(OUT))
    for line in log:
        print("text:", line)

    media_log = replace_media_and_extents(OUT)
    for line in media_log:
        print("media:", line)

    verify(OUT)
    OUT_DOCS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT, OUT_DOCS)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    print(f"copied {OUT_DOCS}")


if __name__ == "__main__":
    main()
