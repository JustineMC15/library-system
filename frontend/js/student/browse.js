// Browse Books: search, All / Physical / Digital, Available Only, and a grid of book cards with covers.
let type = "";
let onlyAvailable = false;
let timer;

function card(b) {
  return `
    <a class="book-card" href="book.html?id=${encodeURIComponent(b.BookID)}">
      ${coverHtml(b)}
      <div class="title">${esc(b.BookTitle)}</div>
      <div class="meta">${esc(b.BookAuthor)}</div>
      <div class="foot">${badge(b.BookType)} ${availabilityBadge(b)}</div>
    </a>`;
}

// "Showing results for 60 books: 30 physical, 30 digital" (plus what's filtered)
function summary(books, search) {
  const physical = books.filter((b) => b.BookType === "Physical").length;
  let s = `Showing results for ${plural(books.length, "book")}: ${physical} physical, ${books.length - physical} digital`;
  if (onlyAvailable) s += ", available now";
  if (search) s += `, matching "${search}"`;
  return s;
}

async function load() {
  hideAlert("alert");
  const search = $("search").value.trim();
  $("clear").classList.toggle("hidden", !search && !type && !onlyAvailable);
  $("count").textContent = "Searching…";
  try {
    const books = await API.books({ search, type, available: onlyAvailable ? "1" : "" });
    $("count").textContent = summary(books, search);
    $("grid").innerHTML = books.length
      ? books.map(card).join("")
      : `<div class="card empty" style="grid-column: 1 / -1">
           <p><strong>No books match.</strong></p>
           <p>${search ? "Check the spelling, or search by author or call number instead. " : ""}${onlyAvailable ? "Turning off Available Only shows books you can request after they're returned." : ""}</p>
           <button type="button" class="btn secondary" data-clear>Clear filters</button></div>`;
  } catch (err) {
    $("count").textContent = "";
    $("grid").innerHTML = "";
    showAlert("alert", err.message);
  }
}

function setType(next) {
  type = next;
  $("type").querySelectorAll("button[data-type]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.type === type)));
}

$("type").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  if (btn.id === "available") {
    onlyAvailable = !onlyAvailable;
    btn.setAttribute("aria-pressed", String(onlyAvailable));
  } else if (btn.id === "clear") {
    return clearFilters();
  } else {
    setType(btn.dataset.type);
  }
  load();
});

function clearFilters() {
  $("search").value = "";
  onlyAvailable = false;
  $("available").setAttribute("aria-pressed", "false");
  setType("");
  load();
  $("search").focus();
}
$("grid").addEventListener("click", (e) => { if (e.target.closest("[data-clear]")) clearFilters(); });

$("search").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 250); });
$("filters").addEventListener("submit", (e) => { e.preventDefault(); load(); });

// "/" jumps to the search box (unless you're already typing somewhere)
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
    e.preventDefault();
    $("search").focus();
  }
});

startPage("student", "browse").then(load);
