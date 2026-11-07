/* ui.js: display helpers shared by every page (no backend calls here). */

// Library rules, same values as backend/config.py (display only; the backend decides)
const RULES = { borrowLimit: 3, loanDays: 7, maxRenewals: 3, finePerDay: 2, dueSoonDays: 2 };

// The five reasons a borrow can be denied (DenyReason table in schema.sql)
const DENY_REASONS = [
  "Unreturned books",
  "Unpaid fines",
  "Borrow limit reached",
  "No valid Student ID",
  "Suspension of privileges",
];

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);


/* ---------- Text ---------- */

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function peso(amount) {
  return "₱" + Number(amount || 0).toLocaleString("en-PH");
}

// The middle initial as one capital letter: "r", "R.", " r " -> "R". Digits and symbols are dropped.
function cleanInitial(value) {
  const letter = String(value || "").replace(/[^A-Za-zÑñ]/g, "").charAt(0);
  return letter.toUpperCase();
}

function fullName(s) {
  if (!s) return "";
  const mi = cleanInitial(s.MiddleInitial);
  return [s.FirstName, mi && `${mi}.`, s.LastName].filter(Boolean).join(" ");
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}


/* ---------- Dates and working days ----------
   Working day = not Sunday and not a marked non-working day. Saturday counts. */

