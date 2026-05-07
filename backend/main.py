from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI(title="SMS Monitoring API", version="0.1.0")


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


@app.post("/api/v1/agents/register", response_model=RegisterResponse)
def register_agent(payload: RegisterRequest):
    _ = payload
    return RegisterResponse(agent_id=uuid4(), token="replace-with-real-jwt")


@app.post("/api/v1/metrics/batch")
def ingest_metrics(payload: MetricsBatchRequest):
    return {"accepted": len(payload.metrics)}


@app.get("/api/v1/tree")
def get_tree():
    return [
        {"id": 1, "parent_id": None, "name": "HQ", "path": "HQ"},
        {"id": 2, "parent_id": 1, "name": "Seoul", "path": "HQ.Seoul"},
        {"id": 3, "parent_id": 2, "name": "Payment", "path": "HQ.Seoul.Payment"},
    ]


@app.get("/api/v1/nodes/{node_id}/agents")
def get_agents_by_node(
    node_id: int,
    include_descendants: bool = True,
    page: int = 1,
    size: int = 50,
    sort: str = Query("cpu_usage_pct,desc"),
):
    _ = (node_id, include_descendants, page, size, sort)
    return {
        "total": 1,
        "items": [
            {
                "agent_id": str(uuid4()),
                "hostname": "web-01",
                "os_type": "linux",
                "status": "online",
                "last_seen_at": datetime.utcnow().isoformat() + "Z",
                "cpu_usage_pct": 25.3,
                "mem_usage_pct": 48.7,
                "disk_read_bytes_ps": 110000,
                "disk_write_bytes_ps": 220000,
                "net_rx_bytes_ps": 330000,
                "net_tx_bytes_ps": 120000,
            }
        ],
    }


@app.get("/api/v1/agents/{agent_id}/metrics")
def get_agent_metrics(agent_id: UUID, from_ts: datetime, to_ts: datetime, step: str = "60s"):
    _ = (agent_id, from_ts, to_ts, step)
    return {
        "series": [
            {
                "time": datetime.utcnow().isoformat() + "Z",
                "cpu_usage_pct": 31.2,
                "mem_usage_pct": 60.1,
            }
        ]
    }
