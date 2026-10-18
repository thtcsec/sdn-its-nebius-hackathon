/**
 * JunctionTrace product UI — Nebius × NVIDIA hackathon.
 * Never exposes NEBIUS_API_KEY. Never labels offline planner as live Nemotron.
 * Untrusted API strings are applied via textContent only (no HTML interpolation).
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
      title: "Quiet zone + low-rate anomaly",
      blurb:
        "Rule-only often rate-limits. Investigation may still observe if evidence is thin — watch the full trace; model outcomes vary.",
      why: "Quiet roads weaken a pure-congestion story, but uncertainty can still justify caution over hard contain.",
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
    judgeToken: "", // session memory only — never localStorage
  };

  const $ = (id) => document.getElementById(id);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = String(text);
    return node;
  }

  function clearChildren(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function setError(msg) {
    const banner = $("error-banner");
    if (!msg) {
      banner.classList.remove("show");
      banner.textContent = "";
      return;
    }
    banner.textContent = msg;
    banner.classList.add("show");
  }

  function authHeaders() {
    const headers = { "Content-Type": "application/json" };
    const tok = (state.judgeToken || "").trim();
    if (tok) headers["X-API-Token"] = tok;
    return headers;
  }

  function renderScenarios() {
    const grid = $("scenario-grid");
    clearChildren(grid);
    for (const s of PRODUCT_SCENARIOS) {
      const btn = el("button", "scenario-card" + (s.id === state.scenarioId ? " selected" : ""));
      btn.type = "button";
      btn.setAttribute("role", "option");
      btn.setAttribute("aria-selected", s.id === state.scenarioId ? "true" : "false");
      btn.dataset.id = s.id;
      btn.appendChild(el("div", "letter", `Scenario ${s.letter}`));
      btn.appendChild(el("h3", null, s.title));
      btn.appendChild(el("p", null, s.blurb));
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
        "Real Nebius requires a server-side NEBIUS_API_KEY. Credentials are not present — Real mode cannot produce live inference.";
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
      const tokenRow = $("token-row");
      if (tokenRow) {
        tokenRow.hidden = !data.api_token_required;
      }
      setMode(state.mode);
    } catch (e) {
      $("cap-mode").textContent = "Capabilities unavailable";
      $("cap-mode").classList.add("warn");
    }
  }

  function resetTimeline() {
    document.querySelectorAll(".step").forEach((node) => {
      node.classList.remove("active", "done");
    });
    for (let i = 1; i <= 7; i++) {
      const d = $(`d${i}`);
      if (d) d.textContent = "";
    }
  }

  function activateStep(n, detail) {
    document.querySelectorAll(".step").forEach((node) => {
      const sn = Number(node.dataset.step);
      node.classList.toggle("active", sn === n);
      node.classList.toggle("done", sn < n);
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

  function appendBadge(parent, className, text) {
    parent.appendChild(el("span", `badge ${className || ""}`.trim(), text));
  }

  function evidenceClassLabel(ec) {
    if (ec === "real_api") return { cls: "live", text: "LIVE Nebius / real_api" };
    if (ec === "deterministic_planner") return { cls: "offline", text: "deterministic planner (offline)" };
    if (ec === "validation_error") return { cls: "err", text: "validation_error" };
    if (ec === "blocked_no_credentials") return { cls: "err", text: "blocked_no_credentials" };
    if (ec === "blocked_guard") return { cls: "err", text: "blocked_guard" };
    return { cls: "", text: ec || "unknown" };
  }

  function addKv(dl, dtText, ddText) {
    dl.appendChild(el("dt", null, dtText));
    dl.appendChild(el("dd", null, ddText));
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

    const root = $("result-body");
    clearChildren(root);

    const badges = el("div", "badge-row");
    badges.style.display = "flex";
    badges.style.flexWrap = "wrap";
    badges.style.gap = "0.4rem";
    badges.style.marginBottom = "0.75rem";
    const ec = evidenceClassLabel(payload.evidence_class);
    appendBadge(badges, ec.cls, ec.text);
    appendBadge(badges, "synth", "synthetic camera metadata");
    appendBadge(badges, "", `OF ${payload.of_backend || "mock"}`);
    appendBadge(badges, gate.cls, `gate ${gate.label}`);
    root.appendChild(badges);

    const dl = el("dl", "kv");
    addKv(dl, "Scenario", `${scenarioMeta.title} (${scenarioMeta.id})`);
    addKv(dl, "Network alarm", String(bundle.network_prediction || "—"));
    addKv(dl, "RSU / DPID", "zone demo · dpid mock");
    addKv(
      dl,
      "Telemetry ΔPIN",
      `${tel.packet_in_delta_pct ?? "—"} · dominance ${tel.source_dominance ?? "—"}`,
    );
    addKv(
      dl,
      "Camera",
      `${cam.physical_label || "—"} / ${cam.activity_band || "—"} · tracks ${cam.visible_vehicle_tracks ?? "—"} · stale=${cam.stale}`,
    );
    addKv(dl, "Conclusion source", String(source));
    addKv(dl, "Latency / cost", `${latency} · ${cost} ${tokens}`.trim());
    root.appendChild(dl);

    const outcome = el("div", "outcome");
    outcome.appendChild(el("div", "mode-hint", "Recommended next action"));
    outcome.appendChild(
      el("p", "action", rec.recommended_action || (payload.ok ? "—" : "fail-closed")),
    );
    const rationale = el("p", "rationale");
    rationale.style.color = "var(--muted)";
    rationale.style.fontSize = "0.9rem";
    rationale.style.margin = "0";
    rationale.textContent = rec.rationale || payload.error || "No rationale.";
    outcome.appendChild(rationale);
    root.appendChild(outcome);

    const compare = el("div", "compare");
    const miniRule = el("div", "mini");
    miniRule.appendChild(el("h4", null, "Rule-only baseline"));
    miniRule.appendChild(el("strong", null, rule.recommended_action || "—"));
    const ruleP = el("p", null, rule.rationale || rule.evidence_class || "");
    ruleP.style.margin = "0.35rem 0 0";
    ruleP.style.color = "var(--muted)";
    ruleP.style.fontSize = "0.78rem";
    miniRule.appendChild(ruleP);

    const miniInv = el("div", "mini");
    miniInv.appendChild(el("h4", null, "Investigation + gate"));
    miniInv.appendChild(el("strong", null, rec.recommended_action || "—"));
    const invP = el("p", null, `kind=${payload.conclusion_kind || "—"}`);
    invP.style.margin = "0.35rem 0 0";
    invP.style.color = "var(--muted)";
    invP.style.fontSize = "0.78rem";
    miniInv.appendChild(invP);

    compare.appendChild(miniRule);
    compare.appendChild(miniInv);
    root.appendChild(compare);

    const why = el("p", null, "");
    why.style.margin = "1rem 0 0";
    why.style.color = "var(--muted)";
    why.style.fontSize = "0.82rem";
    const whyStrong = el("strong", null, "Why it matters: ");
    why.appendChild(whyStrong);
    why.appendChild(document.createTextNode(scenarioMeta.why));
    root.appendChild(why);

    const foot = el(
      "p",
      null,
      "Remaining uncertainty is recorded in the audit trail. No live switch containment is performed.",
    );
    foot.style.margin = "0.5rem 0 0";
    foot.style.color = "var(--muted)";
    foot.style.fontSize = "0.78rem";
    root.appendChild(foot);
  }

  function renderErrorBody(msg) {
    const root = $("result-body");
    clearChildren(root);
    appendBadge(root, "err", "error");
    const p = el("p", null, msg);
    p.style.marginTop = "0.75rem";
    root.appendChild(p);
    root.appendChild(
      el(
        "p",
        "mode-hint",
        "Offline planner or Real Nebius may fail closed on malformed output, missing credentials, rate limits, or budget exhaustion. No live containment is applied.",
      ),
    );
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
    const fallback =
      src === "deterministic_fallback" ? "FALLBACK (not model conclude)" : "model/planner conclude path";
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
    document.querySelectorAll(".step").forEach((node) => {
      node.classList.add("done");
      node.classList.remove("active");
    });
    renderResult(payload, scenarioMeta);
  }

  async function runInvestigation() {
    if (state.running) return;
    setError("");
    state.running = true;
    $("btn-investigate").disabled = true;
    $("loading-state").hidden = false;
    clearChildren($("result-body"));
    resetTimeline();
    activateStep(1, "Starting…");
    document.getElementById("investigation-board").scrollIntoView({ behavior: "smooth", block: "start" });

    const scenarioMeta = PRODUCT_SCENARIOS.find((s) => s.id === state.scenarioId) || PRODUCT_SCENARIOS[0];
    const tokInput = $("judge-token");
    if (tokInput) state.judgeToken = tokInput.value || "";

    try {
      const r = await fetch("/api/v1/hackathon/multistep", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          scenario_id: state.scenarioId,
          mode: state.mode,
          demo_mode: true,
          apply_gate: true,
          include_camera: true,
          // Hosted servers ignore client containment overrides; product UI never requests contain.
          allow_containment_in_demo: false,
        }),
      });
      const payload = await r.json();
      $("loading-state").hidden = true;

      if (r.status === 401) {
        setError("Unauthorized — provide the judge API token when the server requires SDN_API_TOKEN.");
        renderErrorBody(payload.detail || payload.error || "unauthorized");
        return;
      }
      if (r.status === 429) {
        setError(payload.detail || payload.error || "Rate limit or budget exhausted.");
        renderErrorBody(payload.detail || payload.error || "rate_limited");
        return;
      }

      if (!r.ok && !payload.trace) {
        const msg =
          payload.detail ||
          payload.error ||
          (r.status === 502
            ? "Investigation failed closed (validation / API). See details below."
            : `HTTP ${r.status}`);
        setError(msg);
        activateStep(5, msg);
        activateStep(7, "Operator: treat as fail-closed observe / escalate to human.");
        renderErrorBody(msg);
        return;
      }

      if (state.mode === "offline" && payload.evidence_class === "real_api") {
        setError("Inconsistent labeling: offline mode returned real_api — treating display as error.");
      }
      if (state.mode === "real" && payload.evidence_class === "deterministic_planner") {
        setError("Real mode did not reach Nebius; showing labeled deterministic/fallback path.");
      }
      if (payload.evidence_class === "blocked_no_credentials") {
        setError(
          "NEBIUS_API_KEY unavailable on server — fail closed. Use Safe offline, or configure credentials server-side.",
        );
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
