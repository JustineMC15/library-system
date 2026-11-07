
import sqlite3
from datetime import date
from pathlib import Path

from checks import run_checks
from loans import get_due_date


def create_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    schema = Path(__file__).with_name("schema.sql").read_text(
        encoding="utf-8"
    )
    conn.executescript(schema)

    # Student
    conn.execute(
        """
        INSERT INTO Student (
            StudentID, LastName, FirstName,
            DateOfBirth, PasswordHash, Status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("2024-0001", "Test", "Student",
         "2005-01-01", "test_hash", "Active")
    )

    # Librarian
    conn.execute(
        """
        INSERT INTO Librarian (
            LibrarianID, LibrarianName, PasswordHash
        )
        VALUES (?, ?, ?)
        """,
        ("L001", "Test Librarian", "test_hash")
    )

    # Books
    books = [
        ("BOOK-001", "Book A"),
        ("BOOK-002", "Book B"),
        ("BOOK-003", "Book C"),
    ]

    for book_id, title in books:
        conn.execute(
            """
            INSERT INTO Book (
                BookID, BookTitle, BookAuthor, BookType
            )
            VALUES (?, ?, ?, 'Physical')
            """,
            (book_id, title, "Test Author")
        )

    # Two borrowed books and one returned book
    loans = [
        (1, "BOOK-001", "2026-10-26", "Borrowed"),
        (2, "BOOK-002", "2026-11-02", "Borrowed"),
        (3, "BOOK-003", "2026-10-20", "Returned"),
    ]

    for borrow_id, book_id, borrow_date, status in loans:
        conn.execute(
            """
            INSERT INTO Borrow (
                BorrowID, StudentID, BookID,
                LibrarianID, RequestedAt, BorrowDate, Status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                borrow_id,
                "2024-0001",
                book_id,
                "L001",
                "2026-10-20 09:00:00",
                borrow_date,
                status
            )
        )

    # Approved return with an initially unpaid fine
    conn.execute(
        """
        INSERT INTO "Return" (
            BorrowID, LibrarianID, RequestedAt,
            ReturnDate, FineAmount, FinePaidDate, Status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            3,
            "L001",
            "2026-10-25 09:00:00",
            "2026-10-25",
            6,
            None,
            "Approved"
        )
    )

    return conn


def make_clean_db():
    conn = create_test_db()

    # Pay the existing fine.
    conn.execute(
        """
        UPDATE "Return"
        SET FinePaidDate = '2026-10-26'
        """
    )

    return conn


def get_expected_checks(
    unreturned=False,
    unpaid=False,
    limit=False,
    suspended=False
):
    return {
        "Unreturned books": unreturned,
        "Unpaid fines": unpaid,
        "Borrow limit reached": limit,
        "Suspension of privileges": suspended,
    }


def test_baseline():
    conn = make_clean_db()

    try:
        today = date(2026, 11, 3)
        nonworking = set()

        # Verify the expected due dates.
        assert get_due_date(
            conn, 1, nonworking
        ) == date(2026, 11, 3)

        assert get_due_date(
            conn, 2, nonworking
        ) == date(2026, 11, 10)

        result = run_checks(
            conn, "2024-0001", today, nonworking
        )

        assert result == get_expected_checks()

    finally:
        conn.close()


def test_borrow_limit_reached():
    conn = make_clean_db()

    try:
        # Add a fourth book.
        conn.execute(
            """
            INSERT INTO Book (
                BookID, BookTitle, BookAuthor, BookType
            )
            VALUES (?, ?, ?, 'Physical')
            """,
            ("BOOK-004", "Book D", "Test Author")
        )

        # Add a third borrowed loan.
        conn.execute(
            """
            INSERT INTO Borrow (
                BorrowID, StudentID, BookID,
                LibrarianID, RequestedAt, BorrowDate, Status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                4,
                "2024-0001",
                "BOOK-004",
                "L001",
                "2026-11-03 09:00:00",
                "2026-11-03",
                "Borrowed"
            )
        )

        result = run_checks(
            conn,
            "2024-0001",
            date(2026, 11, 3),
            set()
        )

        assert result == get_expected_checks(limit=True)

    finally:
        conn.close()


def test_suspended_student():
    conn = make_clean_db()

    try:
        conn.execute(
            """
            UPDATE Student
            SET Status = 'Suspended'
            WHERE StudentID = ?
            """,
            ("2024-0001",)
        )

        result = run_checks(
            conn,
            "2024-0001",
            date(2026, 11, 3),
            set()
        )

        assert result == get_expected_checks(suspended=True)

    finally:
        conn.close()


def test_pending_loan_does_not_count_toward_limit():
    conn = make_clean_db()

    try:
        conn.execute(
            """
            INSERT INTO Book (
                BookID, BookTitle, BookAuthor, BookType
            )
            VALUES (?, ?, ?, 'Physical')
            """,
            ("BOOK-004", "Book D", "Test Author")
        )

        # Add a Pending loan instead of a Borrowed loan.
        conn.execute(
            """
            INSERT INTO Borrow (
                StudentID, BookID, LibrarianID,
                RequestedAt, BorrowDate, Status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "2024-0001",
                "BOOK-004",
                None,
                "2026-11-03 10:00:00",
                None,
                "Pending"
            )
        )

        result = run_checks(
            conn,
            "2024-0001",
            date(2026, 11, 3),
            set()
        )

        assert result == get_expected_checks()

    finally:
        conn.close()


if __name__ == "__main__":
    test_baseline()
    test_borrow_limit_reached()
    test_suspended_student()
    test_pending_loan_does_not_count_toward_limit()

    print("All verification check tests passed!")
