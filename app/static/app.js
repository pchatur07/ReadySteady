// ReadySteady front end: one page, three role views. Plain JS, no build step.
"use strict";

const state = { user: null, canteens: [], canteenId: null, menu: [], cart: {}, view: null, timer: null,
  drawerOpen: false, lowWarned: false, lastFirstSlot: undefined, seenStatus: {}, nextPickup: null };
const STEPS = ["PLACED", "ACCEPTED", "PREPARING", "READY", "PICKED_UP"];
const STEP_LABEL = { PLACED: "Placed", ACCEPTED: "Accepted", PREPARING: "Preparing", READY: "Ready", PICKED_UP: "Picked up", CANCELLED: "Cancelled", REJECTED: "Rejected" };
const NEXT_ACTION = { PLACED: ["ACCEPTED", "Accept"], ACCEPTED: ["PREPARING", "Start preparing"], PREPARING: ["READY", "Mark ready"], READY: ["PICKED_UP", "Hand over"] };
const LOW_BALANCE_PAISE = 5000;

// Reference photos are mapped client-side by item name so the REST contract stays unchanged.
const ITEM_IMAGES = {
  "masala dosa": "masala-dosa", "idli sambar": "idli-sambar", "veg thali": "veg-thali",
  "rajma chawal": "rajma-chawal", "samosa (2 pcs)": "samosa", "veg sandwich": "veg-sandwich",
  "paneer roll": "paneer-roll", "masala chai": "masala-chai", "cold coffee": "cold-coffee",
  "maggi": "maggi", "cheese maggi": "cheese-maggi", "egg roll": "egg-roll",
  "bread omelette": "bread-omelette", "lemon iced tea": "lemon-iced-tea",
};
const imgFor = (i) => `/static/img/items/${ITEM_IMAGES[(i.name || "").trim().toLowerCase()] || "fallback"}.jpg`;

