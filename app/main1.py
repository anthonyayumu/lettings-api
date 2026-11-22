from pathlib import path
from fastapi.staticfiles import StaticFiles

from datetime import date
from decimal import decimal
from typing import Literal, Optional 

import pymysql
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from app.db import db_cursor

app =  FastAPI(title="Teesside Lettings API")

class ViewingCreate(BaseModel):
    property_id : int = Field(gt=0)
    tenant_id : int = Field(gt=0)
    viewing_date: date
    outcome: Literal["No show","Applied","Not interested"]

class ResloveRequest(BaseModel):
    resolved_date: date 
    cost: decimal = Field(ge=0, max_digits = 8, decimal_places=2)

class MaintenanceRequestCreate(BaseModel):
    property_id: int = Field(gt=0)
    category = Literal[
        "Plumbing",
        "Electrical",
        "Pest control",
        "Roof",
        "Locks/security",
        "Appliance",
        "Damp and mould",
        "Boiler/heating",
    ]
    priority: Literal["Routine","Urgent","Emergency"]
    reported_date: date = Field(default_factory = date.today)

    @field_validator
    @classmethod
    def not_in_future(cls, value: date)-> date:
        if value > date.today():
            raise ValueError("reported_date cannot be in future")
        return value

@app.post("/maintenance-requests", status_code = 201)
def create_maintenance_request(request: MaintenanceRequestCreate):
    sql = """
    insert into maintenance_requests(property_id, reported_date, category, priority)
    values(%s, %s, %s, %s)
    """
    try:
        with db_cursor() as cur:
            cur.execute(sql, (request.property_id, 
                        request.reported_date, request.category, request.priority))
            new_id = cur.lastrowid
    except pymysql.err.IntegrityError as e:
        if e.args[0] == 1452:
            raise HTTPException(status_code=422, detail = "property_id does not exist")
        raise
    return{"request_id": new_id, **request.model_dump(),
           "resolved_date": None, "cost": None}

@app.get("/health")
def health():
    return{"status": "ok"}

@app.get("/branches")
def list_of_branches():
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
def get_branches(branch_id : int):
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


      