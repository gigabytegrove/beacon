package main

import (
	"bytes"
	"embed"
	"encoding/json"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"strings"
	"sync"
	"unicode/utf8"

	"beacon.local/native/internal/beacon"
)

//go:embed assets/*
var assetFiles embed.FS

type glyph struct{ X, Y, W, H, Step int }
type face struct {
	atlas  *image.RGBA
	glyphs map[string]glyph
}
type palette struct{ navy, text, muted, blue, green, amber, red, white, light color.RGBA }

var colors = palette{
	navy: color.RGBA{12, 28, 55, 255}, text: color.RGBA{21, 40, 70, 255}, muted: color.RGBA{113, 132, 157, 255},
	blue: color.RGBA{17, 118, 247, 255}, green: color.RGBA{37, 178, 128, 255}, amber: color.RGBA{226, 154, 48, 255},
	red: color.RGBA{220, 83, 98, 255}, white: color.RGBA{255, 255, 255, 255}, light: color.RGBA{238, 245, 254, 255},
}
var skins = map[string]*image.RGBA{}
var fonts = map[string]face{}

func loadAssets() error {
	for _, key := range []string{"login", "roster", "chat", "directory"} {
		b, e := assetFiles.ReadFile("assets/" + key + ".png")
		if e != nil {
			return e
		}
		im, e := png.Decode(bytes.NewReader(b))
		if e != nil {
			return e
		}
		r := image.NewRGBA(im.Bounds())
		draw.Draw(r, r.Bounds(), im, image.Point{}, draw.Src)
		skins[key] = r
	}
	for _, key := range []string{"tiny", "sm", "md", "md-bold", "lg", "xl"} {
		b, e := assetFiles.ReadFile("assets/font-" + key + ".png")
		if e != nil {
			return e
		}
		im, e := png.Decode(bytes.NewReader(b))
		if e != nil {
			return e
		}
		canvas := image.NewRGBA(im.Bounds())
		draw.Draw(canvas, canvas.Bounds(), im, image.Point{}, draw.Src)
		b, e = assetFiles.ReadFile("assets/font-" + key + ".json")
		if e != nil {
			return e
		}
		var raw map[string][]int
		if e = json.Unmarshal(b, &raw); e != nil {
			return e
		}
		f := face{atlas: canvas, glyphs: map[string]glyph{}}
		for ch, v := range raw {
			if len(v) != 5 {
				continue
			}
			f.glyphs[ch] = glyph{v[0], v[1], v[2], v[3], v[4]}
		}
		fonts[key] = f
	}
	return nil
}
func freshSkin(kind string) *image.RGBA {
	src := skins[kind]
	out := image.NewRGBA(src.Bounds())
	draw.Draw(out, out.Bounds(), src, image.Point{}, draw.Src)
	return out
}
func solid(im *image.RGBA, x, y, w, h int, c color.RGBA) {
	rect := image.Rect(x, y, x+w, y+h).Intersect(im.Bounds())
	if rect.Empty() {
		return
	}
	draw.Draw(im, rect, &image.Uniform{C: c}, image.Point{}, draw.Src)
}
func disc(im *image.RGBA, cx, cy, r int, c color.RGBA) {
	for y := -r; y <= r; y++ {
		for x := -r; x <= r; x++ {
			if x*x+y*y <= r*r {
				px := cx + x
				py := cy + y
				if image.Pt(px, py).In(im.Bounds()) {
					im.SetRGBA(px, py, c)
				}
			}
		}
	}
}
func rounded(im *image.RGBA, x, y, w, h, r int, c color.RGBA) {
	for yy := y; yy < y+h; yy++ {
		for xx := x; xx < x+w; xx++ {
			dx, dy := 0, 0
			if xx < x+r {
				dx = x + r - xx
			} else if xx > x+w-r-1 {
				dx = xx - (x + w - r - 1)
			}
			if yy < y+r {
				dy = y + r - yy
			} else if yy > y+h-r-1 {
				dy = yy - (y + h - r - 1)
			}
			if dx*dx+dy*dy <= r*r && image.Pt(xx, yy).In(im.Bounds()) {
				im.SetRGBA(xx, yy, c)
			}
		}
	}
}
func textWidth(s, kind string) int {
	f := fonts[kind]
	w := 0
	for _, ch := range s {
		g, ok := f.glyphs[string(ch)]
		if !ok {
			g = f.glyphs["?"]
		}
		w += g.Step
	}
	return w
}
func fit(s, kind string, maxW int) string {
	if textWidth(s, kind) <= maxW {
		return s
	}
	var out strings.Builder
	for _, ch := range s {
		next := out.String() + string(ch) + "..."
		if textWidth(next, kind) > maxW {
			break
		}
		out.WriteRune(ch)
	}
	return out.String() + "..."
}
func drawText(im *image.RGBA, x, y int, s, kind string, tint color.RGBA) {
	f, ok := fonts[kind]
	if !ok {
		return
	}
	if x >= im.Bounds().Dx() || y >= im.Bounds().Dy() {
		return
	}
	for _, ch := range s {
		g, ok := f.glyphs[string(ch)]
		if !ok {
			g = f.glyphs["?"]
		}
		// Atlas cells hold antialiased glyph alpha, colored at draw-time.
		for yy := 0; yy < g.H; yy++ {
			py := y + yy
			if py < 0 || py >= im.Rect.Dy() {
				continue
			}
			for xx := 0; xx < g.W; xx++ {
				px := x + xx
				if px < 0 || px >= im.Rect.Dx() {
					continue
				}
				a := f.atlas.RGBAAt(g.X+xx, g.Y+yy).A
				if a == 0 {
					continue
				}
				cur := im.RGBAAt(px, py)
				inv := uint32(255 - a)
				im.SetRGBA(px, py, color.RGBA{
					R: uint8((uint32(tint.R)*uint32(a) + uint32(cur.R)*inv) / 255),
					G: uint8((uint32(tint.G)*uint32(a) + uint32(cur.G)*inv) / 255),
					B: uint8((uint32(tint.B)*uint32(a) + uint32(cur.B)*inv) / 255), A: 255,
				})
			}
		}
		x += g.Step
		if x >= im.Rect.Dx() {
			return
		}
	}
}
func statusColor(s string) color.RGBA {
	switch s {
	case "available":
		return colors.green
	case "away":
		return colors.amber
	case "busy":
		return colors.red
	default:
		return colors.muted
	}
}
func statusLabel(s string) string {
	switch s {
	case "available":
		return "Online"
	case "busy":
		return "Busy"
	case "away":
		return "Away"
	default:
		return "Offline"
	}
}

