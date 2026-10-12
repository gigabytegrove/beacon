#!/usr/bin/env bash
# Bootstrap Beacon 0.9.1 into an existing Docker Compose service.
# One-time installation of native GitHub updater; never delete the data volume.
set -Eeuo pipefail
for bin in docker git python3; do command -v "$bin" >/dev/null || { echo "Missing $bin"; exit 1; }; done
docker compose version >/dev/null
mapfile -t found < <(docker ps -q --filter label=com.docker.compose.service=beacon)
if ((${#found[@]} != 1)); then
  echo "ERROR: Expected one running Beacon Compose service."
  docker ps -a --filter label=com.docker.compose.service=beacon
  exit 1
fi
cid="${found[0]}"
project="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$cid")"
workdir="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$cid")"
filelist="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$cid")"
volume="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}{{end}}' "$cid")"
image_name="$(docker inspect -f '{{.Config.Image}}' "$cid")"
old_id="$(docker inspect -f '{{.Image}}' "$cid")"
if [[ -z "$project" || -z "$filelist" || -z "$volume" || -z "$image_name" || ! -d "$workdir" || "$image_name" == sha256:* || "$image_name" == *@sha256:* ]]; then
  echo "ERROR: Existing Compose service metadata incomplete; stopping."
  exit 1
fi
IFS=',' read -ra filenames <<< "$filelist"
args=(--project-directory "$workdir" -p "$project")
for f in "${filenames[@]}"; do
  [[ -f "$f" ]] || { echo "ERROR: Missing original Compose file: $f"; exit 1; }
  args+=(-f "$f")
done
cfg="$(mktemp)"
smoke=""
replaced=0
success=0
previous_tag="beacon-previous-before-091:$(date +%Y%m%d%H%M%S)"
cleanup() {
  rc=$?
  trap - EXIT
  [[ -z "$smoke" ]] || docker rm -f "$smoke" >/dev/null 2>&1 || true
  if ((replaced && !success)); then
    echo "NEW RELEASE FAILED — attempting restoration of previous image."
    docker tag "$old_id" "$image_name" || true
    docker compose "${args[@]}" up -d --no-deps --no-build --pull never --force-recreate beacon || true
    echo "Original database volume was not deleted: $volume"
  fi
  rm -f "$cfg"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
docker compose "${args[@]}" config --format json > "$cfg"
python3 - "$cfg" "$project" "$volume" "$image_name" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1]))
svc=cfg.get('services',{}).get('beacon')
if not svc: sys.exit('ERROR: No beacon service in original Compose configuration.')
if svc.get('image') and svc['image']!=sys.argv[4]:
    sys.exit('ERROR: Compose image tag and running image tag differ.')
mounts=[v for v in svc.get('volumes',[]) if v.get('target')=='/data']
if len(mounts)!=1 or mounts[0].get('type')!='volume':
    sys.exit('ERROR: Expected exactly one named persistent /data volume.')
source=mounts[0].get('source','')
volumes=cfg.get('volumes',{})
entry=volumes.get(source,{})
expected=entry.get('name') or (sys.argv[2]+'_'+source if source in volumes else source)
if expected!=sys.argv[3]:
    sys.exit('ERROR: Data volume would change from '+sys.argv[3]+' to '+expected)
print('Verified: original Compose service and named data volume.')
PY
echo "Existing project: $project | volume: $volume"
echo "===== CONSISTENT DATABASE BACKUP ====="
docker exec -i "$cid" python - <<'PY'
import os,sqlite3,time
src=os.getenv('BEACON_DB','/data/beacon.db')
if not src.startswith('/data/') or not os.path.isfile(src):
    raise SystemExit('ERROR: Existing Beacon database not found.')
dest='/data/beacon-pre-0.9.1-'+time.strftime('%Y%m%d-%H%M%S')+'.sqlite3'
with sqlite3.connect('file:'+src+'?mode=ro',uri=True) as old, sqlite3.connect(dest) as copy:
    old.backup(copy)
    if copy.execute('PRAGMA quick_check').fetchone()[0]!='ok':
        raise SystemExit('ERROR: SQLite backup failed integrity check.')
os.chmod(dest,0o600)
print('Verified database backup:',dest)
PY
echo "===== GITHUB SOURCE BUILD ====="
sha="$(git ls-remote --exit-code https://github.com/gigabytegrove/beacon.git refs/heads/main | awk '{print $1}')"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR: Invalid GitHub revision."; exit 1; }
stage="beacon-preflight-091:$(date +%Y%m%d%H%M%S)"
echo "Source: https://github.com/gigabytegrove/beacon/commit/$sha"
docker build --pull --no-cache --build-arg BEACON_VERSION=0.9.1 \
  --build-arg "BEACON_REVISION=$sha" -t "$stage" \
  "https://github.com/gigabytegrove/beacon.git#$sha"
