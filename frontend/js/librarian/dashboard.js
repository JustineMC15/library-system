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

/* Transaction history: every decided borrow, renew and return, and which librarian handled it.
   The search, period, type and sort all run here in the page, on the rows from GET /librarian/history. */
let historyRows = [];
let period = "";
const CODE_PREFIX = { borrow: "BOR", renew: "REN", return: "RET" };
const historyCode = (h) => `${CODE_PREFIX[h.type] || "REQ"}-${h.request_id}`;
const librarianName = (h) => h.LibrarianName || h.LibrarianID || "None";

function inPeriod(dateTime) {
  if (!period) return true;
  const d = new Date(String(dateTime).replace(" ", "T"));
  const now = new Date();
  if (period === "day") return iso(d) === iso(now);
  if (period === "year") return d.getFullYear() === now.getFullYear();
  if (period === "month") return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  // "week": Monday through Sunday of the current week
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7));
  const nextMonday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 7);
  return d >= monday && d < nextMonday;
}

function applyHistory() {
  const words = $("h-search").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const type = $("h-type").value;
  const rows = historyRows
    .filter((h) => (!type || h.type === type) && inPeriod(h.RequestedAt))
    .filter((h) => {
      const text = [historyCode(h), h.StudentName, h.StudentID, h.BookTitle, h.BookID, h.LibrarianName, h.LibrarianID, h.Status, h.type]
        .join(" ").toLowerCase();
      return words.every((w) => text.includes(w));
    })
    .sort((a, b) => {
      const order = String(a.RequestedAt).localeCompare(String(b.RequestedAt));
      return $("h-sort").value === "oldest" ? order : -order;
    });

  $("h-count").textContent = `${plural(rows.length, "transaction")} shown`;
  $("rows").innerHTML = rows.length
    ? rows.map((h) => `
        <tr>
          <td>${esc(historyCode(h))}</td>
          <td>${badge(TYPE[h.type] || h.type, "slate")}</td>
          <td>${student(h)}</td>
          <td>${esc(h.BookTitle)}</td>
          <td>${fmtDate(h.RequestedAt, true)}</td>
          <td>${badge(h.Status)}</td>
          <td>${esc(librarianName(h))}</td>
        </tr>`).join("")
    : emptyRow(7, historyRows.length ? "No transactions match these filters." : "No past requests yet.");
}

async function renderHistory() {
  $("thead").innerHTML = "<tr><th>Code</th><th>Type</th><th>Student</th><th>Book</th><th>Date</th><th>Result</th><th>Handled by</th></tr>";
  $("rows").innerHTML = emptyRow(7, "Loading history…", true);
  try {
    historyRows = await API.history();
    applyHistory();
  } catch (err) {
    $("h-count").textContent = "";
    $("rows").innerHTML = emptyRow(7, err.message);
  }
}

function render() {
  $("history-tools").classList.toggle("hidden", tab !== "history");
  return tab === "history" ? renderHistory() : renderQueue();
}

$("h-search").addEventListener("input", applyHistory);
$("h-type").addEventListener("change", applyHistory);
$("h-sort").addEventListener("change", applyHistory);
$("h-period").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-period]");
  if (!btn) return;
  period = btn.dataset.period;
  $("h-period").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  applyHistory();
});

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
