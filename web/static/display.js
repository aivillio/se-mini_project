"use strict";

let lastVersion = -1;
const seq = {};      // per-sensor sequence numbers (replay protection, see sensors.py)

function board(title, vacant, cats) {
  return h("div", { class: "vms" + (vacant ? "" : " full") },
    h("div", { class: "title" }, title),
    h("div", { class: "val" }, vacant ? vacant + " FREE" : "FULL"),
    cats ? h("div", { class: "cats" }, cats) : null);
}

async function refresh(force = false) {
  try {
    const v = await api("GET", "/api/v1/vms");
    if (!force && v.version === lastVersion) return;
    lastVersion = v.version;
    const cards = [board("ENTRANCE", v.entrance.vacant)];
    v.levels.forEach((l) => cards.push(board(l.board, l.vacant,
      Object.entries(l.by_category).map(([k, n]) => k + " " + n).join("  "))));
    $("#boards").replaceChildren(...cards);
    const slots = await api("GET", "/api/v1/slots");
    const byLevel = {};
    slots.forEach((s) => (byLevel[s.level] = byLevel[s.level] || []).push(s));
    $("#map").replaceChildren(...Object.entries(byLevel).map(([lvl, list]) => h("div", { class: "level" },
      h("h3", {}, "Level " + lvl),
      h("div", { class: "slots" }, ...list.map((s) => h("div", {
        class: "slot", title: s.id + " · " + s.category + " · " + s.status,
        onclick: () => toggle(s),
      }, h("div", { class: "led " + s.led }), s.id.split("-")[1], h("div", { class: "muted", style: "font-size:10px" }, s.category)))))));
  } catch (e) { showErr(e); }
}

async function toggle(s) {
  const occupied = !(s.status === "OCCUPIED");
  seq[s.id] = (seq[s.id] || Date.now()) + 1;
  try {
    const r = await api("POST", "/api/v1/sensors/" + s.id + "/event", { occupied, seq: seq[s.id] });
    $("#lat").textContent = s.id + " → " + r.led + " in " + r.latency_ms + " ms";
    $("#lat").className = "tag ok";
    refresh(true);
  } catch (e) { showErr(e); }
}

document.addEventListener("DOMContentLoaded", () => { refresh(true); setInterval(refresh, 1000); });
