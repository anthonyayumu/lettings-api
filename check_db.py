from app.db import db_cursor


def count_viewings():
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM viewings")
        return cur.fetchone()["n"]


before = count_viewings()
print("before:", before)

try:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO viewings (property_id, tenant_id, viewing_date, outcome) "
            "VALUES (1, 52, '2026-11-12', 'Applied')"
        )
        print("first insert ran, new id:", cur.lastrowid)
        cur.execute(
            "INSERT INTO viewings (property_id, tenant_id, viewing_date, outcome) "
            "VALUES (99999, 52, '2026-11-12', 'Applied')"
        )
except Exception as error:
    print("second insert failed:", error)

after = count_viewings()
print("after:", after)
print("rolled back cleanly" if after == before else "PARTIAL WRITE - something is wrong")