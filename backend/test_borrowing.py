
from datetime import date, datetime

from test_checks import make_clean_db
from borrowing import (
    request_borrow,
    approve_borrow,
    deny_borrow,
    get_queue,
    earlier_pending_count,
)


STUDENT_ID = "2024-0001"
LIBRARIAN_ID = "L001"
TODAY = date(2026, 11, 3)
NONWORKING = set()


def get_borrow(conn, borrow_id):
    return conn.execute(
        "SELECT * FROM Borrow WHERE BorrowID = ?",
        (borrow_id,)
    ).fetchone()


def test_request_ok():
    conn = make_clean_db()

    result = request_borrow(
        conn,
        STUDENT_ID,
        "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )

    assert result["ok"] is True
    assert "BorrowID" in result

    borrow = get_borrow(conn, result["BorrowID"])
    assert borrow["Status"] == "Pending"
    assert borrow["BorrowDate"] is None
    assert borrow["RequestedAt"] == "2026-11-03 10:00:00"

    conn.close()


def test_duplicate_refused():
    conn = make_clean_db()

    first = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    second = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 5, 0)
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["error"] == "Book is not available"

    conn.close()


def test_unknown_book():
    conn = make_clean_db()

    result = request_borrow(
        conn, STUDENT_ID, "BOOK-999",
        datetime(2026, 11, 3, 10, 0, 0)
    )

    assert result == {
        "ok": False,
        "error": "Book does not exist"
    }

    conn.close()


def test_approve_all_pass():
    conn = make_clean_db()

    request = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    borrow_id = request["BorrowID"]

    result = approve_borrow(
        conn,
        borrow_id,
        LIBRARIAN_ID,
        TODAY,
        NONWORKING,
        student_id_ok=True
    )

    assert result["ok"] is True

    borrow = get_borrow(conn, borrow_id)
    assert borrow["Status"] == "Borrowed"
    assert borrow["BorrowDate"] == "2026-11-03"
    assert borrow["LibrarianID"] == LIBRARIAN_ID

    conn.close()


def test_approve_check_fails():
    conn = make_clean_db()

    request = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    borrow_id = request["BorrowID"]

    result = approve_borrow(
        conn,
        borrow_id,
        LIBRARIAN_ID,
        date(2026, 11, 4),
        NONWORKING,
        student_id_ok=True
    )

    assert result["ok"] is False
    assert result["reasons"] == ["Unreturned books"]

    borrow = get_borrow(conn, borrow_id)
    assert borrow["Status"] == "Pending"

    conn.close()


def test_approve_student_id_not_confirmed():
    conn = make_clean_db()

    request = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    borrow_id = request["BorrowID"]

    result = approve_borrow(
        conn,
        borrow_id,
        LIBRARIAN_ID,
        TODAY,
        NONWORKING,
        student_id_ok=False
    )

    assert result["ok"] is False
    assert result["reasons"] == ["No valid Student ID"]

    borrow = get_borrow(conn, borrow_id)
    assert borrow["Status"] == "Pending"

    conn.close()


def test_approve_non_pending():
    conn = make_clean_db()

    request = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    borrow_id = request["BorrowID"]

    first = approve_borrow(
        conn, borrow_id, LIBRARIAN_ID,
        TODAY, NONWORKING, student_id_ok=True
    )
    second = approve_borrow(
        conn, borrow_id, LIBRARIAN_ID,
        TODAY, NONWORKING, student_id_ok=True
    )

    assert first["ok"] is True
    assert second["ok"] is False

    borrow = get_borrow(conn, borrow_id)
    assert borrow["Status"] == "Borrowed"

    conn.close()


def test_deny_multiple_reasons():
    conn = make_clean_db()

    request = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    borrow_id = request["BorrowID"]

    result = deny_borrow(
        conn,
        borrow_id,
        LIBRARIAN_ID,
        ["Unpaid fines", "Borrow limit reached"]
    )

    assert result["ok"] is True

    borrow = get_borrow(conn, borrow_id)
    assert borrow["Status"] == "Denied"

    count = conn.execute(
        "SELECT COUNT(*) FROM DenyReason WHERE BorrowID = ?",
        (borrow_id,)
    ).fetchone()[0]

    assert count == 2

    conn.close()