const ICONS = {
  menu: '<rect x="4" y="4" width="7" height="7" rx="2"/><rect x="13" y="4" width="7" height="7" rx="2"/><rect x="4" y="13" width="7" height="7" rx="2"/><rect x="13" y="13" width="7" height="7" rx="2"/>',
  cart: '<circle cx="9" cy="20" r="1.6"/><circle cx="17" cy="20" r="1.6"/><path d="M3 4h2l2.6 12h10.8L21 8H6"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  wallet: '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 10h18M16 14.5h2"/>',
  history: '<path d="M3.5 12a8.5 8.5 0 1 0 2.5-6"/><path d="M3.5 4.5V9H8"/><path d="M12 8v4l3 2"/>',
  power: '<path d="M12 3v8"/><path d="M6.3 6.5a8 8 0 1 0 11.4 0"/>',
  login: '<path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4"/><path d="M10 8l4 4-4 4M14 12H3"/>',
  queue: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1.4"/><circle cx="4" cy="12" r="1.4"/><circle cx="4" cy="18" r="1.4"/>',
  report: '<path d="M5 20v-6M11 20V6M17 20v-9"/><path d="M3 20h18"/>',
  settings: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2.5"/><circle cx="10" cy="17" r="2.5"/>',
  box: '<path d="M3 8l9-5 9 5v8l-9 5-9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
};
const icon = (n) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n]}</svg>`;

const $ = (sel) => document.querySelector(sel);
const app = $("#app");
// Escape every server value before it goes into HTML, so a menu item name cannot inject script (XSS).
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const rupees = (p) => "₹" + (p / 100).toFixed(p % 100 ? 2 : 0);
const time = (iso) => (iso || "").slice(11, 16);
// Display-only "MRP": a deterministic 20% markup, struck through above the real price.
const mrpPaise = (p) => Math.round((p * 1.2) / 100) * 100;
const priceHTML = (p) => `<span class="mrp">${rupees(mrpPaise(p))}</span>${rupees(p)}<span class="off">20% off</span>`;

async function api(path, options = {}) {
  const res = await fetch("/api" + path, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : {},
    body: options.body ? JSON.stringify(options.body) : undefined,
    credentials: "same-origin",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.message || "Something went wrong."), { code: data.error, status: res.status });
  return data;
}

function toast(msg, bad = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (bad ? " bad" : "");
  t.hidden = false;
  clearTimeout(toast.h);
  toast.h = setTimeout(() => (t.hidden = true), 3500);
}

function poll(fn, ms = 5000) {
  clearInterval(state.timer);
  state.timer = setInterval(() => fn().catch(() => {}), ms);
}

// ---------------- theme ----------------
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("rs-theme", t); } catch (e) {}
}
function toggleTheme(ev) {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  const r = ev.currentTarget.getBoundingClientRect();
  const root = document.documentElement;
  root.style.setProperty("--rx", `${r.left + r.width / 2}px`);
  root.style.setProperty("--ry", `${r.top + r.height / 2}px`);
  if (document.startViewTransition) document.startViewTransition(() => setTheme(next));
  else setTheme(next);
}

// ---------------- glass drawer ----------------
function openDrawer() {
  state.drawerOpen = true;
  renderDrawer();
  const s = $("#scrim");
  s.hidden = false;
  requestAnimationFrame(() => { s.classList.add("open"); $("#drawer").classList.add("open"); });
  $("#drawer").setAttribute("aria-hidden", "false");
  $("#hamburger").classList.add("open");
  $("#hamburger").setAttribute("aria-expanded", "true");
  if (state.user && state.user.role === "student") loadScheduled();
}
function closeDrawer() {
  if (!state.drawerOpen) return;
  state.drawerOpen = false;
  $("#drawer").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
  $("#scrim").classList.remove("open");
  $("#hamburger").classList.remove("open");
  $("#hamburger").setAttribute("aria-expanded", "false");
  setTimeout(() => { if (!state.drawerOpen) $("#scrim").hidden = true; }, 320);
}
async function loadScheduled() {
  try {
    const orders = await api("/orders");
    const nowKey = new Date().toISOString().slice(0, 16);
    const upcoming = orders
      .filter((o) => !["PICKED_UP", "CANCELLED", "REJECTED"].includes(o.status) && o.slot_start >= nowKey)
      .sort((a, b) => a.slot_start.localeCompare(b.slot_start))[0];
    state.nextPickup = upcoming ? { id: upcoming.id, slot: upcoming.slot_start } : null;
    if (state.drawerOpen) renderDrawer();
  } catch (e) {}
}
function goCart() {
  closeDrawer();
  studentView("menu").then(() => {
    const c = $(".cart");
    if (c) c.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}
function renderDrawer() {
  const u = state.user;
  const items = [];
  if (!u) {
    items.push({ icon: "login", label: "Log in", act: () => { closeDrawer(); renderAuth("login"); } });
  } else if (u.role === "student") {
    const cartCount = Object.values(state.cart).reduce((s, q) => s + q, 0);
    items.push({ icon: "menu", label: "Menu", active: state.view === "menu", act: () => { closeDrawer(); studentView("menu"); } });
    items.push({ icon: "cart", label: "Cart", sub: cartCount ? `${cartCount} item${cartCount > 1 ? "s" : ""}` : "empty", act: goCart });
    items.push({ icon: "clock", label: "Scheduled order", sub: state.nextPickup ? time(state.nextPickup.slot) : "none", act: () => { closeDrawer(); studentView("orders"); } });
    items.push({ wallet: true });
    items.push({ icon: "history", label: "Previous orders", active: state.view === "orders", act: () => { closeDrawer(); studentView("orders"); } });
  } else if (u.role === "staff") {
    items.push({ icon: "queue", label: "Order queue", active: true, act: () => { closeDrawer(); staffView(); } });
  } else {
    items.push({ icon: "report", label: "Today's report", active: state.view === "report", act: () => { closeDrawer(); adminView("report"); } });
    items.push({ icon: "queue", label: "Order queue", active: state.view === "queue", act: () => { closeDrawer(); adminView("queue"); } });
    items.push({ icon: "box", label: "Menu & stock", active: state.view === "menu", act: () => { closeDrawer(); adminView("menu"); } });
    items.push({ icon: "settings", label: "Slots & wallets", active: state.view === "settings", act: () => { closeDrawer(); adminView("settings"); } });
  }
  $("#drawerNav").innerHTML = items.map((it, i) => it.wallet ? `
    <details class="wallet-box">
      <summary class="dnav">${icon("wallet")}<span>Wallet</span><span class="dnav-sub">${rupees(u.wallet_paise)}</span></summary>
      <div class="wallet-body"><b>${rupees(u.wallet_paise)}</b><br>
        ${u.wallet_paise < LOW_BALANCE_PAISE ? "Balance is low. " : ""}Top-ups are handled by the canteen admin at the counter.</div>
    </details>` : `
    <button class="dnav ${it.active ? "active" : ""}" data-dnav="${i}">${icon(it.icon)}<span>${it.label}</span>${it.sub ? `<span class="dnav-sub">${esc(it.sub)}</span>` : ""}</button>`).join("");
  $("#drawerNav").querySelectorAll("[data-dnav]").forEach((b) => (b.onclick = items[+b.dataset.dnav].act));
  $("#drawerFoot").innerHTML = u ? `
    <div class="pill"><span class="avatar">${esc(u.name.trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase())}</span>
      <span class="who"><b>${esc(u.name)}</b><span>${esc(u.role)}${u.role === "student" ? " · " + rupees(u.wallet_paise) : ""}</span></span></div>
    <button class="dnav" id="drawerLogout">${icon("power")}<span>Log out</span></button>` : `
    <p class="drawer-note">Log in with your college email to order from your campus wallet.</p>`;
  if (u) $("#drawerLogout").onclick = logout;
}

// ---------------- auth ----------------
function renderAuth(mode = "login") {
  clearInterval(state.timer);
  $("#userbar").innerHTML = "";
  app.innerHTML = `
    <div class="auth card">
      <h1>${mode === "login" ? "Log in" : "Create a student account"}</h1>
      <div class="tabs">
        <button class="tab ${mode === "login" ? "active" : ""}" data-mode="login">Log in</button>
        <button class="tab ${mode === "register" ? "active" : ""}" data-mode="register">Sign up</button>
      </div>
      <form id="authForm" novalidate>
        ${mode === "register" ? `<label for="name">Full name</label><input id="name" autocomplete="name" required>` : ""}
        <label for="email">College email</label><input id="email" type="email" autocomplete="email" required>
        <label for="password">Password</label><input id="password" type="password" autocomplete="${mode === "login" ? "current-password" : "new-password"}" required>
        <p class="error" id="authError"></p>
        <button class="btn primary" style="width:100%">${mode === "login" ? "Log in" : "Sign up"}</button>
      </form>
      <p class="hint">Demo: student@iiita.ac.in / student123 · staff@iiita.ac.in / staff1234 · admin@iiita.ac.in / admin1234</p>
    </div>`;
  app.querySelectorAll(".tab").forEach((b) => (b.onclick = () => renderAuth(b.dataset.mode)));
  $("#authForm").onsubmit = async (e) => {
    e.preventDefault();
    const payload = { email: $("#email").value, password: $("#password").value };
    if (mode === "register") payload.name = $("#name").value;
    try {
      state.user = await api("/auth/" + mode, { method: "POST", body: payload });
      start();
    } catch (err) {
      $("#authError").textContent = err.message;
    }
  };
}

async function logout() {
  closeDrawer();
  await api("/auth/logout", { method: "POST" }).catch(() => {});
  state.user = null;
  state.cart = {};
  state.seenStatus = {};
  state.lastFirstSlot = undefined;
  state.nextPickup = null;
  renderAuth();
}

function renderUserbar() {
  const u = state.user;
  $("#userbar").innerHTML = `
    <span>${esc(u.name)} · ${esc(u.role)}</span>
    ${u.role === "student" ? `<span class="wallet">Wallet ${rupees(u.wallet_paise)}</span>` : ""}
    <button class="icon-btn" id="logoutBtn" title="Log out" aria-label="Log out">${icon("power")}</button>`;
  $("#logoutBtn").onclick = logout;
}

async function refreshMe() {
  state.user = await api("/me");
  renderUserbar();
  checkLowBalance();
}

function checkLowBalance() {
  const u = state.user;
  if (!u || u.role !== "student") return;
  if (u.wallet_paise < LOW_BALANCE_PAISE && !state.lowWarned) {
    state.lowWarned = true;
    toast(`Low wallet balance: ${rupees(u.wallet_paise)}. Ask the admin to top up.`, true);
  } else if (u.wallet_paise >= LOW_BALANCE_PAISE) {
    state.lowWarned = false;
  }
}

// ---------------- student ----------------
async function studentView(tab = "menu") {
  state.view = tab;
  state.canteens = await api("/canteens");
  state.canteenId = state.canteenId || state.canteens[0].id;
  app.innerHTML = `
    <div class="tabs">
      <button class="tab ${tab === "menu" ? "active" : ""}" data-tab="menu">Order food</button>
      <button class="tab ${tab === "orders" ? "active" : ""}" data-tab="orders">My orders</button>
    </div>
    <div id="pane"></div>`;
  app.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => studentView(b.dataset.tab)));
  if (tab === "menu") { clearInterval(state.timer); await renderMenu(); }
  else { await renderMyOrders(); poll(renderMyOrders); }
}

function nextSlotNotice(slots) {
  const open = slots.filter((s) => s.available);
  const first = open.length ? open[0].start : null;
  if (!open.length) toast("No pickup slots left today.", true);
  else if (state.lastFirstSlot !== undefined && first !== state.lastFirstSlot) toast(`Next available slot: ${open[0].label}`);
  state.lastFirstSlot = first;
}

async function renderMenu() {
  const [{ items }, slots] = await Promise.all([
    api(`/canteens/${state.canteenId}/menu`),
    api(`/canteens/${state.canteenId}/slots`),
  ]);
  state.menu = items;
  nextSlotNotice(slots);
  const cats = [...new Set(items.map((i) => i.category))];
  const open = slots.filter((s) => s.available);
  $("#pane").innerHTML = `
    <div class="tabs">${state.canteens.map((c) => `<button class="tab ${c.id === state.canteenId ? "active" : ""}" data-canteen="${c.id}">${esc(c.name)}</button>`).join("")}</div>
    <div class="layout">
      <section>${cats.map((cat) => `
        <div class="menu-cat"><h2>${esc(cat)}</h2><div class="items">
          ${items.filter((i) => i.category === cat).map(itemCard).join("")}
        </div></div>`).join("")}
      </section>
      <aside class="card cart">
        <h3>Your order</h3>
        <div id="cartLines"></div>
        <label for="slot">Pickup slot (today)</label>
        <select id="slot">${open.length ? open.map((s) => `<option value="${s.start}">${esc(s.label)} · ${s.remaining} left</option>`).join("") : `<option value="">No slots left today</option>`}</select>
        <p class="error" id="orderError"></p>
        <button class="btn primary" id="placeBtn" style="width:100%">Place order</button>
        <p class="hint">Paid from your campus wallet. You can cancel until the canteen accepts.</p>
      </aside>
    </div>`;
  app.querySelectorAll("[data-canteen]").forEach((b) => (b.onclick = () => { state.canteenId = +b.dataset.canteen; state.cart = {}; renderMenu(); }));
  app.querySelectorAll("[data-add]").forEach((b) => (b.onclick = () => changeQty(+b.dataset.add, +1)));
  app.querySelectorAll("[data-sub]").forEach((b) => (b.onclick = () => changeQty(+b.dataset.sub, -1)));
  $("#placeBtn").onclick = placeOrder;
  renderCart();
}

function itemCard(i) {
  const out = !i.is_available || i.stock === 0;
  const q = state.cart[i.id] || 0;
  return `<div class="card item">
    <img class="item-img" loading="lazy" src="${imgFor(i)}" alt="${esc(i.name)}">
    <h3>${esc(i.name)}</h3>
    <div class="meta">${i.prep_minutes} min prep · ${out ? "" : i.stock + " left"}</div>
    <div class="row">
      <span class="price">${priceHTML(i.price_paise)}</span>
      ${out ? `<span class="soldout">Sold out</span>` : `<div class="stepper">
        <button aria-label="Remove one ${esc(i.name)}" data-sub="${i.id}" ${q ? "" : "disabled"}>−</button>
        <span aria-live="polite">${q}</span>
        <button aria-label="Add one ${esc(i.name)}" data-add="${i.id}">+</button></div>`}
    </div></div>`;
}

function changeQty(id, d) {
  const item = state.menu.find((i) => i.id === id);
  const q = Math.max(0, Math.min((state.cart[id] || 0) + d, Math.min(10, item.stock)));
  if (q) state.cart[id] = q; else delete state.cart[id];
  const scroll = window.scrollY;
  renderMenu().then(() => window.scrollTo(0, scroll));
}

function renderCart() {
  const lines = Object.entries(state.cart).map(([id, q]) => ({ item: state.menu.find((i) => i.id === +id), q })).filter((l) => l.item);
  const total = lines.reduce((s, l) => s + l.item.price_paise * l.q, 0);
  $("#cartLines").innerHTML = lines.length
    ? lines.map((l) => `<div class="cart-line"><span>${l.q} × ${esc(l.item.name)}</span><span>${rupees(l.item.price_paise * l.q)}</span></div>`).join("") +
      `<div class="total"><span>Total</span><span>${rupees(total)}</span></div>`
    : `<p class="empty">Add items from the menu.</p>`;
  $("#placeBtn").disabled = !lines.length || !$("#slot").value;
}

function showTick() {
  return new Promise((resolve) => {
    const ov = $("#tickOverlay");
    ov.hidden = false;
    requestAnimationFrame(() => ov.classList.add("show"));
    setTimeout(() => {
      ov.classList.remove("show");
      setTimeout(() => { ov.hidden = true; resolve(); }, 260);
    }, 1150);
  });
}

async function placeOrder() {
  const items = Object.entries(state.cart).map(([item_id, quantity]) => ({ item_id: +item_id, quantity }));
  try {
    const order = await api("/orders", { method: "POST", body: { canteen_id: state.canteenId, slot_start: $("#slot").value, items } });
    state.cart = {};
    await refreshMe();
    await showTick();
    toast(`Order placed. Your pickup token is ${order.token}.`);
    studentView("orders");
  } catch (err) {
    $("#orderError").textContent = err.message;
    toast(err.message, true);
  }
}

async function renderMyOrders() {
  const orders = await api("/orders");
  const seen = state.seenStatus, next = {};
  for (const o of orders) {
    next[o.id] = o.status;
    if (seen[o.id] && seen[o.id] !== o.status) toast(`Order #${o.id}: ${STEP_LABEL[o.status]}`);
  }
  state.seenStatus = next;
  const pane = $("#pane");
  if (!pane) return;
  pane.innerHTML = orders.length ? `<div class="orders">${orders.map(orderCard).join("")}</div>` : `<p class="empty">No orders yet.</p>`;
  pane.querySelectorAll("[data-cancel]").forEach((b) => (b.onclick = async () => {
    try { await api(`/orders/${b.dataset.cancel}/cancel`, { method: "POST" }); await refreshMe(); toast("Order cancelled and refunded."); renderMyOrders(); }
    catch (err) { toast(err.message, true); renderMyOrders(); }
  }));
}

