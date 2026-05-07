# SMS Agent 설치/실행 가이드

이 에이전트는 Windows, Linux, macOS 서버/PC에서 CPU, Memory, Disk I/O, Network I/O를 수집해 SMS API 서버로 전송합니다.

## 1) 사전 조건

- Python 3.10 이상
- API 서버 접근 가능: 기본 `http://127.0.0.1:8000`
- 서버 DB에 에이전트가 들어갈 Tree 경로가 먼저 존재해야 합니다. 예: `HQ.Seoul.Payment`

## 2) Ubuntu 26.04 Server 설치

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
