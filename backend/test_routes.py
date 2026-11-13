"""Tests for the borrow, queue, verify, approve and deny routes.
Run from the backend folder:  python test_routes.py"""
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from werkzeug.security import generate_password_hash

import clock
import db
from app import app

NOW = datetime(2026, 11, 3, 10, 0, 0)       # a Tuesday
SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
PASSWORD = "pw"


def make_env(now=NOW):
    """Build a fresh database, point the app at it, and freeze the clock."""
    path = Path(tempfile.mkdtemp()) / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    pw = generate_password_hash(PASSWORD)

    # S1 clean, S2 clean, S3 has an overdue book, S4 is at the borrow limit, S5 is suspended
    for sid, status in [("S1", "Active"), ("S2", "Active"), ("S3", "Active"), ("S4", "Active"), ("S5", "Suspended")]:
        conn.execute(
            "INSERT INTO Student (StudentID, LastName, FirstName, MiddleInitial, Address, DateOfBirth, PasswordHash, Status) "
            "VALUES (?, ?, 'Test', 'Q', 'Marikina', '2007-01-05', ?, ?)",
            (sid, "Last" + sid, pw, status),
        )
    conn.execute("INSERT INTO StudentContact VALUES ('S1', '0917')")
    conn.execute("INSERT INTO StudentContact VALUES ('S1', '0918')")
    conn.execute("INSERT INTO Librarian VALUES ('L1', 'Lib One', ?)", (pw,))

    for i in range(1, 9):
        conn.execute(
            "INSERT INTO Book (BookID, BookTitle, BookAuthor, BookType) VALUES (?, ?, 'Auth', 'Physical')",
            (f"B{i}", f"Book {i}"),
        )
    conn.execute(
        "INSERT INTO Book (BookID, BookTitle, BookAuthor, BookType, DigitalLink) "
        "VALUES ('DIG-001', 'E-book', 'Auth', 'Digital', 'https://example.com/read')"
    )

    def loan(student, book, borrow_date):
        conn.execute(
            "INSERT INTO Borrow (StudentID, BookID, LibrarianID, RequestedAt, BorrowDate, Status) "
            "VALUES (?, ?, 'L1', '2026-10-01 09:00:00', ?, 'Borrowed')",
            (student, book, borrow_date),
        )

    loan("S3", "B6", "2026-10-20")          # due Oct 28, so overdue on Nov 3
    for book in ("B3", "B4", "B5"):
        loan("S4", book, "2026-11-02")      # three loans, not overdue
    conn.commit()
    conn.close()

    db.DB_PATH = path
    clock.now = lambda: now
    return path


def login(role, user_id):
    client = app.test_client()
    r = client.post("/api/login", json={"role": role, "id": user_id, "password": PASSWORD})
    assert r.status_code == 200, r.get_json()
    return client


def row(path, sql, params=()):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    result = conn.execute(sql, params).fetchall()
    conn.close()
    return result


def request_book(student_client, book_id):
    return student_client.post("/api/borrow", json={"BookID": book_id})


# ---------- student borrow ----------

def test_borrow_needs_student_login():
    make_env()
    assert app.test_client().post("/api/borrow", json={"BookID": "B1"}).status_code == 401
    assert request_book(login("librarian", "L1"), "B1").status_code == 403


def test_borrow_creates_pending_request():
    path = make_env()
    r = request_book(login("student", "S1"), "B1")
    assert r.status_code == 201 and r.get_json()["ok"] is True

    saved = row(path, "SELECT * FROM Borrow WHERE BorrowID = ?", (r.get_json()["BorrowID"],))[0]
    assert saved["Status"] == "Pending"
    assert saved["StudentID"] == "S1"
    assert saved["RequestedAt"] == "2026-11-03 10:00:00"
    assert saved["BorrowDate"] is None


def test_borrow_errors():
    make_env()
    s1, s2 = login("student", "S1"), login("student", "S2")
    assert request_book(s1, "B1").status_code == 201
    assert request_book(s2, "B1").status_code == 409          # the single copy is held
    assert request_book(s1, "NOPE").status_code == 404
    assert s1.post("/api/borrow", json={}).status_code == 400
    assert s1.post("/api/borrow", json={"BookID": 5}).status_code == 400
    assert s1.post("/api/borrow", data="not json").status_code == 400


