from fastapi import FastAPI

from app.db import db_cursor

app = FastAPI(title="Lettings Insights API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/branches")
def list_branches():
    sql = """
        SELECT branches.branch_id,
               branches.branch_name,
               COUNT(properties.property_id) AS total_properties,
               ROUND(AVG(properties.listed_rent_pcm), 2) AS average_listed_rent
        FROM branches
        JOIN properties ON ______ = ______
        GROUP BY branches.branch_id, branches.branch_name
        ORDER BY ______
    """
    with db_cursor() as cur:
        cur.execute(sql)
        return ______        # fetch all the rows