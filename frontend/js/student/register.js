// Student register: matches POST /api/register in backend/routes/auth.py
const form = document.getElementById("form");
const val = (id) => document.getElementById(id).value.trim();

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert("alert");

  const data = {
    student_id: val("student_id"),
    last_name: val("last_name"),
    first_name: val("first_name"),
    middle_initial: val("middle_initial") || null,
    address: val("address") || null,
    date_of_birth: val("date_of_birth"),
    contact_numbers: val("contacts").split(",").map((n) => n.trim()).filter(Boolean),
    password: document.getElementById("password").value,
  };

  if (!data.student_id || !data.last_name || !data.first_name || !data.date_of_birth || !data.password) {
    return showAlert("alert", "Fill in every field that isn't marked optional.");
  }
  if (data.password !== document.getElementById("confirm").value) {
    return showAlert("alert", "The two passwords don't match.");
  }

  try {
    await busy(form.querySelector("button"), () => API.registerStudent(data));
    location.href = "login.html?registered=1";
  } catch (err) {
    showAlert("alert", err.message);
  }
});
