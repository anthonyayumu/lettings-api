from pathlib import Path

from fastapi.staticfiles import StaticFiles

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

import pymysql
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.db import db_cursor

app = FastAPI(title="Lettings Insights API")


class ViewingCreate(BaseModel):
    property_id: int = Field(gt=0)
    tenant_id: int = Field(gt=0)
    viewing_date: date
    outcome: Literal["No show", "Not interested", "Applied"]


class ResolveRequest(BaseModel):
    resolved_date: date
    cost: Decimal = Field(ge=0, max_digits=8, decimal_places=2)

class MaintenanceRequestCreate(BaseModel):
    property_id: int = Field(gt=0)
    category: Literal[
        "Roof",
        "Boiler/heating",
        "Plumbing",
        "Electrical",
        "Appliance",
        "Damp and mould",
        "Locks/security",
        "Pest control",
    ]
    priority: Literal["Emergency", "Urgent", "Routine"]
    reported_date: date = Field(default_factory=date.today)

    @field_validator("reported_date")
    @classmethod
    def not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("reported_date cannot be in the future")
        return value

@app.post("/maintenance-requests", status_code=201)
def create_maintenance_request(request: MaintenanceRequestCreate):
    sql = """
        INSERT INTO maintenance_requests (property_id, reported_date, category, priority)
        VALUES (%s, %s, %s, %s)
    """
    try:
        with db_cursor() as cur:
            cur.execute(sql, (request.property_id, request.reported_date,
                              request.category, request.priority))
            new_id = cur.lastrowid
    except pymysql.err.IntegrityError as e:
        if e.args[0] == 1452:
            raise HTTPException(status_code=422, detail="property_id does not exist")
        raise
    return {"request_id": new_id, **request.model_dump(),
            "resolved_date": None, "cost": None}


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
        JOIN properties ON branches.branch_id = properties.branch_id
        GROUP BY branches.branch_id, branches.branch_name
        ORDER BY average_listed_rent DESC
    """
    with db_cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


@app.get("/branches/{branch_id}")
def get_branch(branch_id: int):
    sql = """
        SELECT branches.branch_id,
               branches.branch_name,
               COUNT(DISTINCT properties.property_id) AS all_properties,
               COUNT(DISTINCT CASE WHEN tenancies.status = 'Active'
                                   THEN properties.property_id END) AS active_properties,
               ROUND(COUNT(DISTINCT CASE WHEN tenancies.status = 'Active'
                                         THEN properties.property_id END)
                     / NULLIF(COUNT(DISTINCT properties.property_id), 0) * 100, 1) AS property_share_pct
        FROM branches
        LEFT JOIN properties ON branches.branch_id = properties.branch_id
        LEFT JOIN tenancies ON properties.property_id = tenancies.property_id
        WHERE branches.branch_id = %s
        GROUP BY branches.branch_id, branches.branch_name
    """
    with db_cursor() as cur:
        cur.execute(sql, (branch_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    return row


@app.get("/properties")
def list_properties(
    town: Optional[str] = None,
    min_bedrooms: Optional[int] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conditions, params = [], []
    if town:
        conditions.append("town = %s")
        params.append(town)
    if min_bedrooms is not None:
        conditions.append("bedrooms >= %s")
        params.append(min_bedrooms)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT property_id, address, town, property_type, bedrooms, listed_rent_pcm
        FROM properties
        {where}
        ORDER BY property_id
        LIMIT %s OFFSET %s
    """
    params += [page_size, (page - 1) * page_size]

    with db_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@app.post("/viewings", status_code=201)
def create_viewing(viewing: ViewingCreate):
    sql = """
        INSERT INTO viewings (property_id, tenant_id, viewing_date, outcome)
        VALUES (%s, %s, %s, %s)
    """
    try:
        with db_cursor() as cur:
            cur.execute(sql, (viewing.property_id, viewing.tenant_id,
                              viewing.viewing_date, viewing.outcome))
            new_id = cur.lastrowid
    except pymysql.err.IntegrityError as e:
        if e.args[0] == 1452:          # foreign key check failed
            raise HTTPException(status_code=422,
                                detail="property_id or tenant_id does not exist")
        raise
    return {"viewing_id": new_id, **viewing.model_dump()}


