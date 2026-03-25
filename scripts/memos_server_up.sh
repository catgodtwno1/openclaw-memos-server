#!/bin/zsh
set -euo pipefail

export DOCKER_HOST="unix:///Users/scott/.colima/default/docker.sock"

SERVICE_DIR="/Users/scott/.openclaw/services/memos-server"
REPO_DIR="$SERVICE_DIR/repo"
ENV_FILE="$SERVICE_DIR/.env"
NETWORK="memos-net"
API_PORT="8765"
IMAGE="local/memos-server:latest"

python3 /Users/scott/.openclaw/workspace/scripts/configure_memos_server.py >/tmp/memos-configure.log

if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  docker network create "$NETWORK" >/dev/null
fi

docker rm -f memos-api memos-neo4j memos-qdrant >/dev/null 2>&1 || true

docker run -d \
  --name memos-neo4j \
  --network "$NETWORK" \
  -p 127.0.0.1:7474:7474 \
  -p 127.0.0.1:7687:7687 \
  -e NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
  -e NEO4J_AUTH=neo4j/12345678 \
  -v "$SERVICE_DIR/data/neo4j:/data" \
  -v "$SERVICE_DIR/data/neo4j-logs:/logs" \
  neo4j:5.26.4 >/tmp/memos-neo4j.log

docker run -d \
  --name memos-qdrant \
  --network "$NETWORK" \
  -p 127.0.0.1:6333:6333 \
  -p 127.0.0.1:6334:6334 \
  -v "$SERVICE_DIR/data/qdrant:/qdrant/storage" \
  qdrant/qdrant:v1.15.3 >/tmp/memos-qdrant.log

# wait for dependencies
for i in {1..60}; do
  NEO_OK=0
  QD_OK=0
  curl -fsS http://127.0.0.1:7474 >/dev/null 2>&1 && NEO_OK=1 || true
  curl -fsS http://127.0.0.1:6333 >/dev/null 2>&1 && QD_OK=1 || true
  if [[ "$NEO_OK" == "1" && "$QD_OK" == "1" ]]; then
    break
  fi
  sleep 2
  if [[ $i == 60 ]]; then
    echo "Dependencies failed to become ready" >&2
    exit 1
  fi
done

docker build -t "$IMAGE" -f "$REPO_DIR/docker/Dockerfile" "$REPO_DIR" >/tmp/memos-build.log

docker run -d \
  --name memos-api \
  --network "$NETWORK" \
  -p "$API_PORT":8000 \
  --env-file "$ENV_FILE" \
  -e PYTHONPATH=/app/src \
  -e HF_ENDPOINT=https://hf-mirror.com \
  -e QDRANT_HOST=memos-qdrant \
  -e QDRANT_PORT=6333 \
  -e NEO4J_URI=bolt://memos-neo4j:7687 \
  "$IMAGE" >/tmp/memos-api.log

for i in {1..90}; do
  if curl -fsS "http://127.0.0.1:${API_PORT}/docs" >/dev/null 2>&1; then
    break
  fi
  sleep 2
  if [[ $i == 90 ]]; then
    echo "MemOS API failed to become ready" >&2
    docker logs --tail 200 memos-api >&2 || true
    exit 1
  fi
done

echo "MemOS API is ready at http://127.0.0.1:${API_PORT}"
echo "LAN URL: http://<SERVER_IP>:${API_PORT}"
echo "Note: this MemOS build does not expose /health; use /docs or /product/* for checks."
