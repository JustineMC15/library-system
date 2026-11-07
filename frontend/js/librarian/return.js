// Process Return: return.html?student=<StudentID>&borrow=<BorrowID>
// Pick the student and the book, record the return date, confirm. Shows the fine before confirming.
let st = null;
let offDays = new Set();

function selectedLoan() {
  const id = Number($("BorrowID").value);
  return st && (st.loans || []).find((l) => l.BorrowID === id);
}

function dueOf(l) {
  return l.DueDate || addWorkingDays(l.BorrowDate, RULES.loanDays, offDays);
}

function fineFor(l, returnDate) {
  const due = dueOf(l);
  return returnDate > due ? workingDaysBetween(due, returnDate, offDays) * RULES.finePerDay : 0;
}

function renderSummary() {
  const l = selectedLoan();
  const date = $("ReturnDate").value;
  $("confirm").disabled = !l || !date;
  if (!l) {
    $("summary").innerHTML = `<p class="muted">Pick a book to see its due date and any fine.</p>`;
    return;
  }
  const due = dueOf(l);
  const late = date > due;
  const fine = fineFor(l, date);
  $("summary").innerHTML = `
    <p><strong>${esc(l.BookTitle)}</strong></p>
    <p>${spineLabel(l)}</p>
    <div class="actions" style="margin-bottom:16px">
      ${slip("Borrowed", l.BorrowDate)}
      ${slip("Due", due, late ? "late" : "")}
    </div>
    ${late
      ? `<p>${badge("Overdue")} ${plural(workingDaysBetween(due, date, offDays), "working day")} late</p>
         <p class="money-bad big">Fine: ${peso(fine)}</p>`
      : `<p>${badge("Returned")} On time, no fine.</p>`}`;
}

async function find(studentId, borrowId) {
  hideAlert("alert");
  $("StudentID").value = studentId;
  $("student-name").textContent = "Looking up…";
  try {
    st = await API.student(studentId);
  } catch (err) {
    st = null;
    $("student-name").textContent = "";
    $("BorrowID").innerHTML = `<option value="">Find a student first</option>`;
    $("BorrowID").disabled = true;
    renderSummary();
    return showAlert("alert", err.status === 404 ? `No student with ID ${studentId}.` : err.message);
  }

  const loans = st.loans || [];
  $("student-name").textContent = `${fullName(st)}, ${plural(loans.length, "book")} borrowed`;
  $("BorrowID").innerHTML = loans.length
    ? `<option value="">Choose a book</option>` + loans.map((l) =>
        `<option value="${l.BorrowID}" ${l.BorrowID === borrowId ? "selected" : ""}>${esc(l.BookTitle)}</option>`).join("")
    : `<option value="">No borrowed books</option>`;
  $("BorrowID").disabled = !loans.length;
  renderSummary();
}

$("find").addEventListener("click", () => {
  const id = $("StudentID").value.trim();
  if (!id) return showAlert("alert", "Type a Student ID first.");
  find(id);
});
$("StudentID").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); $("find").click(); }
});
$("BorrowID").addEventListener("change", renderSummary);
$("ReturnDate").addEventListener("input", renderSummary);

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const l = selectedLoan();
  const date = $("ReturnDate").value;
  if (!l || !date) return;
  if (date > todayIso()) return showAlert("alert", "The return date can't be in the future.");
  const fine = fineFor(l, date);
  const ok = await confirmDialog({
    title: "Confirm this return?",
    body: `<p><strong>${esc(l.BookTitle)}</strong> from ${esc(fullName(st))}, returned ${fmtDate(date)}.</p>
      <p>${fine ? `<span class="money-bad">Fine of ${peso(fine)} will be recorded.</span>` : "No fine."}</p>`,
    confirm: "Confirm return",
  });
  if (!ok) return;
  try {
    const res = await busy($("confirm"), () => API.processReturn(l.BorrowID, date), "Saving…");
    const recorded = res && res.FineAmount !== undefined ? res.FineAmount : fine;
    showAlert("alert", `Return saved for ${l.BookTitle}.${recorded ? ` Fine recorded: ${peso(recorded)}.` : ""}`, "success");
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
  if (params.get("student")) find(params.get("student"), Number(params.get("borrow")) || null);
})();
