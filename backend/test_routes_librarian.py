"""Tests for the non-working day, stats, overdue and history routes.
Run from the backend folder:  python test_routes_librarian.py

Test data comes from make_env() in test_routes.py (today is Tuesday 2026-11-03):
  S3 holds BorrowID 1 (B6, borrowed Oct 20, due Oct 28: 5 working days overdue)
  S4 holds BorrowIDs 2, 3, 4 (borrowed Nov 2, due Nov 10)
"""
import sqlite3
from datetime import datetime

import clock
from app import app
from test_routes import NOW, login, make_env, request_book, row


# ---------- non-working days ----------

def test_nonworking_list_needs_login():
    make_env()
    assert app.test_client().get("/api/nonworking").status_code == 401
    assert login("student", "S1").get("/api/nonworking").get_json() == []
    assert login("librarian", "L1").get("/api/nonworking").get_json() == []


def test_mark_and_unmark_day():
    path = make_env()
    lib = login("librarian", "L1")
    url = "/api/librarian/nonworking"

    r = lib.post(url, json={"date": "2026-11-10", "reason": "Holiday"})
    assert r.status_code == 201 and r.get_json()["ok"] is True
    assert login("student", "S1").get("/api/nonworking").get_json() == [
        {"NonWorkingDate": "2026-11-10", "Reason": "Holiday", "LibrarianID": "L1"}
    ]
    assert lib.post(url, json={"date": "2026-11-10", "reason": "Other"}).status_code == 409   # already marked

    bad_bodies = [
        {},
        {"date": "2026-11-11"},                                    # no reason
        {"reason": "Holiday"},                                     # no date
        {"date": "11/11/2026", "reason": "Holiday"},
        {"date": 5, "reason": "Holiday"},
        {"date": "2026-11-11", "reason": "Party"},
        {"date": "2026-11-08", "reason": "Holiday"},               # Sunday
        {"date": "2026-11-02", "reason": "Holiday"},               # yesterday
    ]
    for body in bad_bodies:
        assert lib.post(url, json=body).status_code == 400, body

    assert lib.post(url, json={"date": "2026-11-03", "reason": "School suspension"}).status_code == 201   # today is allowed

    assert lib.delete(f"{url}/2026-11-10").status_code == 200
    assert lib.delete(f"{url}/2026-11-10").status_code == 404
    assert lib.delete(f"{url}/not-a-date").status_code == 400
    assert [r["NonWorkingDate"] for r in row(path, "SELECT NonWorkingDate FROM NonWorkingDay")] == ["2026-11-03"]


def test_nonworking_write_routes_need_librarian():
    make_env()
    student, anon = login("student", "S1"), app.test_client()
    body = {"date": "2026-11-10", "reason": "Holiday"}
    for client, expected in ((student, 403), (anon, 401)):
        assert client.post("/api/librarian/nonworking", json=body).status_code == expected
        assert client.delete("/api/librarian/nonworking/2026-11-10").status_code == expected
        assert client.get("/api/librarian/nonworking/impact?date=2026-11-10").status_code == expected


def test_past_day_cannot_be_removed():
    path = make_env()
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO NonWorkingDay VALUES ('2026-10-29', 'Holiday', 'L1')")
    conn.commit()
    conn.close()
    assert login("librarian", "L1").delete("/api/librarian/nonworking/2026-10-29").status_code == 400
    assert len(row(path, "SELECT * FROM NonWorkingDay")) == 1


def test_marked_day_moves_due_dates_and_impact_counts_them():
    make_env()
    lib, s4 = login("librarian", "L1"), login("student", "S4")

    def impact(day):
        return lib.get(f"/api/librarian/nonworking/impact?date={day}").get_json()["borrowed_affected"]

    def due_of_borrow_2():
        return next(l for l in s4.get("/api/student/loans").get_json() if l["BorrowID"] == 2)["DueDate"]

    assert due_of_borrow_2() == "2026-11-10"
    assert impact("2026-11-05") == 3        # S4's three loans move; S3's loan is already past that day
    assert impact("2026-10-22") == 1        # only S3's loan (borrowed Oct 20) counts that day
    assert impact("2026-11-08") == 0        # Sunday changes nothing

    lib.post("/api/librarian/nonworking", json={"date": "2026-11-05", "reason": "Holiday"})
    assert due_of_borrow_2() == "2026-11-11"
    assert impact("2026-11-05") == 3        # unmarking would move them back

    lib.delete("/api/librarian/nonworking/2026-11-05")
    assert due_of_borrow_2() == "2026-11-10"

    assert lib.get("/api/librarian/nonworking/impact").status_code == 400
    assert lib.get("/api/librarian/nonworking/impact?date=abc").status_code == 400


