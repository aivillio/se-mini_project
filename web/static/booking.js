"use strict";

function show(r) {
  $("#none").classList.add("hidden");
  $("#res").classList.remove("hidden");
  $("#code").textContent = r.code;
  $("#lcode").value = r.code;
  $("#slot").textContent = r.slot_id + " (level " + r.level + ", " + r.category + ")";
  $("#veh").textContent = r.plate_masked;
  $("#win").textContent = fmtTime(r.start_time) + " → " + fmtTime(r.end_time);
  $("#dead").textContent = fmtTime(r.no_show_deadline);
  $("#bstate").textContent = r.status;
  $("#bstate").className = "tag " + (r.status === "BOOKED" || r.status === "CHECKED_IN" ? "ok" : "warn");
}

async function book() {
  try {
    const start = new Date($("#start").value);
    show(await api("POST", "/api/v1/reservations", { plate_number: $("#plate").value, vehicle_category: $("#cat").value,
      start_time: start.toISOString(), duration_hours: Number($("#dur").value), contact: $("#contact").value.trim() || null }));
    toast("Slot reserved");
  } catch (e) { showErr(e); }
}

async function lookup() {
  try { show(await api("GET", "/api/v1/reservations/" + encodeURIComponent($("#lcode").value.trim()))); } catch (e) { showErr(e); }
}

async function cancel() {
  try {
    show(await api("POST", "/api/v1/reservations/" + encodeURIComponent($("#lcode").value.trim()) + "/cancel",
      { plate_number: $("#plate").value }));
    toast("Reservation cancelled · slot released");
  } catch (e) { showErr(e); }
}

document.addEventListener("DOMContentLoaded", () => {
  const d = new Date(Date.now() + 60 * 60000);
  d.setMinutes(0, 0, 0);
  const pad = (n) => String(n).padStart(2, "0");
  $("#start").value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`;
  $("#book").addEventListener("click", book);
  $("#lookup").addEventListener("click", lookup);
  $("#cancel").addEventListener("click", cancel);
});
