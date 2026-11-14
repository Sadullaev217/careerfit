#!/usr/bin/env bash
# Deploys one commit to one Render service and waits until it is live.
# Usage: RENDER_API_KEY=... scripts/render-deploy.sh <service id> <commit sha>
set -euo pipefail

service="$1"
sha="$2"
api="https://api.render.com/v1/services/$service/deploys"
auth=(-H "Authorization: Bearer $RENDER_API_KEY" -H "Accept: application/json")

response=$(curl -sS --fail-with-body "${auth[@]}" -H "Content-Type: application/json" \
  -d "{\"commitId\": \"$sha\"}" "$api")
deploy=$(jq -r '.id // empty' <<< "$response")

# Render queues the request without an id when another deploy is running; find it by its commit.
for _ in $(seq 1 30); do
  [ -n "$deploy" ] && break
  sleep 10
  deploy=$(curl -sS --fail-with-body "${auth[@]}" "$api?limit=10" |
    jq -r --arg sha "$sha" '[.[] | (.deploy // .) | select(.commit.id == $sha)][0].id // empty')
done
[ -n "$deploy" ] || { echo "Render never started a deploy of $sha on $service"; exit 1; }

# Building the image takes a few minutes; give up after 30.
for _ in $(seq 1 180); do
  status=$(curl -sS --fail-with-body "${auth[@]}" "$api/$deploy" | jq -r '.status')
  case "$status" in
    live) echo "$service: $sha is live"; exit 0 ;;
    build_failed | update_failed | canceled | deactivated | pre_deploy_failed)
      echo "$service: deploy $deploy ended as $status"; exit 1 ;;
  esac
  sleep 10
done
echo "$service: deploy $deploy still $status after 30 minutes"
exit 1
