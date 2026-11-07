
import sqlite3

from checks import run_checks


ALLOWED_DENY_REASONS = {
    "Unreturned books",
    "Unpaid fines",
    "Borrow limit reached",
    "No valid Student ID",
    "Suspension of privileges",
}


def request_borrow(conn, student_id, book_id, now):
    """Create a pending borrow request."""

    book = conn.execute(
        "SELECT 1 FROM Book WHERE BookID = ?",
        (book_id,)
    ).fetchone()

    if book is None:
        return {"ok": False, "error": "Book does not exist"}

    requested_at = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor = conn.execute(
            """
            INSERT INTO Borrow (
                StudentID,
                BookID,
                RequestedAt,
                Status
            )
            VALUES (?, ?, ?, 'Pending')
            """,
            (student_id, book_id, requested_at)
        )

    except sqlite3.IntegrityError as error:
        if "Borrow.BookID" in str(error):
            return {"ok": False, "error": "Book is not available"}
        raise

    return {
        "ok": True,
        "BorrowID": cursor.lastrowid
    }


def get_queue(conn, type_filter=None):
    """Return all pending borrow, renewal, and return requests, oldest first.

    Every row has the same keys: type, request_id (the BorrowID, RenewID or ReturnID),
    BorrowID, StudentID, BookID, RequestedAt. Renewals and returns only count while
    their book is still Borrowed.
    """

    query = """
        SELECT
            'borrow' AS type,
            BorrowID AS request_id,
            BorrowID,
            StudentID,
            BookID,
            RequestedAt
        FROM Borrow
        WHERE Status = 'Pending'

        UNION ALL

        SELECT
            'renew' AS type,
            r.RenewID AS request_id,
            b.BorrowID,
            b.StudentID,
            b.BookID,
            r.RequestedAt
        FROM Renew AS r
        JOIN Borrow AS b ON b.BorrowID = r.BorrowID
        WHERE r.Status = 'Pending'
          AND b.Status = 'Borrowed'

        UNION ALL

        SELECT
            'return' AS type,
            r.ReturnID AS request_id,
            b.BorrowID,
            b.StudentID,
            b.BookID,
            r.RequestedAt
        FROM "Return" AS r
        JOIN Borrow AS b ON b.BorrowID = r.BorrowID
        WHERE r.Status = 'Pending'
          AND b.Status = 'Borrowed'
    """

    params = []

    if type_filter is not None:
        query = f"""
            SELECT *
            FROM ({query}) AS queue
            WHERE type = ?
            ORDER BY RequestedAt ASC, type ASC, request_id ASC
        """
        params.append(type_filter)
    else:
        query += """
            ORDER BY RequestedAt ASC, type ASC, request_id ASC
        """

    rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def earlier_pending_count(queue, request_type, request_id):
    """Return the number of requests appearing before this request."""

    for position, request in enumerate(queue):
        if (
            request["type"] == request_type
            and request["request_id"] == request_id
        ):
            return position

    return None


def approve_borrow(
    conn,
    borrow_id,
    librarian_id,
    today,
    nonworking,
    student_id_ok
):
    """Approve a pending borrow request after server-side verification."""

    borrow = conn.execute(
        """
        SELECT StudentID
        FROM Borrow
        WHERE BorrowID = ?
          AND Status = 'Pending'
        """,
        (borrow_id,)
    ).fetchone()

    if borrow is None:
        return {"ok": False, "error": "Borrow request is not pending"}

    if not student_id_ok:
        return {
            "ok": False,
            "error": "Student failed verification checks",
            "reasons": ["No valid Student ID"]
        }

    checks = run_checks(
        conn,
        borrow["StudentID"],
        today,
        nonworking
    )

    failed_checks = [
        reason
        for reason, failed in checks.items()
        if failed
    ]

    if failed_checks:
        return {
            "ok": False,
            "error": "Student failed verification checks",
            "reasons": failed_checks
        }

    cursor = conn.execute(
        """
        UPDATE Borrow
        SET
            Status = 'Borrowed',
            BorrowDate = ?,
            LibrarianID = ?
        WHERE BorrowID = ?
          AND Status = 'Pending'
        """,
        (
            today.isoformat(),
            librarian_id,
            borrow_id
        )
    )

    if cursor.rowcount != 1:
        return {
            "ok": False,
            "error": "Borrow request is no longer pending"
        }

    return {"ok": True, "BorrowID": borrow_id}


def deny_borrow(conn, borrow_id, librarian_id, reasons):
    """Deny a pending borrow request and record its reasons."""

    if not reasons:
        return {
            "ok": False,
            "error": "At least one denial reason is required"
        }

    reasons = set(reasons)

    if any(reason not in ALLOWED_DENY_REASONS for reason in reasons):
        return {"ok": False, "error": "Invalid denial reason"}

    borrow = conn.execute(
        """
        SELECT 1
        FROM Borrow
        WHERE BorrowID = ?
          AND Status = 'Pending'
        """,
        (borrow_id,)
    ).fetchone()

    if borrow is None:
        return {"ok": False, "error": "Borrow request is not pending"}

    with conn:
        cursor = conn.execute(
            """
            UPDATE Borrow
            SET
                Status = 'Denied',
                LibrarianID = ?
            WHERE BorrowID = ?
              AND Status = 'Pending'
            """,
            (librarian_id, borrow_id)
        )

        if cursor.rowcount != 1:
            return {
                "ok": False,
                "error": "Borrow request is no longer pending"
            }

        conn.executemany(
            """
            INSERT INTO DenyReason (BorrowID, Reason)
            VALUES (?, ?)
            """,
            [
                (borrow_id, reason)
                for reason in reasons
            ]
        )

    return {"ok": True, "BorrowID": borrow_id}
