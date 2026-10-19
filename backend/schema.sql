-- Library System database. seed.py deletes and rebuilds library.db from this file.
-- Dates are TEXT 'YYYY-MM-DD'. Date and time is TEXT 'YYYY-MM-DD HH:MM:SS'.

PRAGMA foreign_keys = ON;

CREATE TABLE Student (
    StudentID      TEXT PRIMARY KEY,
    LastName       TEXT NOT NULL,
    FirstName      TEXT NOT NULL,
    MiddleInitial  TEXT,
    Address        TEXT,
    DateOfBirth    TEXT NOT NULL,                       -- Age is calculated from this
    PasswordHash   TEXT NOT NULL,
    Status         TEXT NOT NULL DEFAULT 'Active' CHECK (Status IN ('Active', 'Suspended'))
);

-- A student can have several contact numbers
CREATE TABLE StudentContact (
    StudentID  TEXT NOT NULL REFERENCES Student(StudentID),
    ContactNo  TEXT NOT NULL,
    PRIMARY KEY (StudentID, ContactNo)
);

CREATE TABLE Librarian (
    LibrarianID    TEXT PRIMARY KEY,
    LibrarianName  TEXT NOT NULL,
    PasswordHash   TEXT NOT NULL
);

CREATE TABLE Book (
    BookID       TEXT PRIMARY KEY,                      -- call number, or DIG-001 for digital books
    BookISBN     TEXT UNIQUE,                           -- digits only, may be empty
    BookTitle    TEXT NOT NULL,
    BookAuthor   TEXT NOT NULL,
    PublishYear  INTEGER,
    BookType     TEXT NOT NULL CHECK (BookType IN ('Physical', 'Digital')),
    DigitalLink  TEXT                                   -- e-book URL, empty for physical books
);

-- One row per borrow request. Status: Pending -> Borrowed -> Returned, or Pending -> Denied.
-- The due date is NOT stored: it is calculated from BorrowDate (or the last approved renewal).
CREATE TABLE Borrow (
    BorrowID     INTEGER PRIMARY KEY AUTOINCREMENT,
    StudentID    TEXT NOT NULL REFERENCES Student(StudentID),
    BookID       TEXT NOT NULL REFERENCES Book(BookID),
    LibrarianID  TEXT REFERENCES Librarian(LibrarianID), -- empty until a librarian decides
    RequestedAt  TEXT NOT NULL,                          -- date and time, decides the queue order
    BorrowDate   TEXT,                                   -- empty until approved
    Status       TEXT NOT NULL DEFAULT 'Pending'
                 CHECK (Status IN ('Pending', 'Borrowed', 'Returned', 'Denied'))
);

-- A book has one copy: only one Pending or Borrowed row per book at a time
CREATE UNIQUE INDEX one_active_borrow_per_book
    ON Borrow(BookID) WHERE Status IN ('Pending', 'Borrowed');

-- One row for each check a denied request failed (the Denied page shows them all)
CREATE TABLE DenyReason (
    BorrowID  INTEGER NOT NULL REFERENCES Borrow(BorrowID),
    Reason    TEXT NOT NULL CHECK (Reason IN (
                  'Unreturned books', 'Unpaid fines', 'Borrow limit reached',
                  'No valid Student ID', 'Suspension of privileges')),
    PRIMARY KEY (BorrowID, Reason)
);

-- Renewal requests. Only Approved rows count toward the 3-renewal limit.
CREATE TABLE Renew (
    RenewID      INTEGER PRIMARY KEY AUTOINCREMENT,
    BorrowID     INTEGER NOT NULL REFERENCES Borrow(BorrowID),
    LibrarianID  TEXT REFERENCES Librarian(LibrarianID),
    RequestedAt  TEXT NOT NULL,
    RenewalDate  TEXT,                                   -- empty until approved
    Status       TEXT NOT NULL DEFAULT 'Pending' CHECK (Status IN ('Pending', 'Approved', 'Denied'))
);
CREATE UNIQUE INDEX one_pending_renew_per_borrow ON Renew(BorrowID) WHERE Status = 'Pending';

-- Return requests. The fine is calculated and saved when a librarian approves.
CREATE TABLE "Return" (
    ReturnID      INTEGER PRIMARY KEY AUTOINCREMENT,
    BorrowID      INTEGER NOT NULL REFERENCES Borrow(BorrowID),
    LibrarianID   TEXT REFERENCES Librarian(LibrarianID),
    RequestedAt   TEXT NOT NULL,
    ReturnDate    TEXT,                                  -- empty until approved
    FineAmount    INTEGER NOT NULL DEFAULT 0,            -- pesos
    FinePaidDate  TEXT,                                  -- empty until the librarian marks it paid
    Status        TEXT NOT NULL DEFAULT 'Pending' CHECK (Status IN ('Pending', 'Approved', 'Denied'))
);
CREATE UNIQUE INDEX one_pending_return_per_borrow ON "Return"(BorrowID) WHERE Status = 'Pending';

-- Days a librarian marked as non-working (holidays, suspensions). Sundays are handled in code.
CREATE TABLE NonWorkingDay (
    NonWorkingDate  TEXT PRIMARY KEY,
    Reason          TEXT NOT NULL CHECK (Reason IN ('Holiday', 'School suspension', 'Other')),
    LibrarianID     TEXT NOT NULL REFERENCES Librarian(LibrarianID)
);