# ---------- dashboard: stats and overdue ----------

def test_dashboard_routes_need_librarian():
    make_env()
    student, anon = login("student", "S1"), app.test_client()
    for url in ("/api/librarian/stats", "/api/librarian/overdue", "/api/librarian/history"):
        assert student.get(url).status_code == 403
        assert anon.get(url).status_code == 401


def test_stats():
    make_env()
    s1, lib = login("student", "S1"), login("librarian", "L1")
    url = "/api/librarian/stats"
    assert lib.get(url).get_json() == {"borrows_today": 0, "returns_today": 0, "overdue": 1}

    borrow_id = request_book(s1, "B1").get_json()["BorrowID"]
    lib.post(f"/api/librarian/borrow/{borrow_id}/approve", json={"student_id_ok": True})
    assert lib.get(url).get_json()["borrows_today"] == 1

    assert lib.post("/api/librarian/returns", json={"BorrowID": 1}).status_code == 200   # S3's overdue book comes back
    assert lib.get(url).get_json() == {"borrows_today": 1, "returns_today": 1, "overdue": 0}


def test_overdue_list():
    path = make_env()
    lib = login("librarian", "L1")
    assert lib.get("/api/librarian/overdue").get_json() == [{
        "BorrowID": 1, "StudentID": "S3", "StudentName": "LastS3, Test Q.", "BookTitle": "Book 6",
        "DueDate": "2026-10-28", "DaysLate": 5, "Fine": 10,
    }]

    conn = sqlite3.connect(path)
    conn.execute('INSERT INTO "Return" (BorrowID, RequestedAt, Status) VALUES (1, ?, \'Pending\')',
                 ("2026-11-02 10:00:00",))
    conn.commit()
    conn.close()
    overdue = lib.get("/api/librarian/overdue").get_json()
    assert overdue[0]["DaysLate"] == 4 and overdue[0]["Fine"] == 8


# ---------- dashboard: history ----------

def test_history_lists_only_decided_requests():
    make_env()
    s1, s2, s4, lib = login("student", "S1"), login("student", "S2"), login("student", "S4"), login("librarian", "L1")
    url = "/api/librarian/history"

    # the 4 seeded loans already count as approved borrows
    first = lib.get(url).get_json()
    assert len(first) == 4 and all(h["type"] == "borrow" and h["Status"] == "Approved" for h in first)

    b1 = request_book(s1, "B1").get_json()["BorrowID"]
    b2 = request_book(s2, "B2").get_json()["BorrowID"]
    renew_id = s4.post("/api/renew", json={"BorrowID": 2}).get_json()["RenewID"]
    assert len(lib.get(url).get_json()) == 4                       # pending requests are not history yet

    lib.post(f"/api/librarian/borrow/{b1}/approve", json={"student_id_ok": True})
    lib.post(f"/api/librarian/borrow/{b2}/deny", json={"reasons": ["Unpaid fines"]})
    lib.post(f"/api/librarian/renew/{renew_id}/deny", json={})

    rows = lib.get(url).get_json()
    assert len(rows) == 7
    new = [h for h in rows if h["RequestedAt"].startswith("2026-11-03")]
    assert sorted((h["type"], h["StudentID"], h["Status"]) for h in new) == [
        ("borrow", "S1", "Approved"), ("borrow", "S2", "Denied"), ("renew", "S4", "Denied"),
    ]
    assert all(h["LibrarianID"] == "L1" for h in new)
    assert all(h["LibrarianName"] == "Lib One" for h in new)
    assert {h["BookID"] for h in new} == {"B1", "B2", "B3"}
    assert rows[0]["RequestedAt"].startswith("2026-11-03")          # newest first
    assert {h["StudentName"] for h in new} == {"LastS1, Test Q.", "LastS2, Test Q.", "LastS4, Test Q."}

    assert len(lib.get(url + "?type=renew").get_json()) == 1
    assert len(lib.get(url + "?type=borrow").get_json()) == 6
    assert lib.get(url + "?type=return").get_json() == []
    assert lib.get(url + "?type=bogus").status_code == 400


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"All {len(tests)} librarian route tests passed!")
