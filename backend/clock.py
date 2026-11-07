from datetime import datetime


def now() -> datetime:
    """The current date and time. Routes call this (never datetime.now() directly) so tests can fake it."""
    return datetime.now()
