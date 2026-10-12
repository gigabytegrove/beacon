package main

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"beacon.local/native/internal/beacon"
)

type View struct {
	Logged    bool
	Me        beacon.User
	Server    string
	Status    string
	Error     string
	Buddies   []beacon.Buddy
	Groups    []beacon.Group
	Chats     map[int][]beacon.Message
	Typing    map[int]bool
	ChatNames map[int]string
}

type Controller struct {
	mu           sync.RWMutex
	api          *beacon.Client
	me           beacon.User
	server       string
	status       string
	notice       string
	buddies      []beacon.Buddy
	groups       []beacon.Group
	chats        map[int][]beacon.Message
	typing       map[int]bool
	chatNames    map[int]string
	stop         chan struct{}
	wake         func()
	loginPending bool
	notifier     func(string, string)
	pollEvery    time.Duration
}

func NewController(wake func()) *Controller {
	return &Controller{status: "available", notifier: systemNotice, pollEvery: 3 * time.Second, chats: map[int][]beacon.Message{}, typing: map[int]bool{}, chatNames: map[int]string{}, wake: wake}
}
func (c *Controller) signal() {
	if c.wake != nil {
		c.wake()
	}
}
func deadline() (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.Background(), 10*time.Second)
}
func (c *Controller) errorf(format string, args ...any) {
	c.mu.Lock()
	c.notice = fmt.Sprintf(format, args...)
	c.mu.Unlock()
	c.signal()
}

// Login admits only one in-flight attempt. A late failed login cannot
// resurrect a session the user has already signed out of.
func (c *Controller) Login(server, username, password string) {
	c.mu.Lock()
	if c.loginPending {
		c.mu.Unlock()
		return
	}
	c.loginPending = true
	c.notice = "Connecting to Beacon server..."
	c.mu.Unlock()
	c.signal()
	go func() {
		a, err := beacon.NewClient(server)
		if err == nil {
			x, end := deadline()
			var result beacon.LoginResult
			result, err = a.Login(x, username, password, "Beacon-Go-Desktop")
			end()
			if err == nil {
				c.mu.Lock()
				c.loginPending = false
				if c.stop != nil {
					close(c.stop)
				}
				c.api = a
				c.me = result.User
				c.server = a.Server()
				c.notice = "Signed in as " + result.User.DisplayName
				c.stop = make(chan struct{})
				c.buddies = nil
				c.groups = nil
				c.chats = map[int][]beacon.Message{}
				c.typing = map[int]bool{}
				c.chatNames = map[int]string{}
				stop := c.stop
				c.mu.Unlock()
				c.signal()
				go c.poll(stop, a)
				return
			}
		}
		c.mu.Lock()
		c.loginPending = false
		c.notice = "Sign-in failed: " + err.Error()
		c.mu.Unlock()
		c.signal()
	}()
}

// expireSession never performs a second API call on an expired token.
func (c *Controller) expireSession(a *beacon.Client) {
	c.mu.Lock()
	if c.api != a {
		c.mu.Unlock()
		return
	}
	if c.stop != nil {
		close(c.stop)
		c.stop = nil
	}
	c.api = nil
	c.me = beacon.User{}
	c.buddies = nil
	c.groups = nil
	c.chats = map[int][]beacon.Message{}
	c.typing = map[int]bool{}
	c.chatNames = map[int]string{}
	c.notice = "Your session expired or was revoked. Please sign in again."
	c.mu.Unlock()
	c.signal()
}

