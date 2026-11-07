// Add librarian: POST /api/librarian/register (librarian login required).
const form = document.getElementById("form");
const val = (id) => document.getElementById(id).value.trim();

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");
  const data = {
    librarian_id: val("librarian_id"),
    librarian_name: val("librarian_name"),
    password: document.getElementById("password").value,
  };
  if (!data.librarian_id || !data.librarian_name || !data.password) {
    return showAlert("alert", "Fill in every field.");
  }
  if (data.password !== document.getElementById("confirm").value) {
    return showAlert("alert", "The two passwords don't match.");
  }
  try {
    await busy(form.querySelector("button"), () => API.registerLibrarian(data));
    showAlert("alert", `Librarian ${data.librarian_id} created. They can log in now.`, "success");
    form.reset();
  } catch (err) {
    showAlert("alert", err.message);
  }
});

requireRole("librarian");
