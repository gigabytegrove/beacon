package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func waitFor(t *testing.T, what string, fn func() bool) {
	t.Helper()
	limit := time.Now().Add(5 * time.Second)
	for time.Now().Before(limit) {
		if fn() {
			return
		}
		time.Sleep(12 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for %s", what)
}

func TestControllerRealPollingCatchupAndSessionExpiry(t *testing.T) {
	var newest atomic.Int64
	newest.Store(4)
	var expired atomic.Bool
	var muted atomic.Bool
	var reads atomic.Int64
	var loginCalls atomic.Int64
	var notifyCalls atomic.Int64
	notifications := make(chan string, 10)
	var mu sync.Mutex
	requests := []string{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		requests = append(requests, r.Method+" "+r.URL.Path)
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.URL.Path == "/api/login":
			loginCalls.Add(1)
			time.Sleep(35 * time.Millisecond)
			_, _ = w.Write([]byte(`{"token":"test-token","user":{"id":1,"username":"brad","display_name":"Brad"}}`))
		case expired.Load():
			w.WriteHeader(401)
			_, _ = w.Write([]byte(`{"detail":"revoked"}`))
		case r.URL.Path == "/api/presence":
			_, _ = w.Write([]byte(`{"ok":true}`))
		case r.URL.Path == "/api/buddies":
			_, _ = w.Write([]byte(`[{"id":2,"username":"alex","display_name":"Alex","presence":"available","muted":` + strconv.FormatBool(muted.Load()) + `}]`))
		case r.URL.Path == "/api/groups":
			_, _ = w.Write([]byte(`[]`))
		case r.URL.Path == "/api/events/latest":
			_, _ = w.Write([]byte(`{"last_message_id":4}`))
		case r.URL.Path == "/api/events":
			after, _ := strconv.ParseInt(r.URL.Query().Get("after"), 10, 64)
			if after < newest.Load() {
				_, _ = w.Write([]byte(`{"events":[{"id":` + strconv.FormatInt(newest.Load(), 10) + `,"sender_id":2,"recipient_id":1,"body":"new message"}],"next_cursor":` + strconv.FormatInt(newest.Load(), 10) + `}`))
			} else {
				_, _ = w.Write([]byte(`{"events":[],"next_cursor":` + strconv.FormatInt(after, 10) + `}`))
			}
		case strings.Contains(r.URL.Path, "/read"):
			reads.Add(1)
			_, _ = w.Write([]byte(`{"ok":true}`))
		default:
			w.WriteHeader(404)
			_ = json.NewEncoder(w).Encode(map[string]string{"detail": "unknown"})
		}
	}))
	defer server.Close()
	c := NewController(nil)
	c.pollEvery = 25 * time.Millisecond
	c.notifier = func(title, body string) { notifyCalls.Add(1); notifications <- body }
	for i := 0; i < 6; i++ {
		c.Login(server.URL, "brad", "password")
	}
	waitFor(t, "login and baseline", func() bool {
		c.mu.RLock()
		defer c.mu.RUnlock()
		return c.api != nil && len(c.buddies) == 1
	})
	if loginCalls.Load() != 1 {
		t.Fatalf("duplicate logins attempted: %d", loginCalls.Load())
	}
	// Confirm the cursor is seeded before introducing a fresh message.
	time.Sleep(100 * time.Millisecond)
	newest.Store(5)
	select {
	case body := <-notifications:
		if !strings.Contains(body, "Alex") {
			t.Fatalf("unexpected alert: %s", body)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("missed new-message notification")
	}
	time.Sleep(100 * time.Millisecond)
	if notifyCalls.Load() != 1 {
		t.Fatalf("duplicated event alert %d", notifyCalls.Load())
	}
	if reads.Load() != 0 {
		t.Fatal("background polling wrongly marked a message read")
	}
	muted.Store(true)
	// Give the next roster request time to observe the new mute state.
	time.Sleep(110 * time.Millisecond)
	newest.Store(6)
	time.Sleep(130 * time.Millisecond)
	if notifyCalls.Load() != 1 {
		t.Fatal("muted buddy triggered an alert")
	}
	expired.Store(true)
	waitFor(t, "revoked login cleanup", func() bool { return !c.Snap().Logged })
	if !strings.Contains(c.Snap().Error, "expired or was revoked") {
		t.Fatalf("inadequate revocation state: %s", c.Snap().Error)
	}
	mu.Lock()
	defer mu.Unlock()
	for _, call := range requests {
		if strings.HasSuffix(call, "/read") {
			t.Fatal("background read request observed")
		}
	}
}
