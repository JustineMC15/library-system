"""Tests for renewals, returns, fines and the student's loan list.
Run from the backend folder:  python test_renew_return.py

Test data comes from make_clean_db() in test_checks.py:
  borrow 1: BOOK-001, borrowed 2026-10-26, due 2026-11-03
  borrow 2: BOOK-002, borrowed 2026-11-02, due 2026-11-10
  borrow 3: BOOK-003, already returned (fine paid)
"""
from datetime import date, datetime

from borrowing import get_queue
from checks import run_checks
from loans import get_due_date, student_loans
from renewals import approve_renew, deny_renew, request_renew
from returns import (
    approve_return,
    deny_return,
    fine_owed,
    pay_fine,
    pay_student_fines,
    process_return,
    request_return,
)
from test_checks import make_clean_db

STUDENT = "2024-0001"
LIBRARIAN = "L001"
NONE = set()
NOV3 = datetime(2026, 11, 3, 10, 0, 0)     # a Tuesday: borrow 1 is due today
NOV4 = datetime(2026, 11, 4, 9, 0, 0)      # borrow 1 is 1 working day overdue


def one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


# ---------- request_renew ----------

def test_renew_ok():
    conn = make_clean_db()
    r = request_renew(conn, STUDENT, 1, NOV3, NONE)
    assert r["ok"] is True and r["BorrowID"] == 1
    saved = one(conn, "SELECT * FROM Renew WHERE RenewID = ?", (r["RenewID"],))
    assert saved["Status"] == "Pending"
    assert saved["RequestedAt"] == "2026-11-03 10:00:00"


def test_renew_refused_when_overdue():
    conn = make_clean_db()
    r = request_renew(conn, STUDENT, 1, NOV4, NONE)
    assert r == {"ok": False, "error": "Overdue books cannot be renewed"}
    assert one(conn, "SELECT COUNT(*) FROM Renew")[0] == 0


def test_renew_refused_with_seven_days_left():
    conn = make_clean_db()
    r = request_renew(conn, STUDENT, 2, datetime(2026, 11, 2, 9, 0, 0), NONE)
    assert r == {"ok": False, "error": "This book already has 7 days left"}


def test_renew_refused_after_three_renewals():
    conn = make_clean_db()
    for renewal_date in ("2026-10-27", "2026-10-28", "2026-10-29"):
        conn.execute(
            "INSERT INTO Renew (BorrowID, LibrarianID, RequestedAt, RenewalDate, Status) "
            "VALUES (1, 'L001', '2026-10-27 09:00:00', ?, 'Approved')",
            (renewal_date,),
        )
    assert get_due_date(conn, 1, NONE) == date(2026, 11, 6)
    r = request_renew(conn, STUDENT, 1, NOV3, NONE)
    assert r == {"ok": False, "error": "All 3 renewals are used"}


def test_renew_needs_own_borrowed_book():
    conn = make_clean_db()
    assert request_renew(conn, "someone-else", 1, NOV3, NONE)["error"] == "Borrowed book not found"
    assert request_renew(conn, STUDENT, 3, NOV3, NONE)["error"] == "Borrowed book not found"   # already returned
    assert request_renew(conn, STUDENT, 999, NOV3, NONE)["error"] == "Borrowed book not found"


def test_renew_and_return_block_each_other():
    conn = make_clean_db()
    assert request_renew(conn, STUDENT, 1, NOV3, NONE)["ok"] is True
    assert request_renew(conn, STUDENT, 1, NOV3, NONE)["error"] == "A renewal request is already pending"
    assert request_return(conn, STUDENT, 1, NOV3)["error"] == "A request is already pending"

    conn = make_clean_db()
    assert request_return(conn, STUDENT, 1, NOV3)["ok"] is True
    assert request_renew(conn, STUDENT, 1, NOV3, NONE)["error"] == "A return request is already pending"


# ---------- approve and deny renew ----------

