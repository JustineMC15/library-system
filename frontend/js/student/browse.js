// Browse Books: search, type filter and "available only" over GET /api/books.
let type = "";
let timer;

function card(b) {
  return `
    <a class="book-card" href="book.html?id=${encodeURIComponent(b.BookID)}">
      <div>${spineLabel(b)}</div>
      <div class="title">${esc(b.BookTitle)}</div>
      <div class="meta">${esc(b.BookAuthor)}${b.PublishYear ? ", " + b.PublishYear : ""}</div>
      <div class="foot">${badge(b.BookType)} ${availabilityBadge(b)}</div>
    </a>`;
}

async function load() {
  hideAlert("alert");
  $("count").textContent = "Searching…";
  try {
    const books = await API.books({
      search: $("search").value.trim(),
      type,
      available: $("available").checked ? "1" : "",
    });
    $("count").textContent = plural(books.length, "book") + (books.length ? "" : " match");
    $("grid").innerHTML = books.length
      ? books.map(card).join("")
      : `<div class="card empty" style="grid-column: 1 / -1">
           No books match. Try fewer words, or turn off "Available only".</div>`;
  } catch (err) {
    $("count").textContent = "";
    $("grid").innerHTML = "";
    showAlert("alert", err.message);
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

// Search while typing, after a short pause
$("search").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 250); });
$("available").addEventListener("change", load);
$("filters").addEventListener("submit", (e) => { e.preventDefault(); load(); });

startPage("student", "browse").then(load);
