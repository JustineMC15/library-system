// My Borrowed Books: borrowed.html (borrowed.html#denied opens the Denied tab).
// Each row: title with "Renewed x of 3", type, dates, status, and Read / Renew / Return.
let offDays = new Set();
let loans = [];

const isDigital = (l) => (l.BookType ? l.BookType === "Digital" : !!l.DigitalLink);
const shortDate = (d) => (d ? new Date(String(d).slice(0, 10) + "T00:00").toLocaleDateString("en-PH", { month: "short", day: "numeric" }) : "None");
const dueOf = (l) => l.DueDate || (l.BorrowDate ? addWorkingDays(l.BorrowDate, RULES.loanDays, offDays) : null);

function renewBlock(l, due) {
  if ((l.Renewals ?? 0) >= RULES.maxRenewals) return "All 3 renewals used";
  if (due >= todayIso() && workingDaysBetween(todayIso(), due, offDays) >= RULES.loanDays) return "Already has 7 days left";
  return "";
}

function row(l) {
  const type = badge(isDigital(l) ? "Digital" : "Physical");
  const title = `<a class="title" href="book.html?id=${encodeURIComponent(l.BookID)}">${esc(l.BookTitle)}</a>`;

  if (l.Status === "Pending") {
    return `<tr><td>${title}<div class="sub">Waiting for approval</div></td><td>${type}</td>
      <td>Not yet</td><td>Set when approved</td>
      <td>${badge("Pending")}${l.RequestedAt ? `<div class="sub">Sent ${waited(l.RequestedAt)} ago</div>` : ""}</td>
      <td><ol class="steps"><li class="done">Request sent</li><li class="now">Librarian checks your account</li>
        <li>${isDigital(l) ? "Read it online" : "Pick it up at the desk"}</li></ol></td></tr>`;
  }
  if (l.Status === "Returned") {
    return `<tr><td>${title}</td><td>${type}</td><td>${shortDate(l.BorrowDate)}</td><td>None</td>
      <td>${badge("Returned")}</td><td></td></tr>`;
  }

  const due = dueOf(l);
  const state = dueState(due, offDays);
  const fine = l.Fine ?? (state === "late" ? workingDaysBetween(due, todayIso(), offDays) * RULES.finePerDay : 0);
  const pending = l.PendingRenew || l.PendingReturn;
  const block = renewBlock(l, due);

  let status = l.PendingRenew ? badge("Renewal pending", "amber")
    : l.PendingReturn ? badge("Return pending", "amber")
    : state === "late" ? badge("Overdue")
    : state === "soon" ? badge("Due soon")
    : badge("Borrowed");
  if (state === "late") status += `<div class="money-bad">Fine: ${peso(fine)}</div>`;

  const read = isDigital(l) && l.DigitalLink
    ? `<a class="btn small" href="${esc(l.DigitalLink)}" target="_blank" rel="noopener">Read</a>` : "";

  return `
    <tr>
      <td>${title}<div class="sub">Renewed ${l.Renewals ?? 0} of ${RULES.maxRenewals}</div></td>
      <td>${type}</td>
      <td>${shortDate(l.BorrowDate)}</td>
      <td>${shortDate(due)}<div class="sub ${state === "late" ? "money-bad" : ""}">${dueText(due, offDays)}</div></td>
      <td>${status}</td>
      <td>
        <div class="actions">
          ${read}
          <button type="button" class="btn small secondary" data-renew="${l.BorrowID}" ${pending || block ? "disabled" : ""}>Renew</button>
          <button type="button" class="btn small" data-return="${l.BorrowID}" ${pending ? "disabled" : ""}>Return</button>
        </div>
        ${block && !pending ? `<div class="why">${block}</div>` : ""}
      </td>
    </tr>`;
}

function render() {
  const order = { Borrowed: 0, Pending: 1, Returned: 2 };
  const rows = loans.filter((l) => l.Status in order).sort((a, b) => order[a.Status] - order[b.Status]);
  const held = loans.filter((l) => l.Status === "Borrowed").length;
  $("summary").textContent = `${held} of ${RULES.borrowLimit} books borrowed.${held >= RULES.borrowLimit ? " Limit reached." : ""}`;
  $("loans").innerHTML = rows.length
    ? rows.map(row).join("")
    : emptyRow(6, "You haven't borrowed anything yet. Browse Books to request one.");
}

async function loadLoans() {
  try {
    loans = await API.myLoans();
    render();
  } catch (err) {
    loans = [];
    $("summary").textContent = "";
    $("loans").innerHTML = emptyRow(6, err.message);
  }
}

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

/* Renew and Return: confirm in a popup, then the row shows "pending" until a librarian decides */
$("loans").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-renew], button[data-return]");
  if (!btn) return;
  hideAlert("alert");
  const id = +(btn.dataset.renew || btn.dataset.return);
  const l = loans.find((x) => x.BorrowID === id);
  const renew = !!btn.dataset.renew;

  const ok = await confirmDialog(renew
    ? {
      title: "Renew this book?",
      body: `<p><strong>${esc(l.BookTitle)}</strong></p>
        <p>New due date if approved: <strong>${fmtDate(addWorkingDays(todayIso(), RULES.loanDays, offDays))}</strong></p>
        <p class="muted">This uses renewal ${(l.Renewals ?? 0) + 1} of ${RULES.maxRenewals}. A librarian must approve it first.</p>`,
      confirm: "Send renewal request",
    }
    : {
      title: "Return this book?",
      body: `<p><strong>${esc(l.BookTitle)}</strong></p>
        <p class="muted">${isDigital(l) ? "You'll lose access to the e-book once the return is approved." : "Bring the book to the library desk."}
        A librarian must approve the return. Until then the book stays on your account.</p>`,
      confirm: "Send return request",
    });
  if (!ok) return;

  try {
    await busy(btn, () => (renew ? API.requestRenew(id) : API.requestReturn(id)), "Sending…");
    showAlert("alert", renew
      ? "Renewal request sent. A librarian must approve it before the due date changes."
      : "Return request sent. A librarian must approve it.", "success");
    loadLoans();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

(async () => {
  await startPage("student", "borrowed");
  offDays = await loadOffDays();
  await loadLoans();
  loadDenied();
  if (location.hash === "#denied") showTab("denied");
})();
