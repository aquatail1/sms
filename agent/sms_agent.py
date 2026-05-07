#!/usr/bin/env python3
"""Cross-platform SMS monitoring agent.

The agent registers itself with the SMS FastAPI server, periodically collects
CPU, memory, disk I/O, and network I/O metrics via psutil, then sends metric
batches to the server. Failed batches are stored in a local JSONL spool file and
retried on the next successful network window.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

import psutil


DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_STATE_PATH = Path.home() / ".sms-agent" / "state.json"
DEFAULT_SPOOL_PATH = Path.home() / ".sms-agent" / "spool.jsonl"


@dataclass(frozen=True)
class AgentConfig:
    server_url: str
    node_path: str
    hostname: str
    interval_seconds: int
    state_path: Path
    spool_path: Path
    agent_version: str = "0.1.0"


class ApiClient:
    def __init__(self, server_url: str) -> None:
        self.server_url = server_url.rstrip("/")

    def post_json(self, path: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(f"{self.server_url}{path}", data=body, headers=headers, method="POST")
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def detect_os_type() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def detect_ip_address() -> str | None:
    for addresses in psutil.net_if_addrs().values():
        for address in addresses:
            if address.family == socket.AF_INET and not address.address.startswith("127."):
                return address.address
    return None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_config() -> AgentConfig:
    server_url = os.getenv("SMS_SERVER_URL", "http://127.0.0.1:8000")
    node_path = os.getenv("SMS_NODE_PATH", "HQ.Seoul.Payment")
    hostname = os.getenv("SMS_HOSTNAME", socket.gethostname())
    interval_seconds = int(os.getenv("SMS_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS)))
    state_path = Path(os.getenv("SMS_STATE_PATH", str(DEFAULT_STATE_PATH))).expanduser()
    spool_path = Path(os.getenv("SMS_SPOOL_PATH", str(DEFAULT_SPOOL_PATH))).expanduser()
    return AgentConfig(
        server_url=server_url,
        node_path=node_path,
        hostname=hostname,
        interval_seconds=interval_seconds,
        state_path=state_path,
        spool_path=spool_path,
    )


def ensure_registered(config: AgentConfig, client: ApiClient) -> dict[str, str]:
    state = load_json(config.state_path)
    agent_id = state.get("agent_id")
    token = state.get("token")
    if agent_id and token:
        UUID(agent_id)
        return {"agent_id": agent_id, "token": token}

    response = client.post_json(
        "/api/v1/agents/register",
        {
            "hostname": config.hostname,
            "os_type": detect_os_type(),
            "os_version": platform.platform(),
            "ip_address": detect_ip_address(),
            "agent_version": config.agent_version,
            "node_path": config.node_path,
        },
    )
    registered = {"agent_id": response["agent_id"], "token": response["token"]}
    save_json(config.state_path, registered)
    return registered


class MetricCollector:
    def __init__(self) -> None:
        self.previous_disk = psutil.disk_io_counters()
        self.previous_net = psutil.net_io_counters()
        self.previous_time = time.monotonic()
        psutil.cpu_percent(interval=None)

    def collect(self) -> dict[str, Any]:
        now = time.monotonic()
        elapsed = max(now - self.previous_time, 1.0)
        disk = psutil.disk_io_counters()
        net = psutil.net_io_counters()
        memory = psutil.virtual_memory()

        metric = {
            "time": utc_now_iso(),
            "cpu_usage_pct": round(psutil.cpu_percent(interval=None), 2),
            "mem_usage_pct": round(memory.percent, 2),
            "mem_used_bytes": int(memory.used),
            "mem_total_bytes": int(memory.total),
            "disk_read_bytes_ps": int((disk.read_bytes - self.previous_disk.read_bytes) / elapsed),
            "disk_write_bytes_ps": int((disk.write_bytes - self.previous_disk.write_bytes) / elapsed),
            "net_rx_bytes_ps": int((net.bytes_recv - self.previous_net.bytes_recv) / elapsed),
            "net_tx_bytes_ps": int((net.bytes_sent - self.previous_net.bytes_sent) / elapsed),
        }

        self.previous_disk = disk
        self.previous_net = net
        self.previous_time = now
        return metric


class Spool:
    def __init__(self, path: Path, max_batches: int = 1000) -> None:
        self.path = path
        self.max_batches = max_batches

    def enqueue(self, batch: dict[str, Any]) -> None:
        self.enqueue_many([batch])

    def enqueue_many(self, batches: list[dict[str, Any]]) -> None:
        if not batches:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else []
        existing.extend(json.dumps(batch, sort_keys=True) for batch in batches)
        kept = existing[-self.max_batches :]
        self.path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    def drain(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.path.unlink(missing_ok=True)
        return [json.loads(line) for line in lines]


def send_batch(client: ApiClient, auth: dict[str, str], metrics: list[dict[str, Any]]) -> None:
    client.post_json(
        "/api/v1/metrics/batch",
        {"agent_id": auth["agent_id"], "metrics": metrics},
        token=auth["token"],
    )


def run_once(config: AgentConfig, client: ApiClient, collector: MetricCollector, spool: Spool) -> None:
    auth = ensure_registered(config, client)
    pending_batches = spool.drain()
    current_batch = {"metrics": [collector.collect()]}
    all_batches = [*pending_batches, current_batch]

    for index, batch in enumerate(all_batches):
        try:
            send_batch(client, auth, batch["metrics"])
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            spool.enqueue_many(all_batches[index:])
            raise


def run_forever(config: AgentConfig) -> None:
    client = ApiClient(config.server_url)
    collector = MetricCollector()
    spool = Spool(config.spool_path)

    while True:
        try:
            run_once(config, client, collector, spool)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            print(f"metric send failed; queued for retry: {exc}", flush=True)
        time.sleep(config.interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SMS resource monitoring agent")
    parser.add_argument("--once", action="store_true", help="collect and send one metric batch, then exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    client = ApiClient(config.server_url)
    collector = MetricCollector()
    spool = Spool(config.spool_path)
    if args.once:
        run_once(config, client, collector, spool)
        return
    run_forever(config)


if __name__ == "__main__":
    main()