echo "===== ISOLATED ACCOUNT-CREATION SMOKE TEST ====="
smoke="$(docker run -d --read-only --security-opt no-new-privileges:true --cap-drop ALL \
  --tmpfs /data:rw,nosuid,nodev,mode=1777,size=64m \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777,size=32m "$stage")"
ready=0
for attempt in {1..35}; do
  if docker exec "$smoke" python -c '
import json,os,urllib.request
with urllib.request.urlopen("http://127.0.0.1:8765/health",timeout=2) as r: d=json.load(r)
assert d["status"]=="ok" and d["version"]=="0.9.1" and d["revision"]==os.environ["BEACON_REVISION"]
' >/dev/null 2>&1; then ready=1; break; fi
  [[ "$(docker inspect -f '{{.State.Running}}' "$smoke")" == true ]] || break
  sleep 1
done
if (( ! ready )); then docker logs --tail 80 "$smoke" || true; echo 'ERROR: Build did not start in isolation.'; exit 1; fi
docker exec -i "$smoke" python - <<'PY'
import hashlib,json,os
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
base='http://127.0.0.1:8765'
def req(path,method='GET',payload=None,token=None):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    with urlopen(Request(base+path,method=method,headers=headers,data=json.dumps(payload).encode() if payload is not None else None),timeout=8) as r:
        return r.status,json.load(r)
key=Path(os.getenv('BEACON_DB','/data/beacon.db')+'.setup-code').read_text().strip()
status,data=req('/api/setup','POST',{'setup_code':key,'username':'preflightadmin','display_name':'Preflight Admin','password':'temporary isolated test password'})
assert status==201,(status,data)
status,data=req('/api/login','POST',{'username':'preflightadmin','password':'temporary isolated test password','device_name':'Isolated check'})
assert status==200,data
token=data['token']
status,data=req('/api/admin/users','POST',{'username':'preflightmember','display_name':'Preflight Member','password':'another isolated test password'},token)
assert status==201 and data['display_name']=='Preflight Member',data
status,users=req('/api/admin/users',token=token)
assert status==200 and any(user['username']=='preflightmember' for user in users)
try:
    req('/api/admin/users','POST',{'username':'PREFLIGHTMEMBER','display_name':'Duplicate','password':'another isolated test password'},token)
except HTTPError as e:
    assert e.code==409,e.code
else: raise AssertionError('Duplicate account was created')
with urlopen(base+'/',timeout=8) as r: html=r.read()
for marker in (b'id="createUserForm"',b'id="adminBuildBadge"',b'id="adminUpdateCheck"'):
    assert marker in html,marker
_,health=req('/health')
assert hashlib.sha256(html).hexdigest()[:16]==health['ui_sha256']
print('PASS: Admin setup, login, account creation, duplicate rejection, member listing, and UI hash.')
PY
docker rm -f "$smoke" >/dev/null
smoke=""
echo "===== REPLACE ONLY EXISTING BEACON IMAGE ====="
docker tag "$old_id" "$previous_tag"
docker tag "$stage" "$image_name"
replaced=1
target_id="$(docker image inspect -f '{{.Id}}' "$stage")"
docker compose "${args[@]}" up -d --no-deps --no-build --pull never --force-recreate beacon
newcid="$(docker compose "${args[@]}" ps -q beacon)"
[[ -n "$newcid" ]] || { echo "ERROR: New Beacon container missing."; exit 1; }
[[ "$(docker inspect -f '{{.Image}}' "$newcid")" == "$target_id" ]] || { echo "ERROR: Compose started a different image."; exit 1; }
[[ "$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}{{end}}' "$newcid")" == "$volume" ]] || { echo "ERROR: Database mount changed."; exit 1; }
echo "===== VERIFY LIVE BEACON AND ACTUAL WEB UI ====="
live=0
for attempt in {1..35}; do
  if docker exec "$newcid" python -c '
import json,hashlib,os,urllib.request
with urllib.request.urlopen("http://127.0.0.1:8765/health",timeout=2) as r: d=json.load(r)
with urllib.request.urlopen("http://127.0.0.1:8765/",timeout=2) as r: html=r.read()
assert d.get("status")=="ok" and d.get("version")=="0.9.1",d
assert d.get("revision")==os.environ["BEACON_REVISION"],d
assert d["ui_sha256"]==hashlib.sha256(html).hexdigest()[:16],d
assert b"adminBuildBadge" in html and b"createUserForm" in html
print("LIVE:",json.dumps(d))
' 2>/dev/null; then live=1; break; fi
  sleep 2
done
if (( ! live )); then docker logs --tail 100 "$newcid" || true; echo "ERROR: Live build/UI verification failed."; exit 1; fi
success=1
echo "===== SUCCESS — BEACON 0.9.1 DEPLOYED ====="
echo "GitHub revision: $sha"
echo "Original database volume: $volume"
echo "Previous image retained as: $previous_tag"
echo "The temporary account-creation test used an isolated disposable database."
echo "Open Beacon Control Center: version/revision should appear in the header."
