// Borrow Denied: denied.html?id=<BorrowID> shows every reason that applied to that request.
// Without an id it shows all of the student's denied requests.
const borrowId = Number(params.get("id"));

// What each reason means and what the student can do about it
const FIX = {
  "Unreturned books": "You have a book past its due date. Return it first.",
  "Unpaid fines": "Pay your fine at the library desk.",
  "Borrow limit reached": `You already hold ${RULES.borrowLimit} books. Return one to free a slot.`,
  "No valid Student ID": "Bring your school ID to the desk when you pick up the book.",
  "Suspension of privileges": "Your borrowing is suspended. Talk to the librarian.",
};

function block(r) {
  const reasons = (r.reasons || []).map((x) => `
    <li>
      <div><strong>${esc(x)}</strong>
        ${x === "Unpaid fines" && r.FineOwed ? ` <span class="money-bad">${peso(r.FineOwed)} owed</span>` : ""}</div>
      <div class="muted">${esc(FIX[x] || "")}</div>
    </li>`).join("");

  return `
    <section class="card">
      <div class="card-head">
        <div>
          <h1>Request denied: ${esc(r.BookTitle)}</h1>
          <p class="muted">Requested ${fmtDate(r.RequestedAt, true)}${r.LibrarianID ? `, reviewed by ${esc(r.LibrarianID)}` : ""}</p>
        </div>
        ${badge("Denied")}
      </div>
      <h2>${r.reasons && r.reasons.length > 1 ? `${r.reasons.length} reasons` : "Reason"}</h2>
      <ul class="checklist">${reasons || '<li class="muted">No reason was recorded.</li>'}</ul>
      <div class="actions" style="margin-top:24px">
        <a class="btn" href="book.html?id=${encodeURIComponent(r.BookID)}">Request this book again</a>
      </div>
    </section>`;
}

(async () => {
  await startPage("student", "dashboard");
  try {
    const rows = await API.myDenied();
    const shown = borrowId ? rows.filter((r) => r.BorrowID === borrowId) : rows;
    $("content").innerHTML = shown.length
      ? shown.map(block).join("")
      : `<div class="card empty">${borrowId ? "That request wasn't found among your denied requests." : "No denied requests."}</div>`;
  } catch (err) {
    $("content").innerHTML = `<div class="card empty">${esc(err.message)}</div>`;
  }
})();
