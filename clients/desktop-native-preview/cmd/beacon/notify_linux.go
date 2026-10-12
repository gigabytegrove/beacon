//go:build linux

package main

import (
	"os/exec"
	"strings"
)

// Desktop notifications are best effort and never block the X11 event loop.
// Arguments are passed directly (never through a shell).
func systemNotice(title, message string) {
	if len(title) > 140 {
		title = title[:140]
	}
	if len(message) > 500 {
		message = message[:500]
	}
	cmd := exec.Command("notify-send", "--app-name=Beacon", "--expire-time=7000", strings.TrimSpace(title), message)
	_ = cmd.Run()
}
