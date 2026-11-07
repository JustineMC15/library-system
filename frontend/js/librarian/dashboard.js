// Librarian dashboard: counts from the request queue, fines and the catalog.
const set = (id, text) => { document.getElementById(id).textContent = text; };
const TYPE_LABEL = { borrow: "Borrow", renew: "Renew", return: "Return" };

async function loadQueue() {
  const tbody = document.getElementById("next");
  try {
    const queue = await API.queue();
    for (const t of ["borrow", "renew", "return"]) set("s-" + t, queue.filter((q) => q.type === t).length);
    tbody.innerHTML = queue.length
      ? queue.slice(0, 5).map((q, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${badge(TYPE_LABEL[q.type], "blue")}</td>
            <td><div class="title">${esc(q.StudentName || q.StudentID)}</div><div class="sub">${esc(q.StudentID)}</div></td>
            <td>${esc(q.BookTitle || q.BookID)}</td>
            <td>${fmtDate(q.RequestedAt, true)}</td>
          </tr>`).join("")
      : emptyRow(5, "No pending requests. All caught up.");
  } catch (err) {
    for (const t of ["borrow", "renew", "return"]) set("s-" + t, "—");
    tbody.innerHTML = emptyRow(5, err.message);
  }
}

async function loadFines() {
  try {
    const unpaid = (await API.fines()).filter((f) => !f.FinePaidDate);
    set("s-fines", peso(unpaid.reduce((sum, f) => sum + f.FineAmount, 0)));
  } catch {
    set("s-fines", "—");
  }
}

async function loadBooks() {
  try {
    const books = await API.books();
    const out = books.filter((b) => b.available === 0 || b.available === false).length;
    set("s-books", `${out} / ${books.length}`);
  } catch {
    set("s-books", "—");
  }
}

requireRole("librarian").then(() => Promise.all([loadQueue(), loadFines(), loadBooks()]));
