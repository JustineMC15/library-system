"""Fills library.db with demo transactions so every page has something to show.

Every date is worked out from today, so run it right before the demo or the screenshots.
It refuses to run on a database that already has transactions. Run seed.py again first
(seed.py wipes library.db, so every registration and request made since is lost).
"""
import sys
from datetime import timedelta

from werkzeug.security import generate_password_hash

import clock
from calendar_db import load_nonworking
from checks import run_checks
from db import get_db
from returns import fine_owed
from working_days import days_overdue, due_date, fine, is_working_day, working_days_between

NOW = clock.now()
TODAY = NOW.date()

TAROYY, CASAS, ENCIO, ZAFRA = "25A-0058", "25A-0026", "24A-0117", "25A-0014"
L1, L2 = "L-001", "L-002"

# Real national holidays. Only the ones still ahead of today are added.
HOLIDAYS = [("2026-11-30", "Holiday"), ("2026-12-08", "Holiday"),
            ("2026-12-25", "Holiday"), ("2026-12-30", "Holiday")]

# A book has one copy, so every active request needs its own book. One name per role.
PHYSICAL = ["taroy_loan", "taroy_pending", "taroy_old_ok", "taroy_old_late",
            "casas_overdue", "casas_pending", "casas_denied",
            "encio_returned", "encio_today", "encio_renew", "encio_pending",
            "zafra_fined", "zafra_denied", "zafra_pending"]
DIGITAL = ["taroy_ebook", "encio_ebook"]


