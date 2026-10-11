# Legacy Beacon Python desktop prototype — Deprecated

**This is NOT the primary Beacon desktop application.** The previous Windows/Linux prototype was implemented in Python/Tkinter without an explicit requirement to use Python. That was a poor choice for Beacon's install-and-run goal.

From v0.8.0, **Windows and Linux use the native Go/Fyne client** at [clients/desktop-go](../desktop-go/README.md). The old Python source remains temporarily in this directory for reference and feature-parity audits. It is **not packaged into the Windows EXE or Linux archive**, not needed to use Beacon, and is not an ongoing primary feature target.

All desktop builds and user instructions should reference Go. Once the replacement has passed native runtime acceptance checks and feature parity, this legacy code can be retired as a separate approved cleanup.

There is no requirement for Beacon end users to install Python, pip, Tkinter or PyInstaller.
