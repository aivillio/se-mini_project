"use strict";

const A = (method, path, body) => api(method, path, body, { auth: true });
const loaders = {};

async function signin() {
  try {
    setSession(await api("POST", "/api/v1/auth/login", { username: $("#u").value, password: $("#p").value, totp: $("#t").value }));
    location.reload();
  } catch (e) { showErr(e); }
}

function switchTab(v) {
  if (v === "logout") { A("POST", "/api/v1/auth/logout").finally(() => { clearSession(); location.reload(); }); return; }
  $$("section[data-tab]").forEach((s) => s.classList.toggle("hidden", s.dataset.tab !== v));
  if (loaders[v]) loaders[v]().catch(showErr);
}

loaders.tariffs = async () => {
  const rows = await A("GET", "/api/v1/admin/tariffs");
  $("#tariffs").replaceChildren(...rows.map((t) => {
    const f = h("input", { type: "number", value: t.first_hour, style: "max-width:110px" });
    const p = h("input", { type: "number", value: t.per_hour, style: "max-width:110px" });
    const c = h("input", { type: "number", value: t.daily_cap, style: "max-width:110px" });
    return h("tr", {}, h("td", {}, h("b", {}, t.category)), h("td", { class: "num" }, f), h("td", { class: "num" }, p),
      h("td", { class: "num" }, c), h("td", {}, h("button", { class: "small", onclick: async () => {
        try {
          await A("PUT", "/api/v1/admin/tariffs/" + t.category, { first_hour: +f.value, per_hour: +p.value, daily_cap: +c.value });
          toast(t.category + " tariff updated · audited");
        } catch (e) { showErr(e); }
      } }, "Save")));
  }));
};

loaders.pricing = async () => {
  const [surge, coupons] = await Promise.all([A("GET", "/api/v1/admin/surge"), A("GET", "/api/v1/admin/coupons")]);
  $("#surge").replaceChildren(...surge.map((s) => h("tr", {}, h("td", {}, s.name), h("td", {}, s.start_hour + ":00–" + s.end_hour + ":00"),
    h("td", {}, "×" + s.multiplier), h("td", {}, h("button", { class: "small secondary", onclick: async () => {
      try { await A("PATCH", "/api/v1/admin/surge/" + s.id, { active: !s.active }); loaders.pricing(); } catch (e) { showErr(e); }
    } }, s.active ? "Active · disable" : "Off · enable")))));
  $("#coupons").replaceChildren(...coupons.map((c) => h("tr", {}, h("td", {}, h("b", { class: "mono" }, c.code)),
    h("td", {}, c.kind === "PERCENT" ? c.value + "%" : inr(c.value)), h("td", {}, c.used_count + (c.max_uses ? " / " + c.max_uses : "") + " used"))));
};

loaders.layout = async () => {
  const s = await api("GET", "/api/v1/slots/summary");
  $("#layout").replaceChildren(...Object.entries(s.levels).map(([lvl, c]) => h("tr", {}, h("td", {}, "Level " + lvl),
    ...["2W", "4W", "EV", "HANDICAP"].map((k) => h("td", { class: "num" }, c[k].total ? c[k].vacant + " / " + c[k].total : "–")))));
};

loaders.users = async () => {
  const users = await A("GET", "/api/v1/auth/users");
  $("#users").replaceChildren(...users.map((u) => h("tr", {}, h("td", {}, u.username), h("td", {}, u.role),
    h("td", {}, h("span", { class: "tag " + (u.active ? "ok" : "bad") }, u.active ? "active" : "disabled")), h("td", {}, u.failed_logins),
    h("td", {}, h("button", { class: "small secondary", onclick: async () => {
      try { await A("PATCH", "/api/v1/auth/users/" + u.username, { active: !u.active }); loaders.users(); } catch (e) { showErr(e); }
    } }, u.active ? "Disable" : "Enable")))));
};

async function viewReport() {
  const t0 = performance.now();
  const r = await A("GET", `/api/v1/reports/${$("#r-kind").value}?period=${$("#r-period").value}`);
  $("#r-time").textContent = "Generated in " + (performance.now() - t0).toFixed(0) + " ms";
  if (!r.rows.length) { $("#r-out").replaceChildren(h("div", { class: "empty" }, "No data in range")); return; }
  const cols = Object.keys(r.rows[0]);
  const extra = r.kind === "occupancy" ? h("p", {}, `Current occupancy ${r.overall_occupancy_pct}% · peak hour ${r.peak_hour}:00`)
    : r.kind === "revenue" ? h("p", {}, h("b", {}, "Grand total " + inr(r.grand_total))) : null;
  $("#r-out").replaceChildren(h("table", {}, h("thead", {}, h("tr", {}, ...cols.map((c) => h("th", {}, c)))),
    h("tbody", {}, ...r.rows.map((row) => h("tr", {}, ...cols.map((c) => h("td", {}, row[c])))))), extra);
}

