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
