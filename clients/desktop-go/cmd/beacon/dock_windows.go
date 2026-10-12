//go:build windows

package main

import (
    "fmt"
    "os"
    "sync"
    "syscall"
    "unsafe"
)

// Reposition Fyne's existing native window, preserving its canvas and DPI renderer.
var (
    dockUser32 = syscall.NewLazyDLL("user32.dll")
    enumWindows = dockUser32.NewProc("EnumWindows")
    getWindowThreadProcessID = dockUser32.NewProc("GetWindowThreadProcessId")
    getWindowText = dockUser32.NewProc("GetWindowTextW")
    getWindowRect = dockUser32.NewProc("GetWindowRect")
    monitorFromWindow = dockUser32.NewProc("MonitorFromWindow")
    getMonitorInfo = dockUser32.NewProc("GetMonitorInfoW")
    setWindowPos = dockUser32.NewProc("SetWindowPos")
    dockMu sync.Mutex
    undockedBounds nativeRect
    isRightDocked bool
)

type nativeRect struct{ left, top, right, bottom int32 }
type nativeMonitorInfo struct {
    size uint32
    monitor nativeRect
    work nativeRect
    flags uint32
}
const (
    monitorDefaultToNearest = 2
    swpNoZOrder = 0x0004
    swpNoActivate = 0x0010
    swpFrameChanged = 0x0020
)
func buddyListHandle() (uintptr, error) {
    process := uint32(os.Getpid())
    var match uintptr
    callback := syscall.NewCallback(func(hwnd, _ uintptr) uintptr {
        var owner uint32
        getWindowThreadProcessID.Call(hwnd, uintptr(unsafe.Pointer(&owner)))
        if owner != process { return 1 }
        var buf [160]uint16
        n, _, _ := getWindowText.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
        if n == 0 { return 1 }
        if syscall.UTF16ToString(buf[:]) == "Beacon Messenger · Buddy List" {
            match = hwnd
            return 0
        }
        return 1
    })
    enumWindows.Call(callback, 0)
    if match == 0 { return 0, fmt.Errorf("Beacon buddy list window is not open") }
    return match, nil
}
func queryBounds(hwnd uintptr) (nativeRect, error) {
    var r nativeRect
    ok, _, e := getWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&r)))
    if ok == 0 { return r, fmt.Errorf("cannot read buddy list window bounds: %w", e) }
    return r, nil
}
func placeWindow(hwnd uintptr, bounds nativeRect) error {
    width, height := bounds.right-bounds.left, bounds.bottom-bounds.top
    if width <= 0 || height <= 0 { return fmt.Errorf("invalid buddy list dimensions") }
    ok, _, e := setWindowPos.Call(hwnd, 0, uintptr(int32(bounds.left)), uintptr(int32(bounds.top)),
        uintptr(width), uintptr(height), swpNoZOrder|swpNoActivate|swpFrameChanged)
    if ok == 0 { return fmt.Errorf("cannot position buddy list window: %w", e) }
    return nil
}
func dockBuddyList() error {
    dockMu.Lock()
    defer dockMu.Unlock()
    hwnd, err := buddyListHandle()
    if err != nil { return err }
    current, err := queryBounds(hwnd)
    if err != nil { return err }
    monitor, _, e := monitorFromWindow.Call(hwnd, monitorDefaultToNearest)
    if monitor == 0 { return fmt.Errorf("cannot locate the buddy list monitor: %w", e) }
    info := nativeMonitorInfo{size: uint32(unsafe.Sizeof(nativeMonitorInfo{}))}
    ok, _, e := getMonitorInfo.Call(monitor, uintptr(unsafe.Pointer(&info)))
    if ok == 0 { return fmt.Errorf("cannot read monitor work area: %w", e) }
    width := current.right-current.left
    if width > info.work.right-info.work.left { width = info.work.right-info.work.left }
    if width <= 0 { return fmt.Errorf("monitor work area has no width") }
    next := nativeRect{left: info.work.right-width, top: info.work.top,
        right: info.work.right, bottom: info.work.bottom}
    if next.bottom <= next.top { return fmt.Errorf("monitor work area has no height") }
    if err := placeWindow(hwnd, next); err != nil { return err }
    if !isRightDocked { undockedBounds = current }
    isRightDocked = true
    return nil
}
func undockBuddyList() error {
    dockMu.Lock()
    defer dockMu.Unlock()
    if !isRightDocked { return nil }
    hwnd, err := buddyListHandle()
    if err != nil { return err }
    if err := placeWindow(hwnd, undockedBounds); err != nil { return err }
    isRightDocked = false
    return nil
}
