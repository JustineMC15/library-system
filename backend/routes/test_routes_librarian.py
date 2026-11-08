"""Tests for the librarian dashboard routes (stats, overdue, history) and non-working days.
Run from the backend folder:  python test_routes_librarian.py

Test data comes from make_env() in test_routes.py (today is Tuesday 2026-11-03):
  S3 holds BorrowID 1 (B6, borrowed Oct 20, due Oct 28: 5 working days overdue)
  S4 holds BorrowIDs 2, 3, 4 (B3, B4, B5, borrowed Nov 2, due Nov 10)
Extra rows are added with plain SQL, so these tests only depend on login.
"""
import sqlite3
from datetime import date

from app import app
from calendar_db import load_nonworking
from loans import get_due_date
from test_routes import login, make_env, row

LIBRARIAN_ROUTES = [
    ("get", "/api/librarian/stats"),
    ("get", "/api/librarian/overdue"),
    ("get", "/api/librarian/history"),
    ("get", "/api/librarian/nonworking/impact?date=2026-11-04"),
    ("post", "/api/librarian/nonworking"),
    ("delete", "/api/librarian/nonworking/2026-11-04"),
]
NW = "/api/librarian/nonworking"


def sql(path, statement, params=()):
    """Run one write and return the new row's id."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.execute(statement, params)
    conn.commit()
    conn.close()
    return cursor.lastrowid


def add_loan(path, student, book, requested, borrow_date, status="Borrowed"):
    return sql(
        path,
        "INSERT INTO Borrow (StudentID, BookID, LibrarianID, RequestedAt, BorrowDate, Status) "
        "VALUES (?, ?, 'L1', ?, ?, ?)",
        (student, book, requested, borrow_date, status),
    )


def due_of(path, borrow_id):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return get_due_date(conn, borrow_id, load_nonworking(conn))
    finally:
        conn.close()


# ---------- access ----------

def test_librarian_routes_reject_students_and_strangers():
    make_env()
    student, anon = login("student", "S1"), app.test_client()
    for client, expected in ((student, 403), (anon, 401)):
        for method, url in LIBRARIAN_ROUTES:
            assert getattr(client, method)(url).status_code == expected, (method, url)


# ---------- stats and overdue ----------

def test_stats_and_overdue_start_state():
    make_env()
    lib = login("librarian", "L1")
    assert lib.get("/api/librarian/stats").get_json() == {"borrows_today": 0, "returns_today": 0, "overdue": 1}

    rows = lib.get("/api/librarian/overdue").get_json()
    assert len(rows) == 1
    o = rows[0]
    assert (o["BorrowID"], o["StudentID"], o["StudentName"], o["BookTitle"]) == (1, "S3", "LastS3, Test Q.", "Book 6")
    assert (o["DueDate"], o["DaysLate"], o["Fine"], o["ReturnPending"]) == ("2026-10-28", 5, 10, False)


def test_stats_count_today_and_overdue_is_sorted():
    path = make_env()
    lib = login("librarian", "L1")

    add_loan(path, "S1", "B1", "2026-11-03 09:00:00", "2026-11-03")           # approved today
    older = add_loan(path, "S2", "B2", "2026-10-22 09:00:00", "2026-10-22")   # due Oct 30, 3 days late
    sql(path, "UPDATE Borrow SET Status = 'Returned' WHERE BorrowID = 2")      # S4 gives a book back today
    sql(path, 'INSERT INTO "Return" (BorrowID, LibrarianID, RequestedAt, ReturnDate, FineAmount, Status) '
              "VALUES (2, 'L1', '2026-11-03 09:30:00', '2026-11-03', 0, 'Approved')")

    stats = lib.get("/api/librarian/stats").get_json()
    assert stats == {"borrows_today": 1, "returns_today": 1, "overdue": 2}

    rows = lib.get("/api/librarian/overdue").get_json()
    assert [(o["BorrowID"], o["DaysLate"], o["Fine"]) for o in rows] == [(1, 5, 10), (older, 3, 6)]


def test_overdue_fine_stops_at_pending_return_request():
    path = make_env()
    lib = login("librarian", "L1")
    sql(path, 'INSERT INTO "Return" (BorrowID, RequestedAt, Status) VALUES (1, \'2026-11-02 10:00:00\', \'Pending\')')

    rows = lib.get("/api/librarian/overdue").get_json()
    assert len(rows) == 1                                  # still unreturned, so still listed
    assert (rows[0]["DaysLate"], rows[0]["Fine"], rows[0]["ReturnPending"]) == (4, 8, True)   # Monday, not Tuesday
    assert lib.get("/api/librarian/stats").get_json()["overdue"] == 1


def test_overdue_follows_nonworking_days():
    path = make_env()
    for d in ("2026-10-29", "2026-10-30", "2026-10-31", "2026-11-02", "2026-11-03"):
        sql(path, "INSERT INTO NonWorkingDay VALUES (?, 'Holiday', 'L1')", (d,))
    lib = login("librarian", "L1")
    # S3's book is due Nov 3 now, so nothing is overdue
    assert lib.get("/api/librarian/overdue").get_json() == []
    assert lib.get("/api/librarian/stats").get_json()["overdue"] == 0


# ---------- history ----------

def test_history_lists_only_decided_requests():
    path = make_env()
    lib = login("librarian", "L1")

    add_loan(path, "S2", "B2", "2026-11-03 09:30:00", None, "Denied")
    add_loan(path, "S1", "B7", "2026-11-03 09:45:00", None, "Pending")                  # not decided: left out
    sql(path, "INSERT INTO Renew (BorrowID, LibrarianID, RequestedAt, RenewalDate, Status) "
              "VALUES (2, 'L1', '2026-11-03 09:00:00', '2026-11-03', 'Approved')")
    sql(path, "INSERT INTO Renew (BorrowID, RequestedAt, Status) VALUES (3, '2026-11-03 09:10:00', 'Pending')")  # left out
    sql(path, 'INSERT INTO "Return" (BorrowID, LibrarianID, RequestedAt, Status) '
              "VALUES (4, 'L1', '2026-11-03 09:20:00', 'Denied')")

    everything = lib.get("/api/librarian/history").get_json()
    assert {h["Status"] for h in everything} == {"Approved", "Denied"}
    assert all("B7" != h["BookID"] for h in everything)
    stamps = [h["RequestedAt"] for h in everything]
    assert stamps == sorted(stamps, reverse=True)                                       # newest first

    renew = lib.get("/api/librarian/history?type=renew").get_json()
    assert len(renew) == 1
    assert (renew[0]["Status"], renew[0]["StudentName"], renew[0]["BookTitle"], renew[0]["LibrarianID"]) == \
        ("Approved", "LastS4, Test Q.", "Book 3", "L1")

    returns = lib.get("/api/librarian/history?type=return").get_json()
    assert [(h["Status"], h["BookID"]) for h in returns] == [("Denied", "B5")]

    borrows = lib.get("/api/librarian/history?type=borrow").get_json()
    denied = [h for h in borrows if h["Status"] == "Denied"]
    assert [(h["StudentID"], h["BookID"]) for h in denied] == [("S2", "B2")]
    assert sum(1 for h in borrows if h["Status"] == "Approved") == 4                    # the four seeded loans


def test_history_limit_and_validation():
    make_env()
    lib = login("librarian", "L1")
    assert len(lib.get("/api/librarian/history?limit=2").get_json()) == 2
    assert lib.get("/api/librarian/history?type=bogus").status_code == 400
    assert lib.get("/api/librarian/history?limit=abc").status_code == 400


# ---------- non-working days ----------

def test_nonworking_list_needs_login_but_not_librarian():
    path = make_env()
    sql(path, "INSERT INTO NonWorkingDay VALUES ('2026-12-25', 'Holiday', 'L1')")
    assert app.test_client().get("/api/nonworking").status_code == 401
    expected = [{"NonWorkingDate": "2026-12-25", "Reason": "Holiday", "LibrarianID": "L1"}]
    assert login("student", "S1").get("/api/nonworking").get_json() == expected
    assert login("librarian", "L1").get("/api/nonworking").get_json() == expected


def test_mark_validation():
    make_env()
    lib = login("librarian", "L1")
    for body in (
        {},
        {"date": "2026-11-04"},                                    # no reason
        {"date": "2026-11-04", "reason": "Party"},
        {"date": "11/04/2026", "reason": "Holiday"},
        {"date": 20261104, "reason": "Holiday"},
        {"date": "2026-11-02", "reason": "Holiday"},               # yesterday
        {"date": "2026-11-08", "reason": "Holiday"},               # a Sunday
    ):
        assert lib.post(NW, json=body).status_code == 400, body
    assert lib.get("/api/nonworking").get_json() == []


def test_mark_moves_due_dates_and_unmark_moves_them_back():
    path = make_env()
    lib = login("librarian", "L1")

    # S4's three loans (due Nov 10) cover Nov 4; S3's loan (due Oct 28) does not
    assert lib.get(NW + "/impact?date=2026-11-04").get_json() == {"borrowed_affected": 3}
    assert lib.get(NW + "/impact?date=2026-11-10").get_json() == {"borrowed_affected": 3}   # the due day itself
    assert lib.get(NW + "/impact?date=2026-11-11").get_json() == {"borrowed_affected": 0}   # after the due date
    assert lib.get(NW + "/impact?date=2026-11-08").get_json() == {"borrowed_affected": 0}   # Sundays never count
    assert lib.get(NW + "/impact?date=banana").status_code == 400
    assert lib.get(NW + "/impact").status_code == 400

    assert due_of(path, 2) == date(2026, 11, 10)
    r = lib.post(NW, json={"date": "2026-11-04", "reason": "Holiday"})
    assert r.status_code == 201
    assert r.get_json() == {"ok": True, "date": "2026-11-04", "reason": "Holiday", "borrowed_affected": 3}
    assert row(path, "SELECT * FROM NonWorkingDay")[0]["LibrarianID"] == "L1"
    assert due_of(path, 2) == date(2026, 11, 11)

    assert lib.post(NW, json={"date": "2026-11-04", "reason": "Other"}).status_code == 409    # already marked
    assert lib.get("/api/nonworking").get_json() == [
        {"NonWorkingDate": "2026-11-04", "Reason": "Holiday", "LibrarianID": "L1"}
    ]
    assert lib.get(NW + "/impact?date=2026-11-04").get_json() == {"borrowed_affected": 3}    # unmarking would move them back

    assert lib.delete(NW + "/2026-11-04").status_code == 200
    assert due_of(path, 2) == date(2026, 11, 10)
    assert lib.get("/api/nonworking").get_json() == []
    assert lib.delete(NW + "/2026-11-04").status_code == 404
    assert lib.delete(NW + "/banana").status_code == 400


def test_today_can_be_marked_but_past_days_cannot_be_unmarked():
    path = make_env()
    lib = login("librarian", "L1")
    assert lib.post(NW, json={"date": "2026-11-03", "reason": "School suspension"}).status_code == 201

    sql(path, "INSERT INTO NonWorkingDay VALUES ('2026-10-30', 'Holiday', 'L1')")
    assert lib.delete(NW + "/2026-10-30").status_code == 400
    assert len(row(path, "SELECT * FROM NonWorkingDay WHERE NonWorkingDate = '2026-10-30'")) == 1

    assert lib.delete(NW + "/2026-11-03").status_code == 200                                  # today is still allowed


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"All {len(tests)} librarian route tests passed!")