def test_borrow_book_id_with_spaces():
    path = make_env()
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO Book (BookID, BookTitle, BookAuthor, BookType) VALUES ('FIL QA 76.7 L926', 'T', 'A', 'Physical')")
    conn.commit()
    conn.close()
    assert request_book(login("student", "S1"), "FIL QA 76.7 L926").status_code == 201


# ---------- queue ----------

def test_queue_order_names_and_filter():
    make_env()
    s1, s2, lib = login("student", "S1"), login("student", "S2"), login("librarian", "L1")
    clock.now = lambda: datetime(2026, 11, 3, 10, 0, 0)
    request_book(s1, "B1")
    clock.now = lambda: datetime(2026, 11, 3, 10, 5, 0)
    request_book(s2, "B2")

    queue = lib.get("/api/librarian/queue").get_json()
    assert [q["BookID"] for q in queue] == ["B1", "B2"]
    assert [q["earlier_pending"] for q in queue] == [0, 1]
    assert queue[0]["StudentName"] == "LastS1, Test Q."
    assert queue[0]["BookTitle"] == "Book 1"

    only = lib.get("/api/librarian/queue?type=borrow").get_json()
    assert len(only) == 2
    assert lib.get("/api/librarian/queue?type=renew").get_json() == []
    assert lib.get("/api/librarian/queue?type=bogus").status_code == 400


def test_librarian_routes_reject_students_and_strangers():
    make_env()
    student = login("student", "S1")
    for client in (student, app.test_client()):
        expected = 403 if client is student else 401
        assert client.get("/api/librarian/queue").status_code == expected
        assert client.get("/api/librarian/request/borrow/1").status_code == expected
        assert client.post("/api/librarian/borrow/1/approve", json={}).status_code == expected
        assert client.post("/api/librarian/borrow/1/deny", json={"reasons": ["Unpaid fines"]}).status_code == expected


# ---------- verify page data ----------

def test_detail_clean_student():
    make_env()
    request_book(login("student", "S1"), "B1")
    r = login("librarian", "L1").get("/api/librarian/request/borrow/5").get_json()   # 4 seeded loans come first
    assert r["ok"] is True and r["status"] == "Pending"
    assert r["earlier_pending"] == 0
    assert r["student"]["Name"] == "LastS1, Test Q."
    assert r["student"]["Age"] == 19            # born 2007-01-05, today 2026-11-03
    assert r["student"]["Contacts"] == ["0917", "0918"]
    assert r["book"]["BookTitle"] == "Book 1"
    assert [c["name"] for c in r["checks"]] == [
        "Unreturned books", "Unpaid fines", "Borrow limit reached", "No valid Student ID", "Suspension of privileges"
    ]
    auto = [c["failed"] for c in r["checks"]]
    assert auto == [False, False, False, None, False]
    assert r["any_failed"] is False


def test_detail_failed_checks():
    make_env()
    request_book(login("student", "S3"), "B1")     # S3 has an overdue book
    request_book(login("student", "S4"), "B2")     # S4 is at the limit
    request_book(login("student", "S5"), "B7")     # S5 is suspended
    lib = login("librarian", "L1")

    def failed(borrow_id):
        r = lib.get(f"/api/librarian/request/borrow/{borrow_id}").get_json()
        return [c["name"] for c in r["checks"] if c["failed"]], r["any_failed"]

    assert failed(5) == (["Unreturned books"], True)
    assert failed(6) == (["Borrow limit reached"], True)
    assert failed(7) == (["Suspension of privileges"], True)


def test_detail_other_types_and_missing():
    make_env()
    lib = login("librarian", "L1")
    assert lib.get("/api/librarian/request/renew/1").status_code == 501
    assert lib.get("/api/librarian/request/return/1").status_code == 501
    assert lib.get("/api/librarian/request/banana/1").status_code == 404
    assert lib.get("/api/librarian/request/borrow/999").status_code == 404


def test_detail_shows_skipped_requests():
    make_env()
    request_book(login("student", "S1"), "B1")
    clock.now = lambda: datetime(2026, 11, 3, 11, 0, 0)
    request_book(login("student", "S2"), "B2")
    lib = login("librarian", "L1")
    assert lib.get("/api/librarian/request/borrow/5").get_json()["earlier_pending"] == 0
    assert lib.get("/api/librarian/request/borrow/6").get_json()["earlier_pending"] == 1


