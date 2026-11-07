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

function fullName(s) {
  if (!s) return "";
  const mi = s.MiddleInitial ? ` ${s.MiddleInitial.replace(/\.?$/, ".")}` : "";
  return `${s.FirstName}${mi} ${s.LastName}`;
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
}

function hideAlert(el) {
  if (typeof el === "string") el = $(el);
  el.className = "alert hidden";
}

function emptyRow(colspan, message) {
  return `<tr><td colspan="${colspan}" class="empty">${esc(message)}</td></tr>`;
}

// Disables a button and shows a loading label while an action runs
async function busy(button, fn, label = "Working…") {
  const old = button.textContent;
  button.disabled = true;
  button.textContent = label;
  try {
    return await fn();
  } finally {
    button.disabled = false;
    button.textContent = old;
  }
}


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
