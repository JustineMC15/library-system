// Non-Working Days: a month calendar. Click a date to mark it, click a marked date to remove it.
const REASONS = ["Holiday", "School suspension", "Other"];
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
let marked = new Map();   // "YYYY-MM-DD" -> { Reason, LibrarianID }
let view = new Date();
view.setDate(1);

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
  const first = new Date(y, m, 1).getDay();
  for (let i = 0; i < first; i++) cells.push(`<div class="pad"></div>`);

  const days = new Date(y, m + 1, 0).getDate();
  const today = todayIso();
  for (let d = 1; d <= days; d++) {
    const date = new Date(y, m, d);
    const key = iso(date);
    const mark = marked.get(key);
    const sunday = date.getDay() === 0;
    const cls = [sunday && "sunday", mark && "marked", key === today && "today"].filter(Boolean).join(" ");
    const label = `${fmtDate(key)}${sunday ? ", Sunday, always skipped" : mark ? `, ${mark.Reason}` : ""}`;
    cells.push(`
      <button type="button" class="${cls}" data-date="${key}" ${sunday ? "disabled" : ""} aria-label="${esc(label)}">
        <span class="num">${d}</span>
        ${mark ? badge(mark.Reason, mark.Reason === "Holiday" ? "blue" : "amber") : ""}
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
          <button type="button" class="btn small secondary" data-date="${d.NonWorkingDate}">Remove</button>
        </li>`).join("")
    : `<li class="muted">No dates marked yet. Click a day on the calendar.</li>`;
}

// Popup for one date: Save (with impact message) or Remove
async function openDate(date) {
  hideAlert("alert");
  const mark = marked.get(date);
  let impact = "";
  try {
    const r = await API.nonworkingImpact(date);
    impact = r.borrowed_affected
      ? `This will move the due dates of ${plural(r.borrowed_affected, "borrowed book")}.`
      : "No borrowed books are affected.";
  } catch { /* impact route missing: just skip the message */ }

  const dlg = document.createElement("dialog");
  dlg.setAttribute("aria-labelledby", "nw-title");
  dlg.innerHTML = mark
    ? `<h2 id="nw-title">${fmtDate(date)}</h2>
       <p>Marked as <strong>${esc(mark.Reason)}</strong>${mark.LibrarianID ? ` by ${esc(mark.LibrarianID)}` : ""}.</p>
       ${impact ? `<p class="alert warning">${esc(impact)}</p>` : ""}
       <div id="nw-alert" class="alert hidden"></div>
       <div class="actions">
         <button type="button" class="btn secondary" data-a="cancel">Cancel</button>
         <button type="button" class="btn danger" data-a="remove">Remove this date</button>
       </div>`
    : `<h2 id="nw-title">Mark ${fmtDate(date)}</h2>
       <div class="field">
         <label for="nw-reason">Reason</label>
         <select id="nw-reason">${REASONS.map((r) => `<option>${r}</option>`).join("")}</select>
       </div>
       ${impact ? `<p class="alert warning">${esc(impact)}</p>` : ""}
       <div id="nw-alert" class="alert hidden"></div>
       <div class="actions">
         <button type="button" class="btn secondary" data-a="cancel">Cancel</button>
         <button type="button" class="btn" data-a="save">Save</button>
       </div>`;
  document.body.appendChild(dlg);
  dlg.addEventListener("close", () => dlg.remove());
  dlg.addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-a]");
    if (!b) return;
    if (b.dataset.a === "cancel") return dlg.close();
    try {
      if (b.dataset.a === "save") {
        const reason = dlg.querySelector("#nw-reason").value;
        await busy(b, () => API.addNonworking(date, reason), "Saving…");
        showAlert("alert", `${fmtDate(date)} marked as ${reason}.`, "success");
      } else {
        await busy(b, () => API.removeNonworking(date), "Removing…");
        showAlert("alert", `${fmtDate(date)} is a working day again.`, "success");
      }
      dlg.close();
      load();
    } catch (err) {
      showAlert(dlg.querySelector("#nw-alert"), err.message);
    }
  });
  dlg.showModal();
}

$("cal").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-date]");
  if (b && !b.disabled) openDate(b.dataset.date);
});
$("list").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-date]");
  if (b) openDate(b.dataset.date);
});
$("prev").addEventListener("click", () => { view.setMonth(view.getMonth() - 1); renderCalendar(); });
$("next").addEventListener("click", () => { view.setMonth(view.getMonth() + 1); renderCalendar(); });

startPage("librarian", "nonworking").then(load);