function iso(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function parseDate(value) {
  return new Date(String(value).slice(0, 10) + "T00:00");
}

function todayIso() {
  return iso(new Date());
}

function isWorkingDay(d, offDays) {
  return d.getDay() !== 0 && !offDays.has(iso(d));
}

// The date that is n working days after `start`
function addWorkingDays(start, n, offDays = new Set()) {
  const d = parseDate(start);
  while (n > 0) {
    d.setDate(d.getDate() + 1);
    if (isWorkingDay(d, offDays)) n--;
  }
  return iso(d);
}

// Working days after `from`, up to and including `to` (0 if `to` is not later)
function workingDaysBetween(from, to, offDays = new Set()) {
  const d = parseDate(from);
  const end = parseDate(to);
  let n = 0;
  while (d < end) {
    d.setDate(d.getDate() + 1);
    if (isWorkingDay(d, offDays)) n++;
  }
  return n;
}

function age(dateOfBirth) {
  if (!dateOfBirth) return "";
  const b = parseDate(dateOfBirth);
  const t = new Date();
  let a = t.getFullYear() - b.getFullYear();
  if (t.getMonth() < b.getMonth() || (t.getMonth() === b.getMonth() && t.getDate() < b.getDate())) a--;
  return a >= 0 ? a : "";
}

// "2026-11-07" -> "Nov 7, 2026";  with time: "Nov 7, 2026, 9:30 AM"
function fmtDate(value, withTime = false) {
  if (!value) return "None";
  const d = new Date(String(value).replace(" ", "T"));
  if (isNaN(d)) return esc(value);
  const opts = { month: "short", day: "numeric", year: "numeric" };
  if (withTime) Object.assign(opts, { hour: "numeric", minute: "2-digit" });
  return d.toLocaleString("en-PH", opts);
}

// Non-working days as a Set of "YYYY-MM-DD". Falls back to Sundays only if the route is missing.
async function loadOffDays() {
  try {
    return new Set((await API.nonworking()).map((d) => d.NonWorkingDate));
  } catch {
    return new Set();
  }
}


/* ---------- Status pieces (badges and the date-due slip) ---------- */

// Badge colors from the brief. Always text, never color alone.
const BADGES = {
  Available: "green", Borrowed: "", Pending: "amber",
  "Due soon": "amber", Overdue: "red", Returned: "green",
  Physical: "slate", Digital: "blue",
  "Renewal pending": "amber", "Return pending": "amber",
  Denied: "red", Approved: "green", Pass: "green", Fail: "red",
  "Good standing": "green", Suspended: "red",
};

function badge(text, kind) {
  return `<span class="badge ${kind ?? BADGES[text] ?? ""}">${esc(text)}</span>`;
}

function availabilityBadge(book) {
  if (book.available === undefined) return "";
  return book.available ? badge("Available") : badge("Borrowed");
}

// Book cover. Real covers come from Open Library (a free public catalog) by ISBN.
// No ISBN, or no cover found: a plain cover with the title, so the grid never shows a broken image.
function coverPlaceholder(book) {
  return `<div class="cover-fallback ${book.BookType === "Digital" ? "digital" : ""}" aria-hidden="true">
    <span>${esc(book.BookTitle)}</span><small>${esc(book.BookAuthor || "")}</small></div>`;
}

function coverHtml(book, size = "M") {
  const isbn = String(book.BookISBN || "").replace(/[^0-9X]/gi, "");
  const fallback = coverPlaceholder(book);
  if (!isbn) return `<div class="cover">${fallback}</div>`;
  const src = `https://covers.openlibrary.org/b/isbn/${isbn}-${size}.jpg?default=false`;
  // If the image fails to load, the cover swaps itself for the placeholder kept in data-fallback
  return `<div class="cover" data-fallback="${esc(fallback)}">
    <img src="${src}" alt="Cover of ${esc(book.BookTitle)}" loading="lazy"
         onerror="this.parentElement.innerHTML = this.parentElement.dataset.fallback"></div>`;
}

// Call number on a spine label; digital books get the accent color
function spineLabel(book) {
  return `<span class="spine-label ${book.BookType === "Digital" ? "digital" : ""}">${esc(book.BookID)}</span>`;
}

// Date-due slip. state: "" | "soon" | "late"
function slip(label, date, state = "", big = false) {
  return `<span class="slip ${state} ${big ? "big" : ""}"><span class="k">${esc(label)}</span>
    <span class="v">${fmtDate(date)}</span></span>`;
}

function dueState(dueDate, offDays) {
  if (!dueDate) return "";
  const today = todayIso();
  if (dueDate < today) return "late";
  return workingDaysBetween(today, dueDate, offDays) <= RULES.dueSoonDays ? "soon" : "";
}


/* ---------- Messages, loading, errors ---------- */

function showAlert(el, message, kind = "error") {
  if (typeof el === "string") el = $(el);
  el.className = `alert ${kind}`;
  el.textContent = message;
  el.setAttribute("role", kind === "error" ? "alert" : "status");
  // Replay the slide-in even when the box was already showing, and bring it into view
  el.style.animation = "none";
  void el.offsetWidth;
  el.style.animation = "";
  const r = el.getBoundingClientRect();
  if (r.top < 64 || r.bottom > innerHeight) el.scrollIntoView({ block: "center", behavior: "smooth" });
}

function hideAlert(el) {
  if (typeof el === "string") el = $(el);
  el.className = "alert hidden";
}

// loading = true makes the text breathe so a slow load doesn't look frozen
function emptyRow(colspan, message, loading = false) {
  return `<tr><td colspan="${colspan}" class="empty ${loading ? "loading" : ""}">${esc(message)}</td></tr>`;
}

// Disables a button and shows a spinner and a loading label while an action runs
async function busy(button, fn, label = "Working…") {
  const old = button.textContent;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.textContent = label;
  try {
    return await fn();
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.textContent = old;
  }
}


/* ---------- More detail ---------- */

// "just now", "12 min", "2 h 5 min", "3 days": how long something has been waiting
function waited(dateTime) {
  const mins = Math.floor((Date.now() - new Date(String(dateTime).replace(" ", "T"))) / 60000);
  if (isNaN(mins) || mins < 1) return "just now";
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  if (h < 24) return `${h} h${mins % 60 ? ` ${mins % 60} min` : ""}`;
  return plural(Math.floor(h / 24), "day");
}

// "3 working days left", "Due today", "2 working days overdue"
function dueText(dueDate, offDays) {
  if (!dueDate) return "";
  const today = todayIso();
  if (dueDate === today) return "Due today";
  if (dueDate > today) return `${plural(workingDaysBetween(today, dueDate, offDays), "working day")} left`;
  return `${plural(workingDaysBetween(dueDate, today, offDays), "working day")} overdue`;
}


/* ---------- Forms: messages under fields, password toggle ---------- */

// Shows a message under one field (or clears it with ""), and marks the field for screen readers
function fieldError(id, message) {
  const input = $(id);
  const hintId = `${id}-error`;
  let hint = document.getElementById(hintId);
  if (!hint) {
    hint = document.createElement("p");
    hint.id = hintId;
    hint.className = "field-error";
    (input.closest(".inline") || input).insertAdjacentElement("afterend", hint);
  }
  hint.textContent = message;
  input.classList.toggle("invalid", !!message);
  input.setAttribute("aria-invalid", String(!!message));
  if (message) input.setAttribute("aria-describedby", hintId);
  else input.removeAttribute("aria-describedby");
  return !message;
}

// Adds a Show/Hide button to every password field on the page
function addPasswordToggles() {
  document.querySelectorAll('input[type="password"]').forEach((input) => {
    const wrap = document.createElement("div");
    wrap.className = "inline";
    input.replaceWith(wrap);
    wrap.appendChild(input);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn secondary";
    btn.textContent = "Show";
    btn.setAttribute("aria-label", `Show ${input.labels[0] ? input.labels[0].textContent : "password"}`);
    btn.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "Hide" : "Show";
      btn.setAttribute("aria-pressed", String(show));
    });
    wrap.appendChild(btn);
  });
}