def pick_books(conn, book_type, count):
    """Books spread evenly through the catalog, so Browse Books shows borrowed ones all over."""
    ids = [r[0] for r in conn.execute(
        "SELECT BookID FROM Book WHERE BookType = ? ORDER BY BookTitle", (book_type,))]
    if len(ids) < count:
        sys.exit(f"Need at least {count} {book_type.lower()} books in the database, found {len(ids)}.")
    return ids[::len(ids) // count][:count]


def main():
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM Borrow").fetchone()[0]:
        sys.exit("library.db already has transactions. Run python backend/seed.py first, then this script.")
    students = {r[0] for r in conn.execute("SELECT StudentID FROM Student")}
    has_librarian = conn.execute("SELECT 1 FROM Librarian WHERE LibrarianID = ?", (L1,)).fetchone()
    if not {TAROY, CASAS, ENCIO, ZAFRA} <= students or not has_librarian:
        sys.exit("The four seed students and librarian L-001 are missing. Run python backend/seed.py first.")

    phys = dict(zip(PHYSICAL, pick_books(conn, "Physical", len(PHYSICAL))))
    dig = dict(zip(DIGITAL, pick_books(conn, "Digital", len(DIGITAL))))

    with conn:   # all or nothing
        conn.execute(
            "INSERT OR IGNORE INTO Librarian (LibrarianID, LibrarianName, PasswordHash) VALUES (?, ?, ?)",
            (L2, "Librarian Two", generate_password_hash("librarian123")))
        for day, reason in HOLIDAYS:
            if day >= TODAY.isoformat():
                conn.execute("INSERT INTO NonWorkingDay (NonWorkingDate, Reason, LibrarianID) VALUES (?, ?, ?)",
                             (day, reason, L1))
        off = load_nonworking(conn)

        # ---------- helpers ----------

        def ago(n):
            """The working day that is n working days before today (a book borrowed then has 7 - n left)."""
            d = TODAY
            while working_days_between(d, TODAY, off) < n:
                d -= timedelta(days=1)
            while not is_working_day(d, off):
                d -= timedelta(days=1)
            return d

        def at(day, time):
            return f"{day.isoformat()} {time}"

        def minutes_ago(m):
            return (NOW - timedelta(minutes=m)).strftime("%Y-%m-%d %H:%M:%S")

        def loan(student, book, borrow_date, lib, status="Borrowed"):
            requested = at(borrow_date, "08:45:00") if borrow_date < TODAY else minutes_ago(10)
            return conn.execute(
                "INSERT INTO Borrow (StudentID, BookID, LibrarianID, RequestedAt, BorrowDate, Status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (student, book, lib, requested, borrow_date.isoformat(), status)).lastrowid

        def pending_borrow(student, book, minutes):
            return conn.execute(
                "INSERT INTO Borrow (StudentID, BookID, RequestedAt, Status) VALUES (?, ?, ?, 'Pending')",
                (student, book, minutes_ago(minutes))).lastrowid

        def denied_borrow(student, book, day, lib, reasons):
            borrow_id = conn.execute(
                "INSERT INTO Borrow (StudentID, BookID, LibrarianID, RequestedAt, Status) "
                "VALUES (?, ?, ?, ?, 'Denied')",
                (student, book, lib, at(day, "10:20:00"))).lastrowid
            conn.executemany("INSERT INTO DenyReason (BorrowID, Reason) VALUES (?, ?)",
                             [(borrow_id, r) for r in reasons])

        def returned_loan(student, book, borrow_date, return_date, lib, paid):
            borrow_id = loan(student, book, borrow_date, lib, "Returned")
            amount = fine(days_overdue(due_date(borrow_date, off), return_date, off))
            conn.execute(
                'INSERT INTO "Return" (BorrowID, LibrarianID, RequestedAt, ReturnDate, FineAmount, FinePaidDate, Status) '
                "VALUES (?, ?, ?, ?, ?, ?, 'Approved')",
                (borrow_id, lib, at(return_date, "10:00:00"), return_date.isoformat(), amount,
                 return_date.isoformat() if paid and amount else None))

        # ---------- Taroy: clean account (the Verify page passes every check) ----------
        loan(TAROY, phys["taroy_loan"], ago(5), L1)                      # 2 working days left: "Due soon"
        ebook = loan(TAROY, dig["taroy_ebook"], ago(10), L2)
        conn.execute("INSERT INTO Renew (BorrowID, LibrarianID, RequestedAt, RenewalDate, Status) "
                     "VALUES (?, ?, ?, ?, 'Approved')",
                     (ebook, L1, at(ago(4), "09:10:00"), ago(4).isoformat()))   # "Renewed 1 of 3"
        pending_borrow(TAROY, phys["taroy_pending"], 75)                 # approve this one live
        returned_loan(TAROY, phys["taroy_old_ok"], ago(22), ago(16), L1, paid=True)       # on time
        returned_loan(TAROY, phys["taroy_old_late"], ago(26), ago(13), L2, paid=True)     # late, fine paid
        first_loan = conn.execute("SELECT BorrowID FROM Borrow WHERE BookID = ?",
                                  (phys["taroy_loan"],)).fetchone()[0]
        conn.execute("INSERT INTO Renew (BorrowID, LibrarianID, RequestedAt, Status) VALUES (?, ?, ?, 'Denied')",
                     (first_loan, L2, at(ago(1), "14:00:00")))          # a denied renewal in History

        # ---------- Casas: overdue book (fails "Unreturned books") ----------
        loan(CASAS, phys["casas_overdue"], ago(12), L1)                 # 5 working days late, 10 pesos and counting
        pending_borrow(CASAS, phys["casas_pending"], 90)                # deny this one live
        denied_borrow(CASAS, phys["casas_denied"], ago(2), L2, ["Unreturned books"])

        # ---------- Encio: at the borrow limit, with a pending renewal and a pending e-book return ----------
        returned_loan(ENCIO, phys["encio_returned"], ago(5), TODAY, L2, paid=False)     # "Returned Today" = 1
        loan(ENCIO, phys["encio_today"], TODAY, L1)                     # "Borrowed Today" = 1
        encio_ebook = loan(ENCIO, dig["encio_ebook"], ago(4), L2)
        conn.execute('INSERT INTO "Return" (BorrowID, RequestedAt, Status) VALUES (?, ?, \'Pending\')',
                     (encio_ebook, minutes_ago(45)))                    # e-book return waiting in the queue
        renew_loan = loan(ENCIO, phys["encio_renew"], ago(6), L1)       # 1 working day left
        conn.execute("INSERT INTO Renew (BorrowID, RequestedAt, Status) VALUES (?, ?, 'Pending')",
                     (renew_loan, minutes_ago(60)))
        pending_borrow(ENCIO, phys["encio_pending"], 30)                # fails "Borrow limit reached"

        # ---------- Zafra: unpaid fine and suspended (fails two checks at once) ----------
        returned_loan(ZAFRA, phys["zafra_fined"], ago(24), ago(10), L1, paid=False)     # 14 pesos unpaid
        denied_borrow(ZAFRA, phys["zafra_denied"], ago(1), L1, ["Unpaid fines", "Suspension of privileges"])
        pending_borrow(ZAFRA, phys["zafra_pending"], 15)
        conn.execute("UPDATE Student SET Status = 'Suspended' WHERE StudentID = ?", (ZAFRA,))

    # ---------- what the system makes of it ----------
    off = load_nonworking(conn)
    print(f"Demo data added (dates counted from {TODAY.isoformat()}).\n")
    for sid in (TAROY, CASAS, ENCIO, ZAFRA):
        failed = [name for name, bad in run_checks(conn, sid, TODAY, off).items() if bad]
        print(f"  {sid}: fails {', '.join(failed) or 'nothing'}; owes {fine_owed(conn, sid)} pesos")
    queue = conn.execute("SELECT COUNT(*) FROM Borrow WHERE Status = 'Pending'").fetchone()[0] + \
        conn.execute("SELECT COUNT(*) FROM Renew WHERE Status = 'Pending'").fetchone()[0] + \
        conn.execute('SELECT COUNT(*) FROM "Return" WHERE Status = \'Pending\'').fetchone()[0]
    print(f"\n  {queue} requests waiting in the queue. Zafra (25A-0014) is now Suspended.")
    print("  Logins: students use student123, librarians L-001 and L-002 use librarian123.")
    conn.close()


if __name__ == "__main__":
    main()
