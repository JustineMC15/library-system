// Denied requests: GET /api/student/denied, with every DenyReason row per request.
async function load() {
  const tbody = document.getElementById("list");
  try {
    const rows = await API.myDenied();
    tbody.innerHTML = rows.length
      ? rows.map((r) => `
          <tr>
            <td><div class="title">${esc(r.BookTitle)}</div><div class="sub">${esc(r.BookID)}</div></td>
            <td>${fmtDate(r.RequestedAt, true)}</td>
            <td><ul class="reasons">${(r.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></td>
            <td><a class="btn small outline" href="book.html?id=${encodeURIComponent(r.BookID)}">View book</a></td>
          </tr>`).join("")
      : emptyRow(4, "None of your requests have been denied.");
  } catch (err) {
    tbody.innerHTML = emptyRow(4, err.message);
  }
}

requireRole("student").then(load);
