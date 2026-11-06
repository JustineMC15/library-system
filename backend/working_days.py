
from datetime import date, timedelta

from config import LOAN_DAYS, MAX_RENEWALS, FINE_PER_DAY


def is_working_day(d: date, nonworking: set[date]) -> bool:
    return d.weekday() != 6 and d not in nonworking


def add_working_days(
    start: date,
    n: int,
    nonworking: set[date]
) -> date:
    current = start
    count = 0

    while count < n:
        current += timedelta(days=1)

        if is_working_day(current, nonworking):
            count += 1

    return current


def working_days_between(
    start: date,
    end: date,
    nonworking: set[date]
) -> int:
    current = start
    count = 0

    while current < end:
        current += timedelta(days=1)

        if is_working_day(current, nonworking):
            count += 1

    return count


def due_date(base: date, nonworking: set[date]) -> date:
    return add_working_days(base, LOAN_DAYS, nonworking)


def days_overdue(
    due: date,
    end: date,
    nonworking: set[date]
) -> int:
    return working_days_between(due, end, nonworking)


def days_left(
    today: date,
    due: date,
    nonworking: set[date]
) -> int:
    return working_days_between(today, due, nonworking)


def fine(overdue_days: int) -> int:
    return overdue_days * FINE_PER_DAY


def can_renew(
    approved_renewals: int,
    remaining_days: int,
    has_pending: bool
) -> bool:
    return (
        approved_renewals < MAX_RENEWALS
        and remaining_days < LOAN_DAYS
        and not has_pending
    )
