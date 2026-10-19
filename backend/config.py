from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent          # the backend/ folder
DB_PATH = BASE_DIR / "library.db"                   # the SQLite file (not committed to git)
FRONTEND_DIR = BASE_DIR.parent / "frontend"         # the pages the server hands out

# Library rules (change them here, nowhere else)
BORROW_LIMIT = 3        # books a student can hold at once
LOAN_DAYS = 7           # working days per loan (Sunday, holidays and non-working days don't count)
MAX_RENEWALS = 3        # renewals per loan
FINE_PER_DAY = 2        # pesos per overdue working day, per book
