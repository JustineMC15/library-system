// Add Librarian: POST /api/librarian/register (librarian login required).
const form = $("form");
const val = (id) => $(id).value.trim();

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");
  const required = ["LibrarianID", "LibrarianName", "Password"];
  const missing = required.filter((id) => !val(id));
  required.forEach((id) => $(id).classList.toggle("invalid", missing.includes(id)));
  if (missing.length) return showAlert("alert", "Fill in the highlighted fields.");
  if ($("Password").value !== $("Confirm").value) {
    $("Confirm").classList.add("invalid");
    return showAlert("alert", "The two passwords don't match.");
  }

  const data = { librarian_id: val("LibrarianID"), librarian_name: val("LibrarianName"), password: $("Password").value };
  try {
    await busy(form.querySelector("button"), () => API.registerLibrarian(data), "Creating…");
    showAlert("alert", `Librarian ${data.librarian_id} created. They can log in now.`, "success");
    form.reset();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

startPage("librarian", "register");