// ClientState is the presentation model shared by Win32 and X11. It contains
// no OS-specific controls or third-party GUI runtime dependencies.
type ClientState struct {
	ctl              *Controller
	mu               sync.RWMutex
	login            [3]string
	loginFocus       int
	filter           string
	searchFocus      bool
	scroll           int
	chatEntries      map[int]string
	contacts         []beacon.User
	directoryLoading bool
	notice           string
	hover            string
	chatScroll       map[int]int
}

func newClientState(wake func()) *ClientState {
	c := &ClientState{loginFocus: 0, chatEntries: map[int]string{}, chatScroll: map[int]int{}}
	c.login[0] = previousServer()
	c.ctl = NewController(wake)
	return c
}
func (c *ClientState) filtered(s View) []beacon.Buddy {
	term := strings.ToLower(strings.TrimSpace(c.filter))
	if term == "" {
		return s.Buddies
	}
	items := []beacon.Buddy{}
	for _, b := range s.Buddies {
		if strings.Contains(strings.ToLower(b.Name()+" "+b.Username+" "+b.StatusText), term) {
			items = append(items, b)
		}
	}
	return items
}
func (c *ClientState) renderLogin(s View) *image.RGBA {
	return c.paintLogin(s)
}
func (c *ClientState) renderRoster(s View) *image.RGBA {
	return c.paintRoster(s)
}
func onlineCount(bs []beacon.Buddy) int {
	n := 0
	for _, b := range bs {
		if b.Presence != "offline" {
			n++
		}
	}
	return n
}
func (c *ClientState) renderChat(id int, s View) *image.RGBA {
	return c.paintChat(id, s)
}
func (c *ClientState) renderDirectory(s View) *image.RGBA {
	return c.paintDirectory(s)
}
func (c *ClientState) render(screen string, id int) *image.RGBA {
	snap := c.ctl.Snap()
	switch screen {
	case "login":
		return c.renderLogin(snap)
	case "roster":
		return c.renderRoster(snap)
	case "chat":
		return c.renderChat(id, snap)
	case "directory":
		return c.renderDirectory(snap)
	}
	return freshSkin("login")
}