function orderCard(o) {
  const idx = STEPS.indexOf(o.status);
  const closed = o.status === "CANCELLED" || o.status === "REJECTED";
  return `<div class="card">
    <div class="order-head">
      <div><h3>Order #${o.id} · ${esc(o.canteen_name)}</h3>
        <div class="hint">Pickup ${time(o.slot_start)} · ${o.items.map((i) => `${i.quantity} × ${esc(i.name)}`).join(", ")} · ${rupees(o.total_paise)}</div></div>
      <div style="text-align:right"><div class="token" title="Show this at the counter">${closed ? "" : esc(o.token)}</div>
        <span class="badge s-${o.status}">${STEP_LABEL[o.status]}</span></div>
    </div>
    ${closed ? "" : `<div class="progress">${STEPS.map((_, i) => `<span class="${i <= idx ? "on" : ""}"></span>`).join("")}</div>
      <div class="steps">${STEPS.map((s) => `<span>${STEP_LABEL[s]}</span>`).join("")}</div>`}
    ${o.cancellable ? `<div class="actions"><button class="btn small danger" data-cancel="${o.id}">Cancel order</button></div>` : ""}
  </div>`;
}

// ---------------- staff ----------------
async function staffView() {
  state.view = "queue";
  app.innerHTML = `<h1>Live order queue</h1><div id="pane"></div>`;
  await renderQueue();
  poll(renderQueue);
}

