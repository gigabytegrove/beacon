package main

import (
	"image/png"
	"os"
	"path/filepath"
	"testing"
	"time"

	"beacon.local/native/internal/beacon"
)

// Optional visual snapshot utility for checking the actual shared Go renderer.
// Set BEACON_PREVIEW_DIR to emit PNGs during go test; normally emits no files.
func TestRenderPremiumPreview(t *testing.T) {
	dir := os.Getenv("BEACON_PREVIEW_DIR")
	if dir == "" {
		return
	}
	if err := loadAssets(); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	c := newClientState(nil)
	c.login = [3]string{"https://beacon.example.net", "brad", ""}
	c.loginFocus = 1
	export := func(screen string, peer int) {
		t.Helper()
		f, e := os.Create(filepath.Join(dir, screen+".png"))
		if e != nil {
			t.Fatal(e)
		}
		defer f.Close()
		if e = png.Encode(f, c.render(screen, peer)); e != nil {
			t.Fatal(e)
		}
	}
	export("login", 0)
	c.ctl.mu.Lock()
	c.ctl.me = beacon.User{ID: 1, Username: "admin", DisplayName: "Jordan Taylor", StatusText: "Keeping everyone connected"}
	c.ctl.buddies = []beacon.Buddy{
		{User: beacon.User{ID: 2, Username: "alex", DisplayName: "Alex Morgan", StatusText: "Working from home"}, Presence: "available", UnreadCount: 3, GroupName: "Friends"},
		{User: beacon.User{ID: 3, Username: "sarah", DisplayName: "Sarah Chen", StatusText: "Be back in a few"}, Presence: "away", GroupName: "Family"},
		{User: beacon.User{ID: 4, Username: "mike", DisplayName: "Mike Thompson", StatusText: "Heads down on a project"}, Presence: "busy", GroupName: "Work"},
		{User: beacon.User{ID: 5, Username: "robin", DisplayName: "Robin West"}, Presence: "available", GroupName: "Friends"},
		{User: beacon.User{ID: 6, Username: "james", DisplayName: "James Lee"}, Presence: "offline", GroupName: "Family"},
	}
	c.ctl.chatNames[2] = "Alex Morgan"
	now := time.Now().Unix()
	c.ctl.chats[2] = []beacon.Message{
		{ID: 1, SenderID: 2, RecipientID: 1, Body: "Hey! Did you get my message about Saturday?", CreatedAt: now - 3600},
		{ID: 2, SenderID: 1, RecipientID: 2, Body: "I did! Everything's looking good on my end.", CreatedAt: now - 3300},
		{ID: 3, SenderID: 2, RecipientID: 1, Body: "Perfect. I'll send over the details tonight.", CreatedAt: now - 3000},
		{ID: 4, SenderID: 1, RecipientID: 2, Body: "Sounds good — talk soon!", CreatedAt: now - 2700},
	}
	c.ctl.typing[2] = true
	c.ctl.mu.Unlock()
	c.ctl.ChangePresence("available")
	c.contacts = []beacon.User{{ID: 10, Username: "kim", DisplayName: "Kim Rivera"}, {ID: 11, Username: "daniel", DisplayName: "Daniel Roberts"}}
	export("roster", 0)
	export("chat", 2)
	export("directory", 0)
}
