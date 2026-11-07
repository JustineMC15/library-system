// Book Details: book.html?id=<BookID>. One main button: Request to Borrow, with a confirm popup.
const bookId = params.get("id");
let offDays = new Set();

function mainAction(b, mine) {
  if (mine && mine.Status === "Borrowed") {
    const read = b.BookType === "Digital" && mine.DigitalLink
      ? `<a class="btn" href="${esc(mine.DigitalLink)}" target="_blank" rel="noopener">Read</a>` : "";
    return `${read}<span>You have this book. <a href="dashboard.html#borrowed">See it in My Borrowed Books</a></span>`;
  }
  if (mine) return `${badge("Pending")} <span>Your request is waiting for a librarian.</span>`;
  if (b.available === 0 || b.available === false) {
    return `<button class="btn" disabled>Request to Borrow</button>
      <span class="why">Another student has this copy.</span>`;
  }
  return `<button class="btn" id="borrow" type="button">Request to Borrow</button>`;
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
  document.title = `${b.BookTitle} · Library`;
  $("book").innerHTML = `
    <div class="detail">
      <div class="shelf-spine ${digital ? "digital" : ""}" aria-hidden="true">
        <span class="t">${esc(b.BookTitle)}</span>
        <span class="l">${esc(String(b.BookID).split(" ").slice(0, 2).join(" "))}</span>
      </div>
      <div>
        <h1>${esc(b.BookTitle)}</h1>
        <p class="big">${esc(b.BookAuthor)}</p>
        <dl class="facts">
          <dt>Book ID</dt><dd>${spineLabel(b)}</dd>
          <dt>ISBN</dt><dd>${esc(b.BookISBN || "None listed")}</dd>
          <dt>Published</dt><dd>${esc(b.PublishYear || "Unknown")}</dd>
          <dt>Type</dt><dd>${badge(b.BookType)}</dd>
          <dt>Copies</dt><dd>1 copy ${availabilityBadge(b)}</dd>
          ${digital ? "<dt>Reading</dt><dd>Opens as an outside e-book link once your request is approved.</dd>" : ""}
        </dl>
        <div class="actions">${mainAction(b, mine)}</div>
      </div>
    </div>`;

  const btn = $("borrow");
  if (btn) btn.addEventListener("click", () => borrow(b, btn));
}

async function borrow(b, btn) {
  hideAlert("alert");
  const due = addWorkingDays(todayIso(), RULES.loanDays, offDays);
  const ok = await confirmDialog({
    title: "Request to borrow?",
    body: `<p><strong>${esc(b.BookTitle)}</strong></p>
      <p>${slip("Due date if approved today", due, "", true)}</p>
      <p class="muted">A librarian checks your account first. The 7 working days start when they approve,
      so a later approval means a later due date.</p>`,
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
