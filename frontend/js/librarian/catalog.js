// Book Catalog: read-only list of every book with its status.
// Books are loaded once by the team from data/books.csv (python backend/seed.py).
let type = "";
let timer;

function row(b) {
  const link = b.DigitalLink
    ? `<div><a href="${esc(b.DigitalLink)}" target="_blank" rel="noopener">Open e-book link</a></div>` : "";
  return `
    <tr>
      <td>${spineLabel(b)}</td>
      <td><div class="title">${esc(b.BookTitle)}</div><div class="sub">${esc(b.BookAuthor)}</div>${link}</td>
      <td>${esc(b.BookISBN || "None")}</td>
      <td>${esc(b.PublishYear || "Unknown")}</td>
      <td>${badge(b.BookType)}</td>
      <td>${availabilityBadge(b) || "Unknown"}</td>
    </tr>`;
}

async function load() {
  $("count").textContent = "Searching…";
  try {
    const books = await API.books({
      search: $("search").value.trim(),
      type,
      available: $("available").checked ? "1" : "",
    });
    const out = books.filter((b) => b.available === 0 || b.available === false).length;
    $("count").textContent = `${plural(books.length, "book")}, ${out} out on loan`;
    $("books").innerHTML = books.length ? books.map(row).join("") : emptyRow(6, "No books match.");
  } catch (err) {
    $("count").textContent = "";
    $("books").innerHTML = emptyRow(6, err.message);
  }
}

$("type").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  type = btn.dataset.type;
  $("type").querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b === btn);
    b.setAttribute("aria-pressed", String(b === btn));
  });
  load();
});
$("search").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 250); });
$("available").addEventListener("change", load);
$("filters").addEventListener("submit", (e) => { e.preventDefault(); load(); });

startPage("librarian", "catalog").then(load);