async function renderQueue() {
  const groups = await api("/staff/queue" + (state.user.canteen_id ? "" : `?canteen_id=${state.canteenId || 1}`));
  const pane = $("#pane");
  if (!pane) return;
  pane.innerHTML = groups.length ? groups.map((g) => `
    <div class="slot-group"><p class="slot-title">Pickup ${time(g.slot_start)} · ${g.orders.length} order${g.orders.length > 1 ? "s" : ""}</p>
      <div class="queue">${g.orders.map(queueCard).join("")}</div></div>`).join("")
    : `<p class="empty">No open orders right now. New orders appear here automatically.</p>`;
  pane.querySelectorAll("[data-next]").forEach((b) => (b.onclick = () => advance(+b.dataset.id, b.dataset.next)));
}

function queueCard(o) {
  const [next, label] = NEXT_ACTION[o.status] || [];
  return `<div class="card">
    <div class="order-head"><h3>#${o.id} · ${esc(o.student_name)}</h3><span class="badge s-${o.status}">${STEP_LABEL[o.status]}</span></div>
    <div class="hint">${o.items.map((i) => `${i.quantity} × ${esc(i.name)}`).join("<br>")}</div>
    <div class="actions">
      ${next ? `<button class="btn small primary" data-id="${o.id}" data-next="${next}">${label}</button>` : ""}
      ${o.status === "PLACED" ? `<button class="btn small danger" data-id="${o.id}" data-next="REJECTED">Reject</button>` : ""}
    </div></div>`;
}

