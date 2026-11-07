"use strict";

let getCat;
const TARGETS = { plate_capture: 1500, ticket_issue: 2000, barrier_raise: 500, total: 3000 };
const LABELS = { plate_capture: "ANPR plate capture (F-001)", ticket_issue: "Ticket issue (F-002)",
  barrier_raise: "Barrier raise (F-003)", total: "Total ingress (NF-001)" };

function laneId() { return $("#lane").value; }

function paintLane(l, passed = false) {
  const v = $("#lanevis");
  v.classList.toggle("up", l.barrier === "UP");
  v.classList.toggle("onloop", !!l.loop_occupied);
  v.classList.toggle("passed", passed);
  $("#lanetxt").textContent = "Barrier " + l.barrier + (l.loop_occupied ? " · loop occupied" : "");
  $("#lanestate").textContent = l.lane_id;
}

async function refreshLane() {
  const lanes = await api("GET", "/api/v1/lanes");
  paintLane(lanes.find((l) => l.lane_id === laneId()));
}

async function issue() {
  const mins = Number($("#arr").value);
  const body = {
    lane_id: laneId(), plate_number: $("#plate").value, vehicle_category: getCat(),
    confidence: Number($("#conf").value), reservation_code: $("#res").value.trim() || null,
    timestamp: mins ? new Date(Date.now() - mins * 60000).toISOString() : null,
  };
  try {
    const t = await api("POST", "/api/v1/ingress/ticket", body);
    store.setLocal("vps_last_ticket", JSON.stringify({ qr: t.qr_payload, id: t.ticket_id }));
    $("#empty").classList.add("hidden");
    $("#ticket").classList.remove("hidden");
    $("#tstate").textContent = "issued"; $("#tstate").className = "tag ok";
    $("#qr").src = "/api/v1/tickets/" + t.ticket_id + "/qr.svg";
    $("#slot").textContent = t.allocated_slot;
    $("#slotinfo").textContent = "Level " + t.level + " · " + t.category + (t.reservation_id ? " · reserved bay" : "");
    $("#tid").textContent = t.ticket_id;
    $("#veh").textContent = t.plate_masked + " (" + t.entry_mode + ")";
    $("#etime").textContent = fmtTime(t.entry_time);
    $("#deliv").textContent = t.ticket_delivery === "PRINTED" ? "Printed QR ticket" : "Digital ticket (printer fault)";
    $("#timings").replaceChildren(...Object.keys(TARGETS).map((k) => h("tr", {},
      h("td", {}, LABELS[k]), h("td", {}, "≤ " + TARGETS[k] + " ms"),
      h("td", { class: "num" }, h("span", { class: "tag " + (t.timings_ms[k] <= TARGETS[k] ? "ok" : "bad") }, t.timings_ms[k].toFixed(2) + " ms")))));
    toast("Ticket issued · go to " + t.allocated_slot);
    await refreshLane();
  } catch (e) {
    showErr(e);
    $("#tstate").textContent = e.code; $("#tstate").className = "tag bad";
  }
}

async function loop(occupied) {
  try {
    const r = await api("POST", "/api/v1/lanes/" + laneId() + "/loop", { occupied });
    paintLane(r, !occupied && r.barrier === "DOWN");
    if (!occupied) toast("Vehicle cleared the loop · barrier lowered");
  } catch (e) { showErr(e); }
}

async function lower() {
  try {
    const r = await api("POST", "/api/v1/lanes/" + laneId() + "/barrier/lower");
    paintLane(r);
    if (r.halted) toast("Descent halted: vehicle on safety loop", true); else toast("Barrier lowered");
  } catch (e) { showErr(e); }
}

document.addEventListener("DOMContentLoaded", () => {
  getCat = segmented($("#cat"));
  $("#conf").addEventListener("input", () => { $("#confv").textContent = Number($("#conf").value).toFixed(2); });
  $("#go").addEventListener("click", issue);
  $("#onloop").addEventListener("click", () => loop(true));
  $("#cleared").addEventListener("click", () => loop(false));
  $("#lower").addEventListener("click", lower);
  $("#lane").addEventListener("change", refreshLane);
  refreshLane().catch(showErr);
});
