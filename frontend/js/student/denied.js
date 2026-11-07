// Borrow Request Denied: denied.html?id=<BorrowID> shows one red card per reason, each with a way forward.
// Without an id it shows all of the student's denied requests.
const borrowId = Number(params.get("id"));

const MINE = { href: "borrowed.html", label: "Go to My Borrowed Books" };
const HOME = { href: "dashboard.html", label: "Back to Dashboard" };

// What each reason means and where to go next (Figma: Student Borrow Denied)
function reasonCard(reason, r) {
  const info = {
    "Unreturned books": ["You have an overdue book. Return it before requesting another.", MINE],
    "Unpaid fines": [`You owe ${r.FineOwed ? peso(r.FineOwed) : "a fine"}. Pay at the librarian's desk to continue borrowing.`, MINE],
    "Borrow limit reached": [`You already have ${RULES.borrowLimit} books. Return one to borrow another.`, MINE],
    "No valid Student ID": ["We could not verify your Student ID. Bring your school ID or ask the librarian for help.", HOME],
    "Suspension of privileges": ["Your borrowing privileges are suspended. Please talk to the librarian.", HOME],
  }[reason] || ["", HOME];
  return `
    <div class="deny-card">
      <h3>${esc(reason)}</h3>
      <p>${esc(info[0])}</p>
      <a class="btn small secondary" href="${info[1].href}">${info[1].label}</a>
    </div>`;
}

function block(r) {
  const reasons = r.reasons || [];
  return `
    <section class="card" aria-label="Denied request for ${esc(r.BookTitle)}">
      <div class="card-head">
        <div>
          <h2>${esc(r.BookTitle)}</h2>
          <p class="muted">Requested ${fmtDate(r.RequestedAt, true)}${r.LibrarianID ? `, reviewed by ${esc(r.LibrarianID)}` : ""}.
            ${reasons.length > 1 ? `${reasons.length} reasons apply.` : ""}</p>
        </div>
        <a class="btn" href="book.html?id=${encodeURIComponent(r.BookID)}">Request again</a>
      </div>
      ${reasons.map((x) => reasonCard(x, r)).join("") || '<p class="muted">No reason was recorded.</p>'}
    </section>`;
}

(async () => {
  await startPage("student", "borrowed");
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