async function advance(id, status) {
  let token;
  if (status === "PICKED_UP") {
    token = prompt("Enter the student's 4-character pickup token:");
    if (!token) return;
  }
  if (status === "REJECTED" && !confirm("Reject this order? The student will be refunded.")) return;
  try { await api(`/staff/orders/${id}/status`, { method: "POST", body: { status, token } }); toast(`Order #${id}: ${STEP_LABEL[status]}`); }
  catch (err) { toast(err.message, true); }
  renderQueue();
}

// ---------------- admin ----------------
async function adminView(tab = "report") {
  state.view = tab;
  clearInterval(state.timer);
  state.canteenId = state.user.canteen_id || 1;
  app.innerHTML = `
    <div class="tabs">${[["report", "Today's report"], ["queue", "Order queue"], ["menu", "Menu & stock"], ["settings", "Slots & wallets"]]
      .map(([k, l]) => `<button class="tab ${tab === k ? "active" : ""}" data-tab="${k}">${l}</button>`).join("")}</div>
    <div id="pane"></div>`;
  app.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => adminView(b.dataset.tab)));
  if (tab === "report") await renderReport();
  if (tab === "queue") { await renderQueue(); poll(renderQueue); }
  if (tab === "menu") await renderAdminMenu();
  if (tab === "settings") await renderSettings();
}

