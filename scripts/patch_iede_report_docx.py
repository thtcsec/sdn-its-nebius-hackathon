#!/usr/bin/env python
"""Patch Trinh Hoang Tu_3rd Version.docx with architecture + Exp A/B-C/D honesty tables."""

from __future__ import annotations

import shutil
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Trinh Hoang Tu_3rd Version.backup.docx"
if not SRC.exists():
    SRC = ROOT / "Trinh Hoang Tu_3rd Version.docx"
OUT_MAIN = ROOT / "Trinh Hoang Tu_3rd Version.docx"
OUT_DOCS = ROOT / "docs" / "IEDE_Project_Report_Prototype.docx"
ARCH = ROOT / "architecture.png"


def set_run_font(run, name="Times New Roman", size=12, bold=False, italic=False):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def _fmt(para: Paragraph, *, indent=True, center=False, space_after=6):
    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    para.paragraph_format.space_after = Pt(space_after)
    para.paragraph_format.first_line_indent = Cm(0.75) if indent else Cm(0)
    if center:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return para


def insert_paragraph_after(paragraph: Paragraph, text: str = "", *, style=None) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if style is not None:
        new_para.style = style
    if text:
        run = new_para.add_run(text)
        set_run_font(run, size=12 if (style is None or not str(style).startswith("Heading")) else (16 if style == "Heading 1" else 14), bold=str(style).startswith("Heading") if style else False)
    return new_para


def fill_para(para: Paragraph, text: str, *, size=12, bold=False, italic=False, indent=True, center=False, space_after=6):
    # clear existing runs
    for r in list(para.runs):
        r._element.getparent().remove(r._element)
    _fmt(para, indent=indent, center=center, space_after=space_after)
    run = para.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic)
    return para


def find_para(doc: Document, predicate):
    for p in doc.paragraphs:
        if predicate(p.text or "", p.style.name if p.style else ""):
            return p
    return None


def find_para_exact(doc: Document, text: str):
    return find_para(doc, lambda t, s: t.strip() == text)


def find_para_startswith(doc: Document, prefix: str):
    return find_para(doc, lambda t, s: t.strip().startswith(prefix))


def insert_heading_after(anchor: Paragraph, text: str, level: int) -> Paragraph:
    style = f"Heading {level}"
    p = insert_paragraph_after(anchor, "", style=style)
    fill_para(p, text, size=16 if level == 1 else 14 if level == 2 else 12, bold=True, indent=False, space_after=6)
    p.style = style
    return p


def insert_body_after(anchor: Paragraph, text: str, *, indent=True) -> Paragraph:
    p = insert_paragraph_after(anchor, "")
    fill_para(p, text, indent=indent)
    return p


def insert_bullet_after(anchor: Paragraph, text: str) -> Paragraph:
    p = insert_paragraph_after(anchor, "", style="List Bullet")
    fill_para(p, text, indent=False)
    p.style = "List Bullet"
    return p


def insert_number_after(anchor: Paragraph, text: str) -> Paragraph:
    p = insert_paragraph_after(anchor, "", style="List Number")
    fill_para(p, text, indent=False)
    p.style = "List Number"
    return p


def insert_caption_after(anchor: Paragraph, text: str) -> Paragraph:
    p = insert_paragraph_after(anchor, "")
    fill_para(p, text, size=11, italic=True, indent=False, center=True, space_after=12)
    return p


def insert_picture_after(anchor: Paragraph, path: Path, width_cm: float = 15.5) -> Paragraph:
    p = insert_paragraph_after(anchor, "")
    _fmt(p, indent=False, center=True, space_after=6)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(str(path), width=Cm(width_cm))
    return p


def insert_table_after(anchor: Paragraph, headers, rows, col_widths=None) -> Paragraph:
    """Insert a table after anchor; returns a spacer paragraph after the table."""
    # Create table at document end, then move XML after anchor
    doc = anchor.part.document
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(h)
        set_run_font(run, size=10, bold=True)
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            cell = table.rows[r_i + 1].cells[c_i]
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(val))
            set_run_font(run, size=10)
    if col_widths:
        for row in table.rows:
            for idx, w in enumerate(col_widths):
                row.cells[idx].width = Cm(w)

    tbl = table._tbl
    # remove from current location (end) and place after anchor
    tbl.getparent().remove(tbl)
    anchor._p.addnext(tbl)

    # spacer paragraph after table
    spacer = OxmlElement("w:p")
    tbl.addnext(spacer)
    return Paragraph(spacer, anchor._parent)


