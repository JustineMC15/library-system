
from datetime import date

from config import BORROW_LIMIT
from loans import get_due_date
from working_days import days_overdue


def run_checks(
    conn,
    student_id: str,
    today: date,
    nonworking: set[date]
) -> dict[str, bool]:

    # Unreturned books
    borrowed = conn.execute(
        """
        SELECT BorrowID
        FROM Borrow
        WHERE StudentID = ?
          AND Status = 'Borrowed'
        """,
        (student_id,)
    ).fetchall()

    unreturned_books = False

    for row in borrowed:
        due = get_due_date(conn, row["BorrowID"], nonworking)

        if days_overdue(due, today, nonworking) > 0:
            unreturned_books = True
            break

    # Unpaid fines
    unpaid_fines = conn.execute(
        """
        SELECT 1
        FROM "Return" AS r
        JOIN Borrow AS b ON b.BorrowID = r.BorrowID
        WHERE b.StudentID = ?
          AND r.Status = 'Approved'
          AND r.FineAmount > 0
          AND r.FinePaidDate IS NULL
        LIMIT 1
        """,
        (student_id,)
    ).fetchone() is not None

    # Borrow limit reached
    borrowed_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM Borrow
        WHERE StudentID = ?
          AND Status = 'Borrowed'
        """,
        (student_id,)
    ).fetchone()[0]

    borrow_limit_reached = borrowed_count >= BORROW_LIMIT

    # Suspension of privileges
    student = conn.execute(
        """
        SELECT Status
        FROM Student
        WHERE StudentID = ?
        """,
        (student_id,)
    ).fetchone()

    suspension = (
        student is not None
        and student["Status"] == "Suspended"
    )

    return {
        "Unreturned books": unreturned_books,
        "Unpaid fines": unpaid_fines,
        "Borrow limit reached": borrow_limit_reached,
        "Suspension of privileges": suspension,
    }
