import sqlite3

from config import LOAN_DAYS, MAX_RENEWALS
from loans import get_due_date
from working_days import can_renew, days_left, days_overdue


def request_renew(conn, student_id, borrow_id, now, nonworking):
    """Create a pending renewal request for the student's borrowed book."""

    borrow = conn.execute(
        """
        SELECT BorrowID
        FROM Borrow
        WHERE BorrowID = ?
          AND StudentID = ?
          AND Status = 'Borrowed'
        """,
        (borrow_id, student_id)
    ).fetchone()

    if borrow is None:
        return {"ok": False, "error": "Borrowed book not found"}

    has_pending_return = conn.execute(
        """
        SELECT 1
        FROM "Return"
        WHERE BorrowID = ?
          AND Status = 'Pending'
        LIMIT 1
        """,
        (borrow_id,)
    ).fetchone() is not None

    has_pending_renew = conn.execute(
        """
        SELECT 1
        FROM Renew
        WHERE BorrowID = ?
          AND Status = 'Pending'
        LIMIT 1
        """,
        (borrow_id,)
    ).fetchone() is not None

    approved_renewals = conn.execute(
        """
        SELECT COUNT(*)
        FROM Renew
        WHERE BorrowID = ?
          AND Status = 'Approved'
        """,
        (borrow_id,)
    ).fetchone()[0]

    if has_pending_return:
        return {"ok": False, "error": "A return request is already pending"}

    if has_pending_renew:
        return {"ok": False, "error": "A renewal request is already pending"}

    today = now.date()
    due = get_due_date(conn, borrow_id, nonworking)

    # An overdue book cannot be renewed (same test as the "Unreturned books" check)
    if days_overdue(due, today, nonworking) > 0:
        return {"ok": False, "error": "Overdue books cannot be renewed"}

    if approved_renewals >= MAX_RENEWALS:
        return {"ok": False, "error": f"All {MAX_RENEWALS} renewals are used"}

    remaining = days_left(today, due, nonworking)

    if remaining >= LOAN_DAYS:
        return {"ok": False, "error": f"This book already has {LOAN_DAYS} days left"}

    if not can_renew(approved_renewals, remaining, has_pending_renew):
        return {"ok": False, "error": "Book cannot be renewed"}

    requested_at = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor = conn.execute(
            """
            INSERT INTO Renew (
                BorrowID,
                RequestedAt,
                Status
            )
            VALUES (?, ?, 'Pending')
            """,
            (borrow_id, requested_at)
        )
    except sqlite3.IntegrityError as error:
        if "Renew.BorrowID" in str(error):
            return {"ok": False, "error": "A renewal request is already pending"}
        raise

    return {
        "ok": True,
        "RenewID": cursor.lastrowid,
        "BorrowID": borrow_id
    }


def approve_renew(conn, renew_id, librarian_id, today, nonworking):
    """Approve a pending renewal and record its effective date.

    The overdue rule is checked again here: the request may have been sent on the
    due day and approved after it, which would otherwise wipe out the overdue days.
    """

    renew = conn.execute(
        """
        SELECT r.BorrowID
        FROM Renew AS r
        JOIN Borrow AS b ON b.BorrowID = r.BorrowID
        WHERE r.RenewID = ?
          AND r.Status = 'Pending'
          AND b.Status = 'Borrowed'
        """,
        (renew_id,)
    ).fetchone()

    if renew is None:
        return {"ok": False, "error": "Renewal request is not pending"}

    due = get_due_date(conn, renew["BorrowID"], nonworking)

    if days_overdue(due, today, nonworking) > 0:
        return {"ok": False, "error": "Book is overdue and cannot be renewed"}

    cursor = conn.execute(
        """
        UPDATE Renew
        SET
            Status = 'Approved',
            RenewalDate = ?,
            LibrarianID = ?
        WHERE RenewID = ?
          AND Status = 'Pending'
        """,
        (today.isoformat(), librarian_id, renew_id)
    )

    if cursor.rowcount != 1:
        return {"ok": False, "error": "Renewal request is no longer pending"}

    return {
        "ok": True,
        "RenewID": renew_id,
        "BorrowID": renew["BorrowID"]
    }


def deny_renew(conn, renew_id, librarian_id):
    """Deny a pending renewal request."""

    renew = conn.execute(
        """
        SELECT BorrowID
        FROM Renew
        WHERE RenewID = ?
          AND Status = 'Pending'
        """,
        (renew_id,)
    ).fetchone()

    if renew is None:
        return {"ok": False, "error": "Renewal request is not pending"}

    cursor = conn.execute(
        """
        UPDATE Renew
        SET
            Status = 'Denied',
            LibrarianID = ?
        WHERE RenewID = ?
          AND Status = 'Pending'
        """,
        (librarian_id, renew_id)
    )

    if cursor.rowcount != 1:
        return {"ok": False, "error": "Renewal request is no longer pending"}

    return {
        "ok": True,
        "RenewID": renew_id,
        "BorrowID": renew["BorrowID"]
    }
