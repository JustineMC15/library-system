from datetime import date

from working_days import days_overdue, due_date, fine


def get_due_date(conn, borrow_id: int, nonworking: set[date]) -> date:
    row = conn.execute(
        """
        SELECT
            BorrowDate,
            (
                SELECT MAX(RenewalDate)
                FROM Renew
                WHERE BorrowID = Borrow.BorrowID
                  AND Status = 'Approved'
            ) AS LatestRenewalDate
        FROM Borrow
        WHERE BorrowID = ?
        """,
        (borrow_id,)
    ).fetchone()

    if row is None or row["BorrowDate"] is None:
        raise ValueError(f"Invalid or unapproved borrow ID: {borrow_id}")

    borrow_date = date.fromisoformat(row["BorrowDate"])

    if row["LatestRenewalDate"] is not None:
        renewal_date = date.fromisoformat(row["LatestRenewalDate"])
        base = max(borrow_date, renewal_date)
    else:
        base = borrow_date

    return due_date(base, nonworking)


def student_loans(conn, student_id: str, today: date, nonworking: set[date]) -> list[dict]:
    """The student's Pending and Borrowed books, in the shape borrowed.js and book.js expect.

    - DueDate, Renewals, PendingRenew, PendingReturn and Fine are filled only for Borrowed rows.
    - Fine is the live fine for a book still out. While a return is pending it stops at the
      date the return was requested.
    - DigitalLink is sent only while the loan is Borrowed AND no return is pending, so access
      to an e-book ends the moment the student asks to return it (and comes back if denied).
    """
    rows = conn.execute(
        """
        SELECT
            b.BorrowID, b.BookID, bk.BookTitle, bk.BookAuthor, bk.BookType, bk.DigitalLink,
            b.Status, b.RequestedAt, b.BorrowDate,
            (SELECT COUNT(*) FROM Renew AS r
              WHERE r.BorrowID = b.BorrowID AND r.Status = 'Approved') AS Renewals,
            EXISTS (SELECT 1 FROM Renew AS r
              WHERE r.BorrowID = b.BorrowID AND r.Status = 'Pending') AS PendingRenew,
            (SELECT rt.RequestedAt FROM "Return" AS rt
              WHERE rt.BorrowID = b.BorrowID AND rt.Status = 'Pending') AS ReturnRequestedAt
        FROM Borrow AS b
        JOIN Book AS bk ON bk.BookID = b.BookID
        WHERE b.StudentID = ?
          AND b.Status IN ('Pending', 'Borrowed')
        ORDER BY b.RequestedAt DESC, b.BorrowID DESC
        """,
        (student_id,)
    ).fetchall()

    result = []
    for row in rows:
        loan = {
            "BorrowID": row["BorrowID"],
            "BookID": row["BookID"],
            "BookTitle": row["BookTitle"],
            "BookAuthor": row["BookAuthor"],
            "BookType": row["BookType"],
            "Status": row["Status"],
            "RequestedAt": row["RequestedAt"],
            "BorrowDate": row["BorrowDate"],
            "DueDate": None,
            "Renewals": 0,
            "PendingRenew": False,
            "PendingReturn": False,
            "Fine": 0,
            "DigitalLink": None,
        }

        if row["Status"] == "Borrowed":
            due = get_due_date(conn, row["BorrowID"], nonworking)
            return_requested = row["ReturnRequestedAt"]
            fine_until = date.fromisoformat(return_requested[:10]) if return_requested else today

            loan["DueDate"] = due.isoformat()
            loan["Renewals"] = row["Renewals"]
            loan["PendingRenew"] = bool(row["PendingRenew"])
            loan["PendingReturn"] = return_requested is not None
            loan["Fine"] = fine(days_overdue(due, fine_until, nonworking))
            if row["BookType"] == "Digital" and not loan["PendingReturn"]:
                loan["DigitalLink"] = row["DigitalLink"] or None

        result.append(loan)

    return result
