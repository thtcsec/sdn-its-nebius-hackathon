#!/usr/bin/env python
"""Narrative patch for 5th Edition: RSU-zone cyber-physical mitigation story.

Preserves fonts by rewriting first-run text only. Does not rebuild the DOCX.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Trinh Hoang Tu_5th Version.docx"
OUT = ROOT / "Trinh Hoang Tu_5th Version.docx"
BAK = ROOT / "Trinh Hoang Tu_5th Version.pre_narrative.docx"


def put(paragraph, text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(text)
        return
    paragraph.runs[0].text = text
    for r in paragraph.runs[1:]:
        r.text = ""
    r0 = paragraph.runs[0]
    if r0._element.rPr is not None and r0._element.rPr.rFonts is not None:
        r0._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        r0._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        r0._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")


def replace_exact(doc: Document, old: str, new: str) -> bool:
    for p in doc.paragraphs:
        if p.text.strip() == old.strip():
            put(p, new)
            return True
    return False


def replace_contains(doc: Document, needle: str, new: str) -> bool:
    for p in doc.paragraphs:
        if needle in p.text:
            put(p, new)
            return True
    return False


def patch_table_cell(doc: Document, row0: str, col: int, new: str) -> bool:
    for table in doc.tables:
        for row in table.rows:
            if row.cells[0].text.strip().startswith(row0):
                cell = row.cells[col]
                if cell.paragraphs and cell.paragraphs[0].runs:
                    put(cell.paragraphs[0], new)
                    for para in cell.paragraphs[1:]:
                        for r in para.runs:
                            r.text = ""
                else:
                    cell.text = new
                return True
    return False


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    shutil.copyfile(SRC, BAK)

    doc = Document(str(SRC))
    log: list[str] = []

    def ok(name: str, done: bool) -> None:
        log.append(("OK " if done else "MISS ") + name)

    # --- Cover subtitle (title unchanged) ---
    ok(
        "subtitle",
        replace_exact(
            doc,
            "A Lightweight Framework for V2X Network Reliability, Edge Telemetry, and Safety-Aware Mitigation",
            "Network Anomaly Detection, Reversible Mitigation, and Camera-Assisted Physical Context",
        ),
    )

    # --- Abstract ---
    abstract_new = (
        "Software-defined networking enables programmable control for intelligent transportation "
        "systems, but its logically centralized control plane remains vulnerable to flooding attacks, "
        "low-rate probing, and controller overload. The protected asset in this study is RSU-based "
        "ITS/V2X connectivity: an attacker aims to exhaust control-plane or edge-network resources and "
        "degrade legitimate vehicle-to-infrastructure communication. Permanent blacklist or DROP "
        "responses can also harm legitimate mobility traffic during rush-hour surges that elevate the "
        "same coarse counters used for intrusion signals. This research proposes a lightweight "
        "resilience framework that combines flow-level telemetry, temporal anomaly detection, adaptive "
        "thresholding, and reversible OpenFlow mitigation. A hybrid TCN-GRU model processes short "
        "telemetry windows without deep packet inspection, while a safety-aware policy applies "
        "temporary containment and automatic rollback rather than permanent blocking. A camera covering "
        "the same RSU service zone provides an independent physical observation that helps the policy "
        "judge whether abnormal network demand is consistent with observable transportation activity; "
        "the camera does not inspect packets and must not override network evidence. A prototype "
        "operations console and reproducible experiments assess detection quality, response latency, "
        "reversible containment, and fusion-policy behavior. Preliminary evaluation on an InSDN-shaped "
        "holdout reports classifier-head accuracy of 96.2%, F1-score of approximately 97.7%, and "
        "ROC-AUC of 0.977, with a decision-path response time below 10 ms in the evaluated environment. "
        "Mininet experiments demonstrate temporary rule installation and rollback. Camera-fusion "
        "experiments provide scripted policy-validation evidence and, when RTSP hosts resolve, live "
        "object-track observation; labeled-video false-positive reduction is not claimed. These results "
        "support technical feasibility and define remaining work for transportation-scale validation."
    )
    ok("abstract", replace_contains(doc, "Software-defined networking enables programmable control", abstract_new))

    ok(
        "keywords",
        replace_exact(
            doc,
            "Keywords— Software-defined networking; intelligent transportation systems; V2X; anomaly "
            "detection; TCN-GRU; OpenFlow; edge computing; reversible mitigation.",
            "Keywords— Software-defined networking; intelligent transportation systems; V2X; RSU; "
            "anomaly detection; TCN-GRU; OpenFlow; reversible mitigation; physical-context fusion.",
        ),
    )

    # --- 1.1 Motivation ---
    motivation = (
        "The protected asset is RSU-based ITS/V2X connectivity that carries low-latency vehicle-to-"
        "infrastructure and related edge services. Software-defined networking simplifies coordination "
        "on OpenFlow fabrics, but a logically centralized controller becomes a critical dependency: "
        "an attacker who generates PacketIn floods, low-rate probes, or RSU-side flow bursts can "
        "exhaust control-plane or edge-network resources and degrade legitimate communication even "
        "when data-plane bandwidth remains available. A second, equally important failure mode is "
        "over-aggressive mitigation. Permanent blacklists and hard DROP policies may stop an attacker, "
        "yet they can also interrupt legitimate mobility traffic during rush-hour surges that elevate "
        "the same coarse counters used for intrusion signals. This research therefore targets "
        "lightweight non-DPI detection, temporary containment with automatic rollback, and an "
        "independent physical observation of the same RSU service zone—via roadside camera tracks—"
        "so that the mitigation policy can test whether abnormal network demand is consistent with "
        "observable transportation activity. The camera is a physical-context sensor for mitigation "
        "decisions, not a standalone AI vision or DDoS detector."
    )
    ok("motivation", replace_contains(doc, "Intelligent Transportation Systems (ITS) and Vehicle-to-Everything", motivation))

    # --- RQ5 ---
    ok(
        "RQ5",
        replace_exact(
            doc,
            "RQ5. Can camera-derived physical context improve the distinction between legitimate "
            "transportation surges and network-originated flooding without treating object tracks as "
            "calibrated traffic counts?",
            "RQ5. Can camera-observed physical traffic context of the same RSU service zone reduce "
            "unnecessary mitigation during legitimate demand surges without weakening containment of "
            "network-originated attacks?",
        ),
    )

    # --- Contribution ---
    ok(
        "contribution fusion",
        replace_exact(
            doc,
            "A safety-aware fusion mechanism that uses camera-derived physical context as supporting "
            "evidence for false-positive avoidance.",
            "A cyber-physical mitigation policy that combines network anomaly evidence with independent "
            "physical traffic context from the same RSU zone to reduce false containment without "
            "weakening source isolation under high dominance.",
        ),
    )

    # --- Scope tweak ---
    ok(
        "scope",
        replace_contains(
            doc,
            "In scope: flow-level (non-DPI) telemetry windows",
            "In scope: flow-level (non-DPI) telemetry for an RSU/ITS-edge zone; TCN-GRU detection with "
            "adaptive thresholding; temporary OpenFlow-style mitigation with cooldown rollback; camera "
            "object-track context as an independent physical observation of the same service zone; "
            "Mininet laboratory verification for reversible DROP; Windows mock actuation for interactive "
            "demonstration. Out of scope for this stage: city-wide camera networks, vehicle-identity/"
            "Sybil correspondence, full controller compromise, adversarial video attacks, production "
            "PacketIn/s measurement on Ryu, surveyed queue meters, and labeled-video false-positive "
            "rate claims.",
        ),
    )

    # --- Related work 2.5 ---
    ok(
        "rw camera",
        replace_contains(
            doc,
            "Multimodal fusion can reduce false containment",
            "Multimodal fusion can reduce false containment when physical congestion in the same RSU "
            "service zone co-occurs with counter spikes. Unlike vision systems that claim accident or "
            "unusual-event detection, this prototype treats the camera as a physical-context sensor: "
            "YOLO+IoU object tracks summarize whether observable transportation activity is present. "
            "Visible tracks are not veh/h census counts. Scripted fusion wiring, live RTSP observation, "
            "and labeled-video false-positive evaluation are graded separately so camera evidence cannot "
            "be mistaken for an independent cyber detector.",
        ),
    )

    # --- Threat model narrative ---
    ok(
        "threat narrative",
        replace_contains(
            doc,
            "Attack scenarios considered:",
            "Attacker objective: degrade availability of legitimate ITS/V2X communication by exhausting "
            "controller or edge-network resources (for example PacketIn floods and low-rate probes). The "
            "attacker does not need to control the camera; camera feeds may be unavailable, stale, or "
            "unreliable, and the system must fail safely by falling back to network evidence. Attack "
            "scenarios considered: PacketIn flooding; low-rate probing (LOFT-style); RSU link failure; "
            "mixed legitimate surge plus attack; misleading or absent camera context. Camera rush-hour "
            "preserve must not become an attacker-controlled bypass: high source dominance still isolates "
            "the dominant attacker under fusion rules.",
        ),
    )

    ok(
        "fusion engine assumption",
        patch_table_cell(
            doc,
            "Fusion engine",
            1,
            "Uses same-zone camera context to test cyber–physical consistency; never overrides network evidence",
        ),
    )
    ok(
        "camera assumption",
        patch_table_cell(
            doc,
            "Camera source",
            1,
            "Independent physical view of the RSU service zone; may be unavailable, stale, or unreliable",
        ),
    )

    # --- Architecture blurb ---
    ok(
        "architecture",
        replace_contains(
            doc,
            "The implemented path is: Vehicles/RSU/OVS",
            "The implemented path is scoped to an RSU service zone: Vehicles/RSU/OVS telemetry windows → "
            "TCN-GRU scoring → multimodal fusion with a camera observing the same zone in parallel → "
            "policy → actuation. Cameras are not upstream of the data plane and do not classify cyber "
            "attacks. Actuation splits into Mininet/OpenFlow (lab) and Windows in-memory mock rules "
            "(interactive demo).",
        ),
    )

    # --- §3.7 ---
    ok(
        "sec 3.7",
        replace_contains(
            doc,
            "When physical_mode=rtsp_detector, allow-listed RTSP frames",
            "When physical_mode=rtsp_detector, allow-listed RTSP frames from the same RSU service zone "
            "are scored by YOLOv8 with an IoU tracker [15]. The camera answers a decision question—"
            "whether abnormal network demand is consistent with observable transportation activity—"
            "not “is there a DDoS?” Hosts that fail DNS/TCP fall back to the last cached JPEG and/or "
            "scripted scenario replay so demos remain reproducible. Exported fields emphasize "
            "visible_vehicle_tracks and context_reliability (heuristic composite). Occupancy and queue "
            "proxies are zone estimates, not surveyed meters. Object detection is not unusual-event or "
            "accident AI.",
        ),
    )

    # --- RQ–evidence matrix row for RQ5 if present as table ---
    for table in doc.tables:
        for row in table.rows:
            if row.cells[0].text.strip() == "RQ5" and len(row.cells) >= 3:
                put(
                    row.cells[2].paragraphs[0],
                    "Policy effect shown on scripted same-zone cases; labeled FP reduction pending",
                )
                for para in row.cells[2].paragraphs[1:]:
                    for r in para.runs:
                        r.text = ""
                log.append("OK RQ5 evidence cell")

    doc.save(str(OUT))
    shutil.copyfile(OUT, ROOT / "docs" / "IEDE_Project_Report_Prototype.docx")
    for line in log:
        print(line)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB); backup {BAK.name}")


if __name__ == "__main__":
    main()
