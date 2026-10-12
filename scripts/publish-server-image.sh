#!/usr/bin/env bash
set -Eeuo pipefail

# Local build and publish only. No GitHub Actions or paid build infrastructure.
# Usage: ./scripts/publish-server-image.sh 0.8.2
version="${1:-}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
  echo "Usage: $0 MAJOR.MINOR.PATCH[-prerelease]" >&2
  exit 2
fi
command -v docker >/dev/null || { echo "ERROR: Docker is required." >&2; exit 1; }
command -v git >/dev/null || { echo "ERROR: Git is required." >&2; exit 1; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: Refusing to publish from a dirty working tree." >&2
  exit 1
fi
revision="$(git rev-parse --verify HEAD)"
image="ghcr.io/gigabytegrove/beacon"
platform="${BEACON_IMAGE_PLATFORMS:-linux/amd64}"
if ! docker buildx version >/dev/null 2>&1; then
  echo "ERROR: Docker Buildx is required to build/push images." >&2
  exit 1
fi
echo "Publishing $image:$version and $image:latest"
echo "Commit: $revision"
echo "Platform(s): $platform"
echo "Ensure docker login ghcr.io has been completed with a packages-write credential."
docker buildx build \
  --platform "$platform" \
  --build-arg "BEACON_VERSION=$version" \
  --build-arg "BEACON_REVISION=$revision" \
  --tag "$image:$version" \
  --tag "$image:latest" \
  --push .
echo "Published both tags. Verify visibility and pullability before switching Dokploy to image mode."