def test_approve_renew_resets_due_date():
    conn = make_clean_db()
    renew_id = request_renew(conn, STUDENT, 1, NOV3, NONE)["RenewID"]
    r = approve_renew(conn, renew_id, LIBRARIAN, date(2026, 11, 3), NONE)
    assert r["ok"] is True
    saved = one(conn, "SELECT * FROM Renew WHERE RenewID = ?", (renew_id,))
    assert saved["Status"] == "Approved"
    assert saved["RenewalDate"] == "2026-11-03"
    assert saved["LibrarianID"] == LIBRARIAN
    assert get_due_date(conn, 1, NONE) == date(2026, 11, 11)       # 7 working days from Nov 3
    # approving twice does nothing
    assert approve_renew(conn, renew_id, LIBRARIAN, date(2026, 11, 3), NONE)["error"] == "Renewal request is not pending"


def test_approve_renew_refused_when_overdue_by_approval_day():
    conn = make_clean_db()
    renew_id = request_renew(conn, STUDENT, 1, NOV3, NONE)["RenewID"]     # sent on the due day
    r = approve_renew(conn, renew_id, LIBRARIAN, date(2026, 11, 4), NONE)  # approved a day late
    assert r == {"ok": False, "error": "Book is overdue and cannot be renewed"}
    assert one(conn, "SELECT Status FROM Renew WHERE RenewID = ?", (renew_id,))["Status"] == "Pending"
    assert get_due_date(conn, 1, NONE) == date(2026, 11, 3)


def test_deny_renew():
    conn = make_clean_db()
    renew_id = request_renew(conn, STUDENT, 1, NOV3, NONE)["RenewID"]
    assert deny_renew(conn, renew_id, LIBRARIAN)["ok"] is True
    assert one(conn, "SELECT Status FROM Renew WHERE RenewID = ?", (renew_id,))["Status"] == "Denied"
    assert get_due_date(conn, 1, NONE) == date(2026, 11, 3)
    assert deny_renew(conn, renew_id, LIBRARIAN)["ok"] is False
    assert request_renew(conn, STUDENT, 1, NOV3, NONE)["ok"] is True      # can ask again


# ---------- request, approve and deny return ----------

def test_return_request_and_duplicate():
    conn = make_clean_db()
    r = request_return(conn, STUDENT, 1, NOV3)
    assert r["ok"] is True
    assert request_return(conn, STUDENT, 1, NOV3)["error"] == "A request is already pending"
    assert request_return(conn, "someone-else", 2, NOV3)["error"] == "Borrowed book not found"


def test_approve_return_stops_fine_at_request_date():
    conn = make_clean_db()
    return_id = request_return(conn, STUDENT, 1, NOV4)["ReturnID"]       # due Nov 3, requested Nov 4
    r = approve_return(conn, return_id, LIBRARIAN, NONE)                 # no "today": approval day is irrelevant
    assert r["ok"] is True
    assert r["FineAmount"] == 2 and r["ReturnDate"] == "2026-11-04"
    saved = one(conn, 'SELECT * FROM "Return" WHERE ReturnID = ?', (return_id,))
    assert saved["Status"] == "Approved"
    assert saved["FineAmount"] == 2
    assert saved["FinePaidDate"] is None
    assert saved["LibrarianID"] == LIBRARIAN
    assert one(conn, "SELECT Status FROM Borrow WHERE BorrowID = 1")["Status"] == "Returned"
    assert approve_return(conn, return_id, LIBRARIAN, NONE)["error"] == "Return request is not pending"


def test_approve_return_on_time_has_no_fine():
    conn = make_clean_db()
    return_id = request_return(conn, STUDENT, 2, NOV3)["ReturnID"]
    r = approve_return(conn, return_id, LIBRARIAN, NONE)
    assert r["ok"] is True and r["FineAmount"] == 0


def test_deny_return_keeps_book_borrowed():
    conn = make_clean_db()
    return_id = request_return(conn, STUDENT, 1, NOV3)["ReturnID"]
    assert deny_return(conn, return_id, LIBRARIAN)["ok"] is True
    assert one(conn, 'SELECT Status FROM "Return" WHERE ReturnID = ?', (return_id,))["Status"] == "Denied"
    assert one(conn, "SELECT Status FROM Borrow WHERE BorrowID = 1")["Status"] == "Borrowed"
    assert request_return(conn, STUDENT, 1, NOV3)["ok"] is True          # can ask again


# ---------- process_return (desk) ----------

