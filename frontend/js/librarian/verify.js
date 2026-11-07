// Verify Student: verify.html?student=<StudentID>&request=<BorrowID>
// Five checks with Pass / Fail, Pass all, fines with Mark as paid, then Approve or Deny.
let st = null;          // the student from GET /api/librarian/students/<id>
let marks = {};         // reason -> "pass" | "fail" | undefined
let requestId = Number(params.get("request")) || null;
let offDays = new Set();

/* ---------- Load ---------- */

async function find(studentId) {
  hideAlert("alert");
  $("StudentID").value = studentId;
  $("empty").textContent = "Looking up the student…";
  $("empty").classList.remove("hidden");
  $("found").classList.add("hidden");
  try {
    st = await API.student(studentId);
  } catch (err) {
    st = null;
    $("empty").textContent = err.status === 404 ? `No student with ID ${studentId}.` : err.message;
    return;
  }

  // Checks the system knows: true from run_checks means the student fails it
  marks = {};
  for (const r of DENY_REASONS) {
    if (st.checks && r in st.checks) marks[r] = st.checks[r] ? "fail" : "pass";
  }
  const pending = st.pending || [];
  if (!pending.some((p) => p.BorrowID === requestId)) requestId = pending[0] ? pending[0].BorrowID : null;

  history.replaceState(null, "", `?student=${encodeURIComponent(st.StudentID)}${requestId ? "&request=" + requestId : ""}`);
  render();
}

/* ---------- Render ---------- */

function render() {
  $("empty").classList.add("hidden");
  $("found").classList.remove("hidden");

  $("who").textContent = fullName(st);
  $("standing").innerHTML = badge(st.Status === "Suspended" ? "Suspended" : "Good standing");
  const a = age(st.DateOfBirth);
  $("details").innerHTML = `
    <dt>Student ID</dt><dd>${esc(st.StudentID)}</dd>
    <dt>Date of birth</dt><dd>${fmtDate(st.DateOfBirth)}${a !== "" ? ` (${a} years old)` : ""}</dd>
    <dt>Contact</dt><dd>${(st.contacts || []).map(esc).join(", ") || "None"}</dd>
    <dt>Address</dt><dd>${esc(st.Address || "None")}</dd>
    <dt>Books held</dt><dd>${(st.loans || []).length} of ${RULES.borrowLimit}${heldList()}</dd>`;

  renderChecks();
  renderFine();
  renderRequests();
}

// The books the student has now, each with its due date, so "Unreturned books" can be judged at a glance
function heldList() {
  const loans = st.loans || [];
  if (!loans.length) return "";
  return `<ul class="side-list" style="margin-top:8px">${loans.map((l) => {
    const state = dueState(l.DueDate, offDays);
    return `<li><span>${esc(l.BookTitle)}<br><span class="muted">${dueText(l.DueDate, offDays)}</span></span>
      ${slip("Due", l.DueDate, state)}</li>`;
  }).join("")}</ul>`;
}

function renderChecks() {
  $("checks").innerHTML = DENY_REASONS.map((r) => {
    const m = marks[r];
    const extra = r === "Unpaid fines" && st.FineOwed ? ` <span class="money-bad">${peso(st.FineOwed)}</span>` : "";
    return `
      <li>
        <span>${esc(r)}${extra}</span>
        <span class="passfail" role="group" aria-label="${esc(r)}">
          <button type="button" class="pass ${m === "pass" ? "on" : ""}" data-r="${esc(r)}" data-m="pass" aria-pressed="${m === "pass"}">Pass</button>
          <button type="button" class="fail ${m === "fail" ? "on" : ""}" data-r="${esc(r)}" data-m="fail" aria-pressed="${m === "fail"}">Fail</button>
        </span>
      </li>`;
  }).join("");
  const passed = DENY_REASONS.filter((r) => marks[r] === "pass").length;
  const failed = DENY_REASONS.filter((r) => marks[r] === "fail").length;
  $("checks-title").textContent = `Five checks: ${passed} passed${failed ? `, ${failed} failed` : ""}`;
  updateDecision();
}

function renderFine() {
  const owed = st.FineOwed || 0;
  $("fine").innerHTML = owed ? `<span class="money-bad">${peso(owed)} unpaid</span>` : "No unpaid fines.";
  $("pay").disabled = !owed;
}

