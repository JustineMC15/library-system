"""Tests for the renew, return, Process Return, fine and student-detail routes.
Run from the backend folder:  python test_routes_renew_return.py

Test data comes from make_env() in test_routes.py (today is Tuesday 2026-11-03):
  S3 holds BorrowID 1 (B6, borrowed Oct 20, due Oct 28: overdue)
  S4 holds BorrowIDs 2, 3, 4 (borrowed Nov 2, due Nov 10) and is at the borrow limit
"""
from datetime import datetime
import sqlite3
import clock
from app import app
from test_routes import NOW, login, make_env, request_book, row

def run_sql(path, statement, params=()):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    new_id = conn.execute(statement, params).lastrowid
    conn.commit()
    conn.close()
    return new_id


def add_digital_loan(path, student, borrow_date="2026-10-20"):
    """Only e-books can be returned online, so these tests use one. DIG-001 is free in make_env()."""
    return run_sql(
        path,
        "INSERT INTO Borrow (StudentID, BookID, LibrarianID, RequestedAt, BorrowDate, Status) "
        "VALUES (?, 'DIG-001', 'L1', '2026-10-01 09:00:00', ?, 'Borrowed')",
        (student, borrow_date),
    )

def test_renew_and_return_need_student_login():
    make_env()
    anon, lib = app.test_client(), login("librarian", "L1")
    for url in ("/api/renew", "/api/return"):
        assert anon.post(url, json={"BorrowID": 2}).status_code == 401
        assert lib.post(url, json={"BorrowID": 2}).status_code == 403


def test_borrow_accepts_snake_case_body():
    make_env()
    assert login("student", "S1").post("/api/borrow", json={"book_id": "B1"}).status_code == 201


def test_renew_request_and_approve():
    make_env()
    s4, lib = login("student", "S4"), login("librarian", "L1")

    assert s4.post("/api/renew", json={}).status_code == 400
    assert s4.post("/api/renew", json={"BorrowID": "2"}).status_code == 400
    assert login("student", "S3").post("/api/renew", json={"BorrowID": 2}).status_code == 404   # not S3's book

    r = s4.post("/api/renew", json={"BorrowID": 2})
    assert r.status_code == 201 and r.get_json()["ok"] is True
    renew_id = r.get_json()["RenewID"]
    assert s4.post("/api/renew", json={"borrow_id": 2}).status_code == 409                        # already pending

    queue = lib.get("/api/librarian/queue").get_json()
    assert [(q["type"], q["BorrowID"], q["DueDate"], q["StudentName"]) for q in queue] == [
        ("renew", 2, "2026-11-10", "LastS4, Test Q.")
    ]

    def loan():
        return next(l for l in s4.get("/api/student/loans").get_json() if l["BorrowID"] == 2)

    assert loan()["PendingRenew"] is True and loan()["Renewals"] == 0

    assert lib.post(f"/api/librarian/renew/{renew_id}/approve", json={}).status_code == 200
    assert loan()["PendingRenew"] is False
    assert loan()["Renewals"] == 1
    assert loan()["DueDate"] == "2026-11-11"
    assert lib.get("/api/librarian/queue").get_json() == []


def test_overdue_book_cannot_be_renewed():
    make_env()
    r = login("student", "S3").post("/api/renew", json={"BorrowID": 1})
    assert r.status_code == 409
    assert r.get_json()["error"] == "Overdue books cannot be renewed"


def test_deny_renew_needs_no_reasons():
    make_env()
    s4, lib = login("student", "S4"), login("librarian", "L1")
    renew_id = s4.post("/api/renew", json={"BorrowID": 2}).get_json()["RenewID"]
    assert lib.post(f"/api/librarian/renew/{renew_id}/deny", json={}).status_code == 200
    assert lib.post(f"/api/librarian/renew/{renew_id}/deny", json={}).status_code == 409          # already decided
    assert s4.post("/api/renew", json={"BorrowID": 2}).status_code == 201                         # can ask again


def test_missing_renew_or_return_is_404():
    make_env()
    lib = login("librarian", "L1")
    for kind in ("renew", "return"):
        assert lib.post(f"/api/librarian/{kind}/999/approve", json={}).status_code == 404
        assert lib.post(f"/api/librarian/{kind}/999/deny", json={}).status_code == 404


