"use strict";
const $ = (s, r = document) => r.querySelector(s);
const store = { get(k) { try { return sessionStorage.getItem(k); } catch { return null; } }, set(k, v) { try { sessionStorage.setItem(k, v); } catch {} } };
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) e.append(c && c.nodeType ? c : document.createTextNode(c ?? ""));
  return e;
}
async function api(path, { method = "GET", body, raw } = {}) {
  const r = await fetch("/api/v1" + path, { method, headers: { "X-API-Key": store.get("key") || "", ...(body ? { "Content-Type": "application/json" } : {}) }, body: body ? JSON.stringify(body) : undefined });
  if (raw) { if (!r.ok) throw new Error(r.statusText); return r.blob(); }
  let data = null; try { data = await r.json(); } catch {}
  if (!r.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : r.status === 401 ? "Missing or invalid API key." : r.statusText);
  }
  return data;
}
const banner = (msg, ok) => { const b = $("#banner"); b.hidden = !msg; b.textContent = msg || ""; b.className = "banner" + (ok ? " ok" : ""); };
const fail = e => banner(e.message || String(e));
const state = { caseId: store.get("case") || "", map: null, layers: null };

const PLACEHOLDERS = { domain: "example.com", username: "handle (no @)", email: "name@example.com", phone: "+14155550100",
  image: "filename inside the evidence store", topic: "A question about a public topic", area: "west,south,east,north  e.g. 72.80,18.85,72.95,18.98" };
const hintFor = c => c.name === "face_compare" ? "two evidence filenames, comma separated: a.jpg,b.jpg" : PLACEHOLDERS[c.kind] || "";