def add_row(table, cells: list[str]):
    row = table.add_row()
    for i, val in enumerate(cells):
        row.cells[i].text = ""
        run = row.cells[i].paragraphs[0].add_run(val)
        set_run_font(run, size=11)
    return row


def patch() -> Path:
    if not SRC.exists():
        raise SystemExit(f"missing source: {SRC}")
    if not ARCH.exists():
        raise SystemExit(f"missing architecture figure: {ARCH}")

    doc = Document(str(SRC))

    # --- Cover date ---
    for p in doc.paragraphs:
        if (p.text or "").strip() == "July, 2026":
            fill_para(p, "August, 2026", indent=False, center=True, bold=False)
            break

    # --- Abstract ---
    abs_h = find_para_exact(doc, "Abstract")
    if abs_h is not None:
        body = None
        seen_abs = False
        for p in doc.paragraphs:
            if p._p is abs_h._p:
                seen_abs = True
                continue
            if seen_abs and (p.text or "").strip():
                body = p
                break
        if body is not None:
            t = body.text or ""
            extra = (
                " The prototype further fuses SDN alerts with edge camera context "
                "(visible_vehicle_tracks, occupancy/queue proxies, context_reliability) "
                "and grades evidence as scripted fusion wiring versus live observation "
                "versus OpenFlow switch outcomes (Experiments A–D)."
            )
            if "visible_vehicle_tracks" not in t:
                fill_para(body, t.rstrip() + extra)

    # --- RQ5 ---
    rq4 = find_para_startswith(doc, "RQ4:")
    if rq4 is not None:
        # only add once
        already = any((p.text or "").startswith("RQ5:") for p in doc.paragraphs)
        if not already:
            insert_number_after(
                rq4,
                "RQ5: How can multimodal fusion distinguish rush-hour surges from single-source floods "
                "without treating camera tracks as calibrated traffic counts?",
            )

    # --- Contributions ---
    contrib = find_para_exact(doc, "1.3 Contributions of This Prototype")
    if contrib is not None:
        insdn = find_para_startswith(doc, "InSDN download/prepare")
        if insdn is not None and "Explainable camera" not in "\n".join(x.text or "" for x in doc.paragraphs):
            b1 = insert_bullet_after(
                insdn,
                "Explainable camera–network fusion with injectable FusionThresholds (sensitivity-checked).",
            )
            insert_bullet_after(
                b1,
                "Graded experiments: Exp A (Mininet OpenFlow), B/C (scripted fusion), D (live vs scripted camera arms).",
            )

    # --- Section 2 architecture figure ---
    arch_caption_exists = any("Prototype software architecture" in (p.text or "") for p in doc.paragraphs)
    s2_note = find_para_startswith(doc, "The demonstration path uses a Flask REST")
    if s2_note is not None and not arch_caption_exists:
        cur = insert_body_after(
            s2_note,
            "Figure 7 summarises the implemented software path. Edge cameras feed Fusion in parallel with "
            "network scoring (they are not upstream of the ITS data plane). Actuation is split between a "
            "Mininet/OpenFlow lab path (Experiment A) and a Windows in-memory mock channel for demos.",
        )
        pic = insert_picture_after(cur, ARCH, width_cm=15.8)
        insert_caption_after(
            pic,
            "Figure 7. Prototype software architecture: parallel camera context + SDN telemetry → "
            "TCN-GRU → multimodal fusion → policy → temporary OpenFlow (lab) / in-memory rules (Windows demo).",
        )

    # --- Software stack table (first tech table after 3.1) ---
    # Table index 1 in original is Layer/Technology
    if len(doc.tables) >= 2:
        t1 = doc.tables[1]
        hdr = (t1.rows[0].cells[0].text or "").strip().lower()
        if hdr.startswith("layer"):
            existing = " ".join((r.cells[0].text or "") for r in t1.rows).lower()
            if "edge camera" not in existing:
                add_row(t1, ["Edge camera", "RTSP allow-list → YOLO+IoU (detector_tracker_v1) or synthetic"])
            if "fusion" not in existing:
                add_row(t1, ["Fusion", "Rule-based FusionEngine + injectable FusionThresholds"])

    # --- Policy matrix ---
    if len(doc.tables) >= 3:
        t2 = doc.tables[2]
        hdr = (t2.rows[0].cells[0].text or "").strip().lower()
        if "alert" in hdr:
            blob = " ".join((r.cells[0].text or "") for r in t2.rows).lower()
            if "rush + ddos" not in blob and "mixed congestion" not in blob:
                add_row(
                    t2,
                    [
                        "DDoS + rush (low dominance)",
                        "preserve / IGNORE",
                        "Fusion FP avoidance",
                    ],
                )
                add_row(
                    t2,
                    [
                        "DDoS + stable camera",
                        "DROP + THROTTLE",
                        "No matching physical surge",
                    ],
                )

    # --- Section 4 date ---
    s4_intro = find_para_startswith(doc, "This section documents the working prototype UI captured")
    if s4_intro is not None:
        fill_para(
            s4_intro,
            "This section documents the working prototype UI captured at http://127.0.0.1:8080/ "
            "(screenshots initially 30 July 2026; architecture and camera-metric labels updated August 2026). "
            "Camera cards now report visible_vehicle_tracks and context_reliability rather than a fake confidence score.",
        )

    # --- After 4.6 content: new subsections 4.7 / 4.8 (text-only if no new screens) ---
    fig6 = find_para_startswith(doc, "Figure 6. Lower console region")
    if fig6 is not None and not any("4.7 Camera context" in (p.text or "") for p in doc.paragraphs):
        h = insert_heading_after(fig6, "4.7 Camera Context Metrics (Honesty Labels)", 2)
        b = insert_body_after(
            h,
            "The ops console camera cards expose detector/tracker outputs with explicit provenance: "
            "Tracks (= visible_vehicle_tracks, in-view IoU tracks — not veh/h), occupancy and queue_length_proxy_m "
            "(zone proxies — not surveyed meters), and context_reliability (heuristic composite — not calibrated "
            "P(correct)). vehicle_flow_count is reserved for a future line-crossing tracker. "
            "Re-capture a Cam-panel screenshot into assets/images/report/ when preparing the final PDF dossier.",
        )
        h2 = insert_heading_after(b, "4.8 PacketIn Inject vs Camera Physical Override", 2)
        insert_body_after(
            h2,
            "Console PacketIn flood buttons inject network alerts; Cam · * buttons override physical context "
            "(synthetic). Fusion joins both. A rush-hour camera context with low source dominance yields "
            "preserve_rush_hour; stable camera + high dominance yields temporary containment. "
            "This separation is required so reviewers do not treat network inject alone as camera evidence.",
        )

    # --- Section 5 expansions ---
    abl = find_para_exact(doc, "5.3 Ablation Snapshot")
    # Insert new results BEFORE ablation by anchoring on the paragraph before 5.3
    # Find 5.2 closing note
    lat_note = find_para_startswith(doc, "Console-side inference percentiles")
    anchor = lat_note or find_para_exact(doc, "5.2 Latency & Footprint")
    if anchor is not None and not any("5.3 OpenFlow containment" in (p.text or "") for p in doc.paragraphs):
        # Rename old 5.3 Ablation → will insert new 5.3–5.5 then retitle ablation to 5.6
        if abl is not None:
            fill_para(abl, "5.6 Ablation Snapshot", size=14, bold=True, indent=False)
            abl.style = "Heading 2"

        h = insert_heading_after(anchor, "5.3 OpenFlow Containment (Experiment A)", 2)
        b = insert_body_after(
            h,
            "Experiment A exercises reversible mitigation on a Mininet ITS-edge topology with ovs-ofctl "
            "verification (network_evidence=true). Metrics are ICMP delivery ratios (data plane), not controller PacketIn/s.",
        )
        sp = insert_table_after(
            b,
            ["Arm", "Legit delivery", "Attack delivery", "Switch dump", "Rollback"],
            [
                ["none", "0.95", "1.00", "—", "—"],
                ["permanent DROP", "0.85", "0.00", "verified", "n/a"],
                ["temporary (during)", "1.00", "0.00", "verified", "—"],
                ["after DELETE", "0.95", "1.00", "rule cleared", "~5.0 ms"],
            ],
            col_widths=[4.0, 3.0, 3.2, 2.8, 2.5],
        )
        note = insert_caption_after(
            sp,
            "Table. Experiment A — ICMP delivery under mitigation arms (artifacts/results/exp_a/exp_a_metrics.json).",
        )

        h = insert_heading_after(note, "5.4 Camera Fusion & Threshold Sensitivity (Experiments B/C)", 2)
        b = insert_body_after(
            h,
            "Experiments B/C validate explainable fusion rules on scripted physical contexts "
            "(pass = rule wiring, not labeled-video false-positive reduction). "
            "Sensitivity injects FusionThresholds so mid-dominance actions actually flip.",
        )
        sp = insert_table_after(
            b,
            ["Case", "Dominance", "Recommended action"],
            [
                ["Legitimate surge (rush)", "0.30", "preserve_rush_hour"],
                ["PacketIn flood (stable cam)", "0.82", "temporary_drop"],
                ["Mixed rush + attack", "0.82", "isolate source (temporary_drop)"],
            ],
            col_widths=[6.0, 3.0, 6.5],
        )
        note = insert_caption_after(sp, "Table. Experiment B/C fusion outcomes (scripted physical inputs).")
        b = insert_body_after(
            note,
            "Sensitivity sweep at fixed probe dominance = 0.62 (dominance_mixed_isolate / dominance_stable_contain):",
        )
        sp = insert_table_after(
            b,
            ["Threshold", "Rush+DDoS @0.62", "Rush @0.30", "Stable+DDoS @0.60"],
            [
                ["0.55", "temporary_drop", "preserve_rush_hour", "temporary_drop"],
                ["0.65", "preserve_rush_hour", "preserve_rush_hour", "rate_limit"],
                ["0.75", "preserve_rush_hour", "preserve_rush_hour", "rate_limit"],
                ["0.85", "preserve_rush_hour", "preserve_rush_hour", "rate_limit"],
            ],
            col_widths=[2.8, 4.2, 4.2, 4.2],
        )
        note = insert_caption_after(
            sp,
            "Table. Fusion threshold sensitivity — actions vary with injected cutoffs "
            "(artifacts/results/exp_bc/exp_bc_sensitivity.json).",
        )

        h = insert_heading_after(note, "5.5 Experiment D — Graded Camera Evidence", 2)
        b = insert_body_after(
            h,
            "Experiment D separates an unmodified live/synthetic observation arm from an explicitly scripted "
            "congestion arm. pass_scripted_rules only proves fusion/policy wiring on forced congestion inputs.",
        )
        sp = insert_table_after(
            b,
            ["Flag", "Value", "Meaning"],
            [
                ["pass_scripted_rules", "true", "Scripted congestion → preserve then contain"],
                ["detector_live", "false*", "*this artifact run (synthetic source)"],
                ["physical_context_modified", "true", "Scripted arm uses forced rush context"],
                ["openflow_evidence", "false", "No cam→switch outcome without --with-of"],
                ["evidence_grade", "scripted", "Not live congestion proof"],
            ],
            col_widths=[5.0, 3.5, 7.0],
        )
        insert_caption_after(
            sp,
            "Table. Experiment D evidence grades (artifacts/results/exp_d/exp_d_phases.json).",
        )

    # --- Detection quality honesty note (immediately before 5.2) ---
    s52 = find_para_exact(doc, "5.2 Latency & Footprint")
    if s52 is not None:
        # Find previous paragraph to append after (content before 5.2 heading)
        prev = None
        for p in doc.paragraphs:
            if p == s52:
                break
            prev = p
        already = any("InSDN-shaped holdout" in (p.text or "") for p in doc.paragraphs)
        if prev is not None and not already:
            # Insert note after prev (= after metrics table / intro), which sits just before 5.2 in reading order
            # But insert_paragraph_after(prev) places it after prev; if prev is last body before 5.2, good.
            # If we insert after prev and prev is not the immediate predecessor XML-wise of s52, order can drift.
            # Safest: insert the note paragraph before s52 via XML.
            note_p = OxmlElement("w:p")
            s52._p.addprevious(note_p)
            note_para = Paragraph(note_p, s52._parent)
            fill_para(
                note_para,
                "Note: Table values above are synthetic/demo separation used in the IEDE summary. "
                "On an InSDN-shaped holdout (n=7500, classifier head), the prototype reports approximately "
                "cls accuracy 96.2%, precision 96.0%, recall 99.5%, F1 97.7%, ROC-AUC 0.977, "
                "IDL ≈ 6.45 ms and T_response ≈ 9.95 ms (artifacts/results/exp_insdn/metrics.json). "
                "Cross-dataset CIC zero-shot remains weak and is not claimed as a primary result.",
            )

    # --- Limitations ---
    lim = find_para_exact(doc, "6. Discussion & Limitations")
    if lim is not None:
        # update first OF bullet
        of_b = find_para_startswith(doc, "OpenFlow actuation in the Windows demo")
        if of_b is not None and "Experiment A" not in (of_b.text or ""):
            fill_para(
                of_b,
                "OpenFlow actuation in the Windows demo path is mocked; Experiment A provides Mininet/"
                "ovs-ofctl network evidence on Linux/WSL. Production PacketIn/s still needs a Ryu path.",
                indent=False,
            )
            of_b.style = "List Bullet"
        # add honesty bullets once
        if not any("visible_vehicle_tracks" in (p.text or "") and "traffic census" in (p.text or "") for p in doc.paragraphs):
            last_lim = find_para_startswith(doc, "Public InSDN labels approximate")
            if last_lim is not None:
                a = insert_bullet_after(
                    last_lim,
                    "visible_vehicle_tracks are in-view tracks, not a traffic census (veh/h); "
                    "context_reliability is a heuristic composite, not calibrated accuracy.",
                )
                a = insert_bullet_after(
                    a,
                    "Experiments B/C/D scripted pass ≠ labeled-video false-positive reduction; "
                    "Experiment D without --with-of does not prove camera→switch closed loop.",
                )

    # --- Conclusion ---
    conc = find_para_startswith(doc, "The SDN-ITS Resilience prototype demonstrates")
    if conc is not None and "Experiment A" not in (conc.text or ""):
        fill_para(
            conc,
            (conc.text or "").rstrip()
            + " Recent evidence adds reversible OpenFlow containment (Exp A), explainable camera–network "
            "fusion with threshold sensitivity (Exp B/C), and graded camera evidence arms (Exp D).",
        )

    # --- Appendix callouts ---
    if len(doc.tables) >= 1:
        # last table is often annotation guide
        t_last = doc.tables[-1]
        if (t_last.rows[0].cells[0].text or "").strip().lower().startswith("figure"):
            blob = " ".join((r.cells[0].text or "") for r in t_last.rows)
            if "Fig. 7" not in blob and "Fig 7" not in blob:
                add_row(
                    t_last,
                    [
                        "Fig. 7",
                        "A Parallel cameras · B Data plane · C Telemetry/AI · D Fusion · E Policy · F Lab vs mock OF · G Console",
                    ],
                )
                add_row(
                    t_last,
                    [
                        "§4.7–4.8",
                        "Tracks/rel honesty · PacketIn network inject ≠ Cam physical override",
                    ],
                )

    # Save
    OUT_MAIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_DOCS.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_MAIN))
    shutil.copyfile(OUT_MAIN, OUT_DOCS)
    return OUT_MAIN