# ---------- approve ----------

def test_approve_success_and_student_sees_link():
    path = make_env()
    s1, lib = login("student", "S1"), login("librarian", "L1")
    borrow_id = request_book(s1, "DIG-001").get_json()["BorrowID"]

    before = s1.get("/api/student/loans").get_json()
    assert before[0]["Status"] == "Pending" and before[0]["DigitalLink"] is None

    r = lib.post(f"/api/librarian/borrow/{borrow_id}/approve", json={"student_id_ok": True})
    assert r.status_code == 200 and r.get_json()["ok"] is True

    saved = row(path, "SELECT * FROM Borrow WHERE BorrowID = ?", (borrow_id,))[0]
    assert saved["Status"] == "Borrowed"
    assert saved["BorrowDate"] == "2026-11-03"
    assert saved["LibrarianID"] == "L1"

    after = s1.get("/api/student/loans").get_json()
    assert after[0]["Status"] == "Borrowed"
    assert after[0]["DigitalLink"] == "https://example.com/read"


def test_approve_needs_confirmed_student_id():
    path = make_env()
    borrow_id = request_book(login("student", "S1"), "B1").get_json()["BorrowID"]
    lib = login("librarian", "L1")
    for body in ({}, {"student_id_ok": False}, {"student_id_ok": "true"}, {"student_id_ok": 1}):
        r = lib.post(f"/api/librarian/borrow/{borrow_id}/approve", json=body)
        assert r.status_code == 409
        assert r.get_json()["reasons"] == ["No valid Student ID"]
    assert row(path, "SELECT Status FROM Borrow WHERE BorrowID = ?", (borrow_id,))[0]["Status"] == "Pending"


def test_approve_refused_when_a_check_fails():
    path = make_env()
    borrow_id = request_book(login("student", "S3"), "B1").get_json()["BorrowID"]
    r = login("librarian", "L1").post(f"/api/librarian/borrow/{borrow_id}/approve", json={"student_id_ok": True})
    assert r.status_code == 409
    assert r.get_json()["reasons"] == ["Unreturned books"]
    assert row(path, "SELECT Status FROM Borrow WHERE BorrowID = ?", (borrow_id,))[0]["Status"] == "Pending"


def test_approve_twice_and_missing():
    make_env()
    borrow_id = request_book(login("student", "S1"), "B1").get_json()["BorrowID"]
    lib = login("librarian", "L1")
    url = f"/api/librarian/borrow/{borrow_id}/approve"
    assert lib.post(url, json={"student_id_ok": True}).status_code == 200
    assert lib.post(url, json={"student_id_ok": True}).status_code == 409
    assert lib.post("/api/librarian/borrow/999/approve", json={"student_id_ok": True}).status_code == 404


# ---------- deny ----------

def test_deny_saves_every_reason_and_student_sees_them():
    path = make_env()
    s3, lib = login("student", "S3"), login("librarian", "L1")
    borrow_id = request_book(s3, "B1").get_json()["BorrowID"]

    r = lib.post(
        f"/api/librarian/borrow/{borrow_id}/deny",
        json={"reasons": ["Suspension of privileges", "Unreturned books", "Unreturned books"]},
    )
    assert r.status_code == 200
    saved = row(path, "SELECT * FROM Borrow WHERE BorrowID = ?", (borrow_id,))[0]
    assert saved["Status"] == "Denied" and saved["LibrarianID"] == "L1"

    denied = s3.get("/api/student/denied").get_json()
    assert len(denied) == 1
    assert denied[0]["BookTitle"] == "Book 1"
    assert denied[0]["reasons"] == ["Unreturned books", "Suspension of privileges"]   # page order
    assert login("student", "S1").get("/api/student/denied").get_json() == []          # not someone else's

    # the denied request no longer holds the book
    assert request_book(login("student", "S1"), "B1").status_code == 201


