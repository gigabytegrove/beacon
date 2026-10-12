#!/usr/bin/env bash
set -Eeuo pipefail
# Isolated, destructive-to-ITS-OWN-EPHEMERAL-CONTAINER native-updater smoke test.
# NEVER touches the user's existing Beacon service or named database volume.
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

command -v docker >/dev/null || { echo 'ERROR: Docker CLI required.' >&2; exit 1; }
docker info >/dev/null || { echo 'ERROR: Cannot reach Docker Engine.' >&2; exit 1; }

image="beacon-native-smoketest:local"
id=""
cleanup(){
  if [[ -n "$id" ]]; then
    docker rm -f "$id" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo '===== Beacon native GitHub updater acceptance test ====='
echo 'Building test image from this checkout (no production data).'
docker build -t "$image" .

echo 'Starting isolated read-only smoke-test container.'
id="$(docker run -d \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=16m \
  --tmpfs /data:rw,nosuid,nodev,size=64m,uid=10001,gid=10001 \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -e BEACON_DB=/data/beacon.db \
  -e BEACON_REVISION=smoke-test \
  "$image")"

check(){
  docker exec "$id" python -c '
import json,urllib.request
with urllib.request.urlopen("http://127.0.0.1:8765/health",timeout=2) as r:
    d=json.load(r)
assert d["status"]=="ok",d
assert d["revision"]=="smoke-test",d
' >/dev/null 2>&1
}

ready=0
for _ in $(seq 1 60); do
  if check; then ready=1; break; fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$id")" != true ]]; then break; fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo 'FAIL: Native launcher did not start a healthy server.' >&2
  docker logs --tail 100 "$id" >&2
  exit 1
fi
echo 'PASS: Native supervisor starts a healthy server in a read-only container.'

echo 'Injecting an intentionally broken code release into the EPHEMERAL test volume.'
docker exec "$id" python -c '
import json,pathlib
root=pathlib.Path("/data/beacon-updates")
sha="a"*40
folder=root/"releases"/sha/"server"
folder.mkdir(parents=True,exist_ok=True)
(folder/"main.py").write_text("raise RuntimeError(\"intentional rollback smoke test\")\n")
(folder.parent/"release.json").write_text(json.dumps({"revision":sha,"version":"0.9.1"}))
(root/"pending.json").write_text(json.dumps({"revision":sha}))
'

recovered=0
for _ in $(seq 1 100); do
  if check && docker exec "$id" python -c '
import json,pathlib
root=pathlib.Path("/data/beacon-updates")
state=json.loads((root/"current.json").read_text())
status=json.loads((root/"status.json").read_text())
assert state["revision"]=="",state
assert "health check failed" in status.get("last_failure","").lower(),status
' >/dev/null 2>&1; then
    recovered=1
    break
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$id")" != true ]]; then break; fi
  sleep 1
done
if [[ "$recovered" != 1 ]]; then
  echo 'FAIL: Broken staged update did not roll back and return to healthy base.' >&2
  docker logs --tail 120 "$id" >&2
  exit 1
fi
echo 'PASS: Bad release automatically rolled back; original server is healthy.'
echo 'PASS: Test used an ephemeral tmpfs, no production container or data volume.'
