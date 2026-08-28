#!/usr/bin/env python
"""Build IEDE Version-4 research proposal DOCX (prototype-backed research narrative)."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "assets" / "images" / "report" / "compressed"
OUT = ROOT / "Trinh Hoang Tu_4th Version.docx"
OUT_DOCS = ROOT / "docs" / "IEDE_Project_Report_Prototype.docx"


def set_run_font(run, name="Times New Roman", size=12, bold=False, italic=False):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def style_doc(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.5)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.first_line_indent = Cm(0.75)

    for level, size in ((1, 16), (2, 14), (3, 12)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.paragraph_format.first_line_indent = Cm(0)
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(6)

    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def p(doc, text, *, indent=True, bold=False, center=False, size=12, italic=False, space_after=6):
    para = doc.add_paragraph()
    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    para.paragraph_format.space_after = Pt(space_after)
    para.paragraph_format.first_line_indent = Cm(0.75) if indent else Cm(0)
    if center:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic)
    return para


def bullet(doc, text):
    para = doc.add_paragraph(text, style="List Bullet")
    para.paragraph_format.first_line_indent = Cm(0)
    for r in para.runs:
        set_run_font(r, size=12)
    return para


def numbered(doc, text):
    para = doc.add_paragraph(text, style="List Number")
    para.paragraph_format.first_line_indent = Cm(0)
    for r in para.runs:
        set_run_font(r, size=12)
    return para


def caption(doc, text):
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.first_line_indent = Cm(0)
    para.paragraph_format.space_before = Pt(6)
    para.paragraph_format.space_after = Pt(10)
    run = para.add_run(text)
    set_run_font(run, size=11, italic=True)
    return para


def add_figure(doc, path: Path, caption_text: str, width_cm: float = 15.0):
    if not path.exists():
        p(doc, f"[Missing figure: {path.name}]", indent=False, bold=True)
        return
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.first_line_indent = Cm(0)
    run = para.add_run()
    run.add_picture(str(path), width=Cm(width_cm))
    caption(doc, caption_text)


def add_table(doc, headers, rows, col_widths=None):
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
    doc.add_paragraph()
    return table


def h1(doc, text):
    doc.add_heading(text, level=1)


def h2(doc, text):
    doc.add_heading(text, level=2)


def h3(doc, text):
    doc.add_heading(text, level=3)


def build() -> Path:
    doc = Document()
    style_doc(doc)

    # -------- Cover --------
    for _ in range(2):
        doc.add_paragraph()
    p(doc, "TSINGHUA UNIVERSITY", center=True, indent=False, bold=True, size=16, space_after=4)
    p(
        doc,
        "Innovation and Entrepreneurship Development Education (IEDE)",
        center=True,
        indent=False,
        size=12,
        space_after=4,
    )
    p(doc, "Autumn Semester 2026", center=True, indent=False, size=12, space_after=18)
    p(doc, "RESEARCH PROPOSAL", center=True, indent=False, bold=True, size=14, space_after=16)
    p(
        doc,
        "AI-Assisted Resilience for SDN-Enabled Intelligent Transportation Systems",
        center=True,
        indent=False,
        bold=True,
        size=18,
        space_after=8,
    )
    p(
        doc,
        "A Lightweight Framework for V2X Network Reliability, Edge Telemetry, and Safety-Aware Mitigation",
        center=True,
        indent=False,
        size=13,
        space_after=8,
    )
    p(
        doc,
        "A Prototype-Backed Research Proposal with Preliminary Experimental Evidence",
        center=True,
        indent=False,
        italic=True,
        size=12,
        space_after=18,
    )
    p(
        doc,
        "Proposed Category: Transportation · AI · Internet Security · IoT · Cloud/Edge Computing",
        center=True,
        indent=False,
        size=11,
        space_after=20,
    )

    add_table(
        doc,
        ["Role", "Name and affiliation"],
        [
            [
                "Project Advisor",
                "Prof. Kris Singh — Visiting Professor, Tsinghua University; CEO, SRII",
            ],
            [
                "Author",
                "Trinh Hoang Tu — Ho Chi Minh City University of Foreign Languages and "
                "Information Technology (HUFLIT); Software Engineering Intern, Grab",
            ],
        ],
        col_widths=[4.0, 11.5],
    )
    p(
        doc,
        "Prepared as an individual research project for the IEDE Global Program.",
        center=True,
        indent=False,
        italic=True,
        size=11,
        space_after=8,
    )
    p(doc, "Repository: sdn-its-resilience-ai (v0.2.0)", center=True, indent=False, size=11, space_after=4)
    p(doc, "Date: August 2026", center=True, indent=False, size=11, space_after=4)

    doc.add_page_break()

    # -------- Abstract --------
    h1(doc, "Abstract")
    p(
        doc,
        "Software-defined networking enables programmable control for intelligent transportation "
        "systems, but its logically centralized control plane remains vulnerable to flooding attacks, "
        "low-rate probing, controller overload, and false-positive mitigation during legitimate traffic "
        "surges. This research proposes a lightweight resilience framework that combines flow-level "
        "telemetry, temporal anomaly detection, adaptive thresholding, and reversible OpenFlow "
        "mitigation. A hybrid TCN-GRU model processes short telemetry windows without deep packet "
        "inspection, while a safety-aware policy applies temporary containment and automatic rollback "
        "rather than permanent blocking. Camera-derived physical context is incorporated as supporting "
        "evidence to distinguish transportation demand surges from network-originated anomalies. A "
        "prototype operations console and a set of reproducible experiments were developed to assess "
        "detection quality, response latency, reversible containment, and fusion-policy behavior. "
        "Preliminary evaluation on an InSDN-shaped holdout reports classifier-head accuracy of 96.2%, "
        "F1-score of approximately 97.7%, and ROC-AUC of 0.977, with a decision-path response time "
        "below 10 ms in the evaluated environment. Mininet experiments further demonstrate temporary "
        "rule installation and rollback, while camera-fusion experiments currently provide scripted "
        "policy-validation evidence rather than labeled-video performance claims. These results "
        "support the technical feasibility of the proposed framework and define the remaining work "
        "required for full transportation-scale validation.",
    )
    p(
        doc,
        "Keywords— Software-defined networking; intelligent transportation systems; V2X; anomaly "
        "detection; TCN-GRU; OpenFlow; edge computing; reversible mitigation.",
        indent=False,
        italic=True,
    )

    doc.add_page_break()
    h1(doc, "Table of Contents")
    p(
        doc,
        "Update fields in Microsoft Word (right-click → Update Field) after final edits. "
        "Outline: 1 Introduction · 2 Related Work · 3 Threat Model and System Design · "
        "4 Research Methodology · 5 Prototype Implementation · 6 Preliminary Experimental Results · "
        "7 Prototype Demonstration · 8 Discussion · 9 Proposed Research Extension · 10 Conclusion · "
        "References · Appendices A–C.",
        indent=False,
        italic=True,
        size=11,
    )

    # ==================== 1 ====================
    doc.add_page_break()
    h1(doc, "1. Introduction")
    h2(doc, "1.1 Background and Motivation")
    p(
        doc,
        "Intelligent Transportation Systems (ITS) and Vehicle-to-Everything (V2X) services depend on "
        "low-latency, high-reliability connectivity among vehicles, roadside units (RSUs), and traffic "
        "management centers. Software-defined networking (SDN) separates control and data planes and "
        "enables programmable forwarding on OpenFlow switches, which is attractive for dynamic ITS "
        "edge fabrics. However, a logically centralized controller becomes a critical dependency: "
        "PacketIn floods, low-rate probes, and RSU-side faults can overload control-plane capacity even "
        "when the data plane retains spare bandwidth. Permanent blacklists and hard DROP policies may "
        "stop an attacker, yet they also risk disrupting legitimate mobility traffic during rush-hour "
        "surges that elevate the same coarse counters used for intrusion signals. This research is "
        "motivated by the need for lightweight, non-DPI detection at the edge, safety-aware mitigation "
        "that prefers temporary containment, and explicit rollback so transportation continuity remains "
        "a first-class objective.",
    )

    h2(doc, "1.2 Problem Statement")
    p(
        doc,
        "Existing SDN intrusion-detection approaches frequently optimize classification performance "
        "without jointly addressing three operational requirements of transportation networks: "
        "low-latency inference at the edge, avoidance of service disruption during legitimate load "
        "surges, and verifiable rollback of mitigation actions. This research addresses the problem of "
        "detecting control-plane anomalies from non-DPI telemetry and applying temporary mitigation "
        "while preserving legitimate transportation traffic.",
    )

    h2(doc, "1.3 Research Gap")
    bullet(doc, "Many studies stop at offline classification accuracy and do not evaluate detect → contain → rollback loops.")
    bullet(doc, "False-positive cost in ITS is higher than in generic enterprise networks because mitigation can interrupt safety-relevant flows.")
    bullet(doc, "Camera context is often over-claimed as traffic census or accident intelligence, without separating synthetic, live, and labeled evidence.")
    bullet(doc, "Actuation evidence is frequently conflated: mock in-memory rules, scripted policy tests, and switch-verified OpenFlow outcomes are not graded explicitly.")
    p(
        doc,
        "The present work targets these gaps with a prototype-backed evidence protocol rather than a "
        "demo-only narrative.",
    )

    h2(doc, "1.4 Research Questions")
    numbered(doc, "RQ1. How effectively can non-DPI SDN telemetry identify abnormal control-plane and flow behavior in an ITS edge network?")
    numbered(doc, "RQ2. Can a lightweight TCN-GRU model satisfy edge-level latency and memory constraints while maintaining competitive anomaly-detection performance?")
    numbered(doc, "RQ3. To what extent can temporary containment and automatic rollback reduce attack impact without disrupting legitimate rush-hour traffic?")
    numbered(doc, "RQ4. How should public SDN intrusion datasets be combined with simulated ITS/VANET scenarios to improve transportation relevance and cross-scenario evaluation?")
    numbered(doc, "RQ5. Can camera-derived physical context improve the distinction between legitimate transportation surges and network-originated flooding without treating object tracks as calibrated traffic counts?")

    h2(doc, "1.5 Research Contributions")
    p(doc, "Research contributions", indent=False, bold=True)
    bullet(doc, "A lightweight flow-telemetry framework for detecting SDN anomalies in ITS environments without relying on deep packet inspection.")
    bullet(doc, "A reversible mitigation loop that combines temporary containment, cooldown control, and automatic rollback.")
    bullet(doc, "A safety-aware fusion mechanism that uses camera-derived physical context as supporting evidence for false-positive avoidance.")
    bullet(doc, "An evidence-grading protocol that explicitly distinguishes model output, scripted policy validation, mock actuation, and switch-verified OpenFlow outcomes.")
    bullet(doc, "A prototype-backed evaluation covering detection quality, latency, containment, rollback, fusion sensitivity, and system ablation.")
    p(doc, "Engineering artifacts", indent=False, bold=True)
    p(
        doc,
        "The research is supported by a modular implementation (src/sdn_its), reproducible experiment "
        "scripts, an operations console, dataset preparation utilities, and tracked result artifacts "
        "under artifacts/results/.",
    )

    h2(doc, "1.6 Scope of the Study")
    p(
        doc,
        "In scope: flow-level (non-DPI) telemetry windows; TCN-GRU detection with adaptive thresholding; "
        "temporary OpenFlow-style mitigation with cooldown rollback; camera object-track context as "
        "supporting evidence; Mininet laboratory verification for reversible DROP; Windows mock "
        "actuation for interactive demonstration. Out of scope for this stage: full controller "
        "compromise, adversarial video attacks, production PacketIn/s measurement on Ryu, surveyed "
        "queue meters, and labeled-video false-positive rate claims.",
    )

    # ==================== 2 ====================
    h1(doc, "2. Related Work")
    h2(doc, "2.1 SDN Security in Intelligent Transportation Systems")
    p(
        doc,
        "OpenFlow-based SDN enables programmable campus and edge fabrics [1][5], and ITS/V2X "
        "deployments increasingly rely on RSUs and centralized wireless policy [8]. Prior surveys of "
        "cyber-physical intrusion detection emphasize that control-plane overload and false alarms "
        "have asymmetric safety costs [6][7]. This work focuses on ITS-edge PacketIn stress and "
        "reversible containment rather than deep packet inspection of application payloads.",
    )

    h2(doc, "2.2 Flow-Based Anomaly Detection")
    p(
        doc,
        "Flow and counter-based detectors avoid DPI overhead and privacy exposure. Public SDN "
        "intrusion corpora such as InSDN [3] and CIC-family datasets [4][13] provide labeled traffic "
        "for supervised evaluation, yet they are not natively VANET mobility traces. The present study "
        "maps such corpora into a canonical ten-feature schema and treats synthetic ITS scenarios as "
        "separate sanity checks rather than as substitutes for in-domain holdouts.",
    )

    h2(doc, "2.3 Lightweight Temporal Models at the Edge")
    p(
        doc,
        "Temporal convolutional networks provide long effective history with causal convolutions [2], "
        "while GRU/LSTM variants remain strong sequential baselines [14]. This research investigates a "
        "hybrid TCN-GRU as a design candidate for joint reconstruction and multi-class prediction. "
        "The hybrid architecture is investigated as a design candidate rather than assumed to "
        "outperform all recurrent baselines; current ablation artifacts do not yet prove universal "
        "superiority and are reported with that caveat.",
    )

    h2(doc, "2.4 Safety-Aware and Reversible Mitigation")
    p(
        doc,
        "Permanent blacklists maximize attack suppression but raise false-positive blast radius. "
        "Rate limiting and temporary DROP with idle/hard timeouts, followed by explicit DELETE, "
        "better match transportation continuity requirements. Experiment A in this proposal measures "
        "ICMP delivery under none / permanent / temporary arms with ovs-ofctl verification, separating "
        "policy intent from switch-verified outcomes.",
    )

    h2(doc, "2.5 Camera–Network Context Fusion")
    p(
        doc,
        "Multimodal fusion can reduce false containment when physical congestion co-occurs with "
        "counter spikes. Unlike vision systems that claim accident or unusual-event detection, this "
        "prototype uses YOLO+IoU object tracks as contextual support only. Visible tracks are not "
        "treated as veh/h census counts, and scripted fusion wiring is graded separately from live "
        "observation and from OpenFlow evidence.",
    )

    # ==================== 3 ====================
    h1(doc, "3. Threat Model and System Design")
    h2(doc, "3.1 System Assumptions")
    p(
        doc,
        "The prototype assumes an authenticated telemetry path within the lab, trusted switch "
        "forwarding for Experiment A, and a controller that remains benign but may be overloaded. "
        "Camera streams may be unavailable, stale, or synthetic. Fusion never treats camera context as "
        "absolute ground truth that can unconditionally override network evidence.",
    )

    h2(doc, "3.2 Threat Model")
    add_table(
        doc,
        ["Component", "Assumption"],
        [
            ["SDN controller", "Trusted but may be overloaded"],
            ["RSU / source host", "May be compromised or generate floods"],
            ["OpenFlow switch", "Trusted for Experiment A verification"],
            ["Telemetry collector", "Authenticated within prototype scope"],
            ["Camera source", "May be unavailable, stale, or unreliable"],
            ["Fusion engine", "Uses camera context as supporting evidence only"],
            ["Attacker", "Can generate floods or low-rate probes"],
            ["Out of scope", "Full controller compromise; adversarial video; key theft"],
        ],
        col_widths=[5.0, 10.5],
    )
    caption(doc, "Table 3.1. Threat-model assumptions for the prototype-backed study.")
    p(
        doc,
        "Attack scenarios considered: PacketIn flooding; low-rate probing (LOFT-style); RSU link "
        "failure; mixed legitimate surge plus attack; misleading or absent camera context. Camera "
        "rush-hour preserve must not become an attacker-controlled bypass: high source dominance "
        "still isolates the dominant attacker under fusion rules.",
    )

    h2(doc, "3.3 End-to-End Architecture")
    p(
        doc,
        "The implemented path is: Vehicles/RSU/OVS → telemetry windows → TCN-GRU scoring → multimodal "
        "fusion (optional camera branch) → policy → actuation. Cameras feed Fusion in parallel; they "
        "are not upstream of the data plane. Actuation splits into Mininet/OpenFlow (lab) and Windows "
        "in-memory mock rules (interactive demo).",
    )
    add_figure(
        doc,
        IMG / "architecture.jpg",
        "Figure 3.1. Prototype software architecture with parallel camera context and graded actuation paths.",
        width_cm=15.5,
    )

    h2(doc, "3.4 Telemetry and Feature Pipeline")
    p(
        doc,
        "Telemetry is collected as sliding windows of length L=10 over ten non-DPI features "
        "(Section 4.3). Features are standardized with a scaler fit on training data only.",
    )

    h2(doc, "3.5 Detection and Adaptive Thresholding")
    p(
        doc,
        "The model emits reconstruction error RE(x)=||x−x̂||₂² and class logits. An adaptive "
        "threshold τ=μ_RE + kσ_RE is maintained for RE-based flags; the primary reported InSDN "
        "metrics use the classifier head. Online τ adaptation may update μ and σ from recent normal "
        "windows when enabled in the console.",
    )

    h2(doc, "3.6 Mitigation and Rollback Policy")
    p(
        doc,
        "Policy maps alerts to temporary DROP, RATE_LIMIT, THROTTLE_PACKET_IN, preserve/ignore for "
        "rush-hour, or observe. Cooldown timers expire rules; Experiment A also verifies explicit "
        "DELETE and post-rollback reachability.",
    )

    h2(doc, "3.7 Camera-Assisted Physical Context")
    p(
        doc,
        "When physical_mode=rtsp_detector, RTSP frames are scored by YOLOv8 with an IoU tracker [15]. "
        "Exported fields emphasize visible_vehicle_tracks and context_reliability (heuristic "
        "composite). Occupancy and queue proxies are zone estimates, not surveyed meters. Object "
        "detection is not unusual-event or accident AI.",
    )

    # ==================== 4 ====================
    h1(doc, "4. Research Methodology")
    h2(doc, "4.1 Research Design")
    p(
        doc,
        "The study combines (i) in-domain supervised evaluation on InSDN-mapped windows, (ii) "
        "cross-dataset transfer checks on CIC-mapped windows, (iii) controlled synthetic sanity "
        "scenarios, (iv) Mininet reversible mitigation trials, and (v) scripted camera–network fusion "
        "and threshold sensitivity tests with explicit evidence grades.",
    )

    h2(doc, "4.2 Datasets and Scenario Construction")
    p(
        doc,
        "InSDN records were transformed into a canonical flow-feature schema "
        "(datasets/processed/insdn_windows.npz). Synthetic ITS scenarios were generated separately "
        "and were not mixed into the primary holdout unless explicitly stated. CIC windows support "
        "zero-shot and adapted transfer experiments. Label space includes Normal, "
        "DDoS_PacketIn_Flood, LOFT_LowRate_Attack, RSU_Link_Fault, and RushHour_Burst.",
    )

    h2(doc, "4.3 Data Preprocessing and Windowing")
    p(
        doc,
        "Sliding windows use seq_len L=10 with stride 1 over scaled feature rows. StandardScaler "
        "parameters are fit on training splits only to reduce leakage. Live demo paths may use "
        "per-window z-score for readable RE scales; training uses the fitted scaler on canonical CSVs.",
    )

    h2(doc, "4.4 TCN-GRU Model Configuration")
    add_table(
        doc,
        ["Layer / hyperparameter", "Configuration"],
        [
            ["Input", "10 × F (F=10 features)"],
            ["TCN channels", "[32, 64]; kernel_size=3; dilations 1,2"],
            ["GRU AE", "hidden_dim=64; reconstruct to feature space"],
            ["Classifier", "Linear 64→32→5; Dropout=0.2"],
            ["Optimizer", "Adam lr=1e-3; weight_decay=1e-4"],
            ["Batch / epochs (defaults)", "64 / up to 10–15 with early stopping"],
            ["Loss", "reconstruction + classification"],
            ["Quantization", "dynamic INT8 export path available"],
        ],
        col_widths=[6.0, 9.5],
    )
    caption(doc, "Table 4.1. Default TCN-GRU configuration from src/sdn_its/ai/tcn_gru.py and train.py.")

    h2(doc, "4.5 Baselines and Ablation Design")
    p(
        doc,
        "scripts/run_sweep.py compares RNN/LSTM/GRU and TCN-GRU and sweeps k for τ=μ+kσ. Ablation "
        "outputs are treated as exploratory; they do not alone justify claiming TCN-GRU dominance.",
    )

    h2(doc, "4.6 Experimental Environment")
    p(
        doc,
        "Detection latency numbers in Section 6 were measured in the author workstation environment "
        "with PyTorch checkpoints (CUDA available for camera YOLO; CPU path used for reported IDL/"
        "T_response in exp_insdn metrics). Mininet/OpenFlow verification ran in a Linux/WSL lab path. "
        "Interactive console demos commonly run on Windows with mock OpenFlow.",
    )

    h2(doc, "4.7 Evaluation Metrics")
    bullet(doc, "Detection: accuracy, precision, recall, F1, ROC-AUC (classifier head preferred).")
    bullet(doc, "Latency: inference ms; IDL (collect+preprocess+score); T_response (includes policy/API path).")
    bullet(doc, "Mitigation: attack/legit ICMP delivery ratios; switch dump verification; rollback success.")
    bullet(doc, "Fusion: recommended_action agreement on scripted cases; threshold sensitivity action flips.")

    h2(doc, "4.8 Evidence-Grading Protocol")
    add_table(
        doc,
        ["Grade", "Meaning", "Allowed claim"],
        [
            ["model_output", "Classifier/RE scores on datasets", "In-domain / transfer metrics"],
            ["scripted", "Forced physical/network inputs", "Policy wiring / sensitivity"],
            ["live_observation", "Unmodified detector/camera aggregate", "Context availability only"],
            ["mock_actuation", "In-memory rules on Windows", "UI/policy intent, not switch fact"],
            ["openflow_lab", "ovs-ofctl verified install/delete", "Reversible containment evidence"],
        ],
        col_widths=[4.0, 5.5, 6.0],
    )
    caption(doc, "Table 4.2. Evidence-grading protocol used throughout Results and Demonstration.")

    # ==================== 5 ====================
    h1(doc, "5. Prototype Implementation")
    h2(doc, "5.1 Software Stack")
    add_table(
        doc,
        ["Layer", "Technology"],
        [
            ["AI model", "PyTorch TCN-GRU (FP32 + dynamic INT8 path)"],
            ["API / controller", "Flask REST (/api/v1/*)"],
            ["Dashboard", "Ops console (evidence strip, Chart.js)"],
            ["Datasets", "Synthetic + InSDN/CIC → canonical features"],
            ["Camera", "RTSP allow-list → YOLO+IoU (detector_tracker_v1) or synthetic"],
            ["Fusion", "Rule-based FusionEngine + injectable FusionThresholds"],
            ["Experiments", "Exp A/B/C/D scripts + ablation sweep"],
        ],
        col_widths=[4.5, 11.0],
    )

    h2(doc, "5.2 Operations Console")
    p(
        doc,
        "The console exposes live RE vs τ, intended mitigation rules, camera cards, fusion decisions, "
        "topology, and an event audit stream. The evidence strip reports MODEL, OF backend, and NET "
        "evidence state so reviewers do not confuse mock rules with switch installs.",
    )

    h2(doc, "5.3 OpenFlow Actuation Paths")
    p(
        doc,
        "Windows demos default to a mock OpenFlow channel (in-memory rules). Experiment A uses "
        "Mininet + ovs-ofctl to install temporary DROP, verify dumps, DELETE, and measure post-rollback "
        "reachability.",
    )

    h2(doc, "5.4 Runtime Configuration")
    p(
        doc,
        "Settings synchronize poll interval, τ, cooldowns, lab mode, scenario-label override, and "
        "online τ adapt. Lab mode disables silent simulation fallbacks that would invent RE for demos.",
    )

    h2(doc, "5.5 Reproducibility Artifacts")
    p(
        doc,
        "Primary metric files include artifacts/results/exp_insdn/metrics.json, "
        "cross_dataset/eval_metrics.json, cross_dataset/adapted_metrics.json, exp_a/exp_a_metrics.json, "
        "exp_bc/*.json, and exp_d/exp_d_phases.json. Model card: artifacts/models/model_card.json.",
    )

    # ==================== 6 ====================
    h1(doc, "6. Preliminary Experimental Results")
    h2(doc, "6.1 InSDN Detection Performance")
    p(
        doc,
        "These results represent the primary in-domain classifier-head evaluation on an InSDN-mapped "
        "holdout (n_test=7500; artifact exp_insdn/metrics.json).",
    )
    add_table(
        doc,
        ["Metric", "Result"],
        [
            ["Classifier accuracy", "96.21%"],
            ["Precision", "95.95%"],
            ["Recall", "99.47%"],
            ["F1-score", "97.68%"],
            ["ROC-AUC", "0.977"],
            ["Inference (batch=1 mean)", "~0.25 ms"],
            ["IDL (collect+preprocess+score)", "~6.45 ms"],
            ["T_response (incl. policy/API path)", "~9.95 ms"],
        ],
        col_widths=[8.0, 7.5],
    )
    caption(doc, "Table 6.1. Primary InSDN holdout metrics (classifier head).")

    h2(doc, "6.2 Synthetic Sanity-Check Evaluation")
    p(
        doc,
        "Controlled synthetic class separation yields high multi-class accuracy (including 100% in "
        "deliberately separated demos). This value reflects deliberately separated synthetic classes "
        "and is not interpreted as evidence of real-world generalization. Binary synthetic summary "
        "figures occasionally cited in earlier drafts (e.g., ~97% accuracy) are secondary to Table 6.1.",
    )

    h2(doc, "6.3 Latency and Model Footprint")
    add_table(
        doc,
        ["Metric", "FP32 (approx.)", "Notes"],
        [
            ["Checkpoint size", "~0.98 MB", "tcn_gru_best.pt order of magnitude"],
            ["INT8 quantized path", "~0.17 MB", "dynamic quantization artifact"],
            ["T_response", "~9.95 ms", "InSDN eval path; host-dependent"],
        ],
        col_widths=[5.0, 4.5, 6.0],
    )
    caption(doc, "Table 6.2. Latency and footprint notes.")

    h2(doc, "6.4 Reversible OpenFlow Containment")
    p(
        doc,
        "Experiment A (Mininet ITS-edge topology; ping_count=20 per probe) compares none / permanent "
        "DROP / temporary DROP+DELETE. Metrics are ICMP delivery ratios (data plane), not controller "
        "PacketIn/s. The recovery_ms≈5.02 value is the measured rule-deletion / harness recovery "
        "latency after DELETE (not end-to-end application QoS or traffic RTT).",
    )
    add_table(
        doc,
        ["Arm", "Legit delivery", "Attack delivery", "Switch dump", "Notes"],
        [
            ["none", "0.95", "1.00", "—", "baseline"],
            ["permanent DROP", "0.85", "0.00", "verified", "install≈3.2 ms"],
            ["temporary (during)", "1.00", "0.00", "verified", "install≈4.6 ms"],
            ["after DELETE", "0.95", "1.00", "rule cleared", "recovery≈5.0 ms"],
        ],
        col_widths=[4.0, 3.0, 3.2, 2.8, 2.5],
    )
    caption(doc, "Table 6.3. Experiment A — reversible mitigation (openflow_lab grade).")

    h2(doc, "6.5 Camera–Network Fusion")
    p(
        doc,
        "Experiments B/C validate explainable fusion rules on scripted physical contexts. Pass "
        "indicates policy wiring, not labeled-video false-positive reduction.",
    )
    add_table(
        doc,
        ["Case", "Dominance", "Action"],
        [
            ["Legitimate surge (rush)", "0.30", "preserve_rush_hour"],
            ["PacketIn flood (stable cam)", "0.82", "temporary_drop"],
            ["Mixed rush + attack", "0.82", "isolate source (temporary_drop)"],
        ],
        col_widths=[6.0, 3.0, 6.5],
    )
    caption(doc, "Table 6.4. Scripted fusion outcomes (scripted grade).")

    h2(doc, "6.6 Threshold Sensitivity")
    p(
        doc,
        "FusionThresholds are injected into FusionEngine. At fixed probe dominance 0.62, lowering "
        "dominance_mixed_isolate increases temporary_drop on rush+mid-dom; raising "
        "dominance_stable_contain softens stable+mid-dom from temporary_drop to rate_limit.",
    )
    add_table(
        doc,
        ["Threshold", "Rush+DDoS @0.62", "Stable+DDoS @0.60"],
        [
            ["0.55", "temporary_drop", "temporary_drop"],
            ["≥0.65", "preserve_rush_hour", "rate_limit"],
        ],
        col_widths=[3.5, 6.0, 6.0],
    )
    caption(doc, "Table 6.5. Sensitivity summary (actions vary with injected cutoffs).")

    h2(doc, "6.7 Ablation Results")
    p(
        doc,
        "Architecture × k·σ sweeps are stored under artifacts/results/ablation/. They are exploratory "
        "and currently insufficient to claim that TCN-GRU strictly dominates RNN/LSTM/GRU on all "
        "transportation metrics.",
    )

    h2(doc, "6.8 Research-Question Evaluation")
    add_table(
        doc,
        ["RQ", "Evidence", "Current conclusion"],
        [
            ["RQ1", "InSDN classifier metrics", "Supported in-domain"],
            ["RQ2", "IDL/T_response; model size", "Provisionally supported"],
            ["RQ3", "Exp A + rush-hour policy cases", "Supported in lab; broader traffic validation pending"],
            ["RQ4", "Dataset pipeline + CIC transfer", "Partially answered (zero-shot weak; adapted stronger)"],
            ["RQ5", "Exp B/C/D", "Policy feasibility shown; labeled FP reduction not proven"],
        ],
        col_widths=[2.0, 5.5, 8.0],
    )
    caption(doc, "Table 6.6. RQ–evidence matrix (graded support, not binary yes/no).")

    add_table(
        doc,
        ["Evaluation", "Key result", "Interpretation"],
        [
            ["InSDN holdout", "F1≈97.7%, AUC≈0.977", "Primary in-domain"],
            ["CIC zero-shot", "Acc≈37%, F1≈0.47, AUC≈0.52", "Weak transfer"],
            ["CIC adapted holdout", "F1≈0.977, AUC≈0.998", "Post-adaptation (not zero-shot)"],
            ["Synthetic", "High / separated classes", "Sanity check only"],
        ],
        col_widths=[4.5, 5.5, 5.5],
    )
    caption(doc, "Table 6.7. Cross-setting comparison (honesty over cherry-picking).")

    # ==================== 7 ====================
    h1(doc, "7. Prototype Demonstration")
    p(
        doc,
        "Screenshots illustrate operator-facing evidence states. They complement, but do not replace, "
        "Section 6 metrics. Captures use the August 2026 console.",
    )

    h2(doc, "7.1 Nominal Monitoring")
    add_figure(
        doc,
        IMG / "fig01_console_overview.jpg",
        "Figure 7.1. Nominal monitoring view with evidence strip (MODEL / OF·mock / NET state) and KPI cards.",
    )

    h2(doc, "7.2 PacketIn Flood Detection and Containment")
    add_figure(
        doc,
        IMG / "fig02b_re_chart_ddos.jpg",
        "Figure 7.2. PacketIn flood scenario: reconstruction-error chart, network inject controls, and intended mitigation panel.",
    )

    h2(doc, "7.3 Rush-Hour False-Positive Avoidance")
    add_figure(
        doc,
        IMG / "fig04_rush_hour_preserve.jpg",
        "Figure 7.3. Rush-hour network-label scenario emphasizing GT/PRED/MATCH honesty and preserve-oriented policy.",
    )

    h2(doc, "7.4 Scenario Replay")
    add_figure(
        doc,
        IMG / "fig05_replay_timeline.jpg",
        "Figure 7.4. DDoS-cycle replay with synchronized RE chart and policy latency percentiles.",
    )

    h2(doc, "7.5 Topology and Event Audit")
    add_figure(
        doc,
        IMG / "fig06_topology_events.jpg",
        "Figure 7.5. ITS edge topology and chronological containment/rollback event stream.",
    )

    h2(doc, "7.6 Camera Context and Evidence Labels")
    add_figure(
        doc,
        IMG / "fig07_camera_tracks.jpg",
        "Figure 7.6. Live RTSP frames with YOLO object boxes (cars/motorcycles/persons). Object detection supporting fusion — not unusual-event AI.",
        width_cm=12.0,
    )
    add_figure(
        doc,
        IMG / "fig08_fusion_camera.jpg",
        "Figure 7.7. Annotated live frame close-up used as physical-context evidence for fusion discussions.",
    )
    p(
        doc,
        "Settings drawer and additional crops are available in assets/images/report/ for the appendix "
        "dossier; they are omitted here to keep demonstration focused on RQ-relevant views.",
    )

    # ==================== 8 ====================
    h1(doc, "8. Discussion")
    h2(doc, "8.1 Interpretation of Results")
    p(
        doc,
        "In-domain InSDN classifier performance is strong, while CIC zero-shot transfer is weak—an "
        "expected outcome that motivates adaptation and transportation-specific scenario design. "
        "Sub-10 ms T_response supports feasibility of a lightweight decision path on the evaluated "
        "host, not a claim of certified edge deployment. Experiment A shows that temporary DROP can "
        "suppress attacker ICMP delivery and that DELETE restores reachability, reducing the blast "
        "radius of permanent blocking. Fusion sensitivity demonstrates that mid-dominance decisions "
        "actually flip when thresholds are injected, which is a prerequisite for meaningful "
        "safety–security trade-off analysis.",
    )

    h2(doc, "8.2 Transportation-Safety Implications")
    p(
        doc,
        "False positives can interrupt V2X and camera streams that operators rely on during congestion. "
        "Temporary actions, cooldown, and rollback shrink that blast radius. Camera context must remain "
        "supporting evidence: an attacker should not be able to force preserve-by-default merely by "
        "spoofing a busy scene if source dominance indicates a concentrated flood.",
    )

    h2(doc, "8.3 Threats to Validity")
    bullet(doc, "Internal validity: synthetic scenario construction and threshold choices can favor scripted passes.")
    bullet(doc, "External validity: results are not yet validated on production ITS controllers or city-scale traffic.")
    bullet(doc, "Construct validity: visible_vehicle_tracks ≠ vehicle flow (veh/h); ICMP delivery ≠ PacketIn/s.")
    bullet(doc, "Conclusion validity: limited seeds; confidence intervals not yet reported for all tables.")
    bullet(doc, "Reproducibility: depends on tracked artifacts, configs, and environment notes in Section 5.5.")

    h2(doc, "8.4 Limitations")
    bullet(doc, "Windows console OF path is mock unless Experiment A (or Ryu) is used.")
    bullet(doc, "Camera fusion Exp B/C/D scripted pass ≠ labeled-video FP reduction.")
    bullet(doc, "Cross-dataset zero-shot remains weak without adaptation.")
    bullet(doc, "Ablation does not yet prove TCN-GRU superiority over all recurrent baselines.")

    # ==================== 9 ====================
    h1(doc, "9. Proposed Research Extension")
    p(
        doc,
        "The next phase couples the current prototype to production-style controller telemetry and "
        "mobility simulators (SUMO / Mininet-WiFi) [9][10][11][12], then closes the loop from labeled "
        "camera evaluation to switch-verified actuation.",
    )
    add_table(
        doc,
        ["Phase", "Work", "Deliverable"],
        [
            ["1", "Multi-seed baseline evaluation", "Mean ± SD benchmark table"],
            ["2", "Real Ryu PacketIn pipeline", "Controller-load evidence"],
            ["3", "SUMO/VANET coupling", "Mobility-aware scenario dataset"],
            ["4", "Labeled camera evaluation", "FP/FN metrics on video labels"],
            ["5", "Cross-dataset adaptation", "Generalization study"],
            ["6", "Integrated closed-loop test", "Camera + network + switch evidence"],
            ["7", "Manuscript preparation", "Final research report / paper draft"],
        ],
        col_widths=[2.0, 6.5, 7.0],
    )
    caption(doc, "Table 9.1. Proposed work packages for the next research phase.")

    # ==================== 10 ====================
    h1(doc, "10. Conclusion")
    p(
        doc,
        "This research proposes a lightweight and safety-aware resilience framework for SDN-enabled "
        "intelligent transportation systems. The prototype integrates non-DPI flow telemetry, "
        "TCN-GRU-based anomaly detection, adaptive thresholding, temporary mitigation, automatic "
        "rollback, and optional camera-derived physical context. Preliminary results demonstrate "
        "strong in-domain detection performance, sub-10 ms decision-path response in the evaluated "
        "environment, and reversible OpenFlow containment in a Mininet laboratory setup. The evidence "
        "also shows that camera–network fusion policies can be tested transparently while "
        "distinguishing scripted inputs, live observations, mock actuation, and switch-verified "
        "outcomes. However, cross-dataset generalization, production controller-load reduction, "
        "labeled-video false-positive evaluation, and full camera-to-switch closed-loop validation "
        "remain open research tasks. The proposed next phase will address these limitations through "
        "multi-seed baselines, Ryu/SUMO integration, and transportation-scale experiments.",
    )

    # ==================== References ====================
    h1(doc, "References")
    refs = [
        "[1] N. McKeown et al., “OpenFlow: Enabling innovation in campus networks,” ACM SIGCOMM CCR, 2008.",
        "[2] S. Bai, J. Z. Kolter, and V. Koltun, “An empirical evaluation of generic convolutional and recurrent networks for sequence modeling,” arXiv:1803.01271, 2018.",
        "[3] M. S. Elsayed, N.-A. Le-Khac, and A. D. Jurcut, “InSDN: A novel SDN intrusion dataset,” IEEE Access, 2020.",
        "[4] I. Sharafaldin, A. H. Lashkari, and A. A. Ghorbani, “Toward generating a new intrusion detection dataset and intrusion traffic characterization (CSE-CIC-IDS2018).”",
        "[5] Open Networking Foundation, “OpenFlow Switch Specification,” v1.3.0, 2012.",
        "[6] P. Sommer and V. Paxson, “Outside the closed world: On using machine learning for network intrusion detection,” IEEE S&P, 2010.",
        "[7] R. Mitchell and I.-R. Chen, “A survey of intrusion detection techniques for cyber-physical systems,” ACM Comput. Surv., 2014.",
        "[8] M. Amadeo, C. Campolo, and A. Molinaro, “Enhancing IEEE 802.11p/WAVE for infotainment in VANETs,” Ad Hoc Networks, 2012.",
        "[9] P. A. Lopez et al., “Microscopic traffic simulation using SUMO,” IEEE ITSC, 2018.",
        "[10] R. R. Fontes et al., “Mininet-WiFi: Emulating software-defined wireless networks,” CNSM, 2015.",
        "[11] Eclipse SUMO, “Simulation of Urban MObility,” documentation, 2026.",
        "[12] Mininet-WiFi Project, “Emulation platform for software-defined wireless networks,” documentation, 2026.",
        "[13] Canadian Institute for Cybersecurity, “CSE-CIC-IDS2018 Dataset,” University of New Brunswick, 2018.",
        "[14] K. Cho, B. van Merriënboer, et al., “Learning phrase representations using RNN encoder–decoder for statistical machine translation,” EMNLP, 2014. (GRU)",
        "[15] Ultralytics, “YOLOv8 documentation,” 2023–2026. (edge object detection used as context only)",
    ]
    for ref in refs:
        para = doc.add_paragraph(ref)
        para.paragraph_format.first_line_indent = Cm(-0.75)
        para.paragraph_format.left_indent = Cm(0.75)
        for r in para.runs:
            set_run_font(r, size=11)

    # ==================== Appendices ====================
    doc.add_page_break()
    h1(doc, "Appendix A. Model and Training Parameters")
    p(
        doc,
        "Defaults follow Table 4.1. Training entrypoint: python -m sdn_its.ai.train with "
        "--epochs/--batch_size/--lr. Checkpoint: models/checkpoints/tcn_gru_best.pt. Scaler: "
        "models/checkpoints/scaler.joblib when present.",
    )

    h1(doc, "Appendix B. Feature Definitions")
    add_table(
        doc,
        ["Feature", "Definition", "Unit / notes"],
        [
            ["flow_duration", "Observed flow duration", "seconds"],
            ["packet_rate", "Packets per interval", "packets/s"],
            ["byte_rate", "Bytes per interval", "bytes/s"],
            ["pkt_iat_mean", "Mean packet inter-arrival time", "ms"],
            ["pkt_iat_std", "Std. packet inter-arrival time", "ms"],
            ["packet_len_mean", "Mean packet length", "bytes"],
            ["packet_in_count", "Controller PacketIn-related count", "count/window"],
            ["tcp_flags_syn_count", "SYN flag count proxy", "count/window"],
            ["flow_active_ratio", "Active vs idle ratio", "ratio"],
            ["rsu_channel_occupancy", "Wireless/RSU load proxy", "ratio"],
        ],
        col_widths=[4.5, 6.5, 4.5],
    )
    caption(doc, "Table B.1. Canonical FEATURE_COLUMNS used by the prototype.")

    h1(doc, "Appendix C. Experiment Artifact Manifest")
    add_table(
        doc,
        ["Artifact", "Path"],
        [
            ["InSDN metrics", "artifacts/results/exp_insdn/metrics.json"],
            ["CIC zero-shot", "artifacts/results/cross_dataset/eval_metrics.json"],
            ["CIC adapted", "artifacts/results/cross_dataset/adapted_metrics.json"],
            ["Exp A OpenFlow", "artifacts/results/exp_a/exp_a_metrics.json"],
            ["Exp B/C fusion", "artifacts/results/exp_bc/exp_bc_fusion.json"],
            ["Sensitivity", "artifacts/results/exp_bc/exp_bc_sensitivity.json"],
            ["Exp D grades", "artifacts/results/exp_d/exp_d_phases.json"],
            ["Model card", "artifacts/models/model_card.json"],
        ],
        col_widths=[4.5, 11.0],
    )
    caption(doc, "Table C.1. Reproducibility manifest for preliminary results.")

    # Feature table for methodology (also listed earlier briefly)
    h1(doc, "Appendix D. Camera Evidence Grades (Detail)")
    add_table(
        doc,
        ["Experiment", "Camera source", "Context modified", "OpenFlow", "Claim allowed"],
        [
            ["B/C", "scripted", "yes", "no", "fusion rule behavior / sensitivity"],
            ["D-live", "live/synth observation", "no", "no", "detector/context availability"],
            ["D-scripted", "forced congestion", "yes", "optional", "policy wiring"],
            ["A", "none", "no", "yes", "reversible OpenFlow mitigation"],
        ],
        col_widths=[3.0, 4.0, 3.5, 2.0, 3.5],
    )
    caption(doc, "Table D.1. Camera/network evidence grades (expanded).")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # backup existing 4th if present
    if OUT.exists():
        bak = ROOT / "Trinh Hoang Tu_4th Version.prev.docx"
        try:
            if bak.exists():
                bak.unlink()
            OUT.replace(bak)
        except Exception:
            pass
    doc.save(str(OUT))
    OUT_DOCS.parent.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copyfile(OUT, OUT_DOCS)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    print(f"copied {OUT_DOCS}")
    return OUT


if __name__ == "__main__":
    build()
