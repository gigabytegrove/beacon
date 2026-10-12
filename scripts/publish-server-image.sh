#!/usr/bin/env bash
set -Eeuo pipefail

# Local-only image release. No GitHub Actions or Docker access on the Beacon server.
# Usage: bash scripts/publish-server-image.sh 0.8.3
version="${1:-}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
  echo "Usage: bash $0 MAJOR.MINOR.PATCH[-prerelease]" >&2
  exit 2
fi
command -v docker >/dev/null || { echo "ERROR: Docker is required." >&2; exit 1; }
command -v git >/dev/null || { echo "ERROR: Git is required." >&2; exit 1; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: Refusing to publish with uncommitted changes." >&2
  exit 1
fi
if ! docker buildx version >/dev/null 2>&1; then
  echo "ERROR: Docker Buildx is required." >&2
  exit 1
fi
platform="${BEACON_IMAGE_PLATFORMS:-linux/amd64}"
if [[ "$platform" != "linux/amd64" && "$platform" != "linux/arm64" ]]; then
  echo "ERROR: This tested publisher supports one platform per release (linux/amd64 or linux/arm64)." >&2
  exit 1
fi
revision="$(git rev-parse --verify HEAD)"
image="ghcr.io/gigabytegrove/beacon"
local_image="beacon-local-verified:$version"
container_id=""
cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "===== Beacon local GHCR release ====="
echo "Version: $version"
echo "Revision: $revision"
echo "Target: $platform"
echo "Step 1: Build the exact image that will be published."
docker buildx build \
  --platform "$platform" \
  --build-arg "BEACON_VERSION=$version" \
  --build-arg "BEACON_REVISION=$revision" \
  --tag "$local_image" \
  --load .

echo "Step 2: Boot the image in an isolated temporary container."
container_id="$(docker run -d \
  --read-only \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  -e BEACON_DB=/tmp/beacon.db \
  "$local_image")"
ready=0
for ((attempt=1;attempt<=20;attempt++)); do
  if docker exec "$container_id" python -c 'import json,urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8765/health",timeout=2); assert r.status == 200 and json.load(r)["status"] == "ok"' >/dev/null 2>&1; then
    ready=1
    break
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$container_id")" != "true" ]]; then
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "ERROR: The new Beacon image failed its server health check." >&2
  docker logs --tail 80 "$container_id" >&2 || true
  exit 1
fi
docker rm -f "$container_id" >/dev/null
container_id=""

echo "Step 3: Tag the tested image (version plus rolling latest)."
docker tag "$local_image" "$image:$version"
docker tag "$local_image" "$image:latest"

echo "Step 4: Push both tags to GitHub Container Registry."
echo "Docker must already be logged in to ghcr.io with a package-write credential."
docker push "$image:$version"
docker push "$image:latest"

echo "PUBLISHED: $image:$version"
echo "PUBLISHED: $image:latest"
echo "NOTE: New GHCR packages are private by default. Make the package public (or configure Dokploy pull credentials) before switching Compose to image mode."