function renderRequests() {
  const pending = st.pending || [];
  $("requests").innerHTML = pending.length
    ? pending.map((p) => `
        <label class="checkbox" style="margin-bottom:8px">
          <input type="radio" name="req" value="${p.BorrowID}" ${p.BorrowID === requestId ? "checked" : ""}>
          <span><strong>${esc(p.BookTitle)}</strong><br><span class="muted">Requested ${fmtDate(p.RequestedAt, true)}</span></span>
        </label>`).join("")
    : `<p class="muted">This student has no pending borrow request.</p>`;
  updateDecision();
}

function updateDecision() {
  const allPass = DENY_REASONS.every((r) => marks[r] === "pass");
  const undecided = DENY_REASONS.filter((r) => !marks[r]);
  $("approve").disabled = !requestId || !allPass;
  $("deny").disabled = !requestId;
  $("approve-why").textContent = !requestId ? ""
    : undecided.length ? `Still to check: ${undecided.join(", ")}.`
    : !allPass ? "A check failed, so this request can only be denied." : "";
}

/* ---------- Actions ---------- */

$("checks").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-r]");
  if (!b) return;
  marks[b.dataset.r] = b.dataset.m;
  renderChecks();
});

$("pass-all").addEventListener("click", () => {
  DENY_REASONS.forEach((r) => { marks[r] = "pass"; });
  renderChecks();
});

$("requests").addEventListener("change", (e) => {
  requestId = Number(e.target.value);
  updateDecision();
});

$("pay").addEventListener("click", async () => {
  const ok = await confirmDialog({
    title: "Mark fines as paid?",
    body: `<p>${esc(fullName(st))} pays <strong>${peso(st.FineOwed)}</strong> at the desk.</p>`,
    confirm: "Mark as paid",
  });
  if (!ok) return;
  try {
    await busy($("pay"), () => API.payFines(st.StudentID));
    showAlert("alert", `${peso(st.FineOwed)} marked as paid.`, "success");
    st.FineOwed = 0;
    marks["Unpaid fines"] = "pass";
    renderFine();
    renderChecks();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

$("approve").addEventListener("click", async () => {
  try {
    await busy($("approve"), () => API.approve("borrow", requestId, { student_id_ok: true }), "Approving…");
    showAlert("alert", "Borrow approved. The 7 working days start today.", "success");
    find(st.StudentID);
  } catch (err) {
    showAlert("alert", err.message);
  }
});

$("deny").addEventListener("click", () => {
  const failed = DENY_REASONS.filter((r) => marks[r] === "fail");
  const dlg = document.createElement("dialog");
  dlg.setAttribute("aria-labelledby", "dn-title");
  dlg.innerHTML = `
    <h2 id="dn-title">Why is this request denied?</h2>
    <p class="muted">The student sees every reason you tick.</p>
    ${DENY_REASONS.map((r) => `
      <label class="checkbox" style="margin-bottom:8px">
        <input type="checkbox" value="${esc(r)}" ${failed.includes(r) ? "checked" : ""}> ${esc(r)}
      </label>`).join("")}
    <div id="dn-alert" class="alert hidden"></div>
    <div class="actions">
      <button type="button" class="btn secondary" data-a="cancel">Cancel</button>
      <button type="button" class="btn danger" data-a="deny">Deny request</button>
    </div>`;
  document.body.appendChild(dlg);
  dlg.addEventListener("close", () => dlg.remove());
  dlg.addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-a]");
    if (!b) return;
    if (b.dataset.a === "cancel") return dlg.close();
    const reasons = [...dlg.querySelectorAll("input:checked")].map((i) => i.value);
    if (!reasons.length) return showAlert(dlg.querySelector("#dn-alert"), "Tick at least one reason.");
    try {
      await busy(b, () => API.deny("borrow", requestId, { reasons }), "Denying…");
      dlg.close();
      showAlert("alert", "Request denied. The student can see the reasons.", "success");
      find(st.StudentID);
    } catch (err) {
      showAlert(dlg.querySelector("#dn-alert"), err.message);
    }
  });
  dlg.showModal();
});

$("search").addEventListener("submit", (e) => {
  e.preventDefault();
  const id = $("StudentID").value.trim();
  if (!id) return showAlert("alert", "Type a Student ID to search.");
  requestId = null;
  find(id);
});

(async () => {
  await startPage("librarian", "verify");
  offDays = await loadOffDays();
  if (params.get("student")) find(params.get("student"));
  else $("StudentID").focus();
})();
