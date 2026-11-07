// Student register: POST /api/register (backend/routes/auth.py).
// Contact numbers: one input per number (StudentContact table allows several).
const form = $("form");
const contacts = $("contacts");
const val = (id) => $(id).value.trim();

renderSiteBar();

function addContact(focus = false) {
  const n = contacts.children.length + 1;
  const row = document.createElement("div");
  row.className = "inline field";
  row.innerHTML = `
    <input type="tel" inputmode="tel" placeholder="09171234567" aria-label="Contact number ${n}">
    ${n > 1 ? `<button type="button" class="btn secondary" aria-label="Remove contact number ${n}">Remove</button>` : ""}`;
  contacts.appendChild(row);
  if (focus) row.querySelector("input").focus();
}

contacts.addEventListener("click", (e) => {
  if (e.target.closest("button")) e.target.closest(".inline").remove();
});
$("add-contact").addEventListener("click", () => addContact(true));
addContact();

// Age is never typed: it follows the date of birth
$("DateOfBirth").addEventListener("input", () => {
  const a = age(val("DateOfBirth"));
  $("Age").value = a === "" ? "" : plural(a, "year") + " old";
});

addPasswordToggles();
$("DateOfBirth").max = todayIso();

// One clear message per field, checked on submit and again as soon as the field is fixed
const CHECKS = {
  StudentID: () => (val("StudentID") ? "" : "Enter the Student ID from your school ID."),
  LastName: () => (val("LastName") ? "" : "Enter your last name."),
  FirstName: () => (val("FirstName") ? "" : "Enter your first name."),
  DateOfBirth: () => (!val("DateOfBirth") ? "Pick your date of birth."
    : val("DateOfBirth") > todayIso() ? "Date of birth can't be in the future." : ""),
  Password: () => ($("Password").value.length >= 6 ? "" : "Use at least 6 characters."),
  Confirm: () => ($("Confirm").value === $("Password").value ? "" : "This doesn't match the password above."),
};
for (const id of Object.keys(CHECKS)) {
  $(id).addEventListener("blur", () => { if ($(id).value) fieldError(id, CHECKS[id]()); });
  $(id).addEventListener("input", () => { if ($(id).classList.contains("invalid")) fieldError(id, CHECKS[id]()); });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");

  const bad = Object.keys(CHECKS).filter((id) => !fieldError(id, CHECKS[id]()));
  if (bad.length) {
    $(bad[0]).focus();
    return showAlert("alert", bad.length === 1 ? "One field needs fixing." : `${bad.length} fields need fixing.`);
  }

  const data = {
    student_id: val("StudentID"),
    last_name: val("LastName"),
    first_name: val("FirstName"),
    middle_initial: val("MiddleInitial") || null,
    address: val("Address") || null,
    date_of_birth: val("DateOfBirth"),
    contact_numbers: [...contacts.querySelectorAll("input")].map((i) => i.value.trim()).filter(Boolean),
    password: $("Password").value,
  };

  try {
    await busy(form.querySelector("button[type=submit]"), () => API.registerStudent(data), "Creating account…");
    location.href = `login.html?registered=1&id=${encodeURIComponent(data.student_id)}`;
  } catch (err) {
    if (err.status === 409) {
      fieldError("StudentID", "This Student ID already has an account.");
      $("StudentID").focus();
      return showAlert("alert", "This Student ID is already registered. Log in instead, or ask the library desk if it isn't yours.");
    }
    showAlert("alert", err.message);
  }
});