def test_process_return_desk_without_request():
    conn = make_clean_db()
    r = process_return(conn, 1, LIBRARIAN, date(2026, 11, 5), NONE)      # overdue Nov 4 and Nov 5
    assert r["ok"] is True
    assert r["FineAmount"] == 4 and r["ReturnDate"] == "2026-11-05"
    saved = one(conn, 'SELECT * FROM "Return" WHERE ReturnID = ?', (r["ReturnID"],))
    assert saved["Status"] == "Approved" and saved["LibrarianID"] == LIBRARIAN
    assert one(conn, "SELECT Status FROM Borrow WHERE BorrowID = 1")["Status"] == "Returned"


def test_process_return_uses_request_date_when_one_is_pending():
    conn = make_clean_db()
    request_return(conn, STUDENT, 1, NOV4)
    r = process_return(conn, 1, LIBRARIAN, date(2026, 11, 6), NONE)      # librarian processes it two days later
    assert r["ok"] is True
    assert r["FineAmount"] == 2 and r["ReturnDate"] == "2026-11-04"
    assert one(conn, 'SELECT COUNT(*) FROM "Return" WHERE BorrowID = 1')[0] == 1     # no second row


def test_process_return_rejects_date_before_borrow_date():
    conn = make_clean_db()
    r = process_return(conn, 1, LIBRARIAN, date(2026, 10, 25), NONE)     # borrowed Oct 26
    assert r == {"ok": False, "error": "The return date is before the borrow date"}
    assert one(conn, "SELECT Status FROM Borrow WHERE BorrowID = 1")["Status"] == "Borrowed"
    assert one(conn, 'SELECT COUNT(*) FROM "Return" WHERE BorrowID = 1')[0] == 0


def test_process_return_unknown_or_already_returned():
    conn = make_clean_db()
    for borrow_id in (999, 3):
        r = process_return(conn, borrow_id, LIBRARIAN, date(2026, 11, 3), NONE)
        assert r == {"ok": False, "error": "Borrowed record not found"}


def test_return_closes_a_pending_renewal():
    conn = make_clean_db()
    renew_id = request_renew(conn, STUDENT, 1, NOV3, NONE)["RenewID"]
    assert len(get_queue(conn)) == 1
    assert process_return(conn, 1, LIBRARIAN, date(2026, 11, 3), NONE)["ok"] is True
    assert one(conn, "SELECT Status FROM Renew WHERE RenewID = ?", (renew_id,))["Status"] == "Denied"
    assert get_queue(conn) == []


# ---------- fines ----------

def test_unpaid_fine_blocks_until_paid():
    conn = make_clean_db()
    return_id = request_return(conn, STUDENT, 1, NOV4)["ReturnID"]
    approve_return(conn, return_id, LIBRARIAN, NONE)
    assert fine_owed(conn, STUDENT) == 2
    assert run_checks(conn, STUDENT, date(2026, 11, 5), NONE)["Unpaid fines"] is True

    assert pay_fine(conn, return_id, date(2026, 11, 5))["ok"] is True
    assert pay_fine(conn, return_id, date(2026, 11, 5))["error"] == "Fine has already been paid"
    assert fine_owed(conn, STUDENT) == 0
    assert run_checks(conn, STUDENT, date(2026, 11, 5), NONE)["Unpaid fines"] is False


def test_pay_student_fines_pays_everything_owed():
    conn = make_clean_db()
    process_return(conn, 1, LIBRARIAN, date(2026, 11, 5), NONE)           # fine 4
    process_return(conn, 2, LIBRARIAN, date(2026, 11, 3), NONE)           # no fine
    assert fine_owed(conn, STUDENT) == 4
    assert pay_student_fines(conn, STUDENT, date(2026, 11, 5)) == {"ok": True, "paid_count": 1}
    assert fine_owed(conn, STUDENT) == 0
    assert pay_student_fines(conn, STUDENT, date(2026, 11, 5))["paid_count"] == 0


def test_pay_fine_errors():
    conn = make_clean_db()
    assert pay_fine(conn, 999, date(2026, 11, 3))["error"] == "Approved return record not found"
    return_id = process_return(conn, 2, LIBRARIAN, date(2026, 11, 3), NONE)["ReturnID"]
    assert pay_fine(conn, return_id, date(2026, 11, 3))["error"] == "There is no fine to pay"


