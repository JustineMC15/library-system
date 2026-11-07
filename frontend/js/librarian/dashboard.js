// Librarian dashboard: next in line, today's counts, and the Request Queue (with History).
// Borrow -> Verify Student, Return -> Process Return, Renew -> decided here in a popup.
const TYPE = { borrow: "Borrow", renew: "Renew", return: "Return" };
// What Review leads to, so the librarian knows before clicking
const NEXT_STEP = {
  borrow: "Review opens Verify Student to run the five checks.",
  renew: "Review shows the current and new due dates to approve or deny.",
  return: "Review opens Process Return to record the date and any fine.",
};
let tab = "";
let fullQueue = [];   // every pending request, oldest first (positions come from this)
let offDays = new Set();

function setStat(id, value, tone = "") {
  $(id).className = `stat ${tone}`;
  $(id).querySelector(".value").textContent = value;
}

function student(q) {
  return `<div class="title">${esc(q.StudentName || q.StudentID)}</div><div class="sub">${esc(q.StudentID)}</div>`;
}

/* ---------- Next in line + counts ---------- */

function renderNext() {
  const q = fullQueue[0];
  if (!q) {
    $("next").innerHTML = `<p class="muted">No pending requests. The queue is clear.</p>`;
    return;
  }
  // Figma: badge, "Book, [Student], requested Oct 16, 9:02 AM", then Review and Open Request Queue
  $("next").innerHTML = `
    <p>${badge(TYPE[q.type], "slate")} ${esc(q.BookTitle || q.BookID)}, ${esc(q.StudentName || q.StudentID)},
      requested ${fmtDate(q.RequestedAt, true)} <span class="muted">(waiting ${waited(q.RequestedAt)})</span></p>
    <p class="muted">${NEXT_STEP[q.type]}</p>
    <div class="actions">
      <button type="button" class="btn" data-review="0">Review</button>
      <button type="button" class="btn secondary" id="open-queue">Open Request Queue</button>
    </div>`;
  $("open-queue").addEventListener("click", () => {
    $("queue-card").scrollIntoView({ block: "start" });
    $("queue-card").focus({ preventScroll: true });
  });
}

// Figma: Overdue Books table on the dashboard
async function loadOverdue() {
  try {
    const rows = await API.overdue();
    $("overdue").innerHTML = rows.length
      ? rows.map((o) => `
          <tr>
            <td>${student(o)}</td>
            <td>${esc(o.BookTitle)}</td>
            <td>${fmtDate(o.DueDate)}</td>
            <td>${o.DaysLate ?? workingDaysBetween(o.DueDate, todayIso(), offDays)}</td>
            <td class="money-bad">${peso(o.Fine ?? (o.DaysLate || 0) * RULES.finePerDay)}</td>
          </tr>`).join("")
      : emptyRow(5, "No overdue books.");
  } catch (err) {
    $("overdue").innerHTML = emptyRow(5, err.message);
  }
}

async function loadCounts() {
  setStat("s-pending", fullQueue.length, fullQueue.length ? "attention" : "");
  try {
    const s = await API.stats();
    setStat("s-btoday", s.borrows_today);
    setStat("s-rtoday", s.returns_today);
    setStat("s-overdue", s.overdue, s.overdue ? "bad" : "good");
  } catch {
    ["s-btoday", "s-rtoday", "s-overdue"].forEach((id) => setStat(id, "Not available"));
  }
}

/* ---------- Queue and History tables ---------- */

function renderQueue() {
  $("thead").innerHTML = "<tr><th>#</th><th>Request</th><th>Student</th><th>Book</th><th>Waiting</th><th></th></tr>";
  const rows = fullQueue.map((q, i) => ({ q, i })).filter(({ q }) => !tab || q.type === tab);
  $("rows").innerHTML = rows.length
    ? rows.map(({ q, i }) => `
        <tr class="${i === 0 ? "first" : ""}">
          <td><span class="pos" aria-label="Position ${i + 1}">${i + 1}</span></td>
          <td>${badge(TYPE[q.type], "navy")} ${i === 0 ? badge("Next in line", "amber") : ""}</td>
          <td>${student(q)}</td>
          <td><div class="title">${esc(q.BookTitle || q.BookID)}</div><div class="sub">${esc(q.BookID)}</div></td>
          <td><div class="title">${waited(q.RequestedAt)}</div><div class="sub">${fmtDate(q.RequestedAt, true)}</div></td>
          <td><button type="button" class="btn small ${i === 0 ? "" : "secondary"}" data-review="${i}">Review</button></td>
        </tr>`).join("")
    : emptyRow(6, tab ? `No pending ${TYPE[tab].toLowerCase()} requests.` : "No pending requests.");
}

