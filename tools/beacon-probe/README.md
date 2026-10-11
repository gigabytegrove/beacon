# Beacon Probe — compiled Go LAN/API diagnostics

This is **not** the AIM-style GUI messenger and never substitutes for client testing.

The tool uses only the Go standard library, so its Windows and Linux binaries have no Fyne, Python or Android dependencies. It was compiled and smoke-tested on a simulated local API on October 11, 2026.

Build from source where Go is available:

```bash
cd tools/beacon-probe
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o Beacon-Probe-Linux-amd64 main.go
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o Beacon-Probe-Windows-amd64.exe main.go
```

Test health, without credentials:

```powershell
.\Beacon-Probe-Windows-amd64.exe -server http://YOUR_BEACON_LAN_IP:8765
```

Test authenticated APIs and automatically revoke its temporary device session:

```powershell
$env:BEACON_PASSWORD = "your-password"
.\Beacon-Probe-Windows-amd64.exe -server http://YOUR_BEACON_LAN_IP:8765 -username admin
Remove-Item Env:BEACON_PASSWORD
```

The tool checks `/health`, `/api/login`, `/api/me`, `/api/users`, `/api/buddies`, `/api/groups`, `/api/sessions`, `/api/conversations`, `/api/events/latest` and `/api/logout`. It doesn't send chat messages, display session tokens or retain passwords.

Use HTTPS when traversing networks you do not trust. Do not paste the password into a shared or recorded terminal.
