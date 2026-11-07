// Student dashboard: summary cards, entry cards, and My Borrowed Books (Borrowed / Denied tabs).
let offDays = new Set();
let loans = [];

function isDigital(l) {
  return l.BookType ? l.BookType === "Digital" : !!l.DigitalLink;
}

function dueOf(l) {
  return l.DueDate || (l.BorrowDate ? addWorkingDays(l.BorrowDate, RULES.loanDays, offDays) : null);
}

function setStat(id, value, tone = "") {
  const el = $(id);
  el.className = `stat ${tone}`;
  el.querySelector(".value").textContent = value;
}

/* ---------- Summary ---------- */

function renderSummary(me) {
  const borrowed = loans.filter((l) => l.Status === "Borrowed");
  const soon = borrowed.filter((l) => dueState(dueOf(l), offDays) === "soon").length;
  const late = borrowed.filter((l) => dueState(dueOf(l), offDays) === "late").length;

  setStat("stat-borrowed", `${borrowed.length} of ${RULES.borrowLimit} books borrowed`,
    borrowed.length >= RULES.borrowLimit ? "attention" : "");
  setStat("stat-due", late ? `${soon} due soon, ${late} overdue` : `${soon} due soon`,
    late ? "bad" : soon ? "attention" : "");

  if (me.Status) {
    const ok = me.Status !== "Suspended";
    setStat("stat-status", ok ? "Good standing" : "Suspended", ok ? "good" : "bad");
  } else {
    setStat("stat-status", "Not available yet");
  }
}

/* ---------- Borrowed tab ---------- */

function renewBlock(l, due) {
  const renewals = l.Renewals ?? 0;
  const daysLeft = workingDaysBetween(todayIso(), due, offDays);
  if (renewals >= RULES.maxRenewals) return "All 3 renewals used";
  if (due >= todayIso() && daysLeft >= RULES.loanDays) return "Already has 7 days left";
  return "";
}

function loanRow(l) {
  const title = `<a class="title" href="book.html?id=${encodeURIComponent(l.BookID)}">${esc(l.BookTitle)}</a>
    <div class="sub">${esc(l.BookAuthor || "")}</div>`;

  if (l.Status === "Pending") {
    return `<tr><td>${title}</td><td>Not yet</td><td>Set when approved</td>
      <td>${badge("Pending")}</td><td class="why">Waiting for a librarian</td></tr>`;
  }
  if (l.Status === "Returned") {
    return `<tr><td>${title}</td><td>${fmtDate(l.BorrowDate)}</td><td>None</td>
      <td>${badge("Returned")}</td><td></td></tr>`;
  }

  const due = dueOf(l);
  const state = dueState(due, offDays);
  const overdueDays = state === "late" ? workingDaysBetween(due, todayIso(), offDays) : 0;
  const fine = l.Fine ?? overdueDays * RULES.finePerDay;
  const pending = l.PendingRenew || l.PendingReturn;

  let status = state === "late" ? badge("Overdue") : state === "soon" ? badge("Due soon") : badge("Borrowed");
  if (state === "late") status += `<div class="money-bad">Fine ${peso(fine)}</div>`;
  if (l.PendingRenew) status += ` ${badge("Renewal pending")}`;
  if (l.PendingReturn) status += ` ${badge("Return pending")}`;

  const block = renewBlock(l, due);
  const read = isDigital(l) && l.DigitalLink
    ? `<a class="btn small" href="${esc(l.DigitalLink)}" target="_blank" rel="noopener">Read</a>` : "";

  return `
    <tr>
      <td>${title}<div class="sub">Renewed ${l.Renewals ?? 0} of ${RULES.maxRenewals}</div></td>
      <td>${fmtDate(l.BorrowDate)}</td>
      <td>${slip("Due", due, state)}</td>
      <td>${status}</td>
      <td>
        <div class="actions">
          ${read}
          <button type="button" class="btn small secondary" data-renew="${l.BorrowID}" ${pending || block ? "disabled" : ""}>Renew</button>
          <button type="button" class="btn small secondary" data-return="${l.BorrowID}" ${pending ? "disabled" : ""}>Return</button>
        </div>
        ${block && !pending ? `<div class="why">${block}</div>` : ""}
      </td>
    </tr>`;
}

