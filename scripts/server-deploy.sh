#!/usr/bin/env bash
# Runs on the demo server, from a release folder that GitHub Actions just unpacked
# (~/careerfit/releases/<sha>). Builds and starts the stack, makes sure the AI model is there, waits
# until the API is ready, then keeps the three newest releases.
set -euo pipefail

release="$(cd "$(dirname "$0")/.." && pwd)"
home="$HOME/careerfit"
[ -f "$home/.env" ] || { echo "Create $home/.env from deploy/server.env.example first"; exit 1; }
cp "$home/.env" "$release/deploy/.env"
cd "$release/deploy"

docker compose up -d --build --remove-orphans
model="$(grep -E '^LLM_MODEL=' .env | cut -d= -f2-)"
docker compose exec -T ollama ollama pull "${model:-qwen3.5:4b}"

# ClamAV loads its signatures for a few minutes after a first start.
for _ in $(seq 1 60); do
  if docker compose exec -T api python -c "import httpx,sys; sys.exit(httpx.get('http://localhost:8000/health/ready').status_code != 200)"; then
    echo "API ready"
    ln -sfn "$release" "$home/current"
    ls -1dt "$home"/releases/*/ | tail -n +4 | xargs -r rm -rf
    docker image prune -f > /dev/null
    exit 0
  fi
  sleep 10
done
docker compose logs --tail 50 api clamav
echo "API not ready after 10 minutes"
exit 1
