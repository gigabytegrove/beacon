//go:build windows

package main

import "syscall"

// Windows sound is intentionally non-blocking. A future native toast can be
// layered on without introducing a separate runtime dependency.
func systemNotice(title, message string) {
	_ = title
	_ = message
	dll := syscall.NewLazyDLL("user32.dll")
	_, _, _ = dll.NewProc("MessageBeep").Call(0x00000040)
}