// Screen dimensions match the embedded shared visual layouts on both OSes.
func screenSize(screen string) (int, int) {
	switch screen {
	case "chat":
		return 700, 680
	case "directory":
		return 480, 600
	default:
		return 480, 760
	}
}
func (c *ClientState) loginClick(x, y int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for k := 0; k < 3; k++ {
		top := 347 + k*82
		if x >= 49 && x <= 431 && y >= top && y <= top+49 {
			c.loginFocus = k
			return
		}
	}
	if x >= 49 && x <= 431 && y >= 584 && y <= 637 {
		go c.ctl.Login(c.login[0], c.login[1], c.login[2])
	}
}
func (c *ClientState) input(screen string, id int, key string, ch rune) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if screen == "login" {
		if key == "tab" {
			c.loginFocus = (c.loginFocus + 1) % 3
			return
		}
		if key == "enter" {
			go c.ctl.Login(c.login[0], c.login[1], c.login[2])
			return
		}
		if key == "backspace" {
			r := []rune(c.login[c.loginFocus])
			if len(r) > 0 {
				c.login[c.loginFocus] = string(r[:len(r)-1])
			}
			return
		}
		if ch >= 32 && ch != 127 && utf8.RuneCountInString(c.login[c.loginFocus]) < 400 {
			c.login[c.loginFocus] += string(ch)
		}
		return
	}
	if screen == "roster" && c.searchFocus {
		if key == "backspace" {
			r := []rune(c.filter)
			if len(r) > 0 {
				c.filter = string(r[:len(r)-1])
			}
			c.scroll = 0
			return
		}
		if ch >= 32 && ch != 127 && utf8.RuneCountInString(c.filter) < 100 {
			c.filter += string(ch)
			c.scroll = 0
		}
		return
	}
	if screen == "chat" {
		if key == "enter" {
			if strings.TrimSpace(c.chatEntries[id]) != "" {
				txt := c.chatEntries[id]
				c.chatEntries[id] = ""
				go c.ctl.Send(id, txt)
			}
			return
		}
		if key == "backspace" {
			r := []rune(c.chatEntries[id])
			if len(r) > 0 {
				c.chatEntries[id] = string(r[:len(r)-1])
			}
			return
		}
		if ch >= 32 && ch != 127 && utf8.RuneCountInString(c.chatEntries[id]) < 2000 {
			c.chatEntries[id] += string(ch)
			go c.ctl.Typing(id)
		}
	}
}
func (c *ClientState) getDirectory() {
	c.mu.Lock()
	c.contacts = nil
	c.directoryLoading = true
	c.mu.Unlock()
	c.ctl.Directory(func(users []beacon.User, e error) {
		snap := c.ctl.Snap()
		used := map[int]bool{}
		for _, b := range snap.Buddies {
			used[b.ID] = true
		}
		filtered := []beacon.User{}
		for _, u := range users {
			if !used[u.ID] {
				filtered = append(filtered, u)
			}
		}
		c.mu.Lock()
		c.contacts = filtered
		c.directoryLoading = false
		c.mu.Unlock()
		c.ctl.signal()
	})
}

// Action result (open buddy chat / add user / open directory) is interpreted by OS windows.
type uiAction struct {
	kind   string
	peer   beacon.Buddy
	userID int
}

func (c *ClientState) click(screen string, id, x, y, button int) uiAction {
	if screen == "login" {
		c.loginClick(x, y)
		return uiAction{}
	}
	if screen == "chat" && (button == 4 || button == 5) {
		c.mu.Lock()
		messages := c.ctl.Snap().Chats[id]
		maxOffset := len(messages) - 1
		if maxOffset < 0 {
			maxOffset = 0
		}
		if button == 4 && c.chatScroll[id] < maxOffset {
			c.chatScroll[id]++
		}
		if button == 5 && c.chatScroll[id] > 0 {
			c.chatScroll[id]--
		}
		c.mu.Unlock()
		return uiAction{}
	}
	if screen == "roster" {
		if button == 4 || button == 5 {
			c.mu.Lock()
			if button == 4 && c.scroll > 0 {
				c.scroll--
			}
			if button == 5 && c.scroll < len(c.filtered(c.ctl.Snap()))-5 {
				c.scroll++
			}
			c.mu.Unlock()
			return uiAction{}
		}
		if y >= 281 && y <= 322 {
			switch {
			case x >= 22 && x <= 123:
				c.ctl.ChangePresence("available")
			case x >= 130 && x <= 231:
				c.ctl.ChangePresence("away")
			case x >= 238 && x <= 339:
				c.ctl.ChangePresence("busy")
			case x >= 348 && x <= 458:
				c.ctl.Logout()
			}
			return uiAction{}
		}
		if y >= 340 && y <= 390 {
			if x <= 326 {
				c.mu.Lock()
				c.searchFocus = true
				c.mu.Unlock()
			} else {
				c.getDirectory()
				return uiAction{kind: "directory"}
			}
			return uiAction{}
		}
		if y >= 430 && y <= 715 {
			c.mu.RLock()
			n := c.scroll
			c.mu.RUnlock()
			list := c.filtered(c.ctl.Snap())
			idx := n + (y-430)/57
			if idx >= 0 && idx < len(list) {
				return uiAction{kind: "chat", peer: list[idx]}
			}
		}
		c.mu.Lock()
		c.searchFocus = false
		c.mu.Unlock()
	}
	if screen == "directory" && y >= 251 && y <= 556 {
		c.mu.RLock()
		idx := (y - 251) / 61
		contacts := c.contacts
		c.mu.RUnlock()
		if idx < len(contacts) {
			return uiAction{kind: "add", userID: contacts[idx].ID}
		}
	}
	if screen == "chat" && y >= 577 && y <= 636 && x >= 542 && x <= 663 {
		c.mu.Lock()
		msg := c.chatEntries[id]
		c.chatEntries[id] = ""
		c.mu.Unlock()
		if strings.TrimSpace(msg) != "" {
			go c.ctl.Send(id, msg)
		}
	}
	return uiAction{}
}

func (c *ClientState) authenticated() {
	c.mu.Lock()
	c.login[2] = ""
	c.mu.Unlock()
	rememberServer(c.ctl.Snap().Server)
}
