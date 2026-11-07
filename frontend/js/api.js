/* api.js: the only file that talks to the backend.
   Every page loads this first, then its own file from js/student/ or js/librarian/.

   Endpoints marked (exists) are already in the backend (some only on the jhasmine-auth branch).
   Endpoints marked (needed) are what the pages expect; until the backend adds them,
   the page shows "not connected to the backend yet" instead of breaking. */

const API = {
  // ----- Accounts -----
  login: (role, id, password) => request("POST", "/api/login", { role, id, password }),       // (exists)
  logout: () => request("POST", "/api/logout"),                                                 // (exists)
  me: () => request("GET", "/api/me"),                                                          // (exists)
  registerStudent: (data) => request("POST", "/api/register", data),                            // (exists)
  registerLibrarian: (data) => request("POST", "/api/librarian/register", data),                // (exists, librarian only)

  // ----- Books -----
  // filters: { search, type: "Physical"|"Digital", year, available: "1" }
  books: (filters = {}) => request("GET", "/api/books" + query(filters)),                       // (exists)
  book: (bookId) => request("GET", "/api/books/" + encodeURIComponent(bookId)),                 // (exists)

  // ----- Student -----
  myLoans: () => request("GET", "/api/student/loans"),                                          // (exists)
  requestBorrow: (bookId) => request("POST", "/api/borrow", { book_id: bookId }),               // (needed)
  requestRenew: (borrowId) => request("POST", "/api/renew", { borrow_id: borrowId }),           // (needed)
  requestReturn: (borrowId) => request("POST", "/api/return", { borrow_id: borrowId }),         // (needed)
  myDenied: () => request("GET", "/api/student/denied"),                                        // (needed)
  // -> [{ BorrowID, BookID, BookTitle, RequestedAt, reasons: ["Unpaid fines", ...] }]

  // ----- Librarian: request queue (borrowing.get_queue) -----
  queue: (type) => request("GET", "/api/librarian/queue" + query({ type })),                    // (needed)
  // -> [{ type: "borrow"|"renew"|"return", request_id, StudentID, BookID, RequestedAt, BookTitle?, StudentName? }]
  checks: (studentId) => request("GET", "/api/librarian/checks/" + encodeURIComponent(studentId)), // (needed)
  // -> checks.run_checks result: { "Unreturned books": false, "Unpaid fines": false, ... }
  approve: (type, id, data = {}) => request("POST", `/api/librarian/${type}/${id}/approve`, data), // (needed)
  // borrow: data = { student_id_ok: true|false }
  deny: (type, id, data = {}) => request("POST", `/api/librarian/${type}/${id}/deny`, data),    // (needed)
  // borrow: data = { reasons: ["Unpaid fines", ...] }

  // ----- Librarian: fines -----
  fines: () => request("GET", "/api/librarian/fines"),                                          // (needed)
  // -> [{ ReturnID, StudentID, StudentName?, BookTitle, ReturnDate, FineAmount, FinePaidDate }]
  markFinePaid: (returnId) => request("POST", `/api/librarian/fines/${returnId}/paid`),        // (needed)

  // ----- Librarian: non-working days -----
  nonworking: () => request("GET", "/api/librarian/nonworking"),                                // (needed)
  // -> [{ NonWorkingDate, Reason, LibrarianID }]
  addNonworking: (date, reason) => request("POST", "/api/librarian/nonworking", { date, reason }), // (needed)
  removeNonworking: (date) => request("DELETE", "/api/librarian/nonworking/" + date),          // (needed)
};

// Reasons the database accepts for a denied borrow (schema.sql, DenyReason table)
const DENY_REASONS = [
  "Unreturned books",
  "Unpaid fines",
  "Borrow limit reached",
  "No valid Student ID",
  "Suspension of privileges",
];

// Library rules, copied from backend/config.py for display only
const RULES = { borrowLimit: 3, loanDays: 7, maxRenewals: 3, finePerDay: 2 };


/* ---------- Request helper ---------- */

class ApiError extends Error {
  constructor(message, status, notConnected = false) {
    super(message);
    this.status = status;
    this.notConnected = notConnected;
  }
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Could not reach the server. Is `python backend/app.py` running?", 0);
  }

  const isJson = (res.headers.get("Content-Type") || "").includes("application/json");
  const data = isJson ? await res.json() : null;

  if (!res.ok) {
    // Flask answers an unknown route with an HTML 404/405 page, not JSON
    if (!isJson && (res.status === 404 || res.status === 405)) {
      throw new ApiError("This feature isn't connected to the backend yet.", res.status, true);
    }
    throw new ApiError((data && data.error) || `Request failed (${res.status})`, res.status);
  }
  return data;
}

function query(params) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") q.set(k, v);
  }
  const s = q.toString();
  return s ? "?" + s : "";
}


/* ---------- Login guard and top bar ---------- */

// Call at the top of every page that needs a login. Sends the user to the right login page if not.
async function requireRole(role) {
  try {
    const me = await API.me();
    if (me.role !== role) throw new Error("wrong role");
    setupTopbar(me);
    return me;
  } catch (err) {
    if (err instanceof ApiError && err.notConnected) {
      // Backend has no /api/me yet: let the page load so it can still be previewed
      setupTopbar({ id: "(not logged in)", role });
      return { id: null, role };
    }
    location.href = `/${role}/login.html`;
    throw err;
  }
}

function setupTopbar(me) {
  const who = document.getElementById("who");
  if (who) who.textContent = me.id;
  const btn = document.getElementById("logout");
  if (btn) {
    btn.addEventListener("click", async () => {
      try { await API.logout(); } catch { /* go to login either way */ }
      location.href = `/${me.role}/login.html`;
    });
  }
}


/* ---------- Small display helpers ---------- */

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

// "2026-11-07" or "2026-11-07 09:30:00" -> "Nov 7, 2026" (or with time)
function fmtDate(value, withTime = false) {
  if (!value) return "—";
  const d = new Date(String(value).replace(" ", "T"));
  if (isNaN(d)) return esc(value);
  const opts = { month: "short", day: "numeric", year: "numeric" };
  if (withTime) Object.assign(opts, { hour: "numeric", minute: "2-digit" });
  return d.toLocaleString("en-PH", opts);
}

function peso(amount) {
  return "₱" + Number(amount || 0).toLocaleString("en-PH");
}

// Shows a message in a <div class="alert hidden"> box. kind: error | success | warning | info
function showAlert(el, message, kind = "error") {
  if (typeof el === "string") el = document.getElementById(el);
  el.className = `alert ${kind}`;
  el.textContent = message;
}

function hideAlert(el) {
  if (typeof el === "string") el = document.getElementById(el);
  el.className = "alert hidden";
}

const STATUS_BADGE = {
  Pending: "warning",
  Borrowed: "blue",
  Returned: "success",
  Denied: "error",
  Approved: "success",
};

function badge(text, kind) {
  return `<span class="badge ${kind || STATUS_BADGE[text] || ""}">${esc(text)}</span>`;
}

// Table/list placeholder while loading, when empty, or when the endpoint is missing
function emptyRow(colspan, message) {
  return `<tr><td colspan="${colspan}" class="empty">${esc(message)}</td></tr>`;
}

// Disables a button while an async action runs
async function busy(button, fn) {
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Please wait…";
  try {
    return await fn();
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}