async function exportReport(fmt) {
  try {
    const t0 = performance.now();
    const res = await api("GET", `/api/v1/reports/${$("#r-kind").value}?period=${$("#r-period").value}&format=${fmt}`, undefined,
      { auth: true, raw: true });
    const blob = await res.blob();
    const name = (res.headers.get("Content-Disposition") || "").split("filename=")[1]?.replaceAll('"', "") || "report." + fmt;
    const a = h("a", { href: URL.createObjectURL(blob), download: name });
    document.body.append(a); a.click(); a.remove();
    $("#r-time").textContent = `${name} exported in ${(performance.now() - t0).toFixed(0)} ms (server ${res.headers.get("X-Export-Time-ms")} ms · target ≤ 5000 ms)`;
  } catch (e) { showErr(e); }
}
loaders.reports = viewReport;

loaders.audit = async () => {
  const rows = await A("GET", "/api/v1/admin/audit?limit=200");
  $("#audit").replaceChildren(...rows.map((r) => h("tr", {}, h("td", {}, r.id), h("td", {}, fmtTime(r.ts)), h("td", {}, r.actor),
    h("td", {}, h("span", { class: "tag" }, r.action)), h("td", { class: "mono" }, JSON.stringify(r.details)))));
};

async function verifyAudit() {
  const v = await A("GET", "/api/v1/admin/audit/verify");
  $("#a-verify").textContent = v.valid ? `chain intact · ${v.entries} entries` : `TAMPERED at #${v.broken_at}`;
  $("#a-verify").className = "tag " + (v.valid ? "ok" : "bad");
}

loaders.edge = async () => {
  const [e, lanes] = await Promise.all([api("GET", "/api/v1/edge/status"), api("GET", "/api/v1/lanes")]);
  $("#edge").replaceChildren(h("dt", {}, "WAN link"), h("dd", {}, h("span", { class: "tag " + (e.online ? "ok" : "bad") }, e.online ? "online" : "OFFLINE")),
    h("dt", {}, "Queued at edge"), h("dd", {}, e.pending + " events"), h("dt", {}, "Oldest queued"), h("dd", {}, e.oldest_pending_age_hours + " h (budget 72 h)"),
    h("dt", {}, "Central events"), h("dd", {}, e.central_events),
    h("dt", {}, "Last sync"), h("dd", {}, e.last_sync ? `${e.last_sync.synced} events in ${e.last_sync.duration_ms} ms` : "–"));
  $("#lanes").replaceChildren(...lanes.map((l) => h("tr", {}, h("td", {}, l.lane_id), h("td", {}, l.barrier),
    h("td", {}, h("button", { class: "small secondary", onclick: async () => {
      try { await A("POST", `/api/v1/lanes/${l.lane_id}/controller`, { online: !l.controller_online }); loaders.edge(); } catch (er) { showErr(er); }
    } }, l.controller_online ? "Online · take offline" : "Offline · bring online")))));
};

async function setNet(online) {
  try {
    const r = await A("POST", "/api/v1/edge/network", { online });
    toast(online ? `Link restored · ${r.sync.synced} queued events synced` : "WAN down · lanes continue on local queue");
    loaders.edge();
  } catch (e) { showErr(e); }
}

document.addEventListener("DOMContentLoaded", () => {
  $("#signin").addEventListener("click", signin);
  const role = store.get("vps_role");
  if (store.get("vps_token") && (role === "ADMIN" || role === "MANAGER")) {
    $("#login").classList.add("hidden");
    $("#app").classList.remove("hidden");
    segmented($("#tabs"), switchTab);
    loaders.tariffs().catch((e) => { if (e.status === 401) { clearSession(); location.reload(); } else showErr(e); });
  }
  $("#s-add").addEventListener("click", async () => {
    try { await A("POST", "/api/v1/admin/surge", { name: $("#s-name").value, start_hour: +$("#s-from").value, end_hour: +$("#s-to").value,
      multiplier: +$("#s-mult").value }); loaders.pricing(); toast("Surge rule added"); } catch (e) { showErr(e); }
  });
  $("#c-add").addEventListener("click", async () => {
    try { await A("POST", "/api/v1/admin/coupons", { code: $("#c-code").value, kind: $("#c-kind").value, value: +$("#c-val").value,
      max_uses: +$("#c-max").value || null }); loaders.pricing(); toast("Coupon created"); } catch (e) { showErr(e); }
  });
  $("#l-add").addEventListener("click", async () => {
    try { const r = await A("POST", "/api/v1/admin/slots", { level: +$("#l-level").value, category: $("#l-cat").value, count: +$("#l-count").value });
      toast(r.created.length + " slots added"); loaders.layout(); } catch (e) { showErr(e); }
  });
  $("#n-add").addEventListener("click", async () => {
    try { const r = await A("POST", "/api/v1/auth/users", { username: $("#n-user").value, password: $("#n-pass").value, role: $("#n-role").value });
      $("#n-out").textContent = r.totp_secret ? "TOTP enrolment secret (shown once): " + r.totp_secret : "Created " + r.username;
      loaders.users(); } catch (e) { showErr(e); }
  });
  $("#r-view").addEventListener("click", () => viewReport().catch(showErr));
  $("#r-csv").addEventListener("click", () => exportReport("csv"));
  $("#r-pdf").addEventListener("click", () => exportReport("pdf"));
  $("#a-check").addEventListener("click", () => verifyAudit().catch(showErr));
  $("#e-off").addEventListener("click", () => setNet(false));
  $("#e-on").addEventListener("click", () => setNet(true));
});
