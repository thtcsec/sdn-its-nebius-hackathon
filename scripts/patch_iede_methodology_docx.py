#!/usr/bin/env python
"""Light methodology fixes for the IEDE Word proposal (python-docx).

Targets local (gitignored) drafts such as:
  Trinh Hoang Tu_5th Version.docx

Fixes:
  - CIC-IDS2018 wording → CIC-IDS2017 where it refers to *this* experiment
  - RQ2 “competitive” → “useful in-domain”
  - Inject / reinforce split-before-window leakage paragraph
  - Tighten a few known reference titles
  - Table row keep-together + prevent split across pages (best-effort)
  - Bump footer note to remind TOC/field update in Word

Usage:
  pip install -e ".[report]"
  python scripts/patch_iede_methodology_docx.py
  python scripts/patch_iede_methodology_docx.py --src "Trinh Hoang Tu_5th Version.docx"
"""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap  # noqa: F401

from sdn_its.utils.paths import PROJECT_ROOT

REPLACEMENTS = [
    (
        re.compile(r"CSE-CIC-IDS2018", re.I),
        "CIC-IDS2017",
    ),
    (
        re.compile(r"CIC-family datasets", re.I),
        "CIC-IDS2017 (cross-dataset holdout)",
    ),
    (
        re.compile(
            r"maintaining competitive anomaly-detection performance",
            re.I,
        ),
        "maintaining useful in-domain anomaly-detection performance",
    ),
    (
        re.compile(
            r"Can a lightweight time-series AI model detect control-plane flooding, "
            r"abnormal flow behavior, and network faults under edge latency constraints\?",
            re.I,
        ),
        "Can a lightweight TCN-GRU model satisfy prototype edge-level latency and "
        "memory constraints while maintaining useful in-domain anomaly-detection performance?",
    ),
    (
        re.compile(
            r"Enhancing IEEE 802\.11p/WAVE for infotainment in VANETs",
            re.I,
        ),
        "Enhancing IEEE 802.11p/WAVE to provide infotainment applications in VANETs",
    ),
]

LEAKAGE_PARAGRAPH = (
    "Data splitting and leakage prevention. Raw records were partitioned into mutually "
    "exclusive training, validation, and test subsets before sliding-window construction "
    "(protocol rows_before_window_v1). A gap of (L−1) rows separates partitions so that "
    "overlapping windows (L=10, stride 1) cannot span train/test boundaries. StandardScaler "
    "statistics were fitted exclusively on the training partition and applied unchanged to "
    "validation and test data. Reported cls_binary_* metrics are binary Normal-vs-Anomaly "
    "scores (sklearn average='binary'), not 5-class macro F1/AUC; multiclass macro/weighted "
    "and OvR AUC are exported separately by evaluate.py. Default loss weight α=1.0 and "
    "threshold k=2.0; seed=42. See docs/METHODOLOGY.md."
)

METRIC_CLARIFIER = (
    "Metric definition note. Primary detection tables cite classifier-head binary metrics "
    "(prediction = argmax(class) > 0). Precision/Recall/F1 use sklearn average='binary'; "
    "ROC-AUC uses score = Σ P(class ≠ Normal). Do not interpret these as multiclass macro averages."
)


def _iter_paragraphs(doc):
    for p in doc.paragraphs:
        yield p
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def _replace_in_runs(paragraph, pattern: re.Pattern, repl: str) -> int:
    # Simple whole-paragraph replace when pattern matches concatenated text
    text = paragraph.text or ""
    if not pattern.search(text):
        return 0
    new_text = pattern.sub(repl, text)
    if new_text == text:
        return 0
    # Rewrite into first run; clear others (keeps some style)
    if paragraph.runs:
        paragraph.runs[0].text = new_text
        for r in paragraph.runs[1:]:
            r.text = ""
    else:
        paragraph.add_run(new_text)
    return 1


def _ensure_paragraph_after_heading(doc, heading_substr: str, body: str) -> bool:
    paras = list(doc.paragraphs)
    for i, p in enumerate(paras):
        if heading_substr.lower() in (p.text or "").lower():
            # Skip if already present nearby
            window = paras[i : i + 8]
            if any("rows_before_window_v1" in (x.text or "") for x in window):
                return False
            # Insert by adding after this paragraph via XML clone trick:
            new_p = doc.add_paragraph(body)
            # Move new_p XML element to follow heading
            p._p.addnext(new_p._p)
            return True
    # Fallback append
    doc.add_paragraph(body)
    return True


def _fix_tables(doc) -> int:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    n = 0
    for table in doc.tables:
        tbl = table._tbl
        tbl_pr = tbl.tblPr
        if tbl_pr is None:
            tbl_pr = OxmlElement("w:tblPr")
            tbl.insert(0, tbl_pr)
        # Prefer not to split rows across pages
        for row in table.rows:
            tr = row._tr
            tr_pr = tr.get_or_add_trPr()
            cant = tr_pr.find(qn("w:cantSplit"))
            if cant is None:
                cant = OxmlElement("w:cantSplit")
                tr_pr.append(cant)
            n += 1
    return n


def _bump_footer(doc, note: str) -> None:
    for section in doc.sections:
        footer = section.footer
        if footer.paragraphs:
            footer.paragraphs[0].text = note
        else:
            footer.add_paragraph(note)


def patch(src: Path, dst: Path) -> dict:
    from docx import Document

    shutil.copy2(src, dst)
    doc = Document(str(dst))
    stats = {"replacements": 0, "tables_rows": 0, "injected": False}

    for p in _iter_paragraphs(doc):
        for pattern, repl in REPLACEMENTS:
            stats["replacements"] += _replace_in_runs(p, pattern, repl)

    stats["injected"] = _ensure_paragraph_after_heading(
        doc, "Data", LEAKAGE_PARAGRAPH
    ) or _ensure_paragraph_after_heading(doc, "Method", LEAKAGE_PARAGRAPH)

    # Metric clarifier near evaluation / results if present
    for key in ("Evaluation", "Results", "Detection"):
        if any(key.lower() in (p.text or "").lower() for p in doc.paragraphs):
            _ensure_paragraph_after_heading(doc, key, METRIC_CLARIFIER)
            break

    stats["tables_rows"] = _fix_tables(doc)
    _bump_footer(
        doc,
        f"Methodology patch {datetime.now(timezone.utc).strftime('%Y-%m-%d')} UTC — "
        "Update TOC/fields in Word (Ctrl+A, F9). Dataset: CIC-IDS2017. See docs/METHODOLOGY.md.",
    )
    doc.save(str(dst))
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--src",
        default="Trinh Hoang Tu_5th Version.docx",
        help="Source DOCX (gitignored local draft)",
    )
    parser.add_argument(
        "--dst",
        default=None,
        help="Output path (default: <stem>_methodology_patched.docx)",
    )
    args = parser.parse_args()
    src = Path(args.src)
    if not src.is_absolute():
        src = PROJECT_ROOT / src
    if not src.is_file():
        raise SystemExit(f"DOCX not found: {src}")
    dst = Path(args.dst) if args.dst else src.with_name(src.stem + "_methodology_patched.docx")
    if not dst.is_absolute():
        dst = PROJECT_ROOT / dst
    stats = patch(src, dst)
    print(f"[+] Wrote {dst.relative_to(PROJECT_ROOT)}")
    print(f"[+] stats={stats}")
    print("[!] Open in Word → select all → F9 to refresh TOC/fields.")


if __name__ == "__main__":
    main()
