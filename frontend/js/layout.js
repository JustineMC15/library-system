/* layout.js: the shared page frame and the login guard.
   Students get a top bar, librarians get a left sidebar (design brief, principle 6).

   Usage in a page script:   const me = await startPage("student", "browse");
   The page's HTML needs <div id="shell" data-role="student"></div> before <main>. */

// The school's logo (in frontend/assets/) links to the school's website (design brief, principle 6).
const SCHOOL = { name: "OLOPS College Library", logo: "olops-logo.png", url: "https://www.olopsc.edu.ph/" };

// Links in the header of the login and register pages (real pages on the school site only)
const SCHOOL_LINKS = [
  { href: "https://www.olopsc.edu.ph/about", label: "About OLOPSC" },
  { href: "https://www.olopsc.edu.ph/admissions/", label: "Admissions" },
];

const NAV = {
  student: [
    { key: "dashboard", href: "dashboard.html", label: "Dashboard" },
    { key: "browse", href: "browse.html", label: "Browse Books" },
    { key: "borrowed", href: "borrowed.html", label: "My Borrowed Books" },
  ],
  librarian: [
    { key: "dashboard", href: "dashboard.html", label: "Dashboard" },
    { key: "verify", href: "verify.html", label: "Verify Student" },
    { key: "return", href: "return.html", label: "Process Return" },
    { key: "catalog", href: "catalog.html", label: "Book Catalog" },
    { key: "nonworking", href: "nonworking.html", label: "Non-working Days" },
  ],
};

function logoHtml(subtitle = "") {
  const mark = SCHOOL.logo
    ? `<img class="crest" src="../assets/${esc(SCHOOL.logo)}" alt="">`
    : `<span class="mark" aria-hidden="true">[LOGO]</span>`;
  const inner = `${mark}<span class="name"><span>${esc(SCHOOL.name)}</span>${subtitle ? `<small>${esc(subtitle)}</small>` : ""}</span>`;
  return SCHOOL.url
    ? `<a class="logo" href="${esc(SCHOOL.url)}" target="_blank" rel="noopener"
         title="Opens the OLOPS College website in a new tab">${inner}</a>`
    : `<span class="logo">${inner}</span>`;
}

// Header for the login and register pages: logo on the left, school-site links on the right.
// The page needs <div id="site-bar"></div> at the top of <body>.
function renderSiteBar() {
  const el = document.getElementById("site-bar");
  if (!el) return;
  const links = SCHOOL_LINKS.map((l) =>
    `<a href="${esc(l.href)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join("");
  el.outerHTML = `
    <header class="site-bar">
      ${logoHtml("Marikina City, Philippines")}
      <nav aria-label="OLOPS College website">${links}</nav>
    </header>`;
}

// The person's name for display. Falls back to their ID until /api/me sends names.
function displayName(me) {
  if (!me) return "";
  if (me.FirstName || me.LastName) return fullName(me);
  return me.LibrarianName || me.name || me.id || "";
}

// Draws the nav right away (before the login check finishes) so pages don't flash empty.
function renderShell(role, active) {
  const shell = document.getElementById("shell");
  if (!shell) return;
  const links = NAV[role].map((n) =>
    `<a href="${n.href}" ${n.key === active ? 'class="active" aria-current="page"' : ""}>${esc(n.label)}</a>`).join("");
  const user = `
    <span class="who-am-i"><strong id="me-name">&nbsp;</strong><small id="me-id"></small></span>
    <button type="button" id="logout" class="btn small ghost">Log out</button>`;

  if (role === "librarian") {
    shell.outerHTML = `
      <aside class="sidebar" id="sidebar">
        ${logoHtml("Marikina City, Philippines")}
        <button type="button" class="btn small ghost menu-toggle" id="menu-toggle"
                aria-expanded="false" aria-controls="drawer">Menu</button>
        <div class="drawer" id="drawer">
          <div>
            <p class="who-heading" id="me-heading">&nbsp;</p>
            <nav aria-label="Librarian">${links}</nav>
            <div class="user">
              <a href="register.html" ${active === "register" ? 'aria-current="page"' : ""}>Add a librarian account</a>
              ${user}
            </div>
          </div>
        </div>
      </aside>`;
    setupMenu();
  } else {
    shell.outerHTML = `
      <header class="topbar">
        ${logoHtml("Marikina City, Philippines")}
        <nav aria-label="Student">${links}</nav>
        <div class="user">${user}</div>
      </header>`;
  }

  document.getElementById("logout").addEventListener("click", async (e) => {
    e.target.setAttribute("aria-busy", "true");
    try { await API.logout(); } catch { /* go to login either way */ }
    location.href = `/${role}/login.html`;
  });
}

// Tablet and phone: the librarian menu opens and closes; Escape or a link click closes it
function setupMenu() {
  const bar = document.getElementById("sidebar");
  const btn = document.getElementById("menu-toggle");
  const set = (open) => {
    bar.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", String(open));
    btn.textContent = open ? "Close" : "Menu";
  };
  btn.addEventListener("click", () => set(!bar.classList.contains("open")));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && bar.classList.contains("open")) { set(false); btn.focus(); }
  });
  bar.querySelector("nav").addEventListener("click", () => set(false));
}

function showMe(me) {
  const name = displayName(me);
  document.getElementById("me-name").textContent = name || "Not logged in";
  const heading = document.getElementById("me-heading");
  if (heading) heading.textContent = name || "Librarian";
  // Show the ID underneath only when we have a real name to show above it
  document.getElementById("me-id").textContent = me.id && name !== me.id ? me.id : "";
}

// Checks the login and returns { id, role, Status?, FirstName?, LastName?, LibrarianName? }.
// Wrong role or not logged in -> sent to that role's login page.
async function startPage(role, active) {
  renderShell(role, active);
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
  showMe(me);
  return me;
}
