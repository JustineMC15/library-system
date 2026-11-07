// Requests queue: borrow, renew and return requests in arrival order (borrowing.get_queue).
// Borrow requests open a review with the automatic checks (checks.run_checks) and the ID check.
const TYPE_LABEL = { borrow: "Borrow", renew: "Renew", return: "Return" };
const dialog = document.getElementById("review");
let currentType = "";
let queue = [];
let selected = null;

async function load() {
  const tbody = document.getElementById("queue");
  try {
    queue = await API.queue(currentType || undefined);
    tbody.innerHTML = queue.length
      ? queue.map((q, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${badge(TYPE_LABEL[q.type], "blue")}</td>
            <td><div class="title">${esc(q.StudentName || q.StudentID)}</div><div class="sub">${esc(q.StudentID)}</div></td>
            <td><div class="title">${esc(q.BookTitle || q.BookID)}</div><div class="sub">${esc(q.BookID)}</div></td>
            <td>${fmtDate(q.RequestedAt, true)}</td>
            <td><button class="btn small" data-index="${i}">Review</button></td>
          </tr>`).join("")
      : emptyRow(6, "No pending requests.");
  } catch (err) {
    tbody.innerHTML = emptyRow(6, err.message);
  }
}

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b === btn));
  currentType = btn.dataset.type;
  load();
});

document.getElementById("queue").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-index]");
  if (btn) openReview(queue[+btn.dataset.index]);
});

async function openReview(q) {
  selected = q;
  hideAlert("r-alert");
  document.getElementById("r-title").textContent = `${TYPE_LABEL[q.type]} request`;
  document.getElementById("r-sub").textContent =
    `${q.StudentName || q.StudentID} (${q.StudentID}) · ${q.BookTitle || q.BookID}` +
    (q.type === "renew" && q.DueDate ? ` · due ${fmtDate(q.DueDate)}` : "");

  const isBorrow = q.type === "borrow";
  document.getElementById("r-checks").classList.toggle("hidden", !isBorrow);
  dialog.showModal();
  if (!isBorrow) return;

  const idok = document.getElementById("r-idok");
  idok.checked = false;
  renderReasons([]);

  const list = document.getElementById("r-checklist");
  list.innerHTML = `<li class="muted">Running checks…</li>`;
  try {
    const checks = await API.checks(q.StudentID);
    const failed = Object.keys(checks).filter((k) => checks[k]);
    list.innerHTML = Object.entries(checks).map(([name, bad]) =>
      `<li><span>${esc(name)}</span>${bad ? badge("Problem", "error") : badge("OK", "success")}</li>`).join("");
    renderReasons(failed);
  } catch (err) {
    list.innerHTML = `<li class="muted">${esc(err.message)}</li>`;
  }
}

// Deny reason checkboxes; failed checks start ticked
function renderReasons(ticked) {
  document.getElementById("r-reasons").innerHTML = DENY_REASONS.map((r) => `
    <label class="checkbox"><input type="checkbox" value="${esc(r)}" ${ticked.includes(r) ? "checked" : ""}> ${esc(r)}</label>`).join("");
}

// Unticking "valid school ID" ticks the matching deny reason, and the other way round
document.getElementById("r-idok").addEventListener("change", (e) => {
  const box = document.querySelector('#r-reasons input[value="No valid Student ID"]');
  if (box) box.checked = !e.target.checked;
});

document.getElementById("r-cancel").addEventListener("click", () => dialog.close());

document.getElementById("r-approve").addEventListener("click", (e) => decide(e.target, "approve"));
document.getElementById("r-deny").addEventListener("click", (e) => decide(e.target, "deny"));

async function decide(button, action) {
  hideAlert("r-alert");
  const q = selected;
  let data = {};
  if (q.type === "borrow") {
    if (action === "approve") {
      if (!document.getElementById("r-idok").checked) {
        return showAlert("r-alert", "Confirm the student showed a valid school ID before approving.");
      }
      data = { student_id_ok: true };
    } else {
      const reasons = [...document.querySelectorAll("#r-reasons input:checked")].map((i) => i.value);
      if (!reasons.length) return showAlert("r-alert", "Tick at least one reason to deny.");
      data = { reasons };
    }
  }
  try {
    await busy(button, () => (action === "approve" ? API.approve : API.deny)(q.type, q.request_id, data));
    dialog.close();
    showAlert("alert", `${TYPE_LABEL[q.type]} request ${action === "approve" ? "approved" : "denied"}.`, "success");
    load();
  } catch (err) {
    showAlert("r-alert", err.message);
  }
}

requireRole("librarian").then(load);
