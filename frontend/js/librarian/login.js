// Librarian login: sends ID + password, then opens the dashboard.
const form = document.getElementById("form");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");
  const id = document.getElementById("id").value.trim();
  const password = document.getElementById("password").value;
  if (!id || !password) return showAlert("alert", "Enter your Librarian ID and password.");

  const button = form.querySelector("button");
  try {
    await busy(button, () => API.login("librarian", id, password));
    location.href = "dashboard.html";
  } catch (err) {
    showAlert("alert", err.message);
  }
});
