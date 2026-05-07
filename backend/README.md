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

```bash
psql "${DATABASE_URL}" <<'SQL'
INSERT INTO tree_nodes (parent_id, name, path, depth) VALUES
(NULL, 'HQ', 'HQ', 0),
(1, 'Seoul', 'HQ.Seoul', 1),
(2, 'Payment', 'HQ.Seoul.Payment', 2)
ON CONFLICT (path) DO NOTHING;
SQL
```

## 6) 빠른 동작 확인

```bash
curl http://127.0.0.1:8000/api/v1/tree
```