async function renderReport() {
  const r = await api(`/admin/report?canteen_id=${state.canteenId}`);
  const s = r.orders_by_status;
  $("#pane").innerHTML = `
    <div class="stats">
      <div class="card stat"><div class="hint">Revenue today</div><div class="n">${rupees(r.revenue_paise)}</div></div>
      <div class="card stat"><div class="hint">Orders</div><div class="n">${r.orders_total}</div></div>
      <div class="card stat"><div class="hint">Average order</div><div class="n">${rupees(r.average_order_paise)}</div></div>
      <div class="card stat"><div class="hint">Busiest slot</div><div class="n">${r.busiest_slot ? time(r.busiest_slot) : "–"}</div></div>
    </div>
    <h2>Orders by status</h2>
    <div class="card"><table><tr>${Object.keys(s).map((k) => `<th>${STEP_LABEL[k]}</th>`).join("")}</tr><tr>${Object.values(s).map((v) => `<td>${v}</td>`).join("")}</tr></table></div>
    <h2>Top items</h2>
    <div class="card">${r.top_items.length ? `<table><tr><th>Item</th><th>Quantity</th><th>Revenue</th></tr>${r.top_items.map((t) => `<tr><td>${esc(t.name)}</td><td>${t.quantity}</td><td>${rupees(t.revenue_paise)}</td></tr>`).join("")}</table>` : `<p class="empty">No sales yet today.</p>`}</div>`;
}

