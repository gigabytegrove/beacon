# Building the independent Go/Win32 + Go/X11 premium visual preview

**This is a separate feature-incomplete development preview.** The main Beacon Windows/Linux implementation remains `clients/desktop-go` (Go/Fyne), which has broader account, security, notification and multi-device features.

The preview is pure Go plus native OS window APIs. End users do not need the Go SDK or Python. Linux requires a working X11-compatible desktop and `libX11`. The pre-rendered PNG/bitmap font atlases are committed so **Python, Pillow and font files are not required to compile the client**.

## Run source tests

From this directory:

```bash
go test -race -count=1 ./...
go vet ./...
```

## Compile Windows x64

On Windows with Go 1.23+, or from a Go build machine capable of cross-compiling:

```bash
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags="-s -w -H=windowsgui" -o Beacon-Messenger-Windows-x64.exe ./cmd/beacon
```

The Windows preview uses Win32/GDI and the standard library, not Fyne or Python. Confirm PE32+ architecture and execute it on a Windows PC to validate the actual runtime.

## Compile Linux x64

On Linux with Go 1.23+, gcc and the distro's X11 headers:

```bash
CGO_ENABLED=1 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o Beacon-Messenger-Linux-x64 ./cmd/beacon
```

A Linux runtime machine needs `libX11` and a graphical display. These are not Python dependencies.

## Branding assets

The generated background/template PNGs and bitmap font atlases live in `cmd/beacon/assets/`. The optional `create_skin.py` developer script regenerates layout rasters with Pillow and installed Inter/DejaVu fonts. It now uses paths relative to this directory. The project does **not** distribute original font files.

`package.py`, `qa_live.py` and `replace_render.py` are developer utilities; they are **not** needed by the installed desktop client. The existing snapshots were produced by a prior local build and the exact hashes for downloadable preview archives live under `releases/previews/2026-10-11/`.

## What this preview is missing

No OS credential vault, signed installer, Windows runtime acceptance test, system tray, reliable native notifications, rich profile/device management, or full native Android APK. Keep the primary Go/Fyne and Java implementations intact until feature parity has been demonstrated.