// ---------- views ----------
const views = {
  async overview(root) {
    const [sys, aud] = await Promise.all([api("/system"), api("/audit?limit=8")]);
    $("#ver").textContent = "v" + sys.version;
    const llm = sys.llm;
    root.append(h("h1", {}, "Overview"), h("div", { class: "grid" },
      h("div", { class: "card" }, h("div", { class: "stat" }, String(sys.counts.cases), h("small", {}, "cases"))),
      h("div", { class: "card" }, h("div", { class: "stat" }, String(sys.counts.evidence), h("small", {}, "evidence items")), h("div", { class: "mut" }, `${sys.counts.proposed} awaiting review`)),
      h("div", { class: "card" }, h("div", { class: "stat" }, `${sys.connectors.ready}`, h("small", {}, "connectors ready")), h("div", { class: "mut" }, `${sys.connectors.needs_setup} need setup · ${sys.connectors.not_installed} not installed`)),
      h("div", { class: "card" }, h("h2", {}, "Model host"), h("div", {}, h("span", { class: "badge " + (llm.reachable ? "ready" : "not_installed") }, llm.reachable ? "reachable" : "unreachable"), " ", `${llm.config.provider} · ${llm.config.model}`),
        h("div", { class: "mut" }, llm.reachable ? `${llm.latency_ms} ms · ${llm.config.base_url}` : llm.error || ""))),
      h("h2", { style: "margin-top:22px" }, "Recent activity"), auditTable(aud));
  },

  async investigate(root) {
    const [cases, conns] = await Promise.all([api("/cases"), api("/osint/connectors")]);
    if (!cases.some(c => c.case_id === state.caseId)) state.caseId = cases[0]?.case_id || "";
    const sel = h("select", { id: "case", "aria-label": "Case" }, cases.map(c => h("option", { value: c.case_id, selected: c.case_id === state.caseId }, c.title)));
    sel.addEventListener("change", () => { state.caseId = sel.value; store.set("case", sel.value); loadEvidence(); });
    const newTitle = h("input", { placeholder: "New case title", class: "grow" });
    const newCase = h("button", { onclick: async () => { if (!newTitle.value.trim()) return;
      try { const c = await api("/cases", { method: "POST", body: { title: newTitle.value.trim() } }); state.caseId = c.case_id; store.set("case", c.case_id); route(); } catch (e) { fail(e); } } }, "Create case");
    const cSel = h("select", { id: "conn" }, conns.map(c => h("option", { value: c.name }, `${c.name} — ${c.status.replace("_", " ")}`)));
    const target = h("input", { id: "target", class: "grow" }), purpose = h("input", { id: "purpose", class: "grow", placeholder: "Purpose (audited), e.g. Authorized brand-protection review" });
    const ack = h("input", { type: "checkbox", id: "ack" }), ackRow = h("label", { class: "row" }, ack, "I confirm this is lawful, authorized, and consent-based or in the public interest.");
    const info = h("div", { class: "mut" }), run = h("button", { class: "primary" }, "Run connector");
    const sync = () => { const c = conns.find(x => x.name === cSel.value); target.placeholder = hintFor(c); ackRow.hidden = !c.requires_acknowledgment;
      info.textContent = `${c.description}  ·  licence: ${c.license}` + (c.setup ? `  ·  SETUP NEEDED: ${c.setup}` : ""); run.disabled = c.status !== "ready"; };
    cSel.addEventListener("change", sync); sync();
    run.addEventListener("click", async () => {
      if (!state.caseId) return banner("Create a case first.");
      run.disabled = true; run.textContent = "Running…"; banner("");
      try { const r = await api(`/cases/${state.caseId}/osint/run`, { method: "POST", body: { connector: cSel.value, target: target.value, purpose: purpose.value, acknowledge_lawful_use: ack.checked } });
        banner(`Done: ${r.connector} → evidence proposed for review.`, true); loadEvidence(); } catch (e) { fail(e); }
      run.textContent = "Run connector"; sync();
    });
    const list = h("div", { id: "ev" });
    root.append(h("h1", {}, "Investigate"), h("div", { class: "split" },
      h("div", { class: "card" }, h("h2", {}, "Case"), h("div", { class: "row" }, sel), h("div", { class: "row", style: "margin-top:8px" }, newTitle, newCase),
        h("h2", { style: "margin-top:18px" }, "Run a lookup"),
        h("div", { class: "field" }, h("label", { for: "conn" }, "Connector"), cSel), info,
        h("div", { class: "field", style: "margin-top:10px" }, h("label", { for: "target" }, "Target"), target),
        h("div", { class: "field" }, h("label", { for: "purpose" }, "Purpose"), purpose), ackRow, h("div", { style: "margin-top:10px" }, run)),
      h("div", {}, h("h2", {}, "Findings (proposed until you accept)"), list)));
    async function loadEvidence() {
      list.replaceChildren(); if (!state.caseId) return list.append(h("p", { class: "mut" }, "No case yet."));
      try { const items = await api(`/cases/${state.caseId}/evidence`);
        if (!items.length) list.append(h("p", { class: "mut" }, "No findings yet. Run a connector."));
        items.forEach(e => list.append(evidenceCard(e, loadEvidence))); } catch (e) { fail(e); }
    }
    loadEvidence();
  },

  async map(root) {
    const cases = await api("/cases");
    const bboxIn = h("input", { id: "bbox", class: "grow", value: store.get("bbox") || "72.80,18.85,72.95,18.98", "aria-label": "Bounding box" });
    const status = h("div", { class: "mut", id: "mapstatus" }), legend = h("div", { class: "legend mut" });
    const mapDiv = h("div", { id: "map" }), table = h("div");
    root.append(h("h1", {}, "Area watch"),
      h("div", { class: "card" }, h("div", { class: "row" }, bboxIn,
        h("button", { onclick: () => { const b = state.map.getBounds(); bboxIn.value = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(4)).join(","); } }, "Use map view"),
        ...[["sentinel2", "Satellite + detector"], ["opensky", "Flights"], ["aisstream", "Ships (live AIS)"]].map(([n, l]) => h("button", { class: "primary", onclick: ev => go(n, ev.target) }, l)),
        h("button", { onclick: () => { state.layers.clearLayers(); legend.replaceChildren(); table.replaceChildren(); } }, "Clear")),
        status),
      h("div", { style: "height:12px" }), mapDiv, legend, h("div", { style: "height:10px" }), table,
      h("p", { class: "mut" }, "Map © OpenStreetMap contributors. Satellite imagery: contains modified Copernicus Sentinel data. Imagery is days old, the detector is a heuristic baseline (not the KAAL model), and ADS-B/AIS coverage is incomplete."));
    state.map = L.map(mapDiv, { worldCopyJump: true }).setView([18.92, 72.9], 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap contributors" }).addTo(state.map);
    state.layers = L.layerGroup().addTo(state.map);
    const bb = () => bboxIn.value.split(",").map(Number);
    const fit = () => { const [w, s, e, n] = bb(); if ([w, s, e, n].every(isFinite)) state.map.fitBounds([[s, w], [n, e]]); };
    bboxIn.addEventListener("change", () => { store.set("bbox", bboxIn.value); fit(); }); fit();

    async function ensureCase() {
      if (state.caseId && cases.some(c => c.case_id === state.caseId)) return state.caseId;
      const hit = cases.find(c => c.title === "Area watch") || await api("/cases", { method: "POST", body: { title: "Area watch", description: "Imagery, flights and ships" } });
      state.caseId = hit.case_id; store.set("case", state.caseId); return state.caseId;
    }
    async function go(name, btn) {
      const label = btn.textContent; btn.disabled = true; btn.textContent = "Working…"; banner(""); status.textContent = name === "sentinel2" ? "Fetching the latest scene — this can take ~20 s…" : name === "aisstream" ? "Listening to the AIS stream for ~12 s…" : "";
      try {
        const cid = await ensureCase();
        const r = await api(`/cases/${cid}/osint/run`, { method: "POST", body: { connector: name, target: bboxIn.value, purpose: "Area-watch demonstration on public open data", acknowledge_lawful_use: true } });
        draw(name, r); status.textContent = `${name}: done (${r.duration_s}s). Saved as proposed evidence.`;
      } catch (e) { status.textContent = ""; fail(e); }
      btn.disabled = false; btn.textContent = label;
    }
    function dot(color, text) { return h("span", {}, h("i", { class: "dot", style: `background:${color}` }), text); }
    async function draw(name, r) {
      const o = r.outputs; const rows = [];
      if (name === "sentinel2") {
        try { const blob = await api("/imagery/" + o.preview, { raw: true }); const [w, s, e, n] = o.image_bounds;
          L.imageOverlay(URL.createObjectURL(blob), [[s, w], [n, e]], { opacity: .95 }).addTo(state.layers); state.map.fitBounds([[s, w], [n, e]]); } catch (e) { fail(e); }
        o.detections.forEach(d => { L.circleMarker([d.lat, d.lon], { radius: 5, color: "#e5383b", weight: 1.5, fill: false }).bindTooltip(`${d.label} · score ${d.score}`).addTo(state.layers); rows.push([d.label, d.lat, d.lon, `score ${d.score}`]); });
        legend.append(dot("#e5383b", `${o.detections.length} candidates (${o.detector})`), h("span", {}, `scene ${o.captured?.slice(0, 10)} · cloud ${Number(o.cloud_cover).toFixed(1)}%`));
      } else if (name === "opensky") {
        o.aircraft.forEach(a => { L.marker([a.lat, a.lon], { icon: L.divIcon({ className: "", html: `<div class="ac" style="transform:rotate(${a.heading ?? 0}deg)">▲</div>`, iconSize: [18, 18] }) }).bindTooltip(`${a.callsign || a.icao24} · ${a.altitude_m ?? "?"} m`).addTo(state.layers); rows.push([a.callsign || a.icao24, a.lat, a.lon, `${a.altitude_m ?? "?"} m`]); });
        legend.append(dot("#4aa3ff", `${o.count} aircraft`));
      } else if (name === "aisstream") {
        o.vessels.forEach(v => { L.circleMarker([v.lat, v.lon], { radius: 5, color: "#25d0c8", fillOpacity: .7 }).bindTooltip(`${v.name || v.mmsi} · ${v.speed_kn ?? "?"} kn`).addTo(state.layers); rows.push([v.name || String(v.mmsi), v.lat, v.lon, `${v.speed_kn ?? "?"} kn`]); });
        legend.append(dot("#25d0c8", `${o.count} vessels`));
      }
      table.replaceChildren(h("div", { class: "card" }, h("h2", {}, `${name} results`), ...r.warnings.map(w => h("div", { class: "warn" }, "⚠ " + w)),
        h("table", {}, h("thead", {}, h("tr", {}, ["Name", "Lat", "Lon", "Info"].map(x => h("th", {}, x)))), h("tbody", {}, rows.slice(0, 200).map(x => h("tr", {}, x.map(c => h("td", {}, String(c)))))))));
    }
  },

  async models(root) {
    const st = await api("/llm"); const cfg = st.config;
    const prov = h("select", { id: "prov" }, [["ollama", "Ollama"], ["lmstudio", "LM Studio"]].map(([v, l]) => h("option", { value: v, selected: v === cfg.provider }, l)));
    const url = h("input", { id: "url", value: cfg.base_url, class: "grow" }), key = h("input", { id: "lkey", type: "password", placeholder: cfg.api_key ? "(saved — leave blank to keep)" : "optional (LM Studio)", autocomplete: "off" });
    const chat = h("select", { id: "chat" }), emb = h("select", { id: "emb" }), msg = h("div", { class: "mut" }), stEl = h("div");
    const paint = s => stEl.replaceChildren(h("span", { class: "badge " + (s.reachable ? "ready" : "not_installed") }, s.reachable ? `reachable · ${s.latency_ms} ms` : "unreachable"), " ", s.error ? h("span", { class: "warn" }, s.error) : h("span", { class: "mut" }, `${s.config.provider} · ${s.config.model}`));
    paint(st);
    const fill = (models, c) => { for (const [s, want, emb_] of [[chat, c.model, false], [emb, c.embed_model, true]]) {
      s.replaceChildren(); const pool = models.filter(m => m.embedding === emb_ || !models.some(x => x.embedding === emb_)); const names = pool.map(m => m.name);
      if (want && !names.includes(want)) names.unshift(want);
      names.forEach(n => s.append(h("option", { value: n, selected: n === want }, n))); } };
    fill(st.models, cfg);
    prov.addEventListener("change", () => { url.value = prov.value === "ollama" ? "http://localhost:11434" : "http://localhost:1234"; });
    const refresh = h("button", { onclick: async () => { msg.textContent = "Asking the host…";
      try { const cur = { ...cfg, provider: prov.value, base_url: url.value };
        const r = await api("/llm", { method: "PUT", body: { provider: prov.value, base_url: url.value, model: chat.value || undefined, embed_model: emb.value || undefined, ...(key.value ? { api_key: key.value } : {}), verify: false } });
        fill(r.models, r.config); paint(r); msg.textContent = r.reachable ? `Found ${r.models.length} models on ${r.config.base_url}.` : r.error; } catch (e) { fail(e); msg.textContent = ""; } } }, "Connect & list models");
    const save = h("button", { class: "primary", onclick: async () => { try {
      const r = await api("/llm", { method: "PUT", body: { provider: prov.value, base_url: url.value, model: chat.value, embed_model: emb.value, ...(key.value ? { api_key: key.value } : {}) } });
      banner(`Now using ${r.config.model} on ${r.config.provider} (${r.config.base_url}).`, true); msg.textContent = ""; paint(r); } catch (e) { fail(e); } } }, "Use this model");
    const test = h("button", { onclick: async () => { msg.textContent = "Testing…"; try { const r = await api("/llm/test", { method: "POST" }); msg.textContent = `OK — ${r.model} replied: “${r.reply}”`; } catch (e) { msg.textContent = ""; fail(e); } } }, "Send test prompt");
    root.append(h("h1", {}, "Models"), h("div", { class: "split" },
      h("div", { class: "card models" }, h("h2", {}, "Model host"),
        h("p", { class: "mut" }, "Point KAAL at the machine that runs the models (for example your laptop) — Ollama or LM Studio. Pick the model here at any time; it applies immediately with no restart."),
        h("div", { class: "field" }, h("label", { for: "prov" }, "Provider"), prov),
        h("div", { class: "field" }, h("label", { for: "url" }, "Address"), url),
        h("div", { class: "field" }, h("label", { for: "lkey" }, "API key"), key), h("div", { class: "row" }, refresh)),
      h("div", { class: "card models" }, h("h2", {}, "Choose models"),
        h("div", { class: "field" }, h("label", { for: "chat" }, "Chat model"), chat),
        h("div", { class: "field" }, h("label", { for: "emb" }, "Embedding model"), emb),
        h("div", { class: "row" }, save, test), msg,
        stEl,
        h("p", { class: "mut" }, "Tip: on the laptop, start Ollama with OLLAMA_HOST=0.0.0.0 or turn on “Serve on local network” in LM Studio, so this server can reach it."))));
  },

  async audit(root) { root.append(h("h1", {}, "Audit trail"), auditTable(await api("/audit?limit=200"))); },
};

