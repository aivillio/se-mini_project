"use strict";

async function refreshOverview() {
  try {
    const [sum, edge, lanes] = await Promise.all([api("GET", "/api/v1/slots/summary"), api("GET", "/api/v1/edge/status"),
      api("GET", "/api/v1/lanes")]);
    $("#s-free").textContent = sum.totals.VACANT + " / " + sum.capacity;
    $("#s-occ").textContent = sum.totals.OCCUPIED + sum.totals.ALLOCATED;
    $("#s-res").textContent = sum.totals.RESERVED;
    $("#s-edge").textContent = (edge.online ? "Online" : "OFFLINE") + " · " + edge.pending;
    $("#lanes").replaceChildren(...lanes.map((l) => h("tr", {},
      h("td", {}, l.lane_id), h("td", {}, l.direction),
      h("td", {}, h("span", { class: "tag " + (l.barrier === "UP" ? "warn" : "ok") }, l.barrier)),
      h("td", {}, l.loop_occupied ? "vehicle present" : "clear"),
      h("td", {}, h("span", { class: "tag " + (l.controller_online ? "ok" : "bad") }, l.controller_online ? "online" : "offline")))));
  } catch (e) { showErr(e); }
}

document.addEventListener("DOMContentLoaded", () => { refreshOverview(); setInterval(refreshOverview, 3000); });
