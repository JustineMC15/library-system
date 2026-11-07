import sqlite3
from datetime import date

from loans import get_due_date
from working_days import days_overdue, fine


def request_return(conn, student_id, borrow_id, now):
    """Create a pending return request for the student's borrowed book.

    The request date is the day the fine stops (see approve_return), and for a
    digital book it is the moment access to the e-book ends (see loans.student_loans).
    """

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

    pending = conn.execute(
        """
        SELECT
            EXISTS(
                SELECT 1 FROM Renew
                WHERE BorrowID = ?
                  AND Status = 'Pending'
            )
            OR EXISTS(
                SELECT 1 FROM "Return"
                WHERE BorrowID = ?
                  AND Status = 'Pending'
            )
        """,
        (borrow_id, borrow_id)
    ).fetchone()[0]

    if pending:
        return {"ok": False, "error": "A request is already pending"}

    requested_at = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor = conn.execute(
            """
            INSERT INTO "Return" (
                BorrowID,
                RequestedAt,
                Status
            )
            VALUES (?, ?, 'Pending')
            """,
            (borrow_id, requested_at)
        )
    except sqlite3.IntegrityError as error:
        if "Return.BorrowID" in str(error):
            return {"ok": False, "error": "A return request is already pending"}
        raise

    return {
        "ok": True,
        "ReturnID": cursor.lastrowid,
        "BorrowID": borrow_id
    }


def _complete_return(conn, return_id, borrow_id, librarian_id, return_date, nonworking):
    """Complete a return inside the caller's transaction.

    return_date is the day the return counts from: the fine runs up to and including it.
    The Borrow row, the Return row and any renewal still waiting for this book are all
    updated, or the caller's `with conn:` rolls everything back.
    """

    due = get_due_date(conn, borrow_id, nonworking)   # ValueError if the borrow was never approved
    fine_amount = fine(days_overdue(due, return_date, nonworking))

    cursor = conn.execute(
        """
        UPDATE Borrow
        SET Status = 'Returned'
        WHERE BorrowID = ?
          AND Status = 'Borrowed'
        """,
        (borrow_id,)
    )

    if cursor.rowcount != 1:
        raise ValueError("Borrowed record is no longer active")

    cursor = conn.execute(
        """
        UPDATE "Return"
        SET
            Status = 'Approved',
            ReturnDate = ?,
            FineAmount = ?,
            LibrarianID = ?
        WHERE ReturnID = ?
          AND BorrowID = ?
          AND Status = 'Pending'
        """,
        (
            return_date.isoformat(),
            fine_amount,
            librarian_id,
            return_id,
            borrow_id
        )
    )

    if cursor.rowcount != 1:
        raise ValueError("Return request is no longer pending")

    # A renewal for a book that is now back makes no sense: close it so it leaves the queue
    conn.execute(
        """
        UPDATE Renew
        SET
            Status = 'Denied',
            LibrarianID = ?
        WHERE BorrowID = ?
          AND Status = 'Pending'
        """,
        (librarian_id, borrow_id)
    )

    return {
        "ok": True,
        "ReturnID": return_id,
        "BorrowID": borrow_id,
        "ReturnDate": return_date.isoformat(),
        "FineAmount": fine_amount
    }


def approve_return(conn, return_id, librarian_id, nonworking):
    """Approve a pending return.

    The fine stops at the day the student REQUESTED the return, not the day the
    librarian approved it, so waiting in the queue never costs the student money.
    """

    row = conn.execute(
        """
        SELECT r.BorrowID, r.RequestedAt
        FROM "Return" AS r
        JOIN Borrow AS b ON b.BorrowID = r.BorrowID
        WHERE r.ReturnID = ?
          AND r.Status = 'Pending'
          AND b.Status = 'Borrowed'
        """,
        (return_id,)
    ).fetchone()

    if row is None:
        return {"ok": False, "error": "Return request is not pending"}

    return_date = date.fromisoformat(row["RequestedAt"][:10])

    try:
        with conn:
            return _complete_return(
                conn,
                return_id,
                row["BorrowID"],
                librarian_id,
                return_date,
                nonworking
            )
    except ValueError as error:
        return {"ok": False, "error": str(error)}


