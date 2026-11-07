// Non-working days: holidays and suspensions (NonWorkingDay table).
const form = document.getElementById("form");

async function load() {
  const tbody = document.getElementById("days");
  try {
    const days = await API.nonworking();
    tbody.innerHTML = days.length
      ? days.map((d) => `
          <tr>
            <td>${fmtDate(d.NonWorkingDate)}</td>
            <td>${new Date(d.NonWorkingDate + "T00:00").toLocaleDateString("en-PH", { weekday: "long" })}</td>
            <td>${badge(d.Reason, d.Reason === "Holiday" ? "blue" : "warning")}</td>
            <td>${esc(d.LibrarianID)}</td>
            <td><button class="btn small outline" data-date="${esc(d.NonWorkingDate)}">Remove</button></td>
          </tr>`).join("")
      : emptyRow(5, "No non-working days added yet.");
  } catch (err) {
    tbody.innerHTML = emptyRow(5, err.message);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");
  const date = document.getElementById("date").value;
  const reason = document.getElementById("reason").value;
  if (!date) return showAlert("alert", "Pick a date.");
  if (new Date(date + "T00:00").getDay() === 0) {
    return showAlert("alert", "Sundays are already skipped. No need to add them.", "info");
  }
  try {
    await busy(form.querySelector("button"), () => API.addNonworking(date, reason));
    showAlert("alert", `${fmtDate(date)} marked as non-working.`, "success");
    form.reset();
    load();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

document.getElementById("days").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-date]");
  if (!btn) return;
  if (!confirm(`Remove ${fmtDate(btn.dataset.date)}? Due dates will count it as a working day again.`)) return;
  hideAlert("alert");
  try {
    await busy(btn, () => API.removeNonworking(btn.dataset.date));
    load();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

requireRole("librarian").then(load);
