// Student register: POST /api/register (backend/routes/auth.py).
// Contact numbers: one input per number (StudentContact table allows several).
const form = $("form");
const contacts = $("contacts");
const val = (id) => $(id).value.trim();

$("logo").outerHTML = logoHtml();

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

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");

  const required = ["StudentID", "LastName", "FirstName", "DateOfBirth", "Password"];
  const missing = required.filter((id) => !val(id));
  required.forEach((id) => $(id).classList.toggle("invalid", missing.includes(id)));
  if (missing.length) return showAlert("alert", "Fill in the highlighted fields.");
  if ($("Password").value !== $("Confirm").value) {
    $("Confirm").classList.add("invalid");
    return showAlert("alert", "The two passwords don't match.");
  }
  if (val("DateOfBirth") > todayIso()) return showAlert("alert", "Date of birth can't be in the future.");

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
    location.href = "login.html?registered=1";
  } catch (err) {
    showAlert("alert", err.message);
  }
});
