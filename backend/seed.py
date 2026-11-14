"""Builds a fresh library.db: tables from schema.sql, dummy accounts, and books from data/books.csv.
Run:  python backend/seed.py   (it deletes the old library.db first)"""
import csv
import sqlite3
from werkzeug.security import generate_password_hash
from config import BASE_DIR, DB_PATH

SCHEMA = BASE_DIR / "schema.sql"
BOOKS_CSV = BASE_DIR.parent / "data" / "books.csv"

# (StudentID, LastName, FirstName, MiddleInitial, Address, DateOfBirth, ContactNo)
# Phone numbers are made up
STUDENTS = [
    ("25A-0058", "Taroy", "Justine Raine", "J", "Marikina City", "2007-01-05", "09170000001"),
    ("25A-0026", "Casas", "Jhasmine", "", "Marikina City", "2006-12-16", "09170000002"),
    ("24A-0117", "Encio", "Ambrichie Rose", "M.", "San Mateo, Rizal", "2006-12-31", "09170000003"),
    ("25A-0014", "Zafra", "Jabez", "S.", "Marikina City", "2006-10-07", "09170000004"),
]


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")

    student_hash = generate_password_hash("student123")
    for sid, last, first, mi, addr, dob, phone in STUDENTS:
        conn.execute(
            "INSERT INTO Student (StudentID, LastName, FirstName, MiddleInitial, Address, DateOfBirth, PasswordHash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, last, first, mi, addr, dob, student_hash),
        )
        conn.execute("INSERT INTO StudentContact (StudentID, ContactNo) VALUES (?, ?)", (sid, phone))

    conn.execute(
        "INSERT INTO Librarian (LibrarianID, LibrarianName, PasswordHash) VALUES (?, ?, ?)",
        ("L-001", "Librarian One", generate_password_hash("librarian123")),
    )

    with open(BOOKS_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            isbn = row["BookISBN"].replace("-", "").strip() or None   # digits only; empty -> NULL
            link = row["DigitalLink"].strip() or None
            year = int(row["PublishYear"]) if row["PublishYear"].strip() else None
            conn.execute(
                "INSERT INTO Book (BookID, BookISBN, BookTitle, BookAuthor, PublishYear, BookType, DigitalLink) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["BookID"].strip(), isbn, row["BookTitle"].strip(), row["BookAuthor"].strip(),
                 year, row["BookType"].strip(), link),
            )

    conn.commit()
    for table in ("Student", "Librarian", "Book"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")
    conn.close()


if __name__ == "__main__":
    main()
