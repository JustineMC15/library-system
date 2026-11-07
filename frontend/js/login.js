// Login for both roles. The form's data-role says which: "student" or "librarian".
const form = $("form");
const role = form.dataset.role;
const idField = form.querySelector("input:not([type=password])");
const label = role === "student" ? "Student ID" : "Librarian ID";

renderSiteBar();
addPasswordToggles();

if (params.get("registered")) {
  showAlert("alert", "Account created. Log in with your Student ID and new password.", "success");
  if (params.get("id")) idField.value = params.get("id");
  $("Password").focus();
} else {
  idField.focus();
}

// Caps Lock is the most common reason a right password "doesn't work"
$("Password").addEventListener("keyup", (e) => {
  if (e.getModifierState) fieldError("Password", e.getModifierState("CapsLock") ? "Caps Lock is on." : "");
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");
  const id = idField.value.trim();
  const password = $("Password").value;
  const okId = fieldError(idField.id, id ? "" : `Enter your ${label}.`);
  const okPw = fieldError("Password", password ? "" : "Enter your password.");
  if (!okId) return idField.focus();
  if (!okPw) return $("Password").focus();

  try {
    await busy(form.querySelector("button[type=submit]"), () => API.login(role, id, password), "Logging in…");
    location.href = "dashboard.html";
  } catch (err) {
    // Wrong credentials: keep the ID, clear the password, say what happened and what to try
    $("Password").value = "";
    $("Password").focus();
    showAlert("alert", err.status === 401
      ? `That ${label} and password don't match. Check for typos, or ask the library desk to reset your password.`
      : err.message);
  }
});
