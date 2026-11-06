
from datetime import date

from working_days import due_date


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