func (c *Controller) poll(stop <-chan struct{}, a *beacon.Client) {
	tick := time.NewTicker(c.pollEvery)
	defer tick.Stop()
	// Never share a cursor between different accounts. Missed server messages
	// are persisted, and event discovery does not change read markers.
	var cursor beacon.Cursor
	seeded := false
	for {
		select {
		case <-stop:
			return
		default:
		}
		c.mu.RLock()
		status := c.status
		userID := c.me.ID
		ids := make([]int, 0, len(c.chatNames))
		for id := range c.chatNames {
			ids = append(ids, id)
		}
		c.mu.RUnlock()
		x, end := deadline()
		_ = a.Presence(x, status)
		peers, err := a.Buddies(x)
		groups, e2 := a.Groups(x)
		chats := map[int][]beacon.Message{}
		typings := map[int]bool{}
		var arrivals []beacon.Message
		var syncErr error
		if err == nil && e2 == nil {
			if !seeded {
				cursor, syncErr = a.LatestEventID(x)
				seeded = syncErr == nil
			} else {
				var next beacon.Cursor
				next, syncErr = a.CatchUp(x, cursor, 100, 5, func(m beacon.Message) error {
					if m.RecipientID == userID && m.SenderID != userID {
						arrivals = append(arrivals, m)
					}
					return nil
				})
				cursor = next
			}
		}
		if err == nil && e2 == nil {
			for _, id := range ids {
				msgs, e := a.History(x, id)
				if e == nil {
					chats[id] = msgs
				}
				typing, _ := a.Typing(x, id)
				typings[id] = typing
			}
		}
		end()
		if errors.Is(err, beacon.ErrUnauthorized) || errors.Is(e2, beacon.ErrUnauthorized) || errors.Is(syncErr, beacon.ErrUnauthorized) {
			c.expireSession(a)
			return
		}
		c.mu.Lock()
		if c.api != a {
			c.mu.Unlock()
			return
		}
		if err == nil && e2 == nil {
			sort.SliceStable(peers, func(i, j int) bool { return strings.ToLower(peers[i].Name()) < strings.ToLower(peers[j].Name()) })
			c.buddies = peers
			c.groups = groups
			c.notice = "Connected to " + c.server
			if len(arrivals) > 0 {
				people := map[int]string{}
				counts := map[int]int{}
				muted := map[int]bool{}
				for _, buddy := range peers {
					people[buddy.ID] = buddy.Name()
					muted[buddy.ID] = bool(buddy.Muted)
				}
				for _, m := range arrivals {
					counts[m.SenderID]++
				}
				for id, count := range counts {
					if muted[id] {
						continue
					}
					name := people[id]
					if name == "" {
						name = "A Beacon contact"
					}
					text := "sent you a message"
					if count > 1 {
						text = fmt.Sprintf("sent you %d messages", count)
					}
					if c.notifier != nil {
						go c.notifier("Beacon · "+name, name+" "+text)
					}
				}
			}
			for id, m := range chats {
				c.chats[id] = m
			}
			for id, b := range typings {
				c.typing[id] = b
			}
		} else if err != nil {
			c.notice = "Network: " + err.Error()
		} else {
			c.notice = "Network: " + e2.Error()
		}
		c.mu.Unlock()
		c.signal()
		select {
		case <-stop:
			return
		case <-tick.C:
		}
	}
}
func (c *Controller) Snap() View {
	c.mu.RLock()
	defer c.mu.RUnlock()
	s := View{Logged: c.api != nil, Me: c.me, Server: c.server, Status: c.status, Error: c.notice,
		Buddies: append([]beacon.Buddy{}, c.buddies...), Groups: append([]beacon.Group{}, c.groups...), Chats: map[int][]beacon.Message{}, Typing: map[int]bool{}, ChatNames: map[int]string{}}
	for id, m := range c.chats {
		s.Chats[id] = append([]beacon.Message{}, m...)
	}
	for id, v := range c.typing {
		s.Typing[id] = v
	}
	for id, v := range c.chatNames {
		s.ChatNames[id] = v
	}
	return s
}
func (c *Controller) OpenChat(id int, name string) {
	c.mu.Lock()
	c.chatNames[id] = name
	c.mu.Unlock()
	c.signal()
}
func (c *Controller) CloseChat(id int) {
	c.mu.Lock()
	delete(c.chatNames, id)
	delete(c.chats, id)
	delete(c.typing, id)
	c.mu.Unlock()
	c.signal()
}
func (c *Controller) send(id int, text string) {
	c.mu.RLock()
	a := c.api
	c.mu.RUnlock()
	if a == nil || strings.TrimSpace(text) == "" {
		return
	}
	go func() {
		x, end := deadline()
		_, e := a.Send(x, id, strings.TrimSpace(text))
		end()
		if e != nil {
			c.errorf("Send failed: %v", e)
			return
		}
		c.Refresh()
	}()
}
func (c *Controller) Send(id int, text string) { c.send(id, text) }
func (c *Controller) Refresh() {
	c.mu.RLock()
	a := c.api
	c.mu.RUnlock()
	if a == nil {
		return
	}
	go func() {
		x, end := deadline()
		b, e := a.Buddies(x)
		end()
		if e != nil {
			return
		}
		c.mu.Lock()
		if a == c.api {
			c.buddies = b
		}
		c.mu.Unlock()
		c.signal()
	}()
}
func (c *Controller) Typing(id int) {
	c.mu.RLock()
	a := c.api
	c.mu.RUnlock()
	if a != nil {
		go func() { x, end := deadline(); defer end(); _ = a.SendTyping(x, id, true) }()
	}
}
func (c *Controller) ChangePresence(status string) {
	if status != "available" && status != "away" && status != "busy" {
		return
	}
	c.mu.Lock()
	c.status = status
	a := c.api
	c.mu.Unlock()
	c.signal()
	if a != nil {
		go func() { x, end := deadline(); defer end(); _ = a.Presence(x, status) }()
	}
}
func (c *Controller) Logout() {
	c.mu.Lock()
	a := c.api
	if c.stop != nil {
		close(c.stop)
		c.stop = nil
	}
	c.api = nil
	c.buddies = nil
	c.chats = map[int][]beacon.Message{}
	c.chatNames = map[int]string{}
	c.notice = "Logged out"
	c.loginPending = false
	c.mu.Unlock()
	c.signal()
	if a != nil {
		go func() { x, end := deadline(); defer end(); _ = a.Logout(x) }()
	}
}
func (c *Controller) MarkRead(id, msgID int) {
	c.mu.RLock()
	a := c.api
	c.mu.RUnlock()
	if a != nil && msgID > 0 {
		go func() { x, end := deadline(); defer end(); _ = a.MarkRead(x, id, msgID) }()
	}
}
func (c *Controller) AddBuddy(id int) {
	c.mu.RLock()
	a := c.api
	c.mu.RUnlock()
	if a == nil {
		return
	}
	go func() {
		x, end := deadline()
		defer end()
		if e := a.AddBuddy(x, id); e != nil {
			c.errorf("Add buddy: %v", e)
		} else {
			c.Refresh()
		}
	}()
}
func (c *Controller) Directory(f func([]beacon.User, error)) {
	c.mu.RLock()
	a := c.api
	c.mu.RUnlock()
	if a != nil {
		go func() { x, end := deadline(); defer end(); v, e := a.Directory(x); f(v, e) }()
	}
}
