from app.db import db_cursor

with db_cursor() as cur:
    cur.execute("SELECT COUNT(*) AS n FROM properties")
    print(cur.fetchone())

    cur.execute("SELECT branch_name FROM branches WHERE branch_id = %s", (1,))
    print(cur.fetchone())