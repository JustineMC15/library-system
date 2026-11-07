// Catalog: every book with its availability. Librarians also see the e-book link.
// Books come from data/books.csv (run seed.py after editing it).
const tbody = document.getElementById("books");
const count = document.getElementById("count");
let timer;

async function load() {
  const filters = {
    search: document.getElementById("search").value.trim(),
    type: document.getElementById("type").value,
    year: document.getElementById("year").value,
    available: document.getElementById("available").checked ? "1" : "",
  };
  try {
    const books = await API.books(filters);
    count.textContent = `${books.length} book${books.length === 1 ? "" : "s"}`;
    tbody.innerHTML = books.length
      ? books.map((b) => `
          <tr>
            <td>${esc(b.BookID)}</td>
            <td><div class="title">${esc(b.BookTitle)}</div><div class="sub">${esc(b.BookAuthor)}</div>
              ${b.DigitalLink ? `<a class="sub" href="${esc(b.DigitalLink)}" target="_blank" rel="noopener">Open e-book</a>` : ""}</td>
            <td>${esc(b.BookISBN || "—")}</td>
            <td>${esc(b.PublishYear || "—")}</td>
            <td>${badge(b.BookType, b.BookType === "Digital" ? "blue" : "")}</td>
            <td>${b.available === undefined ? "—" : b.available ? badge("Available", "success") : badge("Out", "warning")}</td>
          </tr>`).join("")
      : emptyRow(6, "No books match your search.");
  } catch (err) {
    count.textContent = "";
    tbody.innerHTML = emptyRow(6, err.message);
  }
}

document.getElementById("filters").addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(load, 250);
});
document.getElementById("filters").addEventListener("submit", (e) => { e.preventDefault(); load(); });

requireRole("librarian").then(load);
