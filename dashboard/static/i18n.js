/** EN/VI strings for the ops console. Technical terms kept in English when VI would sound awkward. */
(function (global) {
  const STR = {
    en: {
      "brand.mark": "Tsinghua IEDE · Transportation · AI · Security · IoT · Edge",
      "brand.sub":
        "RSU-zone SDN mitigation informed by physical context — anomaly detect · reversible contain · camera as context sensor (prototype, not a production ITS controller).",
      "btn.settings": "Settings",
      "btn.lang": "VI",
      "btn.lang.title": "Switch to Vietnamese",
      "live.online": "CONTROLLER ONLINE",
      "live.offline": "CONTROLLER OFFLINE",

      "report.title": "Report preview",
      "report.download": "Download .md",
      "report.close": "Close",
      "report.loading": "Loading…",

      "settings.title": "Settings",
      "settings.close": "Close",
      "settings.console": "Console",
      "settings.readonly": "Controller / model (read-only)",
      "settings.apply": "Apply",
      "settings.reset": "Reset",

      "set.poll": "Poll interval (ms)",
      "set.poll.help":
        "How often the UI refreshes status, active rules, and lab panels. Lower = snappier, higher CPU.",
      "set.tau": "τ threshold",
      "set.tau.help":
        "Reconstruction-error cutoff for RE-based anomaly flags. Does not retrain the model; Lab mode prefers the classifier head.",
      "set.ddos_cd": "DDoS cooldown (s)",
      "set.ddos_cd.help":
        "How long DROP / THROTTLE_PACKET_IN rules stay installed after a DDoS alert before auto-rollback.",
      "set.loft_cd": "LOFT cooldown (s)",
      "set.loft_cd.help":
        "TTL for RATE_LIMIT rules after a LOFT alert. Shorter = faster recovery, longer = stronger containment.",
      "set.ksigma": "Online k·σ",
      "set.ksigma.help":
        "When online τ adapt is on, τ = μ_RE + k·σ_RE over recent normal windows. Higher k → fewer RE alarms.",
      "set.dataset": "Dataset mode",
      "set.dataset.help":
        "Which data source the live scorer prefers for windows (sample / synthetic / InSDN path). Does not download datasets by itself.",
      "set.role": "Role mode",
      "set.role.help":
        "Research = full panels. Demo = simpler chrome. Debug = shows ONNX export and extra controls.",
      "set.theme": "Theme",
      "set.theme.help": "Visual density only — does not change detection or OpenFlow behavior.",
      "set.lab": "Lab mode",
      "set.lab.help":
        "Disables scenario label override and silent SIMULATION fallback. Predictions must come from the model (or DEGRADED).",
      "set.override": "Scenario label override",
      "set.override.help":
        "Demo only: forces attack_type to match the button you clicked. Off in Lab — use GT vs PRED instead.",
      "set.adapt": "Online τ adapt (μ+kσ)",
      "set.adapt.help":
        "Updates τ from recent normal RE samples while monitoring. Off = keep fixed τ from settings/checkpoint.",
      "set.compare": "Before/after compare mode",
      "set.compare.help":
        "Shows a reminder banner to contrast permanent-block baselines vs cooldown rollback (rush-hour should add 0 rules).",
      "set.webhook": "Alert webhook URL",
      "set.webhook.help":
        "Optional HTTP endpoint notified when containment or FP-avoid events fire. Empty = disabled path.",
      "set.webhook_on": "Enable webhooks",
      "set.webhook_on.help": "Master switch for outbound webhook posts (still needs a valid URL).",
      "set.ambient": "Ambient RE simulation",
      "set.ambient.help":
        "If live infer fails or is off, drift the RE chart locally. Lab mode never invents RE — leave off for reviews.",
      "set.refresh": "Auto-refresh dashboard",
      "set.refresh.help": "Poll /api/v1/status and related endpoints on the poll interval. Off = manual refresh only.",

      "opt.sample": "sample (canonical)",
      "opt.synthetic": "synthetic",
      "opt.insdn": "insdn raw",
      "opt.research": "Research",
      "opt.demo": "Demo",
      "opt.debug": "Debug",
      "opt.light": "Light ops",
      "opt.dark": "Dark ops",
      "opt.research_theme": "Research (dense)",

      "ro.version": "Version",
      "ro.port": "Port",
      "ro.seq": "Seq len L",
      "ro.feat": "Features",
      "ro.ksigma": "k·σ",
      "ro.classes": "Classes",
      "ro.csv": "Train CSV",
      "ro.raw": "InSDN raw",
      "ro.cooldown": "Default cooldown",

      "sim.banner":
        "SIMULATION / DEGRADED — numbers may not be real model inference. Check MODEL badge.",

      "pipe.vehicle": "Vehicle",
      "pipe.rsu": "RSU",
      "pipe.ovs": "OVS",
      "pipe.ctrl": "Controller",
      "pipe.tel": "Telemetry",
      "pipe.ai": "AI Model",
      "pipe.mit": "Mitigation",
      "pipe.rb": "Rollback",

      "metric.alerts": "Policy decisions",
      "metric.alerts.hint": "alerts → policy engine",
      "metric.rules": "Pending / in-memory rules",
      "metric.rules.hint": "not switch-verified unless NET ok",
      "metric.fp": "Rush-hour preserved (policy)",
      "metric.fp.hint": "not a counterfactual FP metric",
      "metric.re": "RE score",
      "metric.re.hint": "reconstruction error",
      "metric.tau": "τ threshold",
      "metric.tau.hint": "μ + kσ",
      "metric.uptime": "Uptime",
      "metric.uptime.hint": "controller process",

      "panel.re": "Reconstruction error vs τ",
      "panel.re.meta": "sliding window · L=10",
      "panel.rules": "Intended mitigation rules",
      "panel.rules.meta": "in-memory · await switch ack",
      "panel.emp": "Empirical metrics",
      "panel.emp.meta": "classifier head · cached eval",
      "panel.ovs": "OpenFlow / OVS lab",
      "panel.topo": "ITS edge topology",
      "panel.topo.meta": "s1 core · s2/s3/s4 RSU",
      "panel.events": "Event stream",
      "panel.events.meta": "OpenFlow · policy",

      "scen.a.k": "Attack A",
      "scen.a": "PacketIn flood (DDoS)",
      "scen.b.k": "Attack B",
      "scen.b": "LOFT low-rate probe",
      "scen.c.k": "Benign",
      "scen.c": "Rush-hour surge (no block)",

      "btn.play": "Play",
      "btn.stop": "Stop",
      "btn.preview": "Preview report",
      "btn.export": "Export report",
      "btn.onnx": "Export ONNX",
      "replay.idle": "Replay idle",
      "replay.full": "Replay · full story",
      "replay.ddos": "Replay · DDoS cycle",
      "replay.loft": "Replay · LOFT cycle",
      "replay.rush": "Replay · rush vs flood",
      "compare.banner":
        "COMPARE MODE — permanent-block baseline vs Detect→Contain→Rollback. Rush-hour should show 0 rules; flood should contain then rollback.",

      "table.rule": "Rule",
      "table.dpid": "DPID",
      "table.match": "Match",
      "table.action": "Action",
      "table.state": "State",
      "table.ttl": "TTL",
      "table.empty_rules": "No intended mitigations — forwarding nominal.",
      "rollback.armed": "[*] Cooldown daemon armed — expired rules auto-revoke.",

      "emp.eval": "Eval",
      "emp.n": "n",
      "emp.acc": "Acc",
      "emp.f1": "F1",
      "emp.auc": "AUC",
      "emp.loading": "Loading /api/v1/empirical…",
      "emp.note": "cls-head preferred over RE-τ",

      "ovs.hint": "No OVS dump yet — enable SDN_OF_BACKEND=http + WSL of_agent.",
      "topo.contain": "Containment highlights s1 when rules active",
      "topo.rollback": "Rollback clears highlight after cooldown",

      "log.ready": "SDN-ITS ops console ready · live infer + replay armed",
      "log.settings_hint":
        "Settings · Lab mode disables scenario cheat · empirical + OVS panels live",
      "log.settings_ok": "Settings synced",
      "log.settings_local": "Settings saved locally (server sync failed)",
      "log.poll_fail": "Poll failed — is the API up?",
      "log.preview_ok": "Report preview ready",
      "log.preview_fail": "Preview report failed",
      "log.export_ok": "Report downloaded",
      "log.export_disk": "Also saved on disk",
      "log.export_fail": "Export report failed",
      "log.degraded": "DEGRADED — no checkpoint; alert suppressed",
      "log.lab_normal": "Lab · model Normal / no anomaly — alert suppressed",
      "log.alert_fail": "Failed to POST /api/v1/anomaly_alert",
      "log.replay_fail": "Replay failed",
      "log.replay_done": "Replay complete",
      "log.onnx_fail": "ONNX export failed",
      "lab.after": " · model-driven",
    },
    vi: {
      "brand.mark": "Tsinghua IEDE · Transportation · AI · Security · IoT · Edge",
      "brand.sub":
        "Mitigation SDN theo vùng RSU + ngữ cảnh vật lý — phát hiện anomaly · contain tạm thời · camera là sensor ngữ cảnh (prototype, không phải controller ITS production).",
      "btn.settings": "Cài đặt",
      "btn.lang": "EN",
      "btn.lang.title": "Chuyển sang English",
      "live.online": "CONTROLLER ONLINE",
      "live.offline": "CONTROLLER OFFLINE",

      "report.title": "Xem trước report",
      "report.download": "Tải .md",
      "report.close": "Đóng",
      "report.loading": "Đang tải…",

      "settings.title": "Cài đặt",
      "settings.close": "Đóng",
      "settings.console": "Console",
      "settings.readonly": "Controller / model (chỉ đọc)",
      "settings.apply": "Áp dụng",
      "settings.reset": "Đặt lại",

      "set.poll": "Chu kỳ poll (ms)",
      "set.poll.help":
        "Tần suất UI gọi status, active rules và panel lab. Thấp hơn = mượt hơn, tốn CPU hơn.",
      "set.tau": "Ngưỡng τ",
      "set.tau.help":
        "Ngưỡng reconstruction error cho cảnh báo theo RE. Không train lại model; Lab mode ưu tiên classifier head.",
      "set.ddos_cd": "Cooldownoldown DDoS (s)",
      "set.ddos_cd.help":
        "Thời gian rule DROP / THROTTLE_PACKET_IN giữ sau alert DDoS trước khi auto-rollback.",
      "set.loft_cd": "Cooldownoldown LOFT (s)",
      "set.loft_cd.help":
        "TTL rule RATE_LIMIT sau alert LOFT. Ngắn = hồi phục nhanh; dài = contain lâu hơn.",
      "set.ksigma": "Online k·σ",
      "set.ksigma.help":
        "Khi bật adapt τ: τ = μ_RE + k·σ_RE trên cửa sổ normal gần nhất. k cao → ít báo động RE hơn.",
      "set.dataset": "Dataset mode",
      "set.dataset.help":
        "Nguồn cửa sổ telemetry live scorer ưu tiên (sample / synthetic / InSDN). Không tự tải dataset.",
      "set.role": "Role mode",
      "set.role.help":
        "Research = đủ panel. Demo = giao diện gọn. Debug = hiện Export ONNX và control thêm.",
      "set.theme": "Theme",
      "set.theme.help": "Chỉ đổi giao diện — không đổi detection hay OpenFlow.",
      "set.lab": "Lab mode",
      "set.lab.help":
        "Tắt ghi đè nhãn scenario và fallback SIMULATION im lặng. Prediction phải từ model (hoặc DEGRADED).",
      "set.override": "Scenario label override",
      "set.override.help":
        "Chỉ demo: ép attack_type theo nút vừa bấm. Lab tắt — dùng GT vs PRED để đánh giá.",
      "set.adapt": "Online τ adapt (μ+kσ)",
      "set.adapt.help":
        "Cập nhật τ từ mẫu RE normal khi đang monitor. Tắt = giữ τ cố định từ settings/checkpoint.",
      "set.compare": "Compare mode (before/after)",
      "set.compare.help":
        "Hiện banner nhắc so permanent-block với cooldown rollback (rush-hour = 0 rule; flood = contain rồi rollback).",
      "set.webhook": "Webhook URL (alert)",
      "set.webhook.help":
        "Endpoint HTTP (tuỳ chọn) khi có contain hoặc tránh FP. Để trống = không gửi.",
      "set.webhook_on": "Bật webhook",
      "set.webhook_on.help": "Công tắc gửi webhook (vẫn cần URL hợp lệ).",
      "set.ambient": "Ambient RE simulation",
      "set.ambient.help":
        "Khi live infer lỗi/tắt, tự dao động chart RE trên client. Lab không bịa RE — nên tắt khi review.",
      "set.refresh": "Tự làm mới dashboard",
      "set.refresh.help": "Poll /api/v1/status theo chu kỳ. Tắt = chỉ cập nhật khi thao tác.",

      "opt.sample": "sample (canonical)",
      "opt.synthetic": "synthetic",
      "opt.insdn": "insdn raw",
      "opt.research": "Research",
      "opt.demo": "Demo",
      "opt.debug": "Debug",
      "opt.light": "Light ops",
      "opt.dark": "Dark ops",
      "opt.research_theme": "Research (dense)",

      "ro.version": "Version",
      "ro.port": "Port",
      "ro.seq": "Seq len L",
      "ro.feat": "Features",
      "ro.ksigma": "k·σ",
      "ro.classes": "Classes",
      "ro.csv": "Train CSV",
      "ro.raw": "InSDN raw",
      "ro.cooldown": "Default cooldown",

      "sim.banner":
        "SIMULATION / DEGRADED — số trên UI có thể không phải inference thật. Kiểm tra badge MODEL.",

      "pipe.vehicle": "Vehicle",
      "pipe.rsu": "RSU",
      "pipe.ovs": "OVS",
      "pipe.ctrl": "Controller",
      "pipe.tel": "Telemetry",
      "pipe.ai": "AI Model",
      "pipe.mit": "Mitigation",
      "pipe.rb": "Rollback",

      "metric.alerts": "Quyết định policy",
      "metric.alerts.hint": "alert → policy engine",
      "metric.rules": "Rule tạm / in-memory",
      "metric.rules.hint": "chưa verify switch trừ khi NET ok",
      "metric.fp": "Rush-hour giữ bởi policy",
      "metric.fp.hint": "không phải metric FP counterfactual",
      "metric.re": "RE score",
      "metric.re.hint": "reconstruction error",
      "metric.tau": "Ngưỡng τ",
      "metric.tau.hint": "μ + kσ",
      "metric.uptime": "Uptime",
      "metric.uptime.hint": "tiến trình controller",

      "panel.re": "Reconstruction error vs τ",
      "panel.re.meta": "sliding window · L=10",
      "panel.rules": "Rule mitigation dự kiến",
      "panel.rules.meta": "in-memory · chờ switch ack",
      "panel.emp": "Empirical metrics",
      "panel.emp.meta": "classifier head · cached eval",
      "panel.ovs": "OpenFlow / OVS lab",
      "panel.topo": "ITS edge topology",
      "panel.topo.meta": "s1 core · s2/s3/s4 RSU",
      "panel.events": "Event stream",
      "panel.events.meta": "OpenFlow · policy",

      "scen.a.k": "Attack A",
      "scen.a": "PacketIn flood (DDoS)",
      "scen.b.k": "Attack B",
      "scen.b": "LOFT low-rate probe",
      "scen.c.k": "Benign",
      "scen.c": "Rush-hour surge (không block)",

      "btn.play": "Play",
      "btn.stop": "Stop",
      "btn.preview": "Xem report",
      "btn.export": "Xuất report",
      "btn.onnx": "Export ONNX",
      "replay.idle": "Replay idle",
      "replay.full": "Replay · full story",
      "replay.ddos": "Replay · DDoS cycle",
      "replay.loft": "Replay · LOFT cycle",
      "replay.rush": "Replay · rush vs flood",
      "compare.banner":
        "COMPARE MODE — so permanent-block với Detect→Contain→Rollback. Rush-hour = 0 rule; flood = contain rồi rollback.",

      "table.rule": "Rule",
      "table.dpid": "DPID",
      "table.match": "Match",
      "table.action": "Action",
      "table.ttl": "TTL",
      "table.state": "Trạng thái",
      "table.empty_rules": "Không có rule dự kiến — forwarding bình thường.",
      "rollback.armed": "[*] Cooldown daemon sẵn sàng — rule hết hạn tự revoke.",

      "emp.eval": "Eval",
      "emp.n": "n",
      "emp.acc": "Acc",
      "emp.f1": "F1",
      "emp.auc": "AUC",
      "emp.loading": "Đang tải /api/v1/empirical…",
      "emp.note": "ưu tiên cls-head hơn RE-τ",

      "ovs.hint": "Chưa có OVS dump — bật SDN_OF_BACKEND=http + WSL of_agent.",
      "topo.contain": "Containment tô sáng s1 khi có rule",
      "topo.rollback": "Rollback xóa highlight sau cooldown",

      "log.ready": "Console SDN-ITS sẵn sàng · live infer + replay",
      "log.settings_hint":
        "Cài đặt · Lab mode tắt scenario cheat · panel empirical + OVS",
      "log.settings_ok": "Đã đồng bộ settings",
      "log.settings_local": "Đã lưu local (sync server lỗi)",
      "log.poll_fail": "Poll lỗi — API đã chạy chưa?",
      "log.preview_ok": "Report preview sẵn sàng",
      "log.preview_fail": "Preview report thất bại",
      "log.export_ok": "Đã tải report",
      "log.export_disk": "Đã lưu trên disk",
      "log.export_fail": "Xuất report thất bại",
      "log.degraded": "DEGRADED — không có checkpoint; bỏ qua alert",
      "log.lab_normal": "Lab · model Normal / không anomaly — bỏ qua alert",
      "log.alert_fail": "POST /api/v1/anomaly_alert thất bại",
      "log.replay_fail": "Replay thất bại",
      "log.replay_done": "Replay xong",
      "log.onnx_fail": "Export ONNX thất bại",
      "lab.after": " · model-driven",
    },
  };

  let lang = "en";

  function t(key, vars) {
    const table = STR[lang] || STR.en;
    let s = table[key] ?? STR.en[key] ?? key;
    if (vars) {
      Object.keys(vars).forEach((k) => {
        s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(vars[k]));
      });
    }
    return s;
  }

  function setLang(next) {
    lang = next === "vi" ? "vi" : "en";
    try {
      localStorage.setItem("sdn_its_lang", lang);
    } catch (_) {}
    document.documentElement.setAttribute("lang", lang === "vi" ? "vi" : "en");
    applyI18n();
    return lang;
  }

  function getLang() {
    return lang;
  }

  function applyI18n() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;
      const attr = el.getAttribute("data-i18n-attr");
      const val = t(key);
      if (attr) el.setAttribute(attr, val);
      else el.textContent = val;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
    });
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
    });
    try {
      document.documentElement.style.setProperty("--lab-after", JSON.stringify(t("lab.after")));
    } catch (_) {}
    const btn = document.getElementById("btn-lang");
    if (btn) {
      btn.textContent = t("btn.lang");
      btn.setAttribute("title", t("btn.lang.title"));
    }
    const live = document.getElementById("live-label");
    if (live && /CONTROLLER|ONLINE|OFFLINE/i.test(live.textContent || "")) {
      const offline = /OFFLINE/i.test(live.textContent || "");
      live.textContent = offline ? t("live.offline") : t("live.online");
    }
    document.dispatchEvent(new CustomEvent("i18n:applied", { detail: { lang } }));
  }

  function init() {
    let saved = "en";
    try {
      saved = localStorage.getItem("sdn_its_lang") || "en";
    } catch (_) {}
    lang = saved === "vi" ? "vi" : "en";
    document.documentElement.setAttribute("lang", lang === "vi" ? "vi" : "en");
  }

  init();
  global.SDNI18N = { t, setLang, getLang, applyI18n, STR };
  global.t = t;
})(typeof window !== "undefined" ? window : globalThis);