def deny_return(conn, return_id, librarian_id):
    """Deny a pending return request. The book stays borrowed (and the e-book readable again)."""

    row = conn.execute(
        """
        SELECT BorrowID
        FROM "Return"
        WHERE ReturnID = ?
          AND Status = 'Pending'
        """,
        (return_id,)
    ).fetchone()

    if row is None:
        return {"ok": False, "error": "Return request is not pending"}

    cursor = conn.execute(
        """
        UPDATE "Return"
        SET
            Status = 'Denied',
            LibrarianID = ?
        WHERE ReturnID = ?
          AND Status = 'Pending'
        """,
        (librarian_id, return_id)
    )

    if cursor.rowcount != 1:
        return {"ok": False, "error": "Return request is no longer pending"}

    return {
        "ok": True,
        "ReturnID": return_id,
        "BorrowID": row["BorrowID"]
    }


def process_return(conn, borrow_id, librarian_id, return_date, nonworking):
    """Process a physical return at the librarian's desk.

    If the student already has a pending return request, that request is approved
    (its request date decides the fine). Otherwise an already-approved return is
    created with the date the librarian picked.
    """

    borrow = conn.execute(
        """
        SELECT BorrowDate
        FROM Borrow
        WHERE BorrowID = ?
          AND Status = 'Borrowed'
        """,
        (borrow_id,)
    ).fetchone()

    if borrow is None:
        return {"ok": False, "error": "Borrowed record not found"}

    pending = conn.execute(
        """
        SELECT ReturnID
        FROM "Return"
        WHERE BorrowID = ?
          AND Status = 'Pending'
        """,
        (borrow_id,)
    ).fetchone()

    if pending is not None:
        return approve_return(conn, pending["ReturnID"], librarian_id, nonworking)

    if return_date < date.fromisoformat(borrow["BorrowDate"]):
        return {"ok": False, "error": "The return date is before the borrow date"}

    requested_at = return_date.isoformat() + " 00:00:00"

    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO "Return" (
                    BorrowID,
                    LibrarianID,
                    RequestedAt,
                    Status
                )
                VALUES (?, ?, ?, 'Pending')
                """,
                (borrow_id, librarian_id, requested_at)
            )

            return _complete_return(
                conn,
                cursor.lastrowid,
                borrow_id,
                librarian_id,
                return_date,
                nonworking
            )
    except ValueError as error:
        return {"ok": False, "error": str(error)}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "A return request is already pending"}


def fine_owed(conn, student_id):
    """Total pesos of approved, unpaid fines for one student."""

    return conn.execute(
        """
        SELECT COALESCE(SUM(r.FineAmount), 0)
        FROM "Return" AS r
        JOIN Borrow AS b ON b.BorrowID = r.BorrowID
        WHERE b.StudentID = ?
          AND r.Status = 'Approved'
          AND r.FineAmount > 0
          AND r.FinePaidDate IS NULL
        """,
        (student_id,)
    ).fetchone()[0]


def pay_fine(conn, return_id, today):
    """Mark one approved, unpaid fine as paid."""

    row = conn.execute(
        """
        SELECT FineAmount, FinePaidDate
        FROM "Return"
        WHERE ReturnID = ?
          AND Status = 'Approved'
        """,
        (return_id,)
    ).fetchone()

    if row is None:
        return {"ok": False, "error": "Approved return record not found"}

    if row["FineAmount"] <= 0:
        return {"ok": False, "error": "There is no fine to pay"}

    if row["FinePaidDate"] is not None:
        return {"ok": False, "error": "Fine has already been paid"}

    cursor = conn.execute(
        """
        UPDATE "Return"
        SET FinePaidDate = ?
        WHERE ReturnID = ?
          AND Status = 'Approved'
          AND FineAmount > 0
          AND FinePaidDate IS NULL
        """,
        (today.isoformat(), return_id)
    )

    if cursor.rowcount != 1:
        return {"ok": False, "error": "Fine is no longer unpaid"}

    return {
        "ok": True,
        "ReturnID": return_id,
        "FinePaidDate": today.isoformat()
    }


def pay_student_fines(conn, student_id, today):
    """Mark every unpaid fine of one student as paid (the Verify page's "Mark as paid")."""

    cursor = conn.execute(
        """
        UPDATE "Return"
        SET FinePaidDate = ?
        WHERE Status = 'Approved'
          AND FineAmount > 0
          AND FinePaidDate IS NULL
          AND BorrowID IN (
              SELECT BorrowID FROM Borrow WHERE StudentID = ?
          )
        """,
        (today.isoformat(), student_id)
    )

    return {"ok": True, "paid_count": cursor.rowcount}
