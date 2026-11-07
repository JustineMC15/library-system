// Login for both roles. The form's data-role says which: "student" or "librarian".
const form = $("form");
const role = form.dataset.role;
const idField = form.querySelector("input:not([type=password])");
const label = role === "student" ? "Student ID" : "Librarian ID";

$("logo").outerHTML = logoHtml();

if (params.get("registered")) {
  showAlert("alert", "Account created. Log in with your new password.", "success");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");
  const id = idField.value.trim();
  const password = $("Password").value;
  idField.classList.toggle("invalid", !id);
  $("Password").classList.toggle("invalid", !password);
  if (!id || !password) return showAlert("alert", `Enter your ${label} and password.`);

  try {
    await busy(form.querySelector("button"), () => API.login(role, id, password), "Logging in…");
    location.href = "dashboard.html";
  } catch (err) {
    // Wrong credentials: keep the ID, clear the password, say what happened
    $("Password").value = "";
    $("Password").focus();
    showAlert("alert", err.status === 401 ? `That ${label} and password don't match.` : err.message);
  }
});
