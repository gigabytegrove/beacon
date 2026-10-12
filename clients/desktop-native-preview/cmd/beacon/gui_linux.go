//go:build linux

package main

/*
#cgo LDFLAGS: -lX11
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <stdlib.h>
#include <stdio.h>
static Display* open_beacon(){XInitThreads();return XOpenDisplay(NULL);}
static Window make_beacon_window(Display*d,int x,int y,int w,int h,const char*name){
 int screen=DefaultScreen(d);
 Window win=XCreateSimpleWindow(d,RootWindow(d,screen),x,y,w,h,0,BlackPixel(d,screen),WhitePixel(d,screen));
 XStoreName(d,win,name);
 XSelectInput(d,win,ExposureMask|KeyPressMask|ButtonPressMask|PointerMotionMask|StructureNotifyMask|FocusChangeMask);
 Atom del=XInternAtom(d,"WM_DELETE_WINDOW",False);XSetWMProtocols(d,win,&del,1);
 XSizeHints hints;hints.flags=PMinSize|PMaxSize;hints.min_width=w;hints.max_width=w;hints.min_height=h;hints.max_height=h;
 XSetWMNormalHints(d,win,&hints);
 XMapWindow(d,win);return win;
}
static void beacon_rename(Display*d,Window w,const char*title){XStoreName(d,w,title);}
static void beacon_set_icon(Display*d,Window w,unsigned long*argb,int n){
 Atom prop=XInternAtom(d,"_NET_WM_ICON",False);
 Atom type=XInternAtom(d,"CARDINAL",False);
 XChangeProperty(d,w,prop,type,32,PropModeReplace,(unsigned char*)argb,n);
}
static int evtype(XEvent*e){return e->type;}
static Window evwin(XEvent*e){return e->xany.window;}
static int evx(XEvent*e){return e->xbutton.x;}
static int evy(XEvent*e){return e->xbutton.y;}
static int evbtn(XEvent*e){return e->xbutton.button;}
static int evmotionx(XEvent*e){return e->xmotion.x;}
static int evmotiony(XEvent*e){return e->xmotion.y;}
static int evclose(Display*d,XEvent*e){
 return e->type==ClientMessage&&(Atom)e->xclient.data.l[0]==XInternAtom(d,"WM_DELETE_WINDOW",False);
}
static int evkey(XEvent*e,char*buf,int cap,unsigned long*sym){
 KeySym ks=0;int n=XLookupString(&e->xkey,buf,cap,&ks,NULL);*sym=(unsigned long)ks;return n;
}
static void draw_rgba(Display*d,Window win,GC gc,unsigned char*data,int w,int h){
 if(!data)return;
 XImage*img=XCreateImage(d,DefaultVisual(d,DefaultScreen(d)),DefaultDepth(d,DefaultScreen(d)),ZPixmap,0,(char*)data,w,h,32,0);
 if(!img){free(data);return;}
 XPutImage(d,win,gc,img,0,0,0,0,w,h);
 XFlush(d);
 XDestroyImage(img);
}
*/
import "C"
import (
	"bytes"
	"fmt"
	"image/png"
	"os"
	"runtime"
	"time"
	"unicode/utf8"
	"unsafe"

	"beacon.local/native/internal/beacon"
)

type xWindow struct {
	window   C.Window
	screen   string
	peer     beacon.Buddy
	focus    bool
	lastRead int
}
type xClient struct {
	d       *C.Display
	gc      C.GC
	ui      *ClientState
	root    C.Window
	windows map[C.Window]*xWindow
	wake    chan struct{}
}

