# Beacon platform builds

## Windows

Requirements: Windows 10/11, Python 3.12, Tkinter, `clients/desktop/requirements-windows.txt`.

```powershell
py -3 -m pip install -r clients/desktop/requirements-windows.txt
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name Beacon --collect-all pystray --collect-all winotify clients/desktop/beacon_desktop.py
```

Local output: `dist/Beacon.exe`. The GitHub Actions Windows workflow labels its successful artifact `Beacon-Windows-0.7.0.exe`.

## Linux

Requirements: Linux desktop with display server, Python 3.12 with Tkinter, optional AppIndicator/X11 tray support, `clients/desktop/requirements-linux.txt`.

```bash
python3 -m pip install -r clients/desktop/requirements-linux.txt
python3 -m PyInstaller --clean --noconfirm --onefile --windowed --name beacon --collect-all pystray clients/desktop/beacon_desktop.py
```

The GitHub Actions Linux workflow packages the binary with `beacon.desktop`, `beacon.svg`, `install.sh` and `uninstall.sh` as `Beacon-Linux-0.7.0.tar.gz`. Extract and run `./install.sh` inside the extracted directory; it installs to the current user's `~/.local/bin` and XDG applications directory without root access.

## Android

Requirements: Android Studio, JDK 17, Gradle 8.9, SDK platform 35.

Open `clients/android` in Android Studio and assemble a debug APK. The expected filename after successful build is `Beacon-Android-0.7.0-debug.apk`.

## Verification

The source repository and CI workflow do **not** include verified binaries by themselves. Review Actions job status, runner-assigned steps and artifact files. The private GitHub repository has previously shown failed workflow runs before runner allocation. Follow [release checklist](RELEASE-CHECKLIST.md).
