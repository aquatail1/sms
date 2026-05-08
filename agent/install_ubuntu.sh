#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

sudo mkdir -p /etc/sms-agent /var/lib/sms-agent
if [ ! -f /etc/sms-agent/sms-agent.env ]; then
  sudo cp .env.example /etc/sms-agent/sms-agent.env
fi
sudo chown -R "$(id -u):$(id -g)" /var/lib/sms-agent

cat <<MSG

SMS Agent 의존성 설치가 완료되었습니다.

다음 파일에서 API 서버 주소와 Tree 경로를 수정하세요:
  /etc/sms-agent/sms-agent.env

1회 전송 테스트:
  cd ${SCRIPT_DIR}
  set -a && source /etc/sms-agent/sms-agent.env && set +a
  ./.venv/bin/python sms_agent.py --once

MSG
