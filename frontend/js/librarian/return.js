// Returns & fines: approve or deny return requests, and mark fines as paid.
const today = new Date().toISOString().slice(0, 10);

async function loadReturns() {
  const tbody = document.getElementById("returns");
  try {
    const rows = await API.queue("return");
    tbody.innerHTML = rows.length
      ? rows.map((q) => {
          const late = q.DueDate && q.DueDate < today;
          return `
          <tr>
            <td><div class="title">${esc(q.StudentName || q.StudentID)}</div><div class="sub">${esc(q.StudentID)}</div></td>
            <td><div class="title">${esc(q.BookTitle || q.BookID)}</div><div class="sub">${esc(q.BookID)}</div></td>
            <td>${fmtDate(q.DueDate)} ${late ? badge("Late", "error") : ""}</td>
            <td>${fmtDate(q.RequestedAt, true)}</td>
            <td><div class="actions">
              <button class="btn small success" data-approve="${q.request_id}">Book received</button>
              <button class="btn small outline" data-deny="${q.request_id}">Deny</button>
            </div></td>
          </tr>`;
        }).join("")
      : emptyRow(5, "No books waiting to be returned.");
  } catch (err) {
    tbody.innerHTML = emptyRow(5, err.message);
  }
}

async function loadFines() {
  const tbody = document.getElementById("fines");
  const unpaidOnly = document.getElementById("unpaid-only").checked;
  try {
    let rows = await API.fines();
    if (unpaidOnly) rows = rows.filter((f) => !f.FinePaidDate);
    tbody.innerHTML = rows.length
      ? rows.map((f) => `
          <tr>
            <td><div class="title">${esc(f.StudentName || f.StudentID)}</div><div class="sub">${esc(f.StudentID)}</div></td>
            <td>${esc(f.BookTitle)}</td>
            <td>${fmtDate(f.ReturnDate)}</td>
            <td><strong>${peso(f.FineAmount)}</strong></td>
            <td>${f.FinePaidDate ? badge("Paid " + fmtDate(f.FinePaidDate), "success") : badge("Unpaid", "error")}</td>
            <td>${f.FinePaidDate ? "" : `<button class="btn small" data-paid="${f.ReturnID}">Mark paid</button>`}</td>
          </tr>`).join("")
      : emptyRow(6, unpaidOnly ? "No unpaid fines." : "No fines recorded.");
  } catch (err) {
    tbody.innerHTML = emptyRow(6, err.message);
  }
}

document.getElementById("returns").addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  hideAlert("alert");
  try {
    if (btn.dataset.approve) {
      await busy(btn, () => API.approve("return", +btn.dataset.approve));
      showAlert("alert", "Return approved. Any late fine now shows below.", "success");
    } else {
      if (!confirm("Deny this return request? The book stays on the student's account.")) return;
      await busy(btn, () => API.deny("return", +btn.dataset.deny));
      showAlert("alert", "Return request denied.", "success");
    }
    loadReturns();
    loadFines();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

document.getElementById("fines").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-paid]");
  if (!btn) return;
  hideAlert("alert");
  try {
    await busy(btn, () => API.markFinePaid(+btn.dataset.paid));
    showAlert("alert", "Fine marked as paid.", "success");
    loadFines();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

document.getElementById("unpaid-only").addEventListener("change", loadFines);

requireRole("librarian").then(() => Promise.all([loadReturns(), loadFines()]));