@app.patch("/maintenance-requests/{request_id}/resolve")
def resolve_request(request_id: int, body: ResolveRequest):
    with db_cursor() as cur:
        cur.execute(
            "SELECT reported_date, resolved_date FROM maintenance_requests WHERE request_id = %s",
            (request_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Request not found")
        if row["resolved_date"] is not None:
            raise HTTPException(status_code=409, detail="Request already resolved")
        if body.resolved_date < row["reported_date"]:
            raise HTTPException(status_code=422,
                                detail="resolved_date cannot be before reported_date")
        cur.execute(
            """UPDATE maintenance_requests
               SET resolved_date = %s, cost = %s
               WHERE request_id = %s AND resolved_date IS NULL""",
            (body.resolved_date, body.cost, request_id),
        )
    return {"request_id": request_id,
            "resolved_date": body.resolved_date,
            "cost": body.cost}


@app.patch("/maintenance-requests/{request_id}/resolve")
def resolve_request(request_id: int, body: ResolveRequest):
    with db_cursor() as cur:
        cur.execute(
            "SELECT reported_date, resolved_date FROM maintenance_requests WHERE request_id = %s",
            (request_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Request not found")
        if row["resolved_date"] is not None:
            raise HTTPException(status_code=409, detail="Request already resolved")
        if body.resolved_date < row["reported_date"]:
            raise HTTPException(
                status_code=422, detail="resolved_date cannot be before reported_date"
            )
        cur.execute(
            """UPDATE maintenance_requests
               SET resolved_date = %s, cost = %s
               WHERE request_id = %s AND resolved_date IS NULL""",
            (body.resolved_date, body.cost, request_id),
        )
    return {
        "request_id": request_id,
        "resolved_date": body.resolved_date,
        "cost": body.cost,
    }

@app.get("/maintenance-requests")
def list_maintenance_requests(
    status: Literal["open", "resolved", "all"] = "open",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    filters = {
        "open": "WHERE maintenance_requests.resolved_date IS NULL",
        "resolved": "WHERE maintenance_requests.resolved_date IS NOT NULL",
        "all": "",
    }
    where = filters[status]
    offset = (page - 1) * page_size

    count_sql = f"SELECT COUNT(*) AS total FROM maintenance_requests {where}"
    data_sql = f"""
        SELECT maintenance_requests.request_id,
               maintenance_requests.property_id,
               properties.address,
               properties.town,
               maintenance_requests.category,
               maintenance_requests.priority,
               maintenance_requests.reported_date,
               maintenance_requests.resolved_date,
               maintenance_requests.cost
        FROM maintenance_requests
        JOIN properties ON maintenance_requests.property_id = properties.property_id
        {where}
        ORDER BY maintenance_requests.reported_date DESC, maintenance_requests.request_id DESC
        LIMIT %s OFFSET %s
    """
    with db_cursor() as cur:
        cur.execute(count_sql)
        total = cur.fetchone()["total"]
        cur.execute(data_sql, (page_size, offset))
        items = cur.fetchall()
    return {"total": total, "page": page, "page_size": page_size, "items": items}

@app.get("/analytics/monthly-rent")
def monthly_rent(year: int = Query(2025, ge=2000, le=2100)):
    sql = """
        WITH monthly AS (
            SELECT DATE_FORMAT(paid_date, '%%Y-%%m') AS payment_month,
                   SUM(amount_paid) AS collected
            FROM rent_payments
            WHERE paid_date >= %s AND paid_date < %s
            GROUP BY DATE_FORMAT(paid_date, '%%Y-%%m')
        )
        SELECT payment_month,
               collected,
               SUM(collected) OVER (ORDER BY payment_month) AS running_total
        FROM monthly
        ORDER BY payment_month
    """
    with db_cursor() as cur:
        cur.execute(sql, (date(year, 1, 1), date(year + 1, 1, 1)))
        return cur.fetchall()

@app.get("/analytics/arrears")
def arrears(
    as_of: date = date(2025, 9, 30),
    limit: int = Query(50, ge=1, le=200),
):
    sql = """
        SELECT tenancies.tenancy_id,
               tenants.full_name,
               COUNT(CASE WHEN rent_payments.amount_due > rent_payments.amount_paid
                          THEN rent_payments.payment_id END) AS missed_payments,
               ROUND(SUM(CASE WHEN rent_payments.amount_due > rent_payments.amount_paid
                              THEN rent_payments.amount_due - rent_payments.amount_paid END), 2) AS short_falls
        FROM tenancies
        JOIN rent_payments ON tenancies.tenancy_id = rent_payments.tenancy_id
        JOIN tenants ON tenancies.tenant_id = tenants.tenant_id
        WHERE tenancies.status = 'Active'
          AND rent_payments.due_date <= %s
        GROUP BY tenancies.tenancy_id, tenants.full_name
        HAVING short_falls > 0
        ORDER BY short_falls DESC, missed_payments DESC
        LIMIT %s
    """
    with db_cursor() as cur:
        cur.execute(sql, (as_of, limit))
        return cur.fetchall()


@app.get("/analytics/sla")
def sla_compliance(branch_id: Optional[int] = Query(None, gt=0)):
    where = "WHERE branches.branch_id = %s" if branch_id else ""
    params = (branch_id,) if branch_id else ()
    sql = f"""
        WITH request_sla AS (
            SELECT branches.branch_id,
                   branches.branch_name,
                   maintenance_requests.request_id,
                   maintenance_requests.priority,
                   CASE maintenance_requests.priority
                        WHEN 'Emergency' THEN 1
                        WHEN 'Urgent' THEN 7
                        WHEN 'Routine' THEN 28
                   END AS sla_days,
                   DATEDIFF(maintenance_requests.resolved_date,
                            maintenance_requests.reported_date) AS days_taken
            FROM branches
            JOIN properties ON branches.branch_id = properties.branch_id
            JOIN maintenance_requests ON properties.property_id = maintenance_requests.property_id
            {where}
        )
        SELECT branch_id,
               branch_name,
               priority,
               sla_days,
               COUNT(request_id) AS all_jobs,
               COUNT(CASE WHEN days_taken <= sla_days THEN request_id END) AS jobs_resolved_on_time,
               ROUND(COUNT(CASE WHEN days_taken <= sla_days THEN request_id END)
                     / COUNT(request_id) * 100, 1) AS on_time_rate_pct,
               COUNT(CASE WHEN days_taken IS NULL THEN request_id END) AS still_open
        FROM request_sla
        GROUP BY branch_id, branch_name, priority, sla_days
        ORDER BY branch_id, sla_days
    """
    with db_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")