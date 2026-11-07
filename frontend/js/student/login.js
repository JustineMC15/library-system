// Student login: sends ID + password, then opens the dashboard.
const form = document.getElementById("form");

if (new URLSearchParams(location.search).get("registered")) {
  showAlert("alert", "Account created. You can log in now.", "success");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");
  const id = document.getElementById("id").value.trim();
  const password = document.getElementById("password").value;
  if (!id || !password) return showAlert("alert", "Enter your Student ID and password.");

  const button = form.querySelector("button");
  try {
    await busy(button, () => API.login("student", id, password));
    location.href = "dashboard.html";
  } catch (err) {
    showAlert("alert", err.message);
  }
});