func (x *xClient) create(screen string, title string, left, top int, peer beacon.Buddy) C.Window {
	w, h := screenSize(screen)
	ct := C.CString(title)
	defer C.free(unsafe.Pointer(ct))
	win := C.make_beacon_window(x.d, C.int(left), C.int(top), C.int(w), C.int(h), ct)
	x.setWindowIcon(win)
	x.windows[win] = &xWindow{window: win, screen: screen, peer: peer, focus: screen == "chat"}
	return win
}
func (x *xClient) setWindowIcon(win C.Window) {
	raw, e := assetFiles.ReadFile("assets/logo-mark.png")
	if e != nil {
		return
	}
	imageData, e := png.Decode(bytes.NewReader(raw))
	if e != nil {
		return
	}
	const size = 64
	pixels := make([]C.ulong, 2+size*size)
	pixels[0] = size
	pixels[1] = size
	bounds := imageData.Bounds()
	width := bounds.Dx()
	height := bounds.Dy()
	drawW := 46
	drawH := 60
	for y := 0; y < drawH; y++ {
		for px := 0; px < drawW; px++ {
			imageX := bounds.Min.X + px*width/drawW
			imageY := bounds.Min.Y + y*height/drawH
			r, g, b, a := imageData.At(imageX, imageY).RGBA()
			pixels[2+(y+2)*size+(px+9)] = C.ulong((a>>8)<<24 | (r>>8)<<16 | (g>>8)<<8 | (b >> 8))
		}
	}
	C.beacon_set_icon(x.d, win, &pixels[0], C.int(len(pixels)))
}
func (x *xClient) paint(w *xWindow) {
	if w.screen == "roster" && !x.ui.ctl.Snap().Logged {
		w.screen = "login"
		title := C.CString("Beacon Messenger - Sign in")
		C.beacon_rename(x.d, w.window, title)
		C.free(unsafe.Pointer(title))
	}
	if w.screen == "login" && x.ui.ctl.Snap().Logged {
		w.screen = "roster"
		title := C.CString("Beacon Messenger - Buddy List")
		C.beacon_rename(x.d, w.window, title)
		C.free(unsafe.Pointer(title))
		x.ui.authenticated()
	}
	img := x.ui.render(w.screen, w.peer.ID)
	pixels := C.malloc(C.size_t(len(img.Pix)))
	if pixels == nil {
		return
	}
	dst := unsafe.Slice((*byte)(pixels), len(img.Pix))
	for i := 0; i+3 < len(img.Pix); i += 4 {
		dst[i] = img.Pix[i+2]
		dst[i+1] = img.Pix[i+1]
		dst[i+2] = img.Pix[i]
		dst[i+3] = 0
	}
	C.draw_rgba(x.d, w.window, x.gc, (*C.uchar)(pixels), C.int(img.Rect.Dx()), C.int(img.Rect.Dy()))
	if w.screen == "chat" && w.focus {
		s := x.ui.ctl.Snap()
		latest := 0
		for _, message := range s.Chats[w.peer.ID] {
			if message.SenderID == w.peer.ID && message.ID > latest {
				latest = message.ID
			}
		}
		if latest > w.lastRead {
			w.lastRead = latest
			x.ui.ctl.MarkRead(w.peer.ID, latest)
		}
	}
}
func (x *xClient) paintAll() {
	for _, w := range x.windows {
		x.paint(w)
	}
}
func (x *xClient) hasChat(id int) bool {
	for _, w := range x.windows {
		if w.screen == "chat" && w.peer.ID == id {
			C.XRaiseWindow(x.d, w.window)
			return true
		}
	}
	return false
}
func (x *xClient) doAction(a uiAction) {
	switch a.kind {
	case "chat":
		if x.hasChat(a.peer.ID) {
			return
		}
		x.ui.ctl.OpenChat(a.peer.ID, a.peer.Name())
		w := x.create("chat", "Beacon IM - "+a.peer.Name(), 200, 105, a.peer)
		x.paint(x.windows[w])
	case "directory":
		for _, w := range x.windows {
			if w.screen == "directory" {
				C.XRaiseWindow(x.d, w.window)
				return
			}
		}
		win := x.create("directory", "Beacon - Add Buddy", 230, 160, beacon.Buddy{})
		x.paint(x.windows[win])
	case "add":
		x.ui.ctl.AddBuddy(a.userID)
		for win, w := range x.windows {
			if w.screen == "directory" {
				C.XDestroyWindow(x.d, win)
				delete(x.windows, win)
			}
		}
	}
}
func (x *xClient) event(ev *C.XEvent) {
	win := C.evwin(ev)
	w, ok := x.windows[win]
	if !ok {
		return
	}
	if C.evclose(x.d, ev) != 0 {
		if win == x.root {
			os.Exit(0)
		}
		if w.screen == "chat" {
			x.ui.ctl.CloseChat(w.peer.ID)
		}
		C.XDestroyWindow(x.d, win)
		delete(x.windows, win)
		return
	}
	switch C.evtype(ev) {
	case C.Expose:
		x.paint(w)
	case C.MotionNotify:
		if x.ui.HoverAt(w.screen, w.peer.ID, int(C.evmotionx(ev)), int(C.evmotiony(ev))) {
			x.paint(w)
		}
	case C.FocusIn:
		w.focus = true
		x.paint(w)
	case C.FocusOut:
		w.focus = false
	case C.ButtonPress:
		xx, yy, btn := int(C.evx(ev)), int(C.evy(ev)), int(C.evbtn(ev))
		act := x.ui.click(w.screen, w.peer.ID, xx, yy, btn)
		x.doAction(act)
		x.paintAll()
	case C.KeyPress:
		var keybuf [64]C.char
		var sym C.ulong
		n := int(C.evkey(ev, &keybuf[0], 63, &sym))
		key := ""
		ch := rune(0)
		switch uint64(sym) {
		case 0xff09:
			key = "tab"
		case 0xff08:
			key = "backspace"
		case 0xff0d, keyEnterKP:
			key = "enter"
		case 0xff1b:
			key = "escape"
		case 0xff51:
			key = "left"
		case 0xff53:
			key = "right"
		}
		if n > 0 && key == "" {
			txt := C.GoStringN(&keybuf[0], C.int(n))
			ch, _ = utf8.DecodeRuneInString(txt)
		}
		x.ui.input(w.screen, w.peer.ID, key, ch)
		x.paint(w)
	}
}

const keyEnterKP = 0xff8d

func main() {
	runtime.LockOSThread()
	if err := loadAssets(); err != nil {
		fmt.Fprintln(os.Stderr, "Beacon asset error:", err)
		os.Exit(1)
	}
	d := C.open_beacon()
	if d == nil {
		fmt.Fprintln(os.Stderr, "Beacon needs an X11-compatible graphical session (DISPLAY unset or unavailable).")
		os.Exit(1)
	}
	defer C.XCloseDisplay(d)
	wake := make(chan struct{}, 10)
	app := &xClient{d: d, wake: wake, windows: map[C.Window]*xWindow{}}
	app.ui = newClientState(func() {
		select {
		case wake <- struct{}{}:
		default:
		}
	})
	app.gc = C.XCreateGC(d, C.XDefaultRootWindow(d), 0, nil)
	defer C.XFreeGC(d, app.gc)
	app.root = app.create("login", "Beacon Messenger - Sign in", 130, 75, beacon.Buddy{})
	app.paintAll()
	ticker := time.NewTicker(35 * time.Millisecond)
	defer ticker.Stop()
	for range ticker.C {
		for C.XPending(d) > 0 {
			var ev C.XEvent
			C.XNextEvent(d, &ev)
			app.event(&ev)
		}
		select {
		case <-wake:
			app.paintAll()
		default:
		}
	}
}
