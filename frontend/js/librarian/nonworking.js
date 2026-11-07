// Non-working Days: Monday-first month calendar with a side panel (Figma: Librarian Non-working Days).
// Click a day to mark it (pick a reason, see the impact, Save). Click a marked day to remove it.
const REASONS = ["Holiday", "School suspension", "Other"];
const REASON_KIND = { Holiday: "amber", "School suspension": "red", Other: "slate" };
const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
let marked = new Map();   // "YYYY-MM-DD" -> { NonWorkingDate, Reason, LibrarianID }
let view = new Date();
view.setDate(1);
let picked = null;        // the date open in the side panel
let reason = REASONS[0];

async function load() {
  try {
    const days = await API.nonworking();
    marked = new Map(days.map((d) => [d.NonWorkingDate, d]));
  } catch (err) {
    showAlert("alert", err.message);
  }
  renderCalendar();
  renderList();
}

function renderCalendar() {
  const y = view.getFullYear();
  const m = view.getMonth();
  $("month").textContent = view.toLocaleDateString("en-PH", { month: "long", year: "numeric" });

  const cells = DOW.map((d) => `<div class="dow" aria-hidden="true">${d}</div>`);
  const lead = (new Date(y, m, 1).getDay() + 6) % 7;   // Monday = 0
  for (let i = 0; i < lead; i++) cells.push(`<div class="pad"></div>`);

  const days = new Date(y, m + 1, 0).getDate();
  const today = todayIso();
  for (let d = 1; d <= days; d++) {
    const date = new Date(y, m, d);
    const key = iso(date);
    const mark = marked.get(key);
    const sunday = date.getDay() === 0;
    const cls = [sunday && "sunday", mark && `marked ${REASON_KIND[mark.Reason] || ""}`, key === today && "today", key === picked && "picked"]
      .filter(Boolean).join(" ");
    const label = `${fmtDate(key)}${sunday ? ", Sunday, always skipped" : mark ? `, ${mark.Reason}` : ""}`;
    cells.push(`
      <button type="button" class="${cls}" data-date="${key}" ${sunday ? "disabled" : ""} aria-label="${esc(label)}"
              ${key === picked ? 'aria-pressed="true"' : ""}>
        <span class="num">${d}</span>
        ${mark ? `<span class="tag">${mark.Reason === "School suspension" ? "Suspension" : esc(mark.Reason)}</span>` : ""}
      </button>`);
  }
  $("cal").innerHTML = cells.join("");
}

function renderList() {
  const items = [...marked.values()].sort((a, b) => a.NonWorkingDate.localeCompare(b.NonWorkingDate));
  $("list").innerHTML = items.length
    ? items.map((d) => `
        <li>
          <span><strong>${fmtDate(d.NonWorkingDate)}</strong><br><span class="muted">${esc(d.Reason)}</span></span>
          <button type="button" class="btn small secondary" data-remove="${d.NonWorkingDate}">Remove</button>
        </li>`).join("")
    : `<li class="muted">No dates marked yet. Click a day on the calendar.</li>`;
}

/* ---------- Side panel ---------- */

async function openPanel(date) {
  picked = date;
  reason = REASONS[0];
  renderCalendar();
  hideAlert("alert");
  const mark = marked.get(date);
  const short = new Date(date + "T00:00").toLocaleDateString("en-PH", { month: "short", day: "numeric" });

  $("panel").innerHTML = mark
    ? `<h2 id="panel-title">${short}: ${esc(mark.Reason)}</h2>
       <p class="muted">Marked${mark.LibrarianID ? ` by ${esc(mark.LibrarianID)}` : ""}.</p>
       <div id="impact"></div>
       <div class="actions"><button type="button" class="btn secondary" data-a="cancel">Cancel</button>
         <button type="button" class="btn danger" data-a="remove">Remove</button></div>`
    : `<h2 id="panel-title">Mark ${short}</h2>
       <div class="segmented reason-pick" role="group" aria-label="Reason" style="margin-bottom:16px">
         ${REASONS.map((r) => `<button type="button" data-reason="${esc(r)}" aria-pressed="${r === reason}">${esc(r)}</button>`).join("")}
       </div>
       <div id="impact"></div>
       <div class="actions"><button type="button" class="btn secondary" data-a="cancel">Cancel</button>
         <button type="button" class="btn" data-a="save">Save</button></div>`;

  // "This will move the due dates of 4 borrowed books" (skipped quietly if the route is missing)
  try {
    const r = await API.nonworkingImpact(date);
    if (picked === date && $("impact")) {
      $("impact").innerHTML = `<p class="alert warning">${r.borrowed_affected
        ? `This will move the due dates of ${plural(r.borrowed_affected, "borrowed book")}.`
        : "No borrowed books are affected."}</p>`;
    }
  } catch { /* no impact message */ }
}

function closePanel() {
  picked = null;
  $("panel").innerHTML = `<h2 id="panel-title">Mark a date</h2><p class="muted">Pick a day on the calendar.</p>`;
  renderCalendar();
}

$("panel").addEventListener("click", async (e) => {
  const r = e.target.closest("button[data-reason]");
  if (r) {
    reason = r.dataset.reason;
    $("panel").querySelectorAll("button[data-reason]").forEach((b) => b.setAttribute("aria-pressed", String(b === r)));
    return;
  }
  const b = e.target.closest("button[data-a]");
  if (!b) return;
  if (b.dataset.a === "cancel") return closePanel();
  const date = picked;
  try {
    if (b.dataset.a === "save") {
      await busy(b, () => API.addNonworking(date, reason), "Saving…");
      showAlert("alert", `${fmtDate(date)} marked as ${reason}.`, "success");
    } else {
      await busy(b, () => API.removeNonworking(date), "Removing…");
      showAlert("alert", `${fmtDate(date)} is a working day again.`, "success");
    }
    closePanel();
    load();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

$("cal").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-date]");
  if (b && !b.disabled) openPanel(b.dataset.date);
});
$("list").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-remove]");
  if (!b) return;
  const d = new Date(b.dataset.remove + "T00:00");
  view = new Date(d.getFullYear(), d.getMonth(), 1);
  openPanel(b.dataset.remove);
});
$("prev").addEventListener("click", () => { view.setMonth(view.getMonth() - 1); renderCalendar(); });
$("next").addEventListener("click", () => { view.setMonth(view.getMonth() + 1); renderCalendar(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && picked) closePanel(); });

startPage("librarian", "nonworking").then(load);
