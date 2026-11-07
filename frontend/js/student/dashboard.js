// Student dashboard: welcome, the two main choices, and three status cards.
// The full list of loans lives on borrowed.html (My Borrowed Books).

function dueOf(l, offDays) {
  return l.DueDate || (l.BorrowDate ? addWorkingDays(l.BorrowDate, RULES.loanDays, offDays) : null);
}

function renderStatus(me, loans, offDays) {
  const borrowed = loans.filter((l) => l.Status === "Borrowed");
  const dues = borrowed.map((l) => ({ l, due: dueOf(l, offDays) }));
  const late = dues.filter((d) => dueState(d.due, offDays) === "late");
  const soon = dues.filter((d) => dueState(d.due, offDays) === "soon").sort((a, b) => a.due.localeCompare(b.due));

  $("s-borrowed").textContent = `${borrowed.length} of ${RULES.borrowLimit}`;

  // Overdue matters more than due soon, so it shows first
  if (late.length) {
    $("s-due").innerHTML = badge(`${plural(late.length, "book")} overdue`, "red");
  } else if (soon.length) {
    const first = new Date(soon[0].due + "T00:00").toLocaleDateString("en-PH", { month: "short", day: "numeric" });
    $("s-due").innerHTML = badge(`${plural(soon.length, "book")} due ${soon.length === 1 ? first : "soon"}`, "amber");
  } else {
    $("s-due").innerHTML = badge("Nothing due soon", "green");
  }

  $("s-status").innerHTML = !me.Status ? '<span class="muted">Not available yet</span>'
    : me.Status === "Suspended" ? badge("Suspended") : badge("Good Standing", "green");
}

(async () => {
  const me = await startPage("student", "dashboard");
  const first = me.FirstName || displayName(me);
  if (first) $("hello").textContent = `Welcome, ${first}`;
  const offDays = await loadOffDays();
  try {
    renderStatus(me, await API.myLoans(), offDays);
  } catch (err) {
    renderStatus(me, [], offDays);
    $("s-borrowed").textContent = "Not available";
    $("s-due").innerHTML = `<span class="muted">${esc(err.message)}</span>`;
  }
})();