async function renderAdminMenu() {
  const { items } = await api(`/canteens/${state.canteenId}/menu`);
  $("#pane").innerHTML = `
    <div class="card"><table>
      <tr><th>Item</th><th>Category</th><th>Price (₹)</th><th>Stock</th><th>Available</th><th></th></tr>
      ${items.map((i) => `<tr>
        <td>${esc(i.name)}</td><td>${esc(i.category)}</td>
        <td><input type="number" min="1" step="1" value="${i.price_paise / 100}" id="p${i.id}" aria-label="Price of ${esc(i.name)}"></td>
        <td><input type="number" min="0" value="${i.stock}" id="s${i.id}" aria-label="Stock of ${esc(i.name)}"></td>
        <td><input type="checkbox" ${i.is_available ? "checked" : ""} id="a${i.id}" style="width:auto;min-height:0" aria-label="${esc(i.name)} available"></td>
        <td><button class="btn small" data-save="${i.id}">Save</button></td></tr>`).join("")}
    </table></div>
    <h2>Add an item</h2>
    <form class="card grid2" id="addForm">
      <div><label for="nName">Name</label><input id="nName" required></div>
      <div><label for="nCat">Category</label><input id="nCat" required></div>
      <div><label for="nPrice">Price (₹)</label><input id="nPrice" type="number" min="1" required></div>
      <div><label for="nPrep">Prep time (min)</label><input id="nPrep" type="number" min="1" value="5"></div>
      <div><label for="nStock">Stock</label><input id="nStock" type="number" min="0" value="20"></div>
      <div><button class="btn primary">Add item</button></div>
    </form>`;
  app.querySelectorAll("[data-save]").forEach((b) => (b.onclick = async () => {
    const id = b.dataset.save;
    try {
      await api(`/admin/items/${id}`, { method: "PATCH", body: {
        price_paise: Math.round(+$("#p" + id).value * 100), stock: +$("#s" + id).value, is_available: $("#a" + id).checked } });
      toast("Saved.");
    } catch (err) { toast(err.message, true); }
  }));
  $("#addForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api(`/admin/canteens/${state.canteenId}/items`, { method: "POST", body: {
        name: $("#nName").value, category: $("#nCat").value, price_paise: Math.round(+$("#nPrice").value * 100),
        prep_minutes: +$("#nPrep").value, stock: +$("#nStock").value, is_available: true } });
      toast("Item added."); renderAdminMenu();
    } catch (err) { toast(err.message, true); }
  };
}

async function renderSettings() {
  const canteen = (await api("/canteens")).find((c) => c.id === state.canteenId);
  $("#pane").innerHTML = `
    <h2>Pickup slots · ${esc(canteen.name)}</h2>
    <form class="card grid2" id="slotForm">
      <div><label for="sMin">Slot length</label><select id="sMin">${[5, 10, 15, 20, 30, 60].map((m) => `<option ${m === canteen.slot_minutes ? "selected" : ""}>${m}</option>`).join("")}</select></div>
      <div><label for="sCap">Orders per slot</label><input id="sCap" type="number" min="1" max="500" value="${canteen.slot_capacity}"></div>
      <div><button class="btn primary">Save slots</button></div>
    </form>
    <h2>Top up a student wallet</h2>
    <form class="card grid2" id="topForm">
      <div><label for="tEmail">Student email</label><input id="tEmail" type="email" required></div>
      <div><label for="tAmt">Amount (₹)</label><input id="tAmt" type="number" min="1" max="5000" required></div>
      <div><button class="btn primary">Add money</button></div>
    </form>`;
  $("#slotForm").onsubmit = async (e) => {
    e.preventDefault();
    try { await api(`/admin/canteens/${state.canteenId}/slots`, { method: "PATCH", body: { slot_minutes: +$("#sMin").value, slot_capacity: +$("#sCap").value } }); toast("Slot settings saved."); }
    catch (err) { toast(err.message, true); }
  };
  $("#topForm").onsubmit = async (e) => {
    e.preventDefault();
    try { const r = await api("/admin/wallets/topup", { method: "POST", body: { email: $("#tEmail").value, amount_paise: Math.round(+$("#tAmt").value * 100) } });
      toast(`New balance for ${r.email}: ${rupees(r.wallet_paise)}`); e.target.reset(); }
    catch (err) { toast(err.message, true); }
  };
}

// ---------------- start ----------------
function start() {
  renderUserbar();
  checkLowBalance();
  const role = state.user.role;
  if (role === "student") studentView();
  else if (role === "staff") staffView();
  else adminView();
}

$("#hamburger").onclick = () => (state.drawerOpen ? closeDrawer() : openDrawer());
$("#drawerClose").onclick = closeDrawer;
$("#scrim").onclick = closeDrawer;
$("#themeBtn").onclick = toggleTheme;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

api("/me").then((u) => { state.user = u; start(); }).catch(() => renderAuth());