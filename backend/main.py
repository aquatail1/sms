import os
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sms")

app = FastAPI(title="SMS Monitoring API", version="0.2.0")
pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10, kwargs={"autocommit": True})


class RegisterRequest(BaseModel):
    hostname: str
    os_type: str
    os_version: Optional[str] = None
    ip_address: Optional[str] = None
    agent_version: Optional[str] = None
    node_path: str


class RegisterResponse(BaseModel):
    agent_id: UUID
    token: str
    collect_interval_sec: int = 30


class MetricPoint(BaseModel):
    time: datetime
    cpu_usage_pct: Optional[float] = None
    mem_usage_pct: Optional[float] = None
    mem_used_bytes: Optional[int] = None
    mem_total_bytes: Optional[int] = None
    disk_read_bytes_ps: Optional[int] = None
    disk_write_bytes_ps: Optional[int] = None
    net_rx_bytes_ps: Optional[int] = None
    net_tx_bytes_ps: Optional[int] = None


class MetricsBatchRequest(BaseModel):
    agent_id: UUID
    metrics: List[MetricPoint] = Field(default_factory=list)


@app.on_event("startup")
def startup() -> None:
    pool.open(wait=True)


@app.on_event("shutdown")
def shutdown() -> None:
    pool.close()


def _get_node_id_by_path(node_path: str) -> int:
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM tree_nodes WHERE path = %s::ltree", (node_path,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail=f"node_path not found: {node_path}")
    return row["id"]


@app.post("/api/v1/agents/register", response_model=RegisterResponse)
def register_agent(payload: RegisterRequest):
    if payload.os_type not in {"windows", "linux", "macos"}:
        raise HTTPException(status_code=400, detail="os_type must be windows/linux/macos")

    node_id = _get_node_id_by_path(payload.node_path)
    agent_id = uuid4()

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agents (
              id, hostname, os_type, os_version, ip_address, node_id, agent_version,
              status, last_seen_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,'online',NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (
                str(agent_id),
                payload.hostname,
                payload.os_type,
                payload.os_version,
                payload.ip_address,
                node_id,
                payload.agent_version,
            ),
        )

    return RegisterResponse(agent_id=agent_id, token="replace-with-real-jwt")


@app.post("/api/v1/metrics/batch")
def ingest_metrics(payload: MetricsBatchRequest):
    if not payload.metrics:
        return {"accepted": 0}

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM agents WHERE id = %s", (str(payload.agent_id),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="agent not found")

        rows = [
            (
                m.time,
                str(payload.agent_id),
                m.cpu_usage_pct,
                m.mem_usage_pct,
                m.mem_used_bytes,
                m.mem_total_bytes,
                m.disk_read_bytes_ps,
                m.disk_write_bytes_ps,
                m.net_rx_bytes_ps,
                m.net_tx_bytes_ps,
            )
            for m in payload.metrics
        ]
        cur.executemany(
            """
            INSERT INTO metrics_resource (
              time, agent_id, cpu_usage_pct, mem_usage_pct, mem_used_bytes, mem_total_bytes,
              disk_read_bytes_ps, disk_write_bytes_ps, net_rx_bytes_ps, net_tx_bytes_ps
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (time, agent_id) DO NOTHING
            """,
            rows,
        )
        cur.execute("UPDATE agents SET last_seen_at = NOW(), status='online' WHERE id = %s", (str(payload.agent_id),))

    return {"accepted": len(rows)}


@app.get("/api/v1/tree")
def get_tree():
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, parent_id, name, path::text AS path FROM tree_nodes ORDER BY path"
        )
        rows = cur.fetchall()
    return rows


@app.get("/api/v1/nodes/{node_id}/agents")
def get_agents_by_node(
    node_id: int,
    include_descendants: bool = True,
    page: int = 1,
    size: int = 50,
    sort: str = Query("cpu_usage_pct,desc"),
):
    offset = (max(page, 1) - 1) * max(size, 1)
    sort_field, sort_dir = (sort.split(",", 1) + ["desc"])[:2]
    sort_field = sort_field if sort_field in {"cpu_usage_pct", "mem_usage_pct", "last_seen_at", "hostname"} else "hostname"
    sort_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT path FROM tree_nodes WHERE id = %s", (node_id,))
        node = cur.fetchone()
        if not node:
            raise HTTPException(status_code=404, detail="node not found")

        path_clause = "n.path <@ %s::ltree" if include_descendants else "n.id = %s"
        path_value = node["path"] if include_descendants else node_id

        cur.execute(
            f"""
            WITH target_agents AS (
              SELECT a.*
              FROM agents a
              JOIN tree_nodes n ON n.id = a.node_id
              WHERE {path_clause}
            ),
            latest_metrics AS (
              SELECT DISTINCT ON (mr.agent_id)
                mr.agent_id, mr.time, mr.cpu_usage_pct, mr.mem_usage_pct,
                mr.disk_read_bytes_ps, mr.disk_write_bytes_ps, mr.net_rx_bytes_ps, mr.net_tx_bytes_ps
              FROM metrics_resource mr
              JOIN target_agents ta ON ta.id = mr.agent_id
              ORDER BY mr.agent_id, mr.time DESC
            )
            SELECT
              ta.id::text AS agent_id, ta.hostname, ta.os_type, ta.status, ta.last_seen_at,
              lm.cpu_usage_pct, lm.mem_usage_pct, lm.disk_read_bytes_ps, lm.disk_write_bytes_ps,
              lm.net_rx_bytes_ps, lm.net_tx_bytes_ps
            FROM target_agents ta
            LEFT JOIN latest_metrics lm ON lm.agent_id = ta.id
            ORDER BY {sort_field} {sort_dir} NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (path_value, size, offset),
        )
        items = cur.fetchall()

        cur.execute(
            f"""
            SELECT COUNT(*) AS cnt
            FROM agents a
            JOIN tree_nodes n ON n.id = a.node_id
            WHERE {path_clause}
            """,
            (path_value,),
        )
        total = cur.fetchone()["cnt"]

    return {"total": total, "items": items}


@app.get("/api/v1/agents/{agent_id}/metrics")
def get_agent_metrics(agent_id: UUID, from_ts: datetime, to_ts: datetime, step: str = "60s"):
    _ = step
    if from_ts >= to_ts:
        raise HTTPException(status_code=400, detail="from_ts must be earlier than to_ts")

    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT time, cpu_usage_pct, mem_usage_pct, disk_read_bytes_ps, disk_write_bytes_ps,
                   net_rx_bytes_ps, net_tx_bytes_ps
            FROM metrics_resource
            WHERE agent_id = %s AND time BETWEEN %s AND %s
            ORDER BY time ASC
            """,
            (str(agent_id), from_ts, to_ts),
        )
        series = cur.fetchall()

    return {"series": series}
