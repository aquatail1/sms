# SMS Agent 설치/실행 가이드

이 에이전트는 Windows, Linux, macOS 서버/PC에서 CPU, Memory, Disk I/O, Network I/O를 수집해 SMS API 서버로 전송합니다.

## 1) 사전 조건

- Python 3.10 이상
- API 서버 접근 가능: 기본 `http://127.0.0.1:8000`
- 서버 DB에 에이전트가 들어갈 Tree 경로가 먼저 존재해야 합니다. 예: `HQ.Seoul.Payment`

## 2) Ubuntu 26.04 Server 설치

`ModuleNotFoundError: No module named 'psutil'` 오류가 나오면 아래 설치 단계를 먼저 수행하지 않은 상태입니다.

간편 설치:

```bash
cd /workspace/sms/agent
./install_ubuntu.sh
```

수동 설치:

```bash
cd /workspace/sms/agent
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
sudo mkdir -p /etc/sms-agent /var/lib/sms-agent
sudo cp .env.example /etc/sms-agent/sms-agent.env
sudo chown -R $(id -u):$(id -g) /var/lib/sms-agent
```

`/etc/sms-agent/sms-agent.env`에서 API 서버 주소와 Tree 경로를 수정합니다.

```bash
SMS_SERVER_URL=http://<API_SERVER_IP>:8000
SMS_NODE_PATH=HQ.Seoul.Payment
SMS_INTERVAL_SECONDS=30
```

1회 전송 테스트:

```bash
set -a
source /etc/sms-agent/sms-agent.env
set +a
./.venv/bin/python sms_agent.py --once
```

또는 venv를 활성화한 상태라면 다음처럼 실행할 수 있습니다.

```bash
source .venv/bin/activate
./sms_agent.py --once
```

## 3) systemd 서비스 등록 (Ubuntu)

```bash
sudo cp /workspace/sms/deploy/systemd/sms-agent.service /etc/systemd/system/sms-agent.service
sudo systemctl daemon-reload
sudo systemctl enable --now sms-agent
sudo systemctl status sms-agent
journalctl -u sms-agent -f
```

> `deploy/systemd/sms-agent.service`의 `User`, `WorkingDirectory`, `EnvironmentFile`, `ExecStart`는 실제 설치 경로에 맞게 수정하세요.

## 4) Windows/macOS 수동 실행

```bash
cd agent
python -m venv .venv
.venv\Scripts\activate     # Windows PowerShell은 .venv\Scripts\Activate.ps1
pip install -r requirements.txt
set SMS_SERVER_URL=http://<API_SERVER_IP>:8000
set SMS_NODE_PATH=HQ.Seoul.Payment
python sms_agent.py --once
python sms_agent.py
```

macOS/Linux shell에서는 `set` 대신 `export`를 사용하세요.

## 5) 수집 항목

- `cpu_usage_pct`
- `mem_usage_pct`, `mem_used_bytes`, `mem_total_bytes`
- `disk_read_bytes_ps`, `disk_write_bytes_ps`
- `net_rx_bytes_ps`, `net_tx_bytes_ps`

네트워크 장애 시 실패한 배치는 `SMS_SPOOL_PATH`에 JSONL로 저장되고 다음 전송 성공 시 재시도됩니다.

## 6) 실행 결과 확인 방법

### Agent PC에서 즉시 확인

`--once` 실행이 성공하면 JSON 결과가 출력됩니다.

```bash
cd /workspace/sms/agent
set -a
source /etc/sms-agent/sms-agent.env
set +a
./.venv/bin/python sms_agent.py --once
```

정상 예시는 다음과 같습니다.

```json
{
  "accepted": 1,
  "agent_id": "등록된-agent-uuid",
  "metric": {
    "cpu_usage_pct": 12.5,
    "mem_usage_pct": 43.2
  },
  "sent_batches": 1
}
```

- `accepted`가 `1` 이상이면 API 서버가 메트릭을 정상 수신한 것입니다.
- 실패하면 `/var/lib/sms-agent/spool.jsonl`에 재전송 대기 데이터가 저장됩니다.

### Agent 서비스 로그 확인

```bash
systemctl status sms-agent
journalctl -u sms-agent -f
```

### API 서버에서 수신 여부 확인

```bash
curl http://<API_SERVER_IP>:8000/api/v1/tree
curl "http://<API_SERVER_IP>:8000/api/v1/nodes/3/agents?include_descendants=true&page=1&size=50"
```

### PostgreSQL에서 직접 확인

```bash
psql "postgresql://sms_user:sms_pass@127.0.0.1:5432/sms" <<'SQL'
SELECT id, hostname, os_type, status, last_seen_at
FROM agents
ORDER BY last_seen_at DESC
LIMIT 10;

SELECT agent_id, time, cpu_usage_pct, mem_usage_pct, disk_read_bytes_ps, disk_write_bytes_ps
FROM metrics_resource
ORDER BY time DESC
LIMIT 10;
SQL
```
