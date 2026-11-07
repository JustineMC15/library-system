/* layout.js: the shared page frame and the login guard.
   Students get a top bar, librarians get a left sidebar (design brief, principle 6).

   Usage in a page script:   const me = await startPage("student", "browse");
   The page's HTML needs <div id="shell" data-role="student"></div> before <main>. */

// The school's logo (in frontend/assets/) links to the school's website (design brief, principle 6).
const SCHOOL = { name: "OLOPS College Library", logo: "olops-logo.png", url: "https://www.olopsc.edu.ph/" };

const NAV = {
  student: [
    { key: "dashboard", href: "dashboard.html", label: "Dashboard" },
    { key: "browse", href: "browse.html", label: "Browse Books" },
  ],
  librarian: [
    { key: "dashboard", href: "dashboard.html", label: "Dashboard" },
    { key: "verify", href: "verify.html", label: "Verify Student" },
    { key: "return", href: "return.html", label: "Process Return" },
    { key: "catalog", href: "catalog.html", label: "Book Catalog" },
    { key: "nonworking", href: "nonworking.html", label: "Non-Working Days" },
    { key: "register", href: "register.html", label: "Add Librarian" },
  ],
};

function logoHtml() {
  const mark = SCHOOL.logo
    ? `<img class="crest" src="../assets/${esc(SCHOOL.logo)}" alt="">`
    : `<span class="mark" aria-hidden="true">[LOGO]</span>`;
  const inner = `${mark}<span>${esc(SCHOOL.name)}</span>`;
  return SCHOOL.url
    ? `<a class="logo" href="${esc(SCHOOL.url)}" target="_blank" rel="noopener"
         title="Opens the OLOPS College website in a new tab">${inner}</a>`
    : `<span class="logo">${inner}</span>`;
}

function renderShell(role, active, me) {
  const shell = document.getElementById("shell");
  if (!shell) return;
  const links = NAV[role].map((n) =>
    `<a href="${n.href}" ${n.key === active ? 'class="active" aria-current="page"' : ""}>${esc(n.label)}</a>`).join("");
  const user = `<span>${esc(me.id || "Not logged in")}</span>
    <button type="button" id="logout" class="btn small ghost">Log out</button>`;

  if (role === "librarian") {
    shell.outerHTML = `
      <aside class="sidebar">
        ${logoHtml()}
        <nav aria-label="Librarian">${links}</nav>
        <div class="user">${user}</div>
      </aside>`;
  } else {
    shell.outerHTML = `
      <header class="topbar">
        ${logoHtml()}
        <nav aria-label="Student">${links}</nav>
        <div class="user">${user}</div>
      </header>`;
  }

  document.getElementById("logout").addEventListener("click", async () => {
    try { await API.logout(); } catch { /* go to login either way */ }
    location.href = `/${role}/login.html`;
  });
}

// Checks the login, draws the frame, and returns { id, role, Status? }.
// Wrong role or not logged in -> sent to that role's login page.
async function startPage(role, active) {
  let me;
  try {
    me = await API.me();
    if (me.role !== role) throw new Error("wrong role");
  } catch (err) {
    if (err instanceof ApiError && err.notConnected) {
      me = { id: null, role }; // backend has no /api/me yet: let the page render for previewing
    } else {
      location.href = `/${role}/login.html`;
      throw err;
    }
  }
  renderShell(role, active, me);
  return me;
}
