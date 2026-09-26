#!/usr/bin/env python
"""Refresh InSDN table numbers in the IEDE Word draft from the split-safe rerun."""

from __future__ import annotations

import shutil
from pathlib import Path

import _bootstrap  # noqa: F401
from docx import Document

from sdn_its.utils.paths import PROJECT_ROOT

SRC = PROJECT_ROOT / "Trinh Hoang Tu_6th Version.docx"
BACKUP = PROJECT_ROOT / "Trinh Hoang Tu_6th Version.pre_metrics.docx"
OUTS = [
    PROJECT_ROOT / "Trinh Hoang Tu_6th Version.docx",
    PROJECT_ROOT / "docs" / "IEDE_Project_Report_Prototype.docx",
]

WINDOW_OLD_PREFIX = "Sliding windows use seq_len L=10"
WINDOW_NEW = (
    "Sliding windows use seq_len L=10 with stride 1. Protocol rows_before_window_v1 "
    "(seed 42): 50,000 InSDN rows were partitioned before windowing, with a gap of "
    "L−1 rows. Resulting windows: train 34,978 / validation 7,488 / test 7,489. "
    "StandardScaler was fit on the training partition only. Table values below are "
    "binary classifier-head metrics (Normal vs anomaly; sklearn average='binary'), "
    "not 5-class macro scores. This subsample contains only Normal and "
    "DDoS_PacketIn_Flood. The reported checkpoint is epoch 8, saved before training "
    "loss became NaN."
)

CELL_MAP = {
    "96.21%": "96.02%",
    "95.95%": "95.69%",
    "99.47%": "99.52%",
    "97.68%": "97.56%",
    "0.977": "0.975",
    "~0.25 ms": "~0.16 ms",
    "~6.45 ms": "~6.36 ms",
    "~9.95 ms": "~9.86 ms",
    "F1≈97.7%, AUC≈0.977": "F1≈97.6%, AUC≈0.975; n=7,489; binary",
}


def _set_paragraph_text(paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def _replace_cells(doc: Document) -> int:
    n = 0
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                raw = cell.text.strip()
                if raw in CELL_MAP:
                    _set_paragraph_text(cell.paragraphs[0], CELL_MAP[raw])
                    for extra in cell.paragraphs[1:]:
                        _set_paragraph_text(extra, "")
                    n += 1
    return n


def patch(src: Path) -> int:
    doc = Document(str(src))
    replaced = _replace_cells(doc)
    for para in doc.paragraphs:
        if (para.text or "").startswith(WINDOW_OLD_PREFIX):
            _set_paragraph_text(para, WINDOW_NEW)
            break
    return replaced, doc


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"missing {SRC}")
    if not BACKUP.is_file():
        shutil.copy2(SRC, BACKUP)
    replaced, doc = patch(BACKUP)
    for out in OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))
        print(f"[+] {out.name} cells={replaced}")


if __name__ == "__main__":
    main()