def test_deny_duplicate_reasons():
    conn = make_clean_db()

    request = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    borrow_id = request["BorrowID"]

    result = deny_borrow(
        conn,
        borrow_id,
        LIBRARIAN_ID,
        ["Unpaid fines", "Unpaid fines"]
    )

    assert result["ok"] is True

    count = conn.execute(
        "SELECT COUNT(*) FROM DenyReason WHERE BorrowID = ?",
        (borrow_id,)
    ).fetchone()[0]

    assert count == 1

    conn.close()


def test_deny_empty_reasons():
    conn = make_clean_db()

    request = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    borrow_id = request["BorrowID"]

    result = deny_borrow(
        conn, borrow_id, LIBRARIAN_ID, []
    )

    assert result["ok"] is False
    assert get_borrow(conn, borrow_id)["Status"] == "Pending"

    conn.close()


def test_deny_invalid_reason():
    conn = make_clean_db()

    request = request_borrow(
        conn, STUDENT_ID, "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )
    borrow_id = request["BorrowID"]

    result = deny_borrow(
        conn, borrow_id, LIBRARIAN_ID, ["Late fee"]
    )

    assert result["ok"] is False
    assert get_borrow(conn, borrow_id)["Status"] == "Pending"

    conn.close()



def test_queue_order_and_filter():
    conn = make_clean_db()

    # Pending renewal requested first.
    conn.execute(
        """
        INSERT INTO Renew (BorrowID, RequestedAt, Status)
        VALUES (?, ?, 'Pending')
        """,
        (1, "2026-11-03 09:00:00")
    )

    # Add another book using all required Book columns.
    conn.execute(
        """
        INSERT INTO Book (
            BookID,
            BookISBN,
            BookTitle,
            BookAuthor,
            PublishYear,
            BookType,
            DigitalLink
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "BOOK-004",
            None,
            "Test Book D",
            "Test Author",
            2026,
            "Physical",
            None
        )
    )

    # First pending borrow: 10:00.
    first_borrow = request_borrow(
        conn,
        STUDENT_ID,
        "BOOK-003",
        datetime(2026, 11, 3, 10, 0, 0)
    )

    # Second pending borrow: 10:30.
    second_borrow = request_borrow(
        conn,
        STUDENT_ID,
        "BOOK-004",
        datetime(2026, 11, 3, 10, 30, 0)
    )

    assert first_borrow["ok"] is True
    assert second_borrow["ok"] is True

    # All three request types should be ordered oldest first.
    queue = get_queue(conn)

    assert [item["type"] for item in queue] == [
        "renew",
        "borrow",
        "borrow"
    ]

    assert [item["RequestedAt"] for item in queue] == [
        "2026-11-03 09:00:00",
        "2026-11-03 10:00:00",
        "2026-11-03 10:30:00"
    ]

    # Filtering should return only borrow requests.
    borrow_queue = get_queue(conn, type_filter="borrow")

    assert len(borrow_queue) == 2
    assert all(item["type"] == "borrow" for item in borrow_queue)

    # The 10:30 request has two requests before it.
    position = earlier_pending_count(
        queue,
        "borrow",
        second_borrow["BorrowID"]
    )

    assert position == 2

    conn.close()


if __name__ == "__main__":
    test_request_ok()
    test_duplicate_refused()
    test_unknown_book()
    test_approve_all_pass()
    test_approve_check_fails()
    test_approve_student_id_not_confirmed()
    test_approve_non_pending()
    test_deny_multiple_reasons()
    test_deny_duplicate_reasons()
    test_deny_empty_reasons()
    test_deny_invalid_reason()
    test_queue_order_and_filter()

    print("All borrowing tests passed!")
