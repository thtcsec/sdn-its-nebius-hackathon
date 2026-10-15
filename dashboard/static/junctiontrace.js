/**
 * JunctionTrace product UI — Nebius × NVIDIA hackathon.
 * Never exposes NEBIUS_API_KEY. Never labels offline planner as live Nemotron.
 */
(() => {
  const PRODUCT_SCENARIOS = [
    {
      id: "scenario_rush_vs_attack",
      letter: "A",
      title: "Legitimate congestion",
      blurb: "Surge looks like DDoS, but the junction queue is real — avoid pointless disruption.",
      why: "Operators must preserve legitimate mobility traffic during rush hour.",
    },
    {
      id: "scenario_loft_stable",
      letter: "B",
      title: "Credible cyberattack",
      blurb: "Low-rate anomaly with a quiet, stable physical zone — proportionate response may be justified.",
      why: "Quiet roads weaken the “just congestion” explanation.",
    },
    {
      id: "scenario_missing_camera",
      letter: "C",
      title: "Missing / stale evidence",
      blurb: "Physical context is unavailable or stale — prefer caution over hard containment.",
      why: "Containing without trustworthy context risks false disruption.",
    },
    {
      id: "scenario_conflict_signals",
      letter: "D",
      title: "Contradictory signals",
      blurb: "Network attack label conflicts with a busy physical queue — investigate further.",
      why: "Cyber and physical views disagree; jumping to drop is premature.",
    },
  ];

  const TOOL_HELP = {
    retrieve_network_telemetry: "Read PacketIn / dominance fields for the window",
    inspect_camera_metadata: "Inspect same-zone camera metadata (synthetic in demo)",
    check_physical_evidence_quality: "Judge whether physical evidence is sufficient / stale",
    compare_temporal_windows: "Compare current telemetry to a prior baseline",
    identify_contradictions: "Flag cyber vs physical contradictions",
    escalate_human_review: "Request human review when still uncertain",
  };

  const state = {
    mode: "offline",
    scenarioId: PRODUCT_SCENARIOS[0].id,
    capabilities: null,
    running: false,
  };

  const $ = (id) => document.getElementById(id);

  function setError(msg) {
    const el = $("error-banner");
    if (!msg) {
      el.classList.remove("show");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.classList.add("show");
  }

  function renderScenarios() {
    const grid = $("scenario-grid");
    grid.innerHTML = "";
    for (const s of PRODUCT_SCENARIOS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "scenario-card" + (s.id === state.scenarioId ? " selected" : "");
      btn.setAttribute("role", "option");
      btn.setAttribute("aria-selected", s.id === state.scenarioId ? "true" : "false");
      btn.dataset.id = s.id;
      btn.innerHTML = `<div class="letter">Scenario ${s.letter}</div><h3>${s.title}</h3><p>${s.blurb}</p>`;
      btn.addEventListener("click", () => {
        state.scenarioId = s.id;
        renderScenarios();
      });
      grid.appendChild(btn);
    }
  }

  function setMode(mode) {
    state.mode = mode;
    $("mode-offline").classList.toggle("active", mode === "offline");
    $("mode-real").classList.toggle("active", mode === "real");
    const realReady = Boolean(state.capabilities?.nebius_api_key_present);
    if (mode === "real" && !realReady) {
      $("mode-hint").textContent =
        "Real Nebius requires a server-side NEBIUS_API_KEY. Credentials are not present — switch stays available but the call will fail closed.";
    } else if (mode === "real") {
      $("mode-hint").textContent =
        "Real mode calls NVIDIA Nemotron via Nebius Token Factory. Offline planner results are never shown as live inference.";
    } else {
      $("mode-hint").textContent =
        "Offline uses a deterministic planner with real tool logic — never labeled as live Nemotron.";
    }
  }

  async function loadCapabilities() {
    try {
      const r = await fetch("/api/v1/hackathon/capabilities");
      const data = await r.json();
      state.capabilities = data;
      const chip = $("cap-mode");
      if (data.nebius_api_key_present) {
        chip.textContent = "Nebius credentials: ready";
        chip.classList.add("on");
      } else {
        chip.textContent = "Nebius credentials: not configured";
        chip.classList.add("warn");
      }
      $("cap-model").textContent = `Model: ${data.nebius_model || "Nemotron"}`;
      $("cap-of").textContent = `OpenFlow: ${data.of_backend_default || "mock"}`;
      setMode(state.mode);
    } catch (e) {
      $("cap-mode").textContent = "Capabilities unavailable";
      $("cap-mode").classList.add("warn");
    }
  }

  function resetTimeline() {
    document.querySelectorAll(".step").forEach((el) => {
      el.classList.remove("active", "done");
    });
    for (let i = 1; i <= 7; i++) {
      const d = $(`d${i}`);
      if (d) d.textContent = "";
    }
  }

  function activateStep(n, detail) {
    document.querySelectorAll(".step").forEach((el) => {
      const sn = Number(el.dataset.step);
      el.classList.toggle("active", sn === n);
      el.classList.toggle("done", sn < n);
    });
    const d = $(`d${n}`);
    if (d && detail != null) d.textContent = detail;
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function toolsFromTrace(trace) {
    const tools = [];
    for (const t of trace || []) {
      if (t.phase === "select_evidence_tool" && t.detail?.tool) {
        tools.push(t.detail.tool);
      }
    }
    return tools;
  }

  function retrievesFromTrace(trace) {
    const out = [];
    for (const t of trace || []) {
      if (t.phase === "retrieve_validate") {
        out.push(t.detail?.summary || t.detail?.tool || "retrieved");
      }
    }
    return out;
  }

  function uncertaintiesFromTrace(trace) {
    for (const t of trace || []) {
      if (t.phase === "identify_uncertainty") {
        return t.detail?.uncertainties || [];
      }
    }
    return [];
  }

  function gateStatus(payload) {
    const notes = payload.gated_notes || [];
    const pre = payload.pre_gate_action;
    const final = payload.recommendation?.recommended_action;
    const changed = Boolean(pre && final && pre !== final);
    const forced = notes.some((n) => /gate:|forced|deescalat|block|telemetry_unreliable/i.test(String(n)));
    if (!payload.apply_gate && notes.includes("gate:skipped_ablation_arm")) {
      return { label: "SKIPPED", cls: "offline", detail: "Gate skipped (ablation)." };
    }
    if (changed || forced) {
      return {
        label: "OVERRIDE",
        cls: "override",
        detail: `pre=${pre || "—"} → final=${final || "—"} · ${notes.join("; ") || "policy clamp"}`,
      };
    }
    if (final === "observe" && notes.some((n) => /abstain|insufficient|unreliable/i.test(String(n)))) {
      return { label: "ABSTAIN", cls: "override", detail: notes.join("; ") || "observe preferred" };
    }
    return { label: "PASS", cls: "pass", detail: notes.length ? notes.join("; ") : "No policy clamp — advisory unchanged." };
  }

  function evidenceClassBadge(ec) {
    if (ec === "real_api") return '<span class="badge live">LIVE Nebius / real_api</span>';
    if (ec === "deterministic_planner") return '<span class="badge offline">deterministic planner (offline)</span>';
    if (ec === "validation_error") return '<span class="badge err">validation_error</span>';
    if (ec === "blocked_no_credentials") return '<span class="badge err">blocked_no_credentials</span>';
    return `<span class="badge">${ec || "unknown"}</span>`;
  }

  function renderResult(payload, scenarioMeta) {
    const rec = payload.recommendation || {};
    const rule = payload.rule || {};
    const bundle = payload.bundle || {};
    const tel = bundle.telemetry || {};
    const cam = bundle.camera || {};
    const gate = gateStatus(payload);
    const source = payload.pre_gate_source || payload.conclusion_kind || "—";
    const latency = payload.latency_ms != null ? `${Math.round(payload.latency_ms)} ms` : "—";
    const cost =
      payload.estimated_cost_usd != null ? `$${Number(payload.estimated_cost_usd).toFixed(5)}` : "—";
    const usage = payload.usage || {};
    const tokens = usage.total_tokens != null ? `${usage.total_tokens} tokens` : "";

    $("result-body").innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:0.4rem;margin-bottom:0.75rem">
        ${evidenceClassBadge(payload.evidence_class)}
        <span class="badge synth">synthetic camera metadata</span>
        <span class="badge">OF ${payload.of_backend || "mock"}</span>
        <span class="badge ${gate.cls}">gate ${gate.label}</span>
      </div>
      <dl class="kv">
        <dt>Scenario</dt><dd>${scenarioMeta.title} (${scenarioMeta.id})</dd>
        <dt>Network alarm</dt><dd>${bundle.network_prediction || "—"}</dd>
        <dt>RSU / DPID</dt><dd>zone demo · dpid mock</dd>
        <dt>Telemetry ΔPIN</dt><dd>${tel.packet_in_delta_pct ?? "—"} · dominance ${tel.source_dominance ?? "—"}</dd>
        <dt>Camera</dt><dd>${cam.physical_label || "—"} / ${cam.activity_band || "—"} · tracks ${cam.visible_vehicle_tracks ?? "—"} · stale=${cam.stale}</dd>
        <dt>Conclusion source</dt><dd>${source}</dd>
        <dt>Latency / cost</dt><dd>${latency} · ${cost} ${tokens}</dd>
      </dl>
      <div class="outcome">
        <div class="mode-hint">Recommended next action</div>
        <p class="action">${rec.recommended_action || (payload.ok ? "—" : "fail-closed")}</p>
        <p style="color:var(--muted);font-size:0.9rem;margin:0">${rec.rationale || payload.error || "No rationale."}</p>
      </div>
      <div class="compare">
        <div class="mini">
          <h4>Rule-only baseline</h4>
          <strong>${rule.recommended_action || "—"}</strong>
          <p style="margin:0.35rem 0 0;color:var(--muted);font-size:0.78rem">${rule.rationale || rule.evidence_class || ""}</p>
        </div>
        <div class="mini">
          <h4>Investigation + gate</h4>
          <strong>${rec.recommended_action || "—"}</strong>
          <p style="margin:0.35rem 0 0;color:var(--muted);font-size:0.78rem">kind=${payload.conclusion_kind || "—"}</p>
        </div>
      </div>
      <p style="margin:1rem 0 0;color:var(--muted);font-size:0.82rem"><strong>Why it matters:</strong> ${scenarioMeta.why}</p>
      <p style="margin:0.5rem 0 0;color:var(--muted);font-size:0.78rem">Remaining uncertainty is recorded in the audit trail. No live switch containment is performed.</p>
    `;
  }

  async function animateFromPayload(payload, scenarioMeta) {
    const trace = payload.trace || [];
    const tools = toolsFromTrace(trace);
    const retrieves = retrievesFromTrace(trace);
    const unc = uncertaintiesFromTrace(trace);
    const bundle = payload.bundle || {};
    const tel = bundle.telemetry || {};
    const cam = bundle.camera || {};

    activateStep(
      1,
      `alarm=${bundle.network_prediction}\nΔPacketIn=${tel.packet_in_delta_pct ?? "n/a"}%\nsource=synthetic/demo fixture`,
    );
    await sleep(280);

    activateStep(2, unc.length ? unc.join("\n") : "no open uncertainties listed");
    await sleep(280);

    if (tools.length) {
      const lines = tools.map((t, i) => `${i + 1}. ${t} — ${TOOL_HELP[t] || "evidence tool"}`);
      const who =
        payload.evidence_class === "real_api"
          ? "Selected during live Nemotron tool rounds"
          : "Selected by deterministic planner (offline)";
      activateStep(3, `${who}\n${lines.join("\n")}`);
    } else {
      activateStep(3, "No tool selections recorded");
    }
    await sleep(320);

    activateStep(
      4,
      [
        ...retrieves.slice(0, 4),
        `camera label=${cam.physical_label} band=${cam.activity_band} (synthetic metadata)`,
        `stale=${cam.stale} analytics_valid=${cam.analytics_valid}`,
      ].join("\n"),
    );
    await sleep(280);

    const rec = payload.recommendation || {};
    const src = payload.pre_gate_source || "—";
    const fallback = src === "deterministic_fallback" ? "FALLBACK (not model conclude)" : "model/planner conclude path";
    activateStep(
      5,
      `action=${rec.recommended_action || "none"}\nsource=${src}\n${fallback}\nlatency=${payload.latency_ms != null ? Math.round(payload.latency_ms) + " ms" : "—"}\n${rec.rationale || payload.error || ""}`,
    );
    await sleep(280);

    const gate = gateStatus(payload);
    activateStep(6, `${gate.label}\n${gate.detail}`);
    await sleep(220);

    activateStep(
      7,
      `advise=${rec.recommended_action || "fail-closed"}\nOF=${payload.of_backend || "mock"} (no live containment)\naudit recorded`,
    );
    document.querySelectorAll(".step").forEach((el) => {
      el.classList.add("done");
      el.classList.remove("active");
    });
    renderResult(payload, scenarioMeta);
  }

  async function runInvestigation() {
    if (state.running) return;
    setError("");
    state.running = true;
    $("btn-investigate").disabled = true;
    $("loading-state").hidden = false;
    $("result-body").innerHTML = "";
    resetTimeline();
    activateStep(1, "Starting…");
    document.getElementById("investigation-board").scrollIntoView({ behavior: "smooth", block: "start" });

    const scenarioMeta = PRODUCT_SCENARIOS.find((s) => s.id === state.scenarioId) || PRODUCT_SCENARIOS[0];

    try {
      const r = await fetch("/api/v1/hackathon/multistep", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_id: state.scenarioId,
          mode: state.mode,
          demo_mode: true,
          apply_gate: true,
          include_camera: true,
          allow_containment_in_demo: true,
        }),
      });
      const payload = await r.json();
      $("loading-state").hidden = true;

      if (!r.ok && !payload.trace) {
        const msg =
          payload.error ||
          (r.status === 502
            ? "Investigation failed closed (validation / API). See details below."
            : `HTTP ${r.status}`);
        setError(msg);
        activateStep(5, msg);
        activateStep(7, "Operator: treat as fail-closed observe / escalate to human.");
        $("result-body").innerHTML = `
          <span class="badge err">error</span>
          <p style="margin-top:0.75rem">${msg}</p>
          <p class="mode-hint">Offline planner or Real Nebius may fail closed on malformed model output or missing credentials. No live containment is applied.</p>
        `;
        return;
      }

      // Honesty: if offline, never claim live
      if (state.mode === "offline" && payload.evidence_class === "real_api") {
        setError("Inconsistent labeling: offline mode returned real_api — treating display as error.");
      }
      if (state.mode === "real" && payload.evidence_class === "deterministic_planner") {
        setError("Real mode did not reach Nebius; showing labeled deterministic/fallback path.");
      }
      if (payload.evidence_class === "blocked_no_credentials") {
        setError("NEBIUS_API_KEY unavailable on server — fail closed. Use Safe offline, or configure credentials server-side.");
      }
      if (payload.evidence_class === "validation_error") {
        setError(`Model/schema validation failed: ${payload.error || "invalid recommendation"}`);
      }

      await animateFromPayload(payload, scenarioMeta);
    } catch (e) {
      $("loading-state").hidden = true;
      setError(`Request failed: ${e.message || e}`);
      activateStep(7, "Network or server error — no containment intended.");
    } finally {
      state.running = false;
      $("btn-investigate").disabled = false;
    }
  }

  function bind() {
    renderScenarios();
    $("btn-investigate").addEventListener("click", runInvestigation);
    $("btn-scroll-scenarios").addEventListener("click", () => {
      $("scenario-grid").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    $("mode-offline").addEventListener("click", () => setMode("offline"));
    $("mode-real").addEventListener("click", () => setMode("real"));
    loadCapabilities();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