def test_return_request_ends_digital_access():
    make_env()
    s1, lib = login("student", "S1"), login("librarian", "L1")
    borrow_id = request_book(s1, "DIG-001").get_json()["BorrowID"]
    lib.post(f"/api/librarian/borrow/{borrow_id}/approve", json={"student_id_ok": True})

    def loan():
        return s1.get("/api/student/loans").get_json()[0]

    assert loan()["DigitalLink"] == "https://example.com/read"

    r = s1.post("/api/return", json={"BorrowID": borrow_id})
    assert r.status_code == 201
    return_id = r.get_json()["ReturnID"]
    assert loan()["DigitalLink"] is None and loan()["PendingReturn"] is True
    assert s1.post("/api/return", json={"BorrowID": borrow_id}).status_code == 409                # already pending
    assert s1.post("/api/renew", json={"BorrowID": borrow_id}).status_code == 409                 # nothing else while pending

    assert lib.post(f"/api/librarian/return/{return_id}/deny", json={}).status_code == 200
    assert loan()["DigitalLink"] == "https://example.com/read"                                    # denied: access is back


def test_return_fine_stops_at_request_date_and_can_be_paid():
    path = make_env()
    s2, lib = login("student", "S2"), login("librarian", "L1")
    borrow_id = add_digital_loan(path, "S2")

    clock.now = lambda: datetime(2026, 11, 2, 10, 0, 0)          # Monday: 4 working days overdue
    r = s2.post("/api/return", json={"BorrowID": borrow_id})
    assert r.status_code == 201
    return_id = r.get_json()["ReturnID"]

    clock.now = lambda: NOW                                        # approved a day later, Tuesday Nov 3
    queue = lib.get("/api/librarian/queue").get_json()
    assert queue[0]["type"] == "return" and queue[0]["BorrowID"] == borrow_id and queue[0]["DueDate"] == "2026-10-28"

    res = lib.post(f"/api/librarian/return/{return_id}/approve", json={})
    assert res.status_code == 200 and res.get_json()["FineAmount"] == 8        # not 10
    saved = row(path, 'SELECT * FROM "Return" WHERE ReturnID = ?', (return_id,))[0]
    assert saved["ReturnDate"] == "2026-11-02" and saved["Status"] == "Approved" and saved["LibrarianID"] == "L1"
    assert row(path, "SELECT Status FROM Borrow WHERE BorrowID = ?", (borrow_id,))[0]["Status"] == "Returned"

    detail = lib.get("/api/librarian/students/S2").get_json()
    assert detail["FineOwed"] == 8 and detail["checks"]["Unpaid fines"] is True

    assert lib.post("/api/librarian/students/S2/pay-fines").status_code == 200
    assert lib.get("/api/librarian/students/S2").get_json()["FineOwed"] == 0
    assert lib.post("/api/librarian/students/S2/pay-fines").status_code == 409
    assert lib.post("/api/librarian/students/NOPE/pay-fines").status_code == 404


def test_pay_one_fine_route():
    path = make_env()
    s2, lib = login("student", "S2"), login("librarian", "L1")
    borrow_id = add_digital_loan(path, "S2")
    return_id = s2.post("/api/return", json={"BorrowID": borrow_id}).get_json()["ReturnID"]   # today: 5 days = 10
    assert lib.post(f"/api/librarian/fine/{return_id}/paid").status_code == 404        # not approved yet
    assert lib.post(f"/api/librarian/return/{return_id}/approve", json={}).get_json()["FineAmount"] == 10
    assert lib.post(f"/api/librarian/fine/{return_id}/paid").status_code == 200
    assert lib.post(f"/api/librarian/fine/{return_id}/paid").status_code == 409
    assert lib.post("/api/librarian/fine/999/paid").status_code == 404
    assert s2.post(f"/api/librarian/fine/{return_id}/paid").status_code == 403


def test_process_return_route():
    path = make_env()
    lib = login("librarian", "L1")
    url = "/api/librarian/returns"

    assert login("student", "S4").post(url, json={"BorrowID": 2}).status_code == 403
    assert app.test_client().post(url, json={"BorrowID": 2}).status_code == 401
    assert lib.post(url, json={"ReturnDate": "2026-11-03"}).status_code == 400                    # no BorrowID
    assert lib.post(url, json={"BorrowID": 2, "ReturnDate": "not a date"}).status_code == 400
    assert lib.post(url, json={"BorrowID": 2, "ReturnDate": "2026-11-04"}).status_code == 400     # future
    assert lib.post(url, json={"BorrowID": 2, "ReturnDate": "2026-11-01"}).status_code == 409     # before Nov 2 borrow
    assert lib.post(url, json={"BorrowID": 999, "ReturnDate": "2026-11-03"}).status_code == 404

    r = lib.post(url, json={"borrow_id": 2, "return_date": "2026-11-03"})
    assert r.status_code == 200 and r.get_json()["FineAmount"] == 0
    assert row(path, "SELECT Status FROM Borrow WHERE BorrowID = 2")[0]["Status"] == "Returned"
    assert lib.post(url, json={"BorrowID": 2}).status_code == 404                                 # already returned

    # a missing date means today; S3's book is 5 working days overdue
    r = lib.post(url, json={"BorrowID": 1})
    assert r.status_code == 200 and r.get_json()["FineAmount"] == 10 and r.get_json()["ReturnDate"] == "2026-11-03"


