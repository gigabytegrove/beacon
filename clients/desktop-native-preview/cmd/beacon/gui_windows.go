//go:build windows

package main

import (
	_ "embed"
	"encoding/binary"
	"fmt"
	"runtime"
	"syscall"
	"unicode/utf16"
	"unsafe"

	"beacon.local/native/internal/beacon"
)

//go:embed assets/icon.ico
var appIcon []byte

var (
	user32               = syscall.NewLazyDLL("user32.dll")
	kernel32             = syscall.NewLazyDLL("kernel32.dll")
	gdi32                = syscall.NewLazyDLL("gdi32.dll")
	pRegisterClass       = user32.NewProc("RegisterClassExW")
	pCreateWindow        = user32.NewProc("CreateWindowExW")
	pDefWindowProc       = user32.NewProc("DefWindowProcW")
	pDestroyWindow       = user32.NewProc("DestroyWindow")
	pShowWindow          = user32.NewProc("ShowWindow")
	pUpdateWindow        = user32.NewProc("UpdateWindow")
	pGetMessage          = user32.NewProc("GetMessageW")
	pTranslateMessage    = user32.NewProc("TranslateMessage")
	pDispatchMessage     = user32.NewProc("DispatchMessageW")
	pPostMessage         = user32.NewProc("PostMessageW")
	pPostQuit            = user32.NewProc("PostQuitMessage")
	pGetModuleHandle     = kernel32.NewProc("GetModuleHandleW")
	pLoadCursor          = user32.NewProc("LoadCursorW")
	pBeginPaint          = user32.NewProc("BeginPaint")
	pEndPaint            = user32.NewProc("EndPaint")
	pInvalidateRect      = user32.NewProc("InvalidateRect")
	pAdjustWindowRect    = user32.NewProc("AdjustWindowRect")
	pSetForegroundWindow = user32.NewProc("SetForegroundWindow")
	pSetWindowText       = user32.NewProc("SetWindowTextW")
	pSendMessageIcon     = user32.NewProc("SendMessageW")
	pCreateIcon          = user32.NewProc("CreateIconFromResourceEx")
	pStretchDIBits       = gdi32.NewProc("StretchDIBits")
)

const (
	WS_OVERLAPPEDWINDOW = 0x00cf0000
	WS_VISIBLE          = 0x10000000
	WS_CAPTION          = 0x00c00000
	WS_SYSMENU          = 0x00080000
	WS_MINIMIZEBOX      = 0x00020000
	WM_DESTROY          = 0x0002
	WM_CLOSE            = 0x0010
	WM_PAINT            = 0x000F
	WM_ERASEBKGND       = 0x0014
	WM_SETFOCUS         = 0x0007
	WM_KILLFOCUS        = 0x0008
	WM_LBUTTONDOWN      = 0x0201
	WM_MOUSEMOVE        = 0x0200
	WM_MOUSEWHEEL       = 0x020A
	WM_CHAR             = 0x0102
	WM_KEYDOWN          = 0x0100
	WM_APP              = 0x8000
	SW_SHOW             = 5
	SRCCOPY             = 0x00CC0020
)

type winClass struct {
	Size, Style                                                        uint32
	Callback                                                           uintptr
	ClassExtra, WindowExtra                                            int32
	Instance, Icon, Cursor, Background, MenuName, ClassName, IconSmall uintptr
}
type winPoint struct{ X, Y int32 }
type winMsg struct {
	Window         uintptr
	Message        uint32
	Pad            uint32
	Wparam, Lparam uintptr
	Time           uint32
	Pt             winPoint
	Private        uint32
}
type winRect struct{ Left, Top, Right, Bottom int32 }
type winBitmapInfo struct {
	Size                         uint32
	Width, Height                int32
	Planes, BitCount             uint16
	Compression, ImageSize       uint32
	XPelsPerMeter, YPelsPerMeter int32
	ClrUsed, ClrImportant        uint32
}
type winPaint struct {
	HDC                uintptr
	Erase              int32
	Rect               winRect
	Restore, IncUpdate int32
	Reserved           [32]byte
}
type winWindow struct {
	hwnd     uintptr
	screen   string
	peer     beacon.Buddy
	focus    bool
	lastRead int
}
type windowsUI struct {
	instance uintptr
	icon     uintptr
	ui       *ClientState
	root     uintptr
	windows  map[uintptr]*winWindow
}

var appWindows *windowsUI

