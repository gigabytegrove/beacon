package main

import (
	"beacon.local/native/internal/beacon"
	"image/color"
	"os"
	"strings"
	"testing"
)

func TestBrandedRenderersAndWindowSizes(t *testing.T) {
	if err := loadAssets(); err != nil {
		t.Fatal(err)
	}
	for _, screen := range []string{"login", "roster", "chat", "directory"} {
		w, h := screenSize(screen)
		im := freshSkin(screen)
		if im.Rect.Dx() != w || im.Rect.Dy() != h {
			t.Fatalf("%s %d,%d != %d,%d", screen, im.Rect.Dx(), im.Rect.Dy(), w, h)
		}
		if im.RGBAAt(0, 0) != (color.RGBA{9, 23, 45, 255}) {
			t.Errorf("%s missing consistent navy header", screen)
		}
	}
	ui := newClientState(nil)
	ui.login[0] = "http://192.168.1.20:8765"
	ui.login[1] = "test"
	ui.login[2] = "password must not be drawn"
	login := ui.render("login", 0)
	if login.RGBAAt(49, 584).B < 200 {
		t.Error("login primary button not blue")
	}
	ui.ctl.mu.Lock()
	ui.ctl.me = beacon.User{ID: 1, Username: "tester", DisplayName: "Example User"}
	ui.ctl.buddies = []beacon.Buddy{{User: beacon.User{ID: 2, DisplayName: "Alice"}, Presence: "available", UnreadCount: 4}}
	ui.ctl.api, _ = beacon.NewClient("http://127.0.0.1:8765")
	ui.ctl.mu.Unlock()
	roster := ui.render("roster", 0)
	if roster.RGBAAt(0, 0) != (color.RGBA{9, 23, 45, 255}) {
		t.Fatal("roster lost branding")
	}
	_ = ui.render("chat", 2)
	_ = ui.render("directory", 0)
}
func TestPreferencesOnlyRememberServer(t *testing.T) {
	temp := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", temp)
	rememberServer("https://beacon.example.net")
	got := previousServer()
	if got != "https://beacon.example.net" {
		t.Fatalf("got %q", got)
	}
	data, err := os.ReadFile(preferencePath())
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(data), "token") || strings.Contains(string(data), "password") {
		t.Fatal("secret field stored in preferences")
	}
	info, err := os.Stat(preferencePath())
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm()&0077 != 0 {
		t.Errorf("preferences not private: %o", info.Mode().Perm())
	}
}
func TestFilterAndUnicodeInputs(t *testing.T) {
	ui := newClientState(nil)
	ui.ctl.mu.Lock()
	ui.ctl.buddies = []beacon.Buddy{{User: beacon.User{ID: 1, DisplayName: "Alice"}}, {User: beacon.User{ID: 2, DisplayName: "Bob"}}}
	ui.ctl.mu.Unlock()
	ui.searchFocus = true
	for _, c := range "ali" {
		ui.input("roster", 0, "", c)
	}
	result := ui.filtered(ui.ctl.Snap())
	if len(result) != 1 || result[0].DisplayName != "Alice" {
		t.Fatalf("filter result: %+v", result)
	}
	ui.input("roster", 0, "backspace", 0)
	if ui.filter != "al" {
		t.Errorf("backspace: %q", ui.filter)
	}
}