def test_student_detail_for_verify_and_return_pages():
    path = make_env()
    lib = login("librarian", "L1")

    d = lib.get("/api/librarian/students/S4").get_json()
    assert d["StudentID"] == "S4" and d["FirstName"] == "Test" and "PasswordHash" not in d
    assert d["FineOwed"] == 0 and d["pending"] == []
    assert d["checks"]["Borrow limit reached"] is True and d["checks"]["Unreturned books"] is False
    assert [l["BorrowID"] for l in d["loans"]] == [2, 3, 4]
    assert all(l["DueDate"] == "2026-11-10" for l in d["loans"])
    assert all(l["ReturnRequestedAt"] is None for l in d["loans"])

    assert lib.get("/api/librarian/students/S1").get_json()["contacts"] == ["0917", "0918"]
    assert lib.get("/api/librarian/students/S3").get_json()["checks"]["Unreturned books"] is True
    assert lib.get("/api/librarian/students/S5").get_json()["checks"]["Suspension of privileges"] is True

    request_book(login("student", "S4"), "B1")
    assert [p["BookID"] for p in lib.get("/api/librarian/students/S4").get_json()["pending"]] == ["B1"]

    run_sql(path, 'INSERT INTO "Return" (BorrowID, RequestedAt, Status) VALUES (3, ?, \'Pending\')',
            ("2026-11-03 10:00:00",))
    loans = lib.get("/api/librarian/students/S4").get_json()["loans"]
    assert [l["ReturnRequestedAt"] for l in loans] == [None, "2026-11-03 10:00:00", None]

    assert lib.get("/api/librarian/students/NOPE").status_code == 404
    assert login("student", "S1").get("/api/librarian/students/S4").status_code == 403
    assert app.test_client().get("/api/librarian/students/S4").status_code == 401


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"All {len(tests)} renew/return route tests passed!")

def test_physical_return_must_go_through_the_desk():
    make_env()
    s3, lib = login("student", "S3"), login("librarian", "L1")
    r = s3.post("/api/return", json={"BorrowID": 1})
    assert r.status_code == 409
    assert r.get_json()["error"] == "Physical books are returned at the library desk"
    assert lib.get("/api/librarian/queue").get_json() == []
    loan = next(l for l in s3.get("/api/student/loans").get_json() if l["BorrowID"] == 1)
    assert loan["Fine"] == 10 and loan["PendingReturn"] is False                      # the fine keeps counting
    assert login("student", "S1").post("/api/return", json={"BorrowID": 1}).status_code == 404   # not S1's loan


def test_student_history_route():
    make_env()
    s3, s4, lib = login("student", "S3"), login("student", "S4"), login("librarian", "L1")
    assert s3.get("/api/student/history").get_json() == []

    assert lib.post("/api/librarian/returns", json={"BorrowID": 1}).status_code == 200           # fine 10
    assert s3.get("/api/student/history").get_json() == [{
        "BorrowID": 1, "BookID": "B6", "BookTitle": "Book 6", "BookType": "Physical",
        "BorrowDate": "2026-10-20", "ReturnDate": "2026-11-03", "Status": "Returned",
        "FineAmount": 10, "FinePaidDate": None,
    }]
    lib.post("/api/librarian/students/S3/pay-fines")
    assert s3.get("/api/student/history").get_json()[0]["FinePaidDate"] == "2026-11-03"

    lib.post("/api/librarian/returns", json={"BorrowID": 3, "ReturnDate": "2026-11-02"})
    lib.post("/api/librarian/returns", json={"BorrowID": 2})
    history = s4.get("/api/student/history").get_json()
    assert [h["BorrowID"] for h in history] == [2, 3]            # newest return first; BorrowID 4 is still out
    assert all(h["FineAmount"] == 0 and h["FinePaidDate"] is None for h in history)

    assert app.test_client().get("/api/student/history").status_code == 401
    assert lib.get("/api/student/history").status_code == 403