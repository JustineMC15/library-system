from flask import request

# The 5 verification checks
CHECK_ORDER = [
    "Unreturned books",
    "Unpaid fines",
    "Borrow limit reached",
    "No valid Student ID",
    "Suspension of privileges",
]


def json_body() -> dict:
    """The request's JSON body, or {} when it is missing, broken or not an object."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def pick(body: dict, *names):
    """The value of the first of these keys that is in the body, or None.

    The pages send snake_case (book_id, borrow_id, return_date) and the draft API
    uses the column names (BookID, BorrowID, ReturnDate). Accepting both keeps them working together.
    """
    for name in names:
        if name in body:
            return body[name]
    return None


def whole_number(value):
    """The value if it is a real integer (not a bool, not a string), otherwise None."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None
