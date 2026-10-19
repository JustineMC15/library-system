# Library System

Fundamentals of DB group project: HTML, CSS, JavaScript, Python (Flask) and SQLite.

## Run it

1. Create and activate a virtual environment (once):
   - `python -m venv venv`
   - Windows: `venv\Scripts\activate`   Mac/Linux: `source venv/bin/activate`
2. Install the packages: `pip install -r requirements.txt`
3. Build the database (also run this again whenever `books.csv` or `schema.sql` changes): `python backend/seed.py`
4. Start the server: `python backend/app.py`
5. Open http://localhost:5000/api-test.html (the book list should appear)

Dummy logins (made by seed.py, for testing only):
- Students: IDs `2024-0001` to `2024-0004`, password `student123`
- Librarian: ID `L-001`, password `librarian123`

## Who edits what
- Ambrichie: `frontend/` only
- Zafra: `data/books.csv` only
- Justine and Jhasmine: `backend/`
Use your own branch and a pull request, so nobody overwrites anyone else.