def verify(path: Path) -> None:
    doc = Document(str(path))
    checks = [
        "August, 2026",
        "visible_vehicle_tracks",
        "RQ5:",
        "Figure 7.",
        "5.3 OpenFlow Containment",
        "5.4 Camera Fusion",
        "5.5 Experiment D",
        "5.6 Ablation Snapshot",
        "4.7 Camera Context",
    ]
    text = "\n".join(p.text or "" for p in doc.paragraphs)
    print(f"verify {path.name}: paras={len(doc.paragraphs)} tables={len(doc.tables)} images="
          f"{sum(1 for r in doc.part.rels.values() if 'image' in r.reltype)}")
    for c in checks:
        ok = c in text
        print(f"  [{'OK' if ok else 'MISSING'}] {c}")
    # ensure doc opens and tables readable
    for _i, t in enumerate(doc.tables):
        _ = [[c.text for c in row.cells] for row in t.rows]


if __name__ == "__main__":
    # Prefer pristine backup as source so re-runs are idempotent-ish
    if not (ROOT / "Trinh Hoang Tu_3rd Version.backup.docx").exists():
        shutil.copyfile(OUT_MAIN, ROOT / "Trinh Hoang Tu_3rd Version.backup.docx")
    out = patch()
    verify(out)
    print(f"wrote {out}")
    print(f"wrote {OUT_DOCS}")