/* ---------- Tables on phones ----------
   Each cell gets its column name (data-label) so responsive.css can show rows as cards. */

function labelTables() {
  document.querySelectorAll("table").forEach((t) => {
    if (!t.tHead) return; // only data tables with column headings become cards
    t.classList.add("stack");
    const heads = [...t.querySelectorAll("thead th")].map((th) => th.textContent.trim());
    t.querySelectorAll("tbody tr").forEach((tr) => {
      [...tr.children].forEach((td, i) => {
        if (!td.hasAttribute("colspan")) td.dataset.label = heads[i] || "";
      });
    });
  });
}
new MutationObserver(labelTables).observe(document.body, { childList: true, subtree: true });
labelTables();

// A page-to-page fade that gets interrupted (fast double click, reload mid-fade) is harmless;
// catch its "skipped" rejections so they don't show as console errors
for (const type of ["pageswap", "pagereveal"]) {
  addEventListener(type, (e) => {
    const vt = e.viewTransition;
    if (!vt) return;
    [vt.ready, vt.finished, vt.updateCallbackDone].forEach((p) => p && p.catch(() => {}));
  });
}

// Clicking the dark area outside any popup closes it, like pressing Cancel
document.addEventListener("click", (e) => {
  if (e.target.tagName === "DIALOG" && e.target.open) {
    const r = e.target.getBoundingClientRect();
    const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    if (!inside) e.target.close();
  }
});


/* ---------- Popups ----------
   confirmDialog({ title, body (HTML), confirm, danger }) -> Promise<boolean>
   Uses <dialog>, so Escape closes it and focus stays inside. */

function confirmDialog({ title, body = "", confirm = "Confirm", cancel = "Cancel", danger = false }) {
  return new Promise((resolve) => {
    const dlg = document.createElement("dialog");
    dlg.setAttribute("aria-labelledby", "dlg-title");
    dlg.innerHTML = `
      <h2 id="dlg-title">${esc(title)}</h2>
      <div>${body}</div>
      <div class="actions">
        <button type="button" class="btn secondary" data-v="0">${esc(cancel)}</button>
        <button type="button" class="btn ${danger ? "danger" : ""}" data-v="1">${esc(confirm)}</button>
      </div>`;
    document.body.appendChild(dlg);
    let result = false;
    dlg.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-v]");
      if (b) { result = b.dataset.v === "1"; dlg.close(); }
    });
    dlg.addEventListener("close", () => { dlg.remove(); resolve(result); });
    dlg.showModal();
    dlg.querySelector('[data-v="1"]').focus();
  });
}
