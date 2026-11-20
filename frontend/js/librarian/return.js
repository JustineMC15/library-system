// Process Return: return.html?student=<StudentID>&borrow=<BorrowID>
// Return Details (Student ID, Book ID, Return Date) on the left, Summary with the fine on the right.
let st = null;
let offDays = new Set();
let timer;

function selectedLoan() {
  const id = $("BookID").value.trim().toLowerCase();
  return st && id && (st.loans || []).find((l) => String(l.BookID).toLowerCase() === id);
}

const dueOf = (l) => l.DueDate || addWorkingDays(l.BorrowDate, RULES.loanDays, offDays);
const daysLate = (l, date) => (date > dueOf(l) ? workingDaysBetween(dueOf(l), date, offDays) : 0);
const isDigital = (l) => l.BookType === "Digital";
const requestedOn = (l) => (l.ReturnRequestedAt ? String(l.ReturnRequestedAt).slice(0, 10) : "");

// The date the fine runs to. When the student already asked to return the book (always the case
// for an e-book), the backend uses the request date, so the page must too, whatever is typed.
const fineDate = (l) => requestedOn(l) || $("ReturnDate").value;

// The date the librarian picked, kept aside while a request date is shown instead
let ownDate = "";

function lockDate(l) {
  const req = l && requestedOn(l);
  const input = $("ReturnDate");
  if (req) {
    if (!input.disabled) ownDate = input.value;
    input.value = req;
  } else if (input.disabled) {
    input.value = ownDate || todayIso();
  }
  input.disabled = !!req;
  $("date-help").textContent = !l ? ""
    : req ? `Set by the student's return request on ${fmtDate(req)}. The fine stops on that day.`
    : isDigital(l) ? ""
    : "The day the book came back to the desk. The fine runs up to this day.";
}

function renderSummary() {
  const l = selectedLoan();
  lockDate(l);
  const typed = $("BookID").value.trim();

  if (!l) {
    $("confirm").disabled = true;
    const hint = st && typed ? `${esc(fullName(st))} hasn't borrowed a book with that ID.`
      : st ? "Enter or pick the Book ID." : "Enter the Student ID first.";
    $("summary").innerHTML = `<tr><td class="muted" colspan="2">${hint}</td></tr>`;
    return;
  }

  // An e-book can only be returned after the student requests it (from My Borrowed Books)
  if (isDigital(l) && !requestedOn(l)) {
    $("confirm").disabled = true;
    $("summary").innerHTML = `
      <tr><th scope="row">Book</th><td>${esc(l.BookTitle)} ${badge("Digital")}</td></tr>
      <tr><td colspan="2" class="why">An e-book can only be returned after the student requests it from My Borrowed Books.</td></tr>`;
    return;
  }

  const date = fineDate(l);
  $("confirm").disabled = !date;
  const late = daysLate(l, date);
  $("summary").innerHTML = `
    <tr><th scope="row">Book</th><td>${esc(l.BookTitle)} ${badge(isDigital(l) ? "Digital" : "Physical")}</td></tr>
    <tr><th scope="row">Due Date</th><td>${fmtDate(dueOf(l))}</td></tr>
    ${requestedOn(l) ? `<tr><th scope="row">Return requested</th><td>${fmtDate(l.ReturnRequestedAt, true)}</td></tr>` : ""}
    <tr><th scope="row">Days Late</th><td>${late ? `${badge("Overdue")} ${plural(late, "working day")}` : `${badge("Returned")} On time`}</td></tr>
    <tr><th scope="row">Fine</th><td class="${late ? "money-bad" : ""}">${peso(late * RULES.finePerDay)}</td></tr>`;
}

// The student detail route may not send BookType yet: look it up from the book itself
async function fillBookTypes(loans) {
  await Promise.all(loans.filter((l) => !l.BookType).map(async (l) => {
    try { l.BookType = (await API.book(l.BookID)).BookType; } catch { /* leave unknown: treated as physical */ }
  }));
}

async function find(studentId, borrowId) {
  hideAlert("alert");
  $("student-name").textContent = "Looking up…";
  try {
    st = await API.student(studentId);
  } catch (err) {
    st = null;
    $("BookID").disabled = true;
    $("student-name").textContent = err.status === 404 ? `No student with ID ${studentId}.` : err.message;
    return renderSummary();
  }
  const loans = st.loans || [];
  await fillBookTypes(loans);
  $("student-name").textContent = `${fullName(st)}, ${plural(loans.length, "book")} borrowed`;
  $("borrowed-books").innerHTML = loans.map((l) => {
    const note = isDigital(l) ? (requestedOn(l) ? " (e-book, return requested)" : " (e-book, no return request)") : "";
    return `<option value="${esc(l.BookID)}">${esc(l.BookTitle + note)}</option>`;
  }).join("");
  $("BookID").disabled = !loans.length;
  const pre = loans.find((l) => l.BorrowID === borrowId) || (loans.length === 1 ? loans[0] : null);
  if (pre) $("BookID").value = pre.BookID;
  renderSummary();
  (pre ? $("ReturnDate") : $("BookID")).focus();
}

// Look the student up shortly after typing stops, or right away on Enter
$("StudentID").addEventListener("input", () => {
  clearTimeout(timer);
  const id = $("StudentID").value.trim();
  if (id.length >= 4) timer = setTimeout(() => find(id), 500);
});
$("StudentID").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); clearTimeout(timer); find($("StudentID").value.trim()); }
});
$("BookID").addEventListener("input", renderSummary);
$("ReturnDate").addEventListener("input", renderSummary);

$("form").addEventListener("reset", () => {
  st = null;
  setTimeout(() => {   // after the browser clears the fields
    $("ReturnDate").value = todayIso();
    $("BookID").disabled = true;
    $("student-name").textContent = "";
    renderSummary();
    $("StudentID").focus();
  });
});

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const l = selectedLoan();
  if (!l || (isDigital(l) && !requestedOn(l))) return;
  const date = fineDate(l);
  if (!date) return;
  if (date > todayIso()) return showAlert("alert", "The return date can't be in the future.");
  const fine = daysLate(l, date) * RULES.finePerDay;
  const ok = await confirmDialog({
    title: "Confirm this return?",
    body: `<p><strong>${esc(l.BookTitle)}</strong> from ${esc(fullName(st))}, ${requestedOn(l) ? `return requested ${fmtDate(date)}` : `returned ${fmtDate(date)}`}.</p>
      <p>${fine ? `<span class="money-bad">A fine of ${peso(fine)} will be recorded.</span>` : "No fine."}</p>`,
    confirm: "Confirm Return",
  });
  if (!ok) return;
  try {
    const res = await busy($("confirm"), () => API.processReturn(l.BorrowID, date), "Saving…");
    const recorded = res && res.FineAmount !== undefined ? res.FineAmount : fine;
    showAlert("alert", `Return saved for ${l.BookTitle}.${recorded ? ` Fine recorded: ${peso(recorded)}.` : ""}`, "success");
    $("BookID").value = "";
    find(st.StudentID);
  } catch (err) {
    showAlert("alert", err.message);
  }
});

(async () => {
  await startPage("librarian", "return");
  $("ReturnDate").value = todayIso();
  $("ReturnDate").max = todayIso();
  offDays = await loadOffDays();
  renderSummary();
  const sid = params.get("student");
  if (sid) {
    $("StudentID").value = sid;
    find(sid, Number(params.get("borrow")) || null);
  } else {
    $("StudentID").focus();
  }
})();
