// Student dashboard: lists the student's loans and lets them ask to renew or return.
// Uses GET /api/student/loans. DueDate, Renewals, PendingRenew and PendingReturn are
// optional extra fields the backend can add; the page works without them.

async function load() {
  const tbody = document.getElementById("loans");
  const history = document.getElementById("history");
  let loans;
  try {
    loans = await API.myLoans();
  } catch (err) {
    tbody.innerHTML = emptyRow(6, err.message);
    history.innerHTML = emptyRow(3, err.message);
    return;
  }

  const active = loans.filter((l) => l.Status === "Pending" || l.Status === "Borrowed");
  const returned = loans.filter((l) => l.Status === "Returned");
  const borrowed = active.filter((l) => l.Status === "Borrowed");

  document.getElementById("stat-borrowed").textContent = `${borrowed.length} / ${RULES.borrowLimit}`;
  document.getElementById("stat-pending").textContent = active.length - borrowed.length;
  const dues = borrowed.map((l) => l.DueDate).filter(Boolean).sort();
  document.getElementById("stat-due").textContent = dues.length ? fmtDate(dues[0]) : "—";

  tbody.innerHTML = active.length
    ? active.map(row).join("")
    : emptyRow(6, "You have no books right now. Browse the catalog to borrow one.");

  history.innerHTML = returned.length
    ? returned.map((l) => `
        <tr>
          <td><div class="title">${esc(l.BookTitle)}</div><div class="sub">${esc(l.BookAuthor)}</div></td>
          <td>${fmtDate(l.BorrowDate)}</td>
          <td>${badge(l.Status)}</td>
        </tr>`).join("")
    : emptyRow(3, "No returned books yet.");
}

function row(l) {
  const overdue = l.DueDate && l.Status === "Borrowed" && l.DueDate < new Date().toISOString().slice(0, 10);
  let actions = "";
  if (l.Status === "Borrowed") {
    const renewals = l.Renewals ?? 0;
    const renewDisabled = l.PendingRenew || l.PendingReturn || renewals >= RULES.maxRenewals;
    actions = `
      <div class="actions">
        ${l.DigitalLink ? `<a class="btn small outline" href="${esc(l.DigitalLink)}" target="_blank" rel="noopener">Open e-book</a>` : ""}
        <button class="btn small outline" data-renew="${l.BorrowID}" ${renewDisabled ? "disabled" : ""}>
          ${l.PendingRenew ? "Renewal requested" : "Renew"}</button>
        <button class="btn small" data-return="${l.BorrowID}" ${l.PendingReturn ? "disabled" : ""}>
          ${l.PendingReturn ? "Return requested" : "Return"}</button>
      </div>`;
  }
  return `
    <tr>
      <td><a class="title" href="book.html?id=${encodeURIComponent(l.BookID)}">${esc(l.BookTitle)}</a>
          <div class="sub">${esc(l.BookAuthor)}</div></td>
      <td>${badge(l.Status)} ${overdue ? badge("Overdue", "error") : ""}</td>
      <td>${fmtDate(l.BorrowDate)}</td>
      <td>${l.Status === "Borrowed" ? fmtDate(l.DueDate) : "—"}</td>
      <td>${l.Status === "Borrowed" ? `${l.Renewals ?? 0} / ${RULES.maxRenewals}` : "—"}</td>
      <td>${actions}</td>
    </tr>`;
}

document.getElementById("loans").addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  hideAlert("alert");
  try {
    if (btn.dataset.renew) {
      await busy(btn, () => API.requestRenew(+btn.dataset.renew));
      showAlert("alert", "Renewal requested. A librarian will review it.", "success");
    } else if (btn.dataset.return) {
      await busy(btn, () => API.requestReturn(+btn.dataset.return));
      showAlert("alert", "Return requested. Bring the book to the library desk.", "success");
    }
    load();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

requireRole("student").then(load);
