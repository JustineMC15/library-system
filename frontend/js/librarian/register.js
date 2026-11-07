// Add Librarian: POST /api/librarian/register (librarian login required).
const form = $("form");
const val = (id) => $(id).value.trim();

addPasswordToggles();

const CHECKS = {
  LibrarianID: () => (val("LibrarianID") ? "" : "Enter an ID for the new librarian, like L-002."),
  LibrarianName: () => (val("LibrarianName") ? "" : "Enter their full name."),
  Password: () => ($("Password").value.length >= 6 ? "" : "Use at least 6 characters."),
  Confirm: () => ($("Confirm").value === $("Password").value ? "" : "This doesn't match the password above."),
};
for (const id of Object.keys(CHECKS)) {
  $(id).addEventListener("input", () => { if ($(id).classList.contains("invalid")) fieldError(id, CHECKS[id]()); });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");
  const bad = Object.keys(CHECKS).filter((id) => !fieldError(id, CHECKS[id]()));
  if (bad.length) return $(bad[0]).focus();

  const data = { librarian_id: val("LibrarianID"), librarian_name: val("LibrarianName"), password: $("Password").value };
  try {
    await busy(form.querySelector("button[type=submit]"), () => API.registerLibrarian(data), "Creating…");
    showAlert("alert", `${data.librarian_name} (${data.librarian_id}) can now log in on the librarian login page.`, "success");
    form.reset();
  } catch (err) {
    if (err.status === 409) {
      fieldError("LibrarianID", "That Librarian ID is taken. Pick another.");
      return $("LibrarianID").focus();
    }
    showAlert("alert", err.message);
  }
});

startPage("librarian", "register");
