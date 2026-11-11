"use strict";

let cashTicket = null;

async function signin() {
  try {
    setSession(await api("POST", "/api/v1/auth/login", { username: $("#u").value, password: $("#p").value }));
    location.reload();
  } catch (e) { showErr(e); }
}

async function loadAlerts() {
  try {
    const list = await api("GET", "/api/v1/alerts", undefined, { auth: true });
    $("#acount").textContent = list.length;
    $("#acount").className = "tag " + (list.length ? "warn" : "ok");
    $("#alerts").replaceChildren(list.length ? h("table", {}, h("tbody", {}, ...list.map((a) => h("tr", {},
      h("td", {}, h("span", { class: "tag " + (a.severity === "CRITICAL" ? "bad" : "warn") }, a.severity)),
      h("td", {}, h("b", {}, a.kind), h("div", { class: "muted" }, a.message + (a.lane_id ? " · " + a.lane_id : ""))),
      h("td", {}, h("button", { class: "secondary small", onclick: () => ack(a.id) }, "Ack"))))))
      : h("div", { class: "empty" }, "No open alerts"));
  } catch (e) {
    if (e.status === 401) { clearSession(); location.reload(); } else showErr(e);
  }
}

async function ack(id) {
  try { await api("POST", "/api/v1/alerts/" + id + "/ack", undefined, { auth: true }); loadAlerts(); } catch (e) { showErr(e); }
}

async function manual() {
  try {
    const t = await api("POST", "/api/v1/ingress/manual", { lane_id: $("#m-lane").value, plate_number: $("#m-plate").value,
      vehicle_category: $("#m-cat").value }, { auth: true });
    $("#m-out").textContent = "Ticket " + t.ticket_id.slice(0, 8) + "… · slot " + t.allocated_slot + " · barrier " + t.barrier;
    toast("Manual ticket issued (audited)");
  } catch (e) { showErr(e); }
}

async function findCash() {
  try {
    const r = await api("POST", "/api/v1/egress/lookup", { plate_number: $("#c-plate").value });
    cashTicket = r;
    $("#c-info").textContent = r.invoice ? r.plate_masked + " · " + r.invoice.duration_minutes + " min · due " + inr(r.invoice.total)
      : r.message;
    $("#c-pay").disabled = !r.invoice;
  } catch (e) { showErr(e); }
}

async function payCash() {
  try {
    const r = await api("POST", "/api/v1/egress/cash", { ticket_id: cashTicket.ticket_id }, { auth: true });
    $("#c-info").textContent = "Collected " + inr(r.amount) + " · barrier " + r.barrier_action;
    $("#c-pay").disabled = true;
    toast("Cash collected · receipt " + r.receipt_url);
  } catch (e) { showErr(e); }
}

async function override() {
  try {
    const r = await api("POST", "/api/v1/admin/barrier-override", { lane_id: $("#o-lane").value, action: $("#o-act").value,
      reason: $("#o-reason").value }, { auth: true });
    toast(r.lane_id + " barrier " + r.state + " · audit entry #" + r.audit_id);
  } catch (e) { showErr(e); }
}

document.addEventListener("DOMContentLoaded", () => {
  $("#signin").addEventListener("click", signin);
  if (store.get("vps_token")) {
    $("#login").classList.add("hidden");
    $("#app").classList.remove("hidden");
    loadAlerts(); setInterval(loadAlerts, 4000);
  }
  $("#manual").addEventListener("click", manual);
  $("#c-find").addEventListener("click", findCash);
  $("#c-pay").addEventListener("click", payCash);
  $("#override").addEventListener("click", override);
});
