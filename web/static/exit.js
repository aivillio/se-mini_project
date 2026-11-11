"use strict";

let current = null;   // lookup result
let getMethod;

function line(label, amount, cls = "") {
  return h("tr", { class: cls }, h("td", {}, label), h("td", { class: "num" }, inr(amount)));
}

function renderInvoice(r) {
  current = r;
  $("#noinv").classList.add("hidden");
  $("#inv").classList.remove("hidden");
  $("#i-veh").textContent = r.plate_masked + " · " + r.category;
  $("#i-slot").textContent = r.slot_id;
  $("#i-in").textContent = fmtTime(r.entry_time);
  const inv = r.invoice;
  if (!inv) {
    $("#istate").textContent = r.status; $("#istate").className = "tag warn";
    $("#lines").replaceChildren(h("tr", {}, h("td", {}, r.message)));
    $("#pay").disabled = true;
    return;
  }
  $("#i-dur").textContent = inv.duration_minutes + " min (" + inv.billable_hours + " billable h)";
  $("#istate").textContent = "retrieved in " + r.latency_ms + " ms"; $("#istate").className = "tag ok";
  const rows = [];
  if (inv.grace_applied) rows.push(h("tr", {}, h("td", { colspan: 2 }, h("span", { class: "tag ok" }, "Grace period ≤ 15 min · no charge"))));
  rows.push(line("Parking charges", inv.base_amount));
  if (inv.surge_amount) rows.push(line("Peak surcharge · " + inv.surge_rule + " ×" + inv.surge_multiplier, inv.surge_amount));
  if (inv.discount) rows.push(line("Coupon " + inv.coupon_code, -inv.discount));
  rows.push(line("Taxable value", inv.taxable_amount), line("CGST 9%", inv.cgst), line("SGST 9%", inv.sgst),
    line("Total payable", inv.total, "total"));
  $("#lines").replaceChildren(...rows);
  $("#pay").disabled = false;
  $("#pay").textContent = inv.total ? "Pay " + inr(inv.total) : "Exit (no charge)";
}

async function scan() {
  $("#pending").classList.add("hidden"); $("#done").classList.add("hidden");
  try {
    renderInvoice(await api("POST", "/api/v1/egress/lookup", {
      qr_payload: $("#qr").value.trim() || null, plate_number: $("#plate").value.trim() || null,
      coupon_code: $("#coupon").value.trim() || null }));
  } catch (e) {
    showErr(e);
    $("#istate").textContent = e.code; $("#istate").className = "tag bad";
    if (e.code === "TAMPERED_TICKET") toast("Security alert raised for the attendant", true);
  }
}

function finished(r) {
  $("#pending").classList.add("hidden");
  $("#done").classList.remove("hidden");
  $("#donemsg").textContent = "PAID " + inr(r.amount) + " via " + r.method.toUpperCase() + " · barrier " + r.barrier_action;
  $("#rcpt").href = r.receipt_url;
  $("#pay").disabled = true;
  $("#istate").textContent = "PAID"; $("#istate").className = "tag ok";
}

async function pay() {
  try {
    const r = await api("POST", "/api/v1/egress/checkout", {
      ticket_id: current.ticket_id, payment_method: getMethod(),
      coupon_code: $("#coupon").value.trim() || null, card_number: getMethod() === "card" ? $("#card").value : null });
    if (r.status === "PAID") { finished(r); return; }
    $("#pending").classList.remove("hidden");
    $("#order").textContent = r.order.order_id + " · " + r.order.method.toUpperCase();
    $("#amt").textContent = inr(r.order.amount);
    $("#upiqr").src = "/api/v1/qr.svg?data=" + encodeURIComponent(r.order.upi_qr || ("card:" + r.order.order_id));
    $("#pending").dataset.order = r.order.order_id;
  } catch (e) { showErr(e); }
}

async function simulate(success) {
  try {
    const r = await api("POST", "/api/v1/payments/" + $("#pending").dataset.order + "/sandbox-pay", { success });
    if (r.status === "PAID") { finished(r); toast("Webhook verified · payment captured"); }
    else toast("Payment failed · barrier stays closed", true);
  } catch (e) { showErr(e); }
}

async function sms() {
  try {
    const r = await api("POST", "/api/v1/receipts/" + current.ticket_id + "/send", { channel: "SMS", recipient: $("#mobile").value.trim() });
    toast("SMS queued to " + r.recipient);
  } catch (e) { showErr(e); }
}

document.addEventListener("DOMContentLoaded", () => {
  getMethod = segmented($("#method"), (v) => $("#cardrow").classList.toggle("hidden", v !== "card"));
  $("#last").addEventListener("click", () => {
    const t = JSON.parse(store.getLocal("vps_last_ticket") || "null");
    if (t) { $("#qr").value = t.qr; $("#plate").value = ""; } else toast("No ticket issued yet in this browser", true);
  });
  $("#tamper").addEventListener("click", () => {
    const v = $("#qr").value.trim();
    if (!v) return;
    const i = v.indexOf(".") - 3;   // flip one character of the signed body
    $("#qr").value = v.slice(0, i) + (v[i] === "A" ? "B" : "A") + v.slice(i + 1);
    toast("Payload modified · signature will no longer match");
  });
  $("#scan").addEventListener("click", scan);
  $("#pay").addEventListener("click", pay);
  $("#sim-ok").addEventListener("click", () => simulate(true));
  $("#sim-fail").addEventListener("click", () => simulate(false));
  $("#sms").addEventListener("click", sms);
});