function auditTable(rows) {
  return h("div", { class: "card", style: "overflow:auto" }, h("table", {}, h("thead", {}, h("tr", {}, ["When (UTC)", "Action", "Resource", "Details"].map(x => h("th", {}, x)))),
    h("tbody", {}, rows.map(a => h("tr", {}, h("td", {}, (a.at || "").replace("T", " ").slice(0, 19)), h("td", {}, a.action), h("td", {}, `${a.resource_type} ${a.resource_id ? String(a.resource_id).slice(0, 12) : ""}`),
      h("td", { class: "mut" }, JSON.stringify(a.metadata || {}).slice(0, 160)))))));
}

function evidenceCard(e, reload) {
  const s = e.summary || {}, conf = Math.round((s.confidence || 0) * 100);
  const review = async d => { try { await api(`/evidence/${e.evidence_id}/review`, { method: "POST", body: { decision: d } }); reload(); } catch (x) { fail(x); } };
  const body = h("pre", {}, "loading…");
  const det = h("details", {}, h("summary", {}, "Full result"), body);
  det.addEventListener("toggle", async () => { if (det.open && body.textContent === "loading…") { try { const f = await api("/evidence/" + e.evidence_id); body.textContent = JSON.stringify(f.result, null, 2); } catch (x) { body.textContent = x.message; } } });
  return h("div", { class: "card", style: "margin-bottom:10px" },
    h("div", { class: "row" }, h("b", {}, e.connector || e.filename), h("span", { class: "badge " + e.status }, e.status), h("span", { class: "mut" }, s.target || ""), h("span", { class: "mut", style: "margin-left:auto" }, (e.created_at || "").slice(0, 16).replace("T", " "))),
    h("div", { class: "mut" }, `Purpose: ${e.purpose || "—"} · ${s.sources || 0} sources`),
    h("div", { class: "bar", title: "confidence" }, h("i", { style: `width:${conf}%` })), h("div", { class: "mut" }, `confidence ${conf}%`),
    ...(s.warnings || []).map(w => h("div", { class: "warn" }, "⚠ " + w)), det,
    e.status === "proposed" ? h("div", { class: "row", style: "margin-top:8px" }, h("button", { onclick: () => review("accepted") }, "Accept as lead"), h("button", { onclick: () => review("rejected") }, "Reject")) : "");
}

// ---------- routing ----------
(function takeKeyFromHash() {      // `#key=...` is handed over by the local launcher; it never reaches the server
  const m = /^#key=([^&]+)/.exec(location.hash);
  if (m) { store.set("key", decodeURIComponent(m[1])); history.replaceState(null, "", location.pathname + "#overview"); }
})();
async function route() {
  const v = (location.hash.slice(1) || "overview"), root = $("#view");
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("on", b.dataset.v === v));
  if (state.map) { state.map.remove(); state.map = null; }
  root.replaceChildren();
  if (!store.get("key")) { banner("Enter your API key (top right) to connect."); return; }
  banner("");
  try { await (views[v] || views.overview)(root); } catch (e) { fail(e); }
  root.focus({ preventScroll: true });
}
$("#nav").addEventListener("click", e => { const b = e.target.closest("button"); if (b) location.hash = b.dataset.v; });
$("#keybar").addEventListener("submit", e => { e.preventDefault(); store.set("key", $("#key").value.trim()); $("#key").value = ""; route(); });
window.addEventListener("hashchange", route);
route();
