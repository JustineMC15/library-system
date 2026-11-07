// Browse: search and filter the catalog (GET /api/books). Clicking a book opens book.html.
const grid = document.getElementById("grid");
const count = document.getElementById("count");
let timer;

async function load() {
  hideAlert("alert");
  const filters = {
    search: document.getElementById("search").value.trim(),
    type: document.getElementById("type").value,
    year: document.getElementById("year").value,
    available: document.getElementById("available").checked ? "1" : "",
  };
  try {
    const books = await API.books(filters);
    count.textContent = `${books.length} book${books.length === 1 ? "" : "s"} found`;
    grid.innerHTML = books.length
      ? books.map(card).join("")
      : `<div class="empty card" style="grid-column: 1 / -1">No books match your search.</div>`;
  } catch (err) {
    count.textContent = "";
    grid.innerHTML = "";
    showAlert("alert", err.message);
  }
}

function card(b) {
  // "available" only exists once the backend adds it; treat a missing value as unknown
  const avail = b.available === undefined ? "" :
    b.available ? badge("Available", "success") : badge("Borrowed", "warning");
  return `
    <a class="book-card" href="book.html?id=${encodeURIComponent(b.BookID)}">
      <div class="title">${esc(b.BookTitle)}</div>
      <div class="meta">${esc(b.BookAuthor)}${b.PublishYear ? " · " + b.PublishYear : ""}</div>
      <div class="meta">${esc(b.BookID)}</div>
      <div class="foot">${badge(b.BookType, b.BookType === "Digital" ? "blue" : "")} ${avail}</div>
    </a>`;
}

// Search as you type, with a short pause so we don't send a request per key
document.getElementById("filters").addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(load, 250);
});
document.getElementById("filters").addEventListener("submit", (e) => { e.preventDefault(); load(); });

requireRole("student").then(load);
