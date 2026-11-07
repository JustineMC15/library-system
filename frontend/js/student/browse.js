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

// "3 digital books, available now, matching "python"": says exactly what's being shown
function summary(n, search, onlyAvailable) {
  const kind = type ? `${type.toLowerCase()} ` : "";
  let s = `${n} ${kind}book${n === 1 ? "" : "s"}`;
  if (onlyAvailable) s += ", available now";
  if (search) s += `, matching "${search}"`;
  return s;
}

async function load() {
  hideAlert("alert");
  const search = $("search").value.trim();
  const onlyAvailable = $("available").checked;
  $("clear").classList.toggle("hidden", !search && !type && !onlyAvailable);
  $("count").textContent = "Searching…";
  try {
    const books = await API.books({ search, type, available: onlyAvailable ? "1" : "" });
    $("count").textContent = summary(books.length, search, onlyAvailable);
    $("grid").innerHTML = books.length
      ? books.map(card).join("")
      : `<div class="card empty" style="grid-column: 1 / -1">
           <p><strong>No books match.</strong></p>
           <p>${search ? "Check the spelling, or search by author or call number instead. " : ""}${onlyAvailable ? "Turning off \"Available only\" shows books you can request after they're returned." : ""}</p>
           <button type="button" class="btn secondary" data-clear>Clear filters</button></div>`;
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

function clearFilters() {
  $("search").value = "";
  $("available").checked = false;
  $("type").querySelector('button[data-type=""]').click(); // also reloads
  $("search").focus();
}
$("clear").addEventListener("click", clearFilters);
$("grid").addEventListener("click", (e) => { if (e.target.closest("[data-clear]")) clearFilters(); });

// "/" jumps to the search box (unless you're already typing somewhere)
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
    e.preventDefault();
    $("search").focus();
  }
});

startPage("student", "browse").then(load);