async function renderHistory() {
  $("thead").innerHTML = "<tr><th>Request</th><th>Student</th><th>Book</th><th>Date</th><th>Result</th><th>Librarian</th></tr>";
  $("rows").innerHTML = emptyRow(6, "Loading history…", true);
  try {
    const rows = await API.history();
    $("rows").innerHTML = rows.length
      ? rows.map((h) => `
          <tr>
            <td>${badge(TYPE[h.type] || h.type, "slate")}</td>
            <td>${student(h)}</td>
            <td>${esc(h.BookTitle)}</td>
            <td>${fmtDate(h.RequestedAt, true)}</td>
            <td>${badge(h.Status)}</td>
            <td>${esc(h.LibrarianID || "None")}</td>
          </tr>`).join("")
      : emptyRow(6, "No past requests yet.");
  } catch (err) {
    $("rows").innerHTML = emptyRow(6, err.message);
  }
}

function render() {
  return tab === "history" ? renderHistory() : renderQueue();
}

$("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-tab]");
  if (!btn) return;
  tab = btn.dataset.tab;
  $("tabs").querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b === btn);
    b.setAttribute("aria-selected", String(b === btn));
  });
  render();
});

/* ---------- Review ---------- */

async function review(index) {
  const q = fullQueue[index];
  hideAlert("alert");
  if (index > 0) {
    const go = await confirmDialog({
      title: "Review out of order?",
      body: `<p>This request skips ${plural(index, "earlier request")}. Requests are normally handled first come, first served.</p>`,
      confirm: "Review anyway",
    });
    if (!go) return;
  }

  if (q.type === "borrow") {
    location.href = `verify.html?student=${encodeURIComponent(q.StudentID)}&request=${q.request_id}`;
  } else if (q.type === "return") {
    location.href = `return.html?student=${encodeURIComponent(q.StudentID)}&borrow=${q.BorrowID}`;
  } else {
    await reviewRenew(q);
  }
}

async function reviewRenew(q) {
  const newDue = addWorkingDays(todayIso(), RULES.loanDays, offDays);
  const dlg = document.createElement("dialog");
  dlg.setAttribute("aria-labelledby", "rn-title");
  dlg.innerHTML = `
    <h2 id="rn-title">Renewal request</h2>
    <p><strong>${esc(q.StudentName || q.StudentID)}</strong> wants to renew <strong>${esc(q.BookTitle || q.BookID)}</strong>.</p>
    <div class="actions" style="justify-content:flex-start;margin:0">
      ${q.DueDate ? slip("Due now", q.DueDate, dueState(q.DueDate, offDays)) : ""}
      ${slip("New due date", newDue)}
    </div>
    <div id="rn-alert" class="alert hidden" style="margin-top:16px"></div>
    <div class="actions">
      <button type="button" class="btn secondary" data-a="cancel">Cancel</button>
      <button type="button" class="btn danger" data-a="deny">Deny</button>
      <button type="button" class="btn success" data-a="approve">Approve renewal</button>
    </div>`;
  document.body.appendChild(dlg);
  dlg.addEventListener("close", () => dlg.remove());
  dlg.addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-a]");
    if (!b) return;
    if (b.dataset.a === "cancel") return dlg.close();
    try {
      await busy(b, () => (b.dataset.a === "approve" ? API.approve : API.deny)("renew", q.request_id));
      dlg.close();
      showAlert("alert", `Renewal ${b.dataset.a === "approve" ? "approved" : "denied"} for ${q.StudentName || q.StudentID}.`, "success");
      load();
    } catch (err) {
      showAlert(dlg.querySelector("#rn-alert"), err.message);
    }
  });
  dlg.showModal();
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-review]");
  if (btn) review(+btn.dataset.review);
});

async function load() {
  try {
    fullQueue = await API.queue();
    renderNext();
  } catch (err) {
    fullQueue = [];
    $("next").innerHTML = `<p class="muted">${esc(err.message)}</p>`;
  }
  loadCounts();
  loadOverdue();
  render();
}

(async () => {
  const me = await startPage("librarian", "dashboard");
  const date = new Date().toLocaleDateString("en-PH", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  $("today").textContent = `Today, ${date}`;
  offDays = await loadOffDays();
  load();
})();