# ---------- student_loans ----------

def add_digital_loan(conn):
    conn.execute(
        "INSERT INTO Book (BookID, BookTitle, BookAuthor, BookType, DigitalLink) "
        "VALUES ('DIG-001', 'E-book', 'Auth', 'Digital', 'https://example.com/read')"
    )
    conn.execute(
        "INSERT INTO Borrow (BorrowID, StudentID, BookID, LibrarianID, RequestedAt, BorrowDate, Status) "
        "VALUES (4, ?, 'DIG-001', 'L001', '2026-11-02 09:00:00', '2026-11-02', 'Borrowed')",
        (STUDENT,),
    )


def by_book(loans, book_id):
    return next(l for l in loans if l["BookID"] == book_id)


def test_loans_have_the_fields_the_pages_need():
    conn = make_clean_db()
    loans = student_loans(conn, STUDENT, date(2026, 11, 3), NONE)
    assert sorted(l["BorrowID"] for l in loans) == [1, 2]                  # the returned loan is not listed
    first = by_book(loans, "BOOK-001")
    assert first["DueDate"] == "2026-11-03"
    assert first["Renewals"] == 0 and first["PendingRenew"] is False and first["PendingReturn"] is False
    assert first["Fine"] == 0 and first["BookType"] == "Physical" and first["DigitalLink"] is None

    request_renew(conn, STUDENT, 1, NOV3, NONE)
    assert by_book(student_loans(conn, STUDENT, date(2026, 11, 3), NONE), "BOOK-001")["PendingRenew"] is True


def test_loan_fine_stops_at_return_request():
    conn = make_clean_db()
    today = date(2026, 11, 6)                                              # 3 working days after the due date
    assert by_book(student_loans(conn, STUDENT, today, NONE), "BOOK-001")["Fine"] == 6
    request_return(conn, STUDENT, 1, NOV4)
    loan = by_book(student_loans(conn, STUDENT, today, NONE), "BOOK-001")
    assert loan["PendingReturn"] is True and loan["Fine"] == 2


def test_digital_access_ends_when_return_is_requested():
    conn = make_clean_db()
    add_digital_loan(conn)
    today = date(2026, 11, 3)

    loan = by_book(student_loans(conn, STUDENT, today, NONE), "DIG-001")
    assert loan["DigitalLink"] == "https://example.com/read"

    return_id = request_return(conn, STUDENT, 4, NOV3)["ReturnID"]
    loan = by_book(student_loans(conn, STUDENT, today, NONE), "DIG-001")
    assert loan["DigitalLink"] is None and loan["PendingReturn"] is True

    deny_return(conn, return_id, LIBRARIAN)                                # denied: access comes back
    loan = by_book(student_loans(conn, STUDENT, today, NONE), "DIG-001")
    assert loan["DigitalLink"] == "https://example.com/read"

    return_id = request_return(conn, STUDENT, 4, NOV3)["ReturnID"]
    approve_return(conn, return_id, LIBRARIAN, NONE)                       # approved: the loan is gone
    assert all(l["BookID"] != "DIG-001" for l in student_loans(conn, STUDENT, today, NONE))


def test_pending_borrow_has_no_dates_or_link():
    conn = make_clean_db()
    conn.execute(
        "INSERT INTO Book (BookID, BookTitle, BookAuthor, BookType, DigitalLink) "
        "VALUES ('DIG-002', 'E-book 2', 'Auth', 'Digital', 'https://example.com/two')"
    )
    conn.execute(
        "INSERT INTO Borrow (StudentID, BookID, RequestedAt, Status) "
        "VALUES (?, 'DIG-002', '2026-11-03 09:00:00', 'Pending')",
        (STUDENT,),
    )
    loan = by_book(student_loans(conn, STUDENT, date(2026, 11, 3), NONE), "DIG-002")
    assert loan["Status"] == "Pending"
    assert loan["DueDate"] is None and loan["DigitalLink"] is None and loan["Fine"] == 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"All {len(tests)} renew/return tests passed!")