function renderLoans() {
  const order = { Borrowed: 0, Pending: 1, Returned: 2 };
  const rows = loans.filter((l) => l.Status in order).sort((a, b) => order[a.Status] - order[b.Status]);
  $("loans").innerHTML = rows.length
    ? rows.map(loanRow).join("")
    : emptyRow(5, "You haven't borrowed anything yet. Browse Books to request one.");
}

/* ---------- Denied tab ---------- */

async function loadDenied() {
  try {
    const rows = await API.myDenied();
    $("denied-count").textContent = rows.length ? `(${rows.length})` : "";
    $("denied").innerHTML = rows.length
      ? rows.map((r) => `
          <tr>
            <td><div class="title">${esc(r.BookTitle)}</div><div class="sub">${esc(r.BookID)}</div></td>
            <td>${fmtDate(r.RequestedAt, true)}</td>
            <td>${(r.reasons || []).map((x) => badge(x, "red")).join(" ")}</td>
            <td><a class="btn small secondary" href="denied.html?id=${r.BorrowID}">See why</a></td>
          </tr>`).join("")
      : emptyRow(4, "No denied requests.");
  } catch (err) {
    $("denied").innerHTML = emptyRow(4, err.message);
  }
}

function showTab(which) {
  const denied = which === "denied";
  $("panel-books").hidden = denied;
  $("panel-denied").hidden = !denied;
  $("tab-books").classList.toggle("active", !denied);
  $("tab-denied").classList.toggle("active", denied);
  $("tab-books").setAttribute("aria-selected", String(!denied));
  $("tab-denied").setAttribute("aria-selected", String(denied));
}
$("tab-books").addEventListener("click", () => showTab("books"));
$("tab-denied").addEventListener("click", () => showTab("denied"));

/* ---------- Renew and Return popups ---------- */

$("loans").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-renew], button[data-return]");
  if (!btn) return;
  hideAlert("alert");
  const id = +(btn.dataset.renew || btn.dataset.return);
  const l = loans.find((x) => x.BorrowID === id);

  if (btn.dataset.renew) {
    const newDue = addWorkingDays(todayIso(), RULES.loanDays, offDays);
    const ok = await confirmDialog({
      title: "Renew this book?",
      body: `<p><strong>${esc(l.BookTitle)}</strong></p>
        <p>${slip("New due date if approved", newDue, "", true)}</p>
        <p class="muted">This uses renewal ${(l.Renewals ?? 0) + 1} of ${RULES.maxRenewals}.
        The request goes to a librarian, and the new date only applies once they approve it.</p>`,
      confirm: "Send renewal request",
    });
    if (!ok) return;
    try {
      await busy(btn, () => API.requestRenew(id), "Sending…");
      showAlert("alert", "Renewal request sent. A librarian must approve it before the due date changes.", "success");
    } catch (err) { return showAlert("alert", err.message); }
  } else {
    const ok = await confirmDialog({
      title: "Return this book?",
      body: `<p><strong>${esc(l.BookTitle)}</strong></p>
        <p class="muted">${isDigital(l)
          ? "You'll lose access to the e-book once the return is approved."
          : "Bring the book to the library desk."}
        A librarian must approve the return. Until then the book stays on your account.</p>`,
      confirm: "Send return request",
    });
    if (!ok) return;
    try {
      await busy(btn, () => API.requestReturn(id), "Sending…");
      showAlert("alert", "Return request sent. A librarian must approve it.", "success");
    } catch (err) { return showAlert("alert", err.message); }
  }
  await loadLoans();
});

async function loadLoans() {
  try {
    loans = await API.myLoans();
    renderLoans();
  } catch (err) {
    loans = [];
    $("loans").innerHTML = emptyRow(5, err.message);
  }
}

(async () => {
  const me = await startPage("student", "dashboard");
  if (me.id) $("hello").textContent = `Your library, ${me.id}`;
  offDays = await loadOffDays();
  await loadLoans();
  renderSummary(me);
  loadDenied();
  if (location.hash === "#denied") showTab("denied");
})();
