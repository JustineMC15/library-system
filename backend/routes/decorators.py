from functools import wraps
from flask import session, jsonify


def login_required(f):
    """Any logged-in user, student or librarian."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(ok=False, error="Login required"), 401
        return f(*args, **kwargs)
    return wrapper


def _require(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return jsonify(ok=False, error="Login required"), 401
            if session.get("role") != role:
                return jsonify(ok=False, error="Not allowed for this role"), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


student_required = _require("student")
librarian_required = _require("librarian")
