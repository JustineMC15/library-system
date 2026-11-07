// Book details: book.html?id=<BookID>. Shows one book and a "Request to borrow" button.
const bookId = new URLSearchParams(location.search).get("id");
const box = document.getElementById("book");

async function load() {
  if (!bookId) {
    box.innerHTML = `<p class="empty">No book selected. <a href="browse.html">Browse books</a></p>`;
    return;
  }
  let b;
  try {
    b = await API.book(bookId);
  } catch (err) {
    box.innerHTML = `<p class="empty">${esc(err.message)}</p>`;
    return;
  }

  // Is this book already on the student's list? (pending or borrowed)
  let mine = null;
  try {
    mine = (await API.myLoans()).find((l) => l.BookID === b.BookID && ["Pending", "Borrowed"].includes(l.Status));
  } catch { /* loans endpoint missing: just skip this check */ }

  let action;
  if (mine && mine.Status === "Borrowed") {
    action = `${badge("You have this book", "blue")}
      ${mine.DigitalLink ? `<a class="btn" href="${esc(mine.DigitalLink)}" target="_blank" rel="noopener">Open e-book</a>` : ""}`;
  } else if (mine) {
    action = badge("Your request is waiting for approval", "warning");
  } else if (b.available === 0 || b.available === false) {
    action = `<button class="btn" disabled>Not available</button>
      <span class="muted">Someone else has this book or requested it first.</span>`;
  } else {
    action = `<button class="btn" id="borrow">Request to borrow</button>`;
  }

  document.title = b.BookTitle;
  box.innerHTML = `
    <div class="detail">
      <div class="cover">${esc(b.BookTitle)}</div>
      <div>
        <h1>${esc(b.BookTitle)}</h1>
        <p class="muted">${esc(b.BookAuthor)}</p>
        <dl class="facts">
          <dt>Call number</dt><dd>${esc(b.BookID)}</dd>
          <dt>ISBN</dt><dd>${esc(b.BookISBN || "—")}</dd>
          <dt>Published</dt><dd>${esc(b.PublishYear || "—")}</dd>
          <dt>Type</dt><dd>${badge(b.BookType, b.BookType === "Digital" ? "blue" : "")}</dd>
          ${b.BookType === "Digital" ? `<dt>Access</dt><dd class="muted">The e-book link appears once your request is approved.</dd>` : ""}
        </dl>
        <div class="actions" style="align-items:center">${action}</div>
      </div>
    </div>`;

  const btn = document.getElementById("borrow");
  if (btn) {
    btn.addEventListener("click", async () => {
      hideAlert("alert");
      try {
        await busy(btn, () => API.requestBorrow(b.BookID));
        showAlert("alert", "Request sent. You'll see it on My books while a librarian reviews it.", "success");
        load();
      } catch (err) {
        showAlert("alert", err.message);
      }
    });
  }
}

requireRole("student").then(load);
