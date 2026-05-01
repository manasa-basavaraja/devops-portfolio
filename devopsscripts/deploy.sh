#!/usr/bin/env bash
set -euo pipefail

# Usage: IMAGE_TAG=v1.2.3 ./deploy.sh
# Requires: curl, docker (or adapt HEALTH_URL to your stack)

IMAGE="${IMAGE:-myapp:latest}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8080/health}"
MAX_WAIT="${MAX_WAIT:-60}"

echo "Pulling ${IMAGE}..."
docker pull "${IMAGE}"

echo "Restarting container..."
docker rm -f myapp 2>/dev/null || true
docker run -d --name myapp -p 8080:8080 "${IMAGE}"

echo "Waiting for health (${MAX_WAIT}s max)..."
for i in $(seq 1 "${MAX_WAIT}"); do
  if curl -fsS "${HEALTH_URL}" >/dev/null; then
    echo "OK: healthy after ${i}s"
    exit 0
  fi
  sleep 1
done
echo "FAIL: health check timed out" >&2
exit 1