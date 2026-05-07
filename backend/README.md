# Backend 실행 가이드 (Ubuntu Server + PostgreSQL)

## 1) DB 준비

```bash
sudo -u postgres psql <<'SQL'
CREATE DATABASE sms;
CREATE USER sms_user WITH ENCRYPTED PASSWORD 'sms_pass';
GRANT ALL PRIVILEGES ON DATABASE sms TO sms_user;
\c sms
CREATE EXTENSION IF NOT EXISTS ltree;
SQL
```

스키마 적용:

```bash
psql "postgresql://sms_user:sms_pass@127.0.0.1:5432/sms" -f db/schema.sql
```

## 2) Python venv + 의존성 설치

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3) 환경변수 설정

```bash
cp .env.example .env
# 필요시 DATABASE_URL 수정
set -a
source .env
set +a
```

## 4) API 실행

```bash
uvicorn main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}
```

## 5) 초기 트리 데이터 샘플

Agent 등록 시 `SMS_NODE_PATH`에 해당하는 Tree가 없으면 API가 자동으로 생성합니다. 수동으로 먼저 만들고 싶으면 repo root에서 다음을 실행하세요.

```bash
psql "${DATABASE_URL}" -f db/seed.sql
```

## 6) 빠른 동작 확인

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/tree
```

## 7) Agent 실행 후 DB 확인

Agent에서 `./.venv/bin/python sms_agent.py --once`를 실행한 뒤 API 서버 DB에서 아래를 확인하세요.

```bash
psql "${DATABASE_URL}" <<'SQL'
SELECT id, hostname, os_type, status, last_seen_at
FROM agents
ORDER BY last_seen_at DESC
LIMIT 10;

SELECT agent_id, time, cpu_usage_pct, mem_usage_pct
FROM metrics_resource
ORDER BY time DESC
LIMIT 10;
SQL
```

`agents`가 비어 있으면 Agent가 API 서버에 도달하지 못했거나, Agent의 `SMS_SERVER_URL`이 잘못된 것입니다. `curl http://<API_SERVER_IP>:8000/api/v1/health`로 먼저 API 연결을 확인하세요.

## 8) 5173 포트 Frontend 확인

Vite 개발 서버를 5173 포트로 실행할 때 `/api` 요청은 `frontend/vite.config.js`에서 `http://127.0.0.1:8000`으로 프록시됩니다.

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://<SERVER_IP>:5173`에 접속하면 Tree와 Agent 목록을 확인할 수 있습니다. API 서버가 8000 포트에서 실행 중이어야 합니다.
