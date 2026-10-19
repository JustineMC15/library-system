# Library System

Fundamentals of DB group project: HTML, CSS, JavaScript, Python (Flask) and SQLite.

## Run it

1. Create and activate a virtual environment (once):

   * `python -m venv venv`
   * Windows: `venv\\Scripts\\activate`   Mac/Linux: `source venv/bin/activate`
2. Install the packages: `pip install -r requirements.txt`
3. Build the database (also run this again whenever `books.csv` or `schema.sql` changes): `python backend/seed.py`
4. Start the server: `python backend/app.py`
5. Open http://localhost:5000/api-test.html (the book list should appear)

Dummy logins (made by seed.py, for testing only):

* Students: IDs `2024-0001` to `2024-0004`, password `student123`
* Librarian: ID `L-001`, password `librarian123`

## Who edits what

* Ambrichie: `frontend/` only
* Zafra: `data/books.csv` only
* Justine and Jhasmine: `backend/`
Use your own branch and a pull request, so nobody overwrites anyone else.

## Commit Conventions

Use the following format for all commits:

`<type>: <short description>`

Write the type in lowercase, use the imperative mood (e.g., "add", "fix", "update"), and keep the description short and clear.

### Commit Types

| Type | Purpose | Example |
|---|---|---|
| `feat` | Add a new feature | `feat: add book search functionality` |
| `fix` | Fix a bug or error | `fix: correct book return date calculation` |
| `style` | Change formatting or visual appearance without changing functionality | `style: improve book list layout` |
| `refactor` | Restructure code without changing its behavior | `refactor: simplify book query logic` |
| `docs` | Add or update documentation | `docs: update project setup instructions` |
| `test` | Add or update tests | `test: add tests for book borrowing` |
| `chore` | Perform maintenance or configuration tasks | `chore: update requirements.txt` |
| `data` | Add or update project data | `data: add sample books to books.csv` |

### Examples for This Project

- `feat: add student login page`
- `feat: implement book borrowing endpoint`
- `feat: add book search by title`
- `fix: prevent borrowing unavailable books`
- `fix: correct database connection path`
- `style: adjust librarian dashboard spacing`
- `refactor: separate database queries from routes`
- `docs: document dummy login credentials`
- `chore: update .gitignore`
- `data: add more sample books`

### Rules

1. **One commit, one purpose.** Avoid combining unrelated changes in a single commit.
2. **Be specific.** Use `fix: correct return date validation` instead of `fix: bug`.
3. **Use lowercase types.** For example, `feat:`, not `FEAT:`.
4. **Do not use vague messages.** Avoid `update`, `changes`, `final`, or `stuff`.
5. **Commit only your relevant changes.** Follow the assigned file ownership and work on your own branch.
6. **Use pull requests.** Push your branch and open a pull request for review before merging into the main branch.

### Commit Message Template

`<type>: <what you changed>`

Good: `feat: add librarian book management page`

Bad: `updated some files`