def test_deny_validation():
    path = make_env()
    borrow_id = request_book(login("student", "S1"), "B1").get_json()["BorrowID"]
    lib = login("librarian", "L1")
    url = f"/api/librarian/borrow/{borrow_id}/deny"
    for body in ({}, {"reasons": []}, {"reasons": "Unpaid fines"}, {"reasons": ["Late fee"]}, {"reasons": [{"a": 1}]}):
        assert lib.post(url, json=body).status_code == 400
    assert row(path, "SELECT Status FROM Borrow WHERE BorrowID = ?", (borrow_id,))[0]["Status"] == "Pending"
    assert lib.post("/api/librarian/borrow/999/deny", json={"reasons": ["Unpaid fines"]}).status_code == 404


def test_deny_after_approve_is_refused():
    make_env()
    borrow_id = request_book(login("student", "S1"), "B1").get_json()["BorrowID"]
    lib = login("librarian", "L1")
    lib.post(f"/api/librarian/borrow/{borrow_id}/approve", json={"student_id_ok": True})
    r = lib.post(f"/api/librarian/borrow/{borrow_id}/deny", json={"reasons": ["Unpaid fines"]})
    assert r.status_code == 409


def test_nonworking_day_changes_overdue_check():
    path = make_env()
    conn = sqlite3.connect(path)
    for d in ("2026-10-29", "2026-10-30", "2026-10-31", "2026-11-02", "2026-11-03"):
        conn.execute("INSERT INTO NonWorkingDay VALUES (?, 'Holiday', 'L1')", (d,))
    conn.commit()
    conn.close()
    borrow_id = request_book(login("student", "S3"), "B1").get_json()["BorrowID"]
    r = login("librarian", "L1").post(f"/api/librarian/borrow/{borrow_id}/approve", json={"student_id_ok": True})
    assert r.status_code == 200


# ---------- register and /api/me ----------

def test_register_and_me():
    path = make_env()
    client = app.test_client()
    body = {"student_id": "25A-7777", "last_name": "Cruz", "first_name": "Ana", "middle_initial": "r",
            "date_of_birth": "2007-01-05", "contact_numbers": ["0917", "0917", " "], "password": "secret1"}
    assert client.post("/api/register", json=body).status_code == 201
    assert client.post("/api/register", json=body).status_code == 409                       # same ID again
    assert client.post("/api/register", json={**body, "student_id": "X1", "date_of_birth": "2999-01-01"}).status_code == 400
    assert client.post("/api/register", json={**body, "student_id": "X2", "contact_numbers": "0917"}).status_code == 400
    assert row(path, "SELECT MiddleInitial FROM Student WHERE StudentID = '25A-7777'")[0]["MiddleInitial"] == "R"
    assert [r["ContactNo"] for r in row(path, "SELECT ContactNo FROM StudentContact WHERE StudentID = '25A-7777'")] == ["0917"]

    assert client.post("/api/login", json={"role": "student", "id": "25A-7777", "password": "secret1"}).status_code == 200
    me = client.get("/api/me").get_json()
    assert (me["FirstName"], me["LastName"], me["Status"]) == ("Ana", "Cruz", "Active")

    lib = login("librarian", "L1")
    assert lib.get("/api/me").get_json()["LibrarianName"] == "Lib One"

def test_register_librarian_needs_librarian_login():
    path = make_env()
    url = "/api/librarian/register"
    body = {"librarian_id": "L2", "librarian_name": "Lib Two", "password": "secret1"}
    assert app.test_client().post(url, json=body).status_code == 401
    assert login("student", "S1").post(url, json=body).status_code == 403
    lib = login("librarian", "L1")
    assert lib.post(url, json=body).status_code == 201
    assert lib.post(url, json=body).status_code == 409
    assert row(path, "SELECT LibrarianName FROM Librarian WHERE LibrarianID = 'L2'")[0]["LibrarianName"] == "Lib Two"


def test_denied_shows_fine_owed():
    make_env()
    s3, lib = login("student", "S3"), login("librarian", "L1")
    assert lib.post("/api/librarian/returns", json={"BorrowID": 1}).get_json()["FineAmount"] == 10
    borrow_id = request_book(s3, "B1").get_json()["BorrowID"]
    lib.post(f"/api/librarian/borrow/{borrow_id}/deny", json={"reasons": ["Unpaid fines"]})
    assert s3.get("/api/student/denied").get_json()[0]["FineOwed"] == 10
    lib.post("/api/librarian/students/S3/pay-fines")
    assert s3.get("/api/student/denied").get_json()[0]["FineOwed"] == 0

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"All {len(tests)} route tests passed!")
