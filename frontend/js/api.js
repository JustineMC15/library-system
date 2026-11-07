/* api.js: the only file that talks to the backend.
   Load order on every page: api.js, ui.js, layout.js, then the page's own script.

   (exists)  the route is in the backend (some only on the jhasmine-auth branch so far)
   (needed)  the route the page expects; until it exists the page shows
             "This feature isn't connected to the backend yet." instead of breaking.
   Field names follow the database columns in backend/schema.sql. */

const API = {
  // ----- Accounts -----
  login: (role, id, password) => request("POST", "/api/login", { role, id, password }),   // (exists)
  logout: () => request("POST", "/api/logout"),                                             // (exists)
  me: () => request("GET", "/api/me"),                                                      // (exists)
  // (needed) for students, also return Status: "Active" | "Suspended"
  registerStudent: (data) => request("POST", "/api/register", data),                        // (exists)
  registerLibrarian: (data) => request("POST", "/api/librarian/register", data),            // (exists)

  // ----- Books -----
  // filters: { search, type: "Physical" | "Digital", available: "1" }
  books: (filters = {}) => request("GET", "/api/books" + query(filters)),                   // (exists)
  book: (bookId) => request("GET", "/api/books/" + encodeURIComponent(bookId)),             // (exists)

  // ----- Calendar (any logged-in user, used to preview due dates) -----
  nonworking: () => request("GET", "/api/nonworking"),                                      // (needed)
  // -> [{ NonWorkingDate, Reason, LibrarianID }]

  // ----- Student -----
  myLoans: () => request("GET", "/api/student/loans"),                                      // (exists)
  // (needed) extra fields per row: BookType, DueDate, Renewals, PendingRenew, PendingReturn, Fine
  requestBorrow: (bookId) => request("POST", "/api/borrow", { book_id: bookId }),           // (needed)
  requestRenew: (borrowId) => request("POST", "/api/renew", { borrow_id: borrowId }),       // (needed)
  requestReturn: (borrowId) => request("POST", "/api/return", { borrow_id: borrowId }),     // (needed)
  myDenied: () => request("GET", "/api/student/denied"),                                    // (needed)
  // -> [{ BorrowID, BookID, BookTitle, RequestedAt, LibrarianID, reasons: [...], FineOwed }]

  // ----- Librarian: dashboard and queue (borrowing.get_queue) -----
  stats: () => request("GET", "/api/librarian/stats"),                                      // (needed)
  // -> { borrows_today, returns_today, overdue }
  queue: (type) => request("GET", "/api/librarian/queue" + query({ type })),                // (needed)
  // -> [{ type: "borrow"|"renew"|"return", request_id, BorrowID, StudentID, StudentName,
  //       BookID, BookTitle, RequestedAt, DueDate }]  oldest first
  history: (type) => request("GET", "/api/librarian/history" + query({ type })),            // (needed)
  // -> [{ type, StudentID, StudentName, BookTitle, RequestedAt, Status, LibrarianID }]
  approve: (type, id, data = {}) => request("POST", `/api/librarian/${type}/${id}/approve`, data), // (needed)
  // borrow: data = { student_id_ok: true }
  deny: (type, id, data = {}) => request("POST", `/api/librarian/${type}/${id}/deny`, data),       // (needed)
  // borrow: data = { reasons: ["Unpaid fines", ...] }

  // ----- Librarian: one student (Verify Student, Process Return) -----
  student: (studentId) => request("GET", "/api/librarian/students/" + encodeURIComponent(studentId)), // (needed)
  // -> { StudentID, LastName, FirstName, MiddleInitial, Address, DateOfBirth, Status,
  //      contacts: [...], FineOwed, checks: { ...checks.run_checks() },
  //      loans: [{ BorrowID, BookID, BookTitle, BorrowDate, DueDate }],      (currently borrowed)
  //      pending: [{ BorrowID, BookID, BookTitle, RequestedAt }] }           (pending borrow requests)
  payFines: (studentId) => request("POST", `/api/librarian/students/${encodeURIComponent(studentId)}/pay-fines`), // (needed)
  processReturn: (borrowId, returnDate) =>                                                  // (needed)
    request("POST", "/api/librarian/returns", { borrow_id: borrowId, return_date: returnDate }),
  // -> { ok, FineAmount }  (also closes the student's pending return request, if any)

  // ----- Librarian: non-working days -----
  addNonworking: (date, reason) => request("POST", "/api/librarian/nonworking", { date, reason }), // (needed)
  removeNonworking: (date) => request("DELETE", "/api/librarian/nonworking/" + date),       // (needed)
  nonworkingImpact: (date) => request("GET", "/api/librarian/nonworking/impact" + query({ date })), // (needed)
  // -> { borrowed_affected: 4 }
};


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
    throw new ApiError("Can't reach the server. Is python backend/app.py running?", 0);
  }

  const isJson = (res.headers.get("Content-Type") || "").includes("application/json");
  const data = isJson ? await res.json() : null;

  if (!res.ok) {
    // Flask answers a route it doesn't have with an HTML 404/405 page, not JSON
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