func ptrText(v string) uintptr {
	p, _ := syscall.UTF16PtrFromString(v)
	return uintptr(unsafe.Pointer(p))
}
func iconHandle() uintptr {
	if len(appIcon) < 22 {
		return 0
	}
	count := int(binary.LittleEndian.Uint16(appIcon[4:6]))
	bestSize := 0
	bestOffset := 0
	bestPixels := 0
	for i := 0; i < count; i++ {
		pos := 6 + i*16
		if pos+16 > len(appIcon) {
			break
		}
		width := int(appIcon[pos])
		if width == 0 {
			width = 256
		}
		size := int(binary.LittleEndian.Uint32(appIcon[pos+8 : pos+12]))
		offset := int(binary.LittleEndian.Uint32(appIcon[pos+12 : pos+16]))
		if offset < 0 || offset+size > len(appIcon) || size < 10 {
			continue
		}
		if width <= 64 && width > bestPixels {
			bestPixels = width
			bestSize = size
			bestOffset = offset
		}
	}
	if bestSize == 0 {
		return 0
	}
	icon, _, _ := pCreateIcon.Call(uintptr(unsafe.Pointer(&appIcon[bestOffset])), uintptr(bestSize), 1, 0x00030000, 32, 32, 0)
	return icon
}

func (u *windowsUI) window(screen, title string, peer beacon.Buddy, left, top int32) uintptr {
	width, height := screenSize(screen)
	rect := winRect{0, 0, int32(width), int32(height)}
	style := uint32(WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_VISIBLE)
	pAdjustWindowRect.Call(uintptr(unsafe.Pointer(&rect)), uintptr(style), 0)
	hwnd, _, _ := pCreateWindow.Call(0, ptrText("BeaconPolishedUI"), ptrText(title), uintptr(style), uintptr(left), uintptr(top), uintptr(rect.Right-rect.Left), uintptr(rect.Bottom-rect.Top), 0, 0, u.instance, 0)
	if hwnd == 0 {
		panic("CreateWindowExW returned NULL")
	}
	u.windows[hwnd] = &winWindow{hwnd: hwnd, screen: screen, peer: peer, focus: screen == "chat"}
	if u.icon != 0 {
		pSendMessageIcon.Call(hwnd, 0x0080, 0, u.icon)
		pSendMessageIcon.Call(hwnd, 0x0080, 1, u.icon)
	}
	pShowWindow.Call(hwnd, SW_SHOW)
	pUpdateWindow.Call(hwnd)
	return hwnd
}
func (u *windowsUI) paint(w *winWindow) {
	if w.screen == "roster" && !u.ui.ctl.Snap().Logged {
		w.screen = "login"
		pSetWindowText.Call(w.hwnd, ptrText("Beacon Messenger - Sign in"))
	}
	if w.screen == "login" && u.ui.ctl.Snap().Logged {
		w.screen = "roster"
		pSetWindowText.Call(w.hwnd, ptrText("Beacon Messenger - Buddy List"))
		u.ui.authenticated()
	}
	var ps winPaint
	dc, _, _ := pBeginPaint.Call(w.hwnd, uintptr(unsafe.Pointer(&ps)))
	if dc == 0 {
		return
	}
	img := u.ui.render(w.screen, w.peer.ID)
	width, height := img.Rect.Dx(), img.Rect.Dy()
	buffer := make([]byte, len(img.Pix))
	for i := 0; i+3 < len(buffer); i += 4 {
		buffer[i] = img.Pix[i+2]
		buffer[i+1] = img.Pix[i+1]
		buffer[i+2] = img.Pix[i]
		buffer[i+3] = 0
	}
	bmi := winBitmapInfo{Size: uint32(unsafe.Sizeof(winBitmapInfo{})), Width: int32(width), Height: -int32(height), Planes: 1, BitCount: 32, Compression: 0}
	pStretchDIBits.Call(dc, 0, 0, uintptr(width), uintptr(height), 0, 0, uintptr(width), uintptr(height), uintptr(unsafe.Pointer(&buffer[0])), uintptr(unsafe.Pointer(&bmi)), 0, SRCCOPY)
	pEndPaint.Call(w.hwnd, uintptr(unsafe.Pointer(&ps)))
	if w.screen == "chat" && w.focus {
		s := u.ui.ctl.Snap()
		last := 0
		for _, m := range s.Chats[w.peer.ID] {
			if m.SenderID == w.peer.ID && m.ID > last {
				last = m.ID
			}
		}
		if last > w.lastRead {
			w.lastRead = last
			u.ui.ctl.MarkRead(w.peer.ID, last)
		}
	}
}
func (u *windowsUI) redrawAll() {
	for hwnd := range u.windows {
		pInvalidateRect.Call(hwnd, 0, 0)
	}
}
func (u *windowsUI) doAction(a uiAction) {
	switch a.kind {
	case "chat":
		for _, win := range u.windows {
			if win.screen == "chat" && win.peer.ID == a.peer.ID {
				pSetForegroundWindow.Call(win.hwnd)
				return
			}
		}
		u.ui.ctl.OpenChat(a.peer.ID, a.peer.Name())
		u.window("chat", "Beacon IM - "+a.peer.Name(), a.peer, 230, 90)
	case "directory":
		for _, win := range u.windows {
			if win.screen == "directory" {
				pSetForegroundWindow.Call(win.hwnd)
				return
			}
		}
		u.window("directory", "Beacon Messenger - Add Buddy", beacon.Buddy{}, 240, 160)
	case "add":
		u.ui.ctl.AddBuddy(a.userID)
		for _, win := range u.windows {
			if win.screen == "directory" {
				pDestroyWindow.Call(win.hwnd)
			}
		}
	}
}
func (u *windowsUI) handle(hwnd uintptr, msg uint32, wparam, lparam uintptr) uintptr {
	w, ok := u.windows[hwnd]
	if !ok {
		r, _, _ := pDefWindowProc.Call(hwnd, uintptr(msg), wparam, lparam)
		return r
	}
	switch msg {
	case WM_APP + 1:
		u.redrawAll()
		return 0
	case WM_PAINT:
		u.paint(w)
		return 0
	case WM_ERASEBKGND:
		return 1
	case WM_SETFOCUS:
		w.focus = true
		u.redrawAll()
		return 0
	case WM_KILLFOCUS:
		w.focus = false
		return 0
	case WM_DESTROY:
		if hwnd == u.root {
			pPostQuit.Call(0)
		} else if w.screen == "chat" {
			u.ui.ctl.CloseChat(w.peer.ID)
		}
		delete(u.windows, hwnd)
		return 0
	case WM_CLOSE:
		pDestroyWindow.Call(hwnd)
		return 0
	case WM_MOUSEMOVE:
		x := int(int16(uint16(lparam)))
		y := int(int16(uint16(lparam >> 16)))
		if u.ui.HoverAt(w.screen, w.peer.ID, x, y) {
			pInvalidateRect.Call(hwnd, 0, 0)
		}
		return 0
	case WM_LBUTTONDOWN:
		x := int(int16(uint16(lparam)))
		y := int(int16(uint16(lparam >> 16)))
		u.doAction(u.ui.click(w.screen, w.peer.ID, x, y, 1))
		u.redrawAll()
		return 0
	case WM_MOUSEWHEEL:
		steps := int(int16(uint16(wparam >> 16)))
		btn := 5
		if steps > 0 {
			btn = 4
		}
		u.doAction(u.ui.click(w.screen, w.peer.ID, 10, 500, btn))
		u.redrawAll()
		return 0
	case WM_KEYDOWN:
		key := ""
		switch wparam {
		case 8:
			key = "backspace"
		case 9:
			key = "tab"
		case 13:
			key = "enter"
		case 27:
			key = "escape"
		}
		if key != "" {
			u.ui.input(w.screen, w.peer.ID, key, 0)
			u.redrawAll()
			return 0
		}
	case WM_CHAR:
		ch := rune(wparam)
		if ch >= 32 && ch != 127 && !utf16.IsSurrogate(ch) {
			u.ui.input(w.screen, w.peer.ID, "", ch)
			u.redrawAll()
		}
		return 0
	}
	r, _, _ := pDefWindowProc.Call(hwnd, uintptr(msg), wparam, lparam)
	return r
}
func winProc(hwnd uintptr, message uint32, wparam, lparam uintptr) uintptr {
	if appWindows != nil {
		return appWindows.handle(hwnd, message, wparam, lparam)
	}
	r, _, _ := pDefWindowProc.Call(hwnd, uintptr(message), wparam, lparam)
	return r
}
func main() {
	runtime.LockOSThread()
	if e := loadAssets(); e != nil {
		panic(fmt.Sprintf("Cannot load Beacon branding: %v", e))
	}
	appWindows = &windowsUI{windows: map[uintptr]*winWindow{}}
	appWindows.icon = iconHandle()
	mod, _, _ := pGetModuleHandle.Call(0)
	appWindows.instance = mod
	cur, _, _ := pLoadCursor.Call(0, 32512)
	wc := winClass{Size: uint32(unsafe.Sizeof(winClass{})), Style: 3, Callback: syscall.NewCallback(winProc), Instance: mod, Cursor: cur, ClassName: ptrText("BeaconPolishedUI")}
	if ok, _, e := pRegisterClass.Call(uintptr(unsafe.Pointer(&wc))); ok == 0 {
		panic(fmt.Sprintf("Window class registration failed: %v", e))
	}
	appWindows.ui = newClientState(func() {
		if appWindows.root != 0 {
			pPostMessage.Call(appWindows.root, WM_APP+1, 0, 0)
		}
	})
	appWindows.root = appWindows.window("login", "Beacon Messenger - Sign in", beacon.Buddy{}, 125, 90)
	var message winMsg
	for {
		r, _, _ := pGetMessage.Call(uintptr(unsafe.Pointer(&message)), 0, 0, 0)
		if r == 0 || r == 0xffffffff {
			break
		}
		pTranslateMessage.Call(uintptr(unsafe.Pointer(&message)))
		pDispatchMessage.Call(uintptr(unsafe.Pointer(&message)))
	}
}
