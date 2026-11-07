
from datetime import date


def load_nonworking(conn) -> set[date]:
    rows = conn.execute(
        "SELECT NonWorkingDate FROM NonWorkingDay"
    ).fetchall()

    return {
        date.fromisoformat(row["NonWorkingDate"])
        for row in rows
    }
