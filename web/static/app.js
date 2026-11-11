/* Shared helpers for all VPS pages (no build step, no external libraries). */
"use strict";

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));

const store = {
  get(k) { try { return sessionStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { sessionStorage.setItem(k, v); } catch { /* storage unavailable */ } },
  del(k) { try { sessionStorage.removeItem(k); } catch { /* storage unavailable */ } },
  getLocal(k) { try { return localStorage.getItem(k); } catch { return null; } },
  setLocal(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
};

class ApiError extends Error {
  constructor(status, code, message, details) { super(message); this.status = status; this.code = code; this.details = details; }
}

async function api(method, path, body, { auth = false, raw = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = store.get("vps_token");
  if (auth && token) headers.Authorization = "Bearer " + token;
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (raw && res.ok) return res;
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) {
    const e = (data && data.error) || {};
    const msg = e.message || (data && data.detail && JSON.stringify(data.detail)) || res.statusText;
    throw new ApiError(res.status, e.code || "HTTP_" + res.status, msg, e.details);
  }
  return data;
}

function toast(msg, isErr = false) {
  let box = $("#toast");
  if (!box) { box = document.createElement("div"); box.id = "toast"; document.body.appendChild(box); }
  const d = document.createElement("div");
  if (isErr) d.className = "err";
  d.textContent = msg;
  box.appendChild(d);
  setTimeout(() => d.remove(), 4200);
}

function showErr(e) { toast((e.code ? e.code + ": " : "") + e.message, true); }

const inr = (x) => (Number(x) < 0 ? "−" : "") + "₹" + Math.abs(Number(x || 0)).toLocaleString("en-IN",
  { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtTime = (iso) => iso ? new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "–";

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) el.append(kid.nodeType ? kid : String(kid));
  return el;
}

function segmented(container, onChange) {
  $$("button", container).forEach((b) => b.addEventListener("click", () => {
    $$("button", container).forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    if (onChange) onChange(b.dataset.v);
  }));
  return () => ($("button.on", container) || {}).dataset?.v;
}

function renderNav() {
  const here = location.pathname.split("/").pop() || "index.html";
  const links = [["index.html", "Overview"], ["entry.html", "Entry kiosk"], ["exit.html", "Exit & pay"],
    ["display.html", "Live display"], ["booking.html", "Pre-book"], ["attendant.html", "Attendant"], ["admin.html", "Admin"]];
  const nav = $("header.top nav");
  if (!nav) return;
  links.forEach(([href, label]) => nav.append(h("a", { href, class: href === here ? "active" : "" }, label)));
  const who = $("header.top .who");
  const u = store.get("vps_user");
  if (who && u) who.textContent = "Signed in: " + u;
}

function setSession(login) {
  store.set("vps_token", login.token);
  store.set("vps_user", login.username + " (" + login.role + ")");
  store.set("vps_role", login.role);
}

function clearSession() { store.del("vps_token"); store.del("vps_user"); store.del("vps_role"); }

document.addEventListener("DOMContentLoaded", renderNav);
