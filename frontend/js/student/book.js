// Book Details: book.html?id=<BookID>. One main button: Request to Borrow, with a confirm popup.
const bookId = params.get("id");
let offDays = new Set();

function mainAction(b, mine) {
  if (mine && mine.Status === "Borrowed") {
    const read = b.BookType === "Digital" && mine.DigitalLink
      ? `<a class="btn" href="${esc(mine.DigitalLink)}" target="_blank" rel="noopener">Read</a>` : "";
    return `${read}<span>You have this book. <a href="borrowed.html">See it in My Borrowed Books</a></span>`;
  }
  if (mine) {
    return `<div><p>${badge("Pending")} Your request is in.${mine.RequestedAt ? ` Sent ${waited(mine.RequestedAt)} ago.` : ""}</p>
      <ol class="steps"><li class="done">Request sent</li><li class="now">Librarian checks your account</li>
      <li>${b.BookType === "Digital" ? "The Read button appears in My Borrowed Books" : "Pick it up at the desk with your school ID"}</li></ol></div>`;
  }
  if (b.available === 0 || b.available === false) {
    return `<button class="btn" disabled>Request To Borrow</button>
      <span class="why">Another student has this copy.</span>`;
  }
  return `<button class="btn" id="borrow" type="button">Request To Borrow</button>`;
}

async function load() {
  if (!bookId) {
    $("book").innerHTML = `<p class="empty">No book picked. <a href="browse.html">Browse Books</a></p>`;
    return;
  }
  let b;
  try {
    b = await API.book(bookId);
  } catch (err) {
    $("book").innerHTML = `<p class="empty">${esc(err.message)} <a href="browse.html">Back to Browse Books</a></p>`;
    return;
  }

  let mine = null;
  try {
    mine = (await API.myLoans()).find((l) => l.BookID === b.BookID && ["Pending", "Borrowed"].includes(l.Status));
  } catch { /* loans route missing: skip the "you have this" check */ }

  const digital = b.BookType === "Digital";
  document.title = `${b.BookTitle} · OLOPS College Library`;
  $("crumb").textContent = b.BookTitle;
  $("book").innerHTML = `
    <div class="detail">
      <div class="card" style="padding:16px">${coverHtml(b, "L")}</div>
      <section class="card">
        <h1>${esc(b.BookTitle)}</h1>
        <p class="muted">${esc(b.BookAuthor)}</p>
        <div class="actions">${badge(b.BookType)} ${availabilityBadge(b)} <span class="muted">1 copy</span></div>
        <table class="details-table">
          <tr><th scope="row">Book ID</th><td>${esc(b.BookID)}</td></tr>
          <tr><th scope="row">ISBN</th><td>${esc(b.BookISBN || "None listed")}</td></tr>
          <tr><th scope="row">Year of Publication</th><td>${esc(b.PublishYear || "Unknown")}</td></tr>
          <tr><th scope="row">Type</th><td>${esc(b.BookType)}${digital ? " (opens as an outside e-book link once approved)" : ""}</td></tr>
        </table>
        <div class="actions">${mainAction(b, mine)}</div>
        <p class="muted" style="margin-top:16px">A librarian will verify and approve your request.</p>
      </section>
    </div>`;

  const btn = $("borrow");
  if (btn) btn.addEventListener("click", () => borrow(b, btn));
}

async function borrow(b, btn) {
  hideAlert("alert");
  const due = addWorkingDays(todayIso(), RULES.loanDays, offDays);
  // Figma: Borrow Popup Confirmation
  const ok = await confirmDialog({
    title: "Confirm borrow request",
    body: `<p>${esc(b.BookTitle)}</p>
      <p class="muted">Loan period: 7 working days after approval. Sundays, holidays and school closures are not counted.</p>
      <p>Due date if approved today: <strong>${fmtDate(due)}</strong></p>`,
    confirm: "Send request",
  });
  if (!ok) return;
  try {
    await busy(btn, () => API.requestBorrow(b.BookID), "Sending…");
    showAlert("alert", "Request sent. It's in My Borrowed Books while a librarian reviews it.", "success");
    load();
  } catch (err) {
    showAlert("alert", err.message);
  }
}

(async () => {
  await startPage("student", "browse");
  offDays = await loadOffDays();
  load();
})();
