package main

import (
	"beacon.local/native/internal/beacon"
	"bytes"
	"strings"
	"testing"
	"time"
)

func TestPremiumScreenRenderingAndInteractions(t *testing.T) {
	if err := loadAssets(); err != nil {
		t.Fatal(err)
	}
	ui := newClientState(nil)
	ui.login[0] = "http://192.168.1.51:8765"
	ui.login[1] = "tester"
	ui.login[2] = "secret"
	before := ui.render("login", 0)
	if !ui.HoverAt("login", 0, 200, 600) {
		t.Fatal("login hover did not activate")
	}
	after := ui.render("login", 0)
	if bytes.Equal(before.Pix, after.Pix) {
		t.Fatal("login primary button has no hover visual state")
	}
	if ui.HoverAt("login", 0, 200, 600) {
		t.Fatal("identical cursor location triggered redraw")
	}
	ui.ctl.mu.Lock()
	ui.ctl.me = beacon.User{ID: 1, Username: "tester", DisplayName: "Test Person"}
	ui.ctl.buddies = []beacon.Buddy{{User: beacon.User{ID: 2, DisplayName: "Alice", Username: "alice"}, Presence: "available", UnreadCount: 2}}
	ui.ctl.mu.Unlock()
	a := ui.render("roster", 0)
	if !ui.HoverAt("roster", 0, 145, 454) {
		t.Fatal("roster hover not set")
	}
	b := ui.render("roster", 0)
	if bytes.Equal(a.Pix, b.Pix) {
		t.Fatal("roster buddy rows do not respond to hover")
	}
	if act := ui.click("roster", 0, 145, 454, 1); act.kind != "chat" || act.peer.ID != 2 {
		t.Fatalf("click wrong buddy: %+v", act)
	}
}
func TestChatHistoryWheelNavigatesOlderItems(t *testing.T) {
	if err := loadAssets(); err != nil {
		t.Fatal(err)
	}
	ui := newClientState(nil)
	ui.ctl.mu.Lock()
	ui.ctl.me = beacon.User{ID: 1, DisplayName: "Me"}
	now := time.Now().Unix()
	for id := 1; id <= 9; id++ {
		ui.ctl.chats[2] = append(ui.ctl.chats[2], beacon.Message{ID: id, SenderID: 2, RecipientID: 1, Body: "Conversation item from earlier " + strings.Repeat("a", id), CreatedAt: now + int64(id)})
	}
	ui.ctl.chatNames[2] = "Alice"
	ui.ctl.mu.Unlock()
	current := ui.render("chat", 2)
	ui.click("chat", 2, 400, 300, 4)
	older := ui.render("chat", 2)
	if bytes.Equal(current.Pix, older.Pix) {
		t.Fatal("chat wheel up failed to show older messages")
	}
	ui.click("chat", 2, 400, 300, 5)
	again := ui.render("chat", 2)
	if !bytes.Equal(current.Pix, again.Pix) {
		t.Fatal("chat wheel down did not return to newest messages")
	}
}
func TestNoPlaceholderRowsWhenRosterEmpty(t *testing.T) {
	if err := loadAssets(); err != nil {
		t.Fatal(err)
	}
	ui := newClientState(nil)
	im := ui.render("roster", 0)
	if im.Bounds().Dx() != 480 || im.Bounds().Dy() != 760 {
		t.Fatal("wrong roster dimensions")
	}
	if !ui.HoverAt("roster", 0, 370, 360) {
		t.Fatal("Add buddy target should be clickable")
	}
}
