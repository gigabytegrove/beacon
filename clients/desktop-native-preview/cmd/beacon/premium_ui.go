package main

import (
	"fmt"
	"image"
	"image/color"
	"strings"
	"time"
	"unicode/utf8"

	"beacon.local/native/internal/beacon"
)

var premium = struct{ ink, subtle, border, ice, blueSoft, white, dark, orange color.RGBA }{
	ink: color.RGBA{18, 34, 61, 255}, subtle: color.RGBA{104, 124, 150, 255},
	border: color.RGBA{221, 231, 244, 255}, ice: color.RGBA{244, 248, 255, 255},
	blueSoft: color.RGBA{230, 242, 255, 255}, white: color.RGBA{255, 255, 255, 255},
	dark: color.RGBA{8, 24, 49, 255}, orange: color.RGBA{245, 168, 62, 255},
}

func framed(im *image.RGBA, x, y, w, h, r int, fill color.RGBA) {
	rounded(im, x, y, w, h, r, premium.border)
	if w > 2 && h > 2 {
		rounded(im, x+1, y+1, w-2, h-2, r-1, fill)
	}
}
func (c *ClientState) hoverOn(target string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.hover == target
}

// HoverAt only redraws when the active control changes. Both native Win32
// and X11 use these same hit boxes and share the identical rendered UI.
func (c *ClientState) HoverAt(screen string, id, x, y int) bool {
	target := ""
	switch screen {
	case "login":
		if x >= 47 && x < 433 && y >= 584 && y < 638 {
			target = "login:submit"
		}
	case "roster":
		if y >= 281 && y < 325 && x >= 20 && x < 460 {
			target = fmt.Sprintf("roster:status:%d", (x-20)/107)
		}
		if y >= 341 && y < 391 && x >= 330 && x < 460 {
			target = "roster:add"
		}
		if y >= 430 && y < 715 && x >= 21 && x < 459 {
			target = fmt.Sprintf("roster:buddy:%d", (y-430)/57)
		}
	case "chat":
		if x >= 542 && x < 665 && y >= 577 && y < 636 {
			target = "chat:send"
		}
	case "directory":
		if x >= 30 && x < 448 && y >= 251 && y < 556 {
			target = fmt.Sprintf("directory:user:%d", (y-251)/61)
		}
	}
	c.mu.Lock()
	changed := c.hover != target
	c.hover = target
	c.mu.Unlock()
	return changed
}

func (c *ClientState) paintLogin(s View) *image.RGBA {
	im := freshSkin("login")
	c.mu.RLock()
	fields := c.login
	focus := c.loginFocus
	c.mu.RUnlock()
	for index, value := range fields {
		y := 347 + 82*index
		if index == focus {
			framed(im, 47, y, 386, 50, 12, premium.white)
			// Crisp focus ring on the active field.
			solid(im, 60, y+47, 358, 2, colors.blue)
		}
		if index == 2 && value != "" {
			value = strings.Repeat("•", utf8.RuneCountInString(value))
		}
		if value == "" {
			value = []string{"http://YOUR-DOKPLOY-IP:8765", "Your username", "Your password"}[index]
		}
		colorText := premium.ink
		if fields[index] == "" {
			colorText = premium.subtle
		}
		drawText(im, 64, y+13, fit(value, "md", 340), "md", colorText)
		if focus == index { // subtle caret confirms the currently active keyboard field
			caretX := 64 + textWidth(fit(value, "md", 340), "md") + 2
			if fields[index] == "" {
				caretX = 64
			}
			if caretX < 417 {
				solid(im, caretX, y+13, 2, 18, colors.blue)
			}
		}
	}
	if c.hoverOn("login:submit") {
		rounded(im, 47, 584, 386, 54, 13, color.RGBA{5, 95, 224, 255})
		drawText(im, 191, 602, "Sign in", "lg", colors.white)
		disc(im, 406, 612, 16, color.RGBA{46, 143, 255, 255})
		drawText(im, 401, 599, ">", "lg", colors.white)
	}
	message := s.Error
	if strings.TrimSpace(message) == "" {
		message = "Ready to connect to your Beacon server."
	}
	low := strings.ToLower(message)
	isError := strings.Contains(low, "failed") || strings.Contains(low, "refused") || strings.Contains(low, "network:") || strings.Contains(low, "error:") || strings.Contains(low, "invalid")
	switch {
	case strings.Contains(low, "refused") || strings.Contains(low, "no such host") || strings.Contains(low, "timeout"):
		message = "Server unreachable. Check the address or Dokploy status."
		isError = true
	case strings.Contains(low, "401") || strings.Contains(low, "incorrect") || strings.Contains(low, "unauthorized"):
		message = "Sign in failed. Check your account details."
		isError = true
	}
	if isError {
		rounded(im, 46, 648, 388, 29, 9, color.RGBA{255, 238, 240, 255})
		disc(im, 61, 661, 5, colors.red)
		drawText(im, 74, 652, fit(message, "sm", 343), "sm", colors.red)
	} else {
		drawText(im, 73, 653, fit(message, "sm", 345), "sm", premium.subtle)
	}
	return im
}
func (c *ClientState) paintRoster(s View) *image.RGBA {
	im := freshSkin("roster")
	c.mu.RLock()
	filter := c.filter
	searchFocus := c.searchFocus
	scroll := c.scroll
	c.mu.RUnlock()
	// Signed-in profile is the main anchor in the roster.
	if !paintAvatar(im, s.Me.Avatar, 76, 211, 27) {
		disc(im, 76, 211, 26, colors.blue)
		initials := "?"
		if r := []rune(s.Me.DisplayName); len(r) > 0 {
			initials = strings.ToUpper(string(r[0]))
		}
		drawText(im, 66, 198, initials, "lg", colors.white)
	}
	drawText(im, 119, 195, fit(s.Me.DisplayName, "lg", 292), "lg", premium.ink)
	drawText(im, 119, 221, fit("@"+s.Me.Username, "sm", 290), "sm", premium.subtle)
	// Status marker and readable text in the profile strip.
	badgeColor := statusColor(s.Status)
	disc(im, 123, 248, 4, badgeColor)
	drawText(im, 135, 239, statusLabel(s.Status)+" on your network", "tiny", badgeColor)
	for i, status := range []string{"available", "away", "busy"} {
		x := 20 + i*107
		w := 101
		if s.Status == status {
			rounded(im, x, 281, w, 44, 11, colors.blue)
		} else if c.hoverOn(fmt.Sprintf("roster:status:%d", i)) {
			rounded(im, x, 281, w, 44, 11, premium.blueSoft)
		}
		label := []string{"Online", "Away", "Busy"}[i]
		tint := premium.ink
		if s.Status == status {
			tint = colors.white
		}
		drawText(im, x+(w-textWidth(label, "md-bold"))/2, 292, label, "md-bold", tint)
	}
	if c.hoverOn("roster:add") {
		rounded(im, 331, 341, 128, 50, 13, color.RGBA{2, 99, 232, 255})
		drawText(im, 352, 356, "+ Add buddy", "md-bold", colors.white)
	}
	if filter == "" {
		filter = "Search people or status..."
	}
	if searchFocus {
		solid(im, 44, 388, 264, 2, colors.blue)
	}
	colorText := premium.ink
	if filter == "Search people or status..." {
		colorText = premium.subtle
	}
	drawText(im, 65, 356, fit(filter, "md", 235), "md", colorText)
	items := c.filtered(s)
	if scroll > len(items)-5 {
		scroll = len(items) - 5
	}
	if scroll < 0 {
		scroll = 0
	}
	summary := fmt.Sprintf("%d people · %d online", len(items), onlineCount(items))
	drawText(im, 169, 404, fit(summary, "sm", 194), "sm", premium.subtle)
	if len(items) == 0 {
		rounded(im, 22, 438, 436, 243, 18, premium.white)
		disc(im, 240, 507, 36, premium.blueSoft)
		drawText(im, 225, 491, "+", "xl", colors.blue)
		if strings.TrimSpace(c.filter) == "" {
			label := "No buddies yet"
			drawText(im, (480-textWidth(label, "lg"))/2, 554, label, "lg", premium.ink)
			sub := "Add someone to start a conversation."
			drawText(im, (480-textWidth(sub, "sm"))/2, 590, sub, "sm", premium.subtle)
		} else {
			label := "No matching people"
			drawText(im, (480-textWidth(label, "lg"))/2, 554, label, "lg", premium.ink)
			sub := "Try a different name or status."
			drawText(im, (480-textWidth(sub, "sm"))/2, 590, sub, "sm", premium.subtle)
		}
		drawText(im, 173, 641, "+ ADD BUDDY", "sm", colors.blue)
		return im
	}
	for i := scroll; i < len(items) && i < scroll+5; i++ {
		b := items[i]
		row := i - scroll
		y := 430 + row*57
		bg := premium.white
		if c.hoverOn(fmt.Sprintf("roster:buddy:%d", row)) {
			bg = premium.blueSoft
		}
		framed(im, 22, y, 436, 53, 12, bg)
		if b.UnreadCount > 0 {
			rounded(im, 22, y+13, 3, 26, 1, colors.blue)
		}
		if !paintAvatar(im, b.Avatar, 56, y+26, 18) {
			disc(im, 56, y+26, 18, premium.blueSoft)
			initials := "?"
			if r := []rune(b.Name()); len(r) > 0 {
				initials = strings.ToUpper(string(r[0]))
			}
			drawText(im, 49, y+15, initials, "md-bold", colors.blue)
		}
		disc(im, 71, y+39, 6, premium.white)
		disc(im, 71, y+39, 4, statusColor(b.Presence))
		drawText(im, 90, y+8, fit(b.Name(), "md-bold", 263), "md-bold", premium.ink)
		subtitle := strings.TrimSpace(b.StatusText)
		if b.GroupName != "" && b.GroupName != "Buddies" {
			if subtitle != "" {
				subtitle = b.GroupName + "  ·  " + subtitle
			} else {
				subtitle = b.GroupName
			}
		}
		if subtitle == "" {
			subtitle = statusLabel(b.Presence)
		}
		drawText(im, 90, y+29, fit(subtitle, "sm", 275), "sm", premium.subtle)
		if b.UnreadCount > 0 {
			count := fmt.Sprintf("%d", b.UnreadCount)
			if b.UnreadCount > 99 {
				count = "99+"
			}
			rounded(im, 409, y+13, 31, 27, 13, colors.blue)
			drawText(im, 424-textWidth(count, "sm")/2, y+17, count, "sm", colors.white)
		} else {
			drawText(im, 412, y+20, ">", "md-bold", colors.blue)
		}
	}
	return im
}

func wrapLines(message string, kind string, maxWidth, maxLines int) []string {
	message = strings.Join(strings.Fields(message), " ")
	if message == "" {
		return []string{""}
	}
	words := strings.Fields(message)
	lines := []string{}
	line := ""
	for _, word := range words {
		next := word
		if line != "" {
			next = line + " " + word
		}
		if textWidth(next, kind) <= maxWidth {
			line = next
			continue
		}
		if line != "" {
			lines = append(lines, line)
			line = ""
		}
		if textWidth(word, kind) > maxWidth {
			line = fit(word, kind, maxWidth-10)
		} else {
			line = word
		}
		if len(lines) >= maxLines {
			break
		}
	}
	if line != "" && len(lines) < maxLines {
		lines = append(lines, line)
	}
	if len(lines) == 0 {
		lines = []string{fit(message, kind, maxWidth)}
	}
	if len(lines) == maxLines && strings.Join(lines, " ") != message {
		lines[maxLines-1] = fit(lines[maxLines-1]+"...", kind, maxWidth)
	}
	return lines
}

func (c *ClientState) paintChat(id int, s View) *image.RGBA {
	im := freshSkin("chat")
	name := s.ChatNames[id]
	presence := "offline"
	for _, buddy := range s.Buddies {
		if buddy.ID == id {
			name = buddy.Name()
			presence = buddy.Presence
			break
		}
	}
	if name == "" {
		name = "Conversation"
	}
	disc(im, 115, 113, 25, premium.blueSoft)
	ini := "?"
	if r := []rune(name); len(r) > 0 {
		ini = strings.ToUpper(string(r[0]))
	}
	drawText(im, 104, 100, ini, "lg", colors.blue)
	drawText(im, 155, 86, fit(name, "lg", 340), "lg", colors.white)
	disc(im, 160, 121, 5, statusColor(presence))
	drawText(im, 174, 113, statusLabel(presence)+"  ·  Beacon messenger", "sm", color.RGBA{175, 203, 236, 255})
	messages := s.Chats[id]
	c.mu.RLock()
	body := c.chatEntries[id]
	offset := c.chatScroll[id]
	c.mu.RUnlock()
	if len(messages) == 0 {
		disc(im, 350, 343, 37, premium.blueSoft)
		drawText(im, 339, 329, "+", "xl", colors.blue)
		heading := "Start a conversation"
		drawText(im, (700-textWidth(heading, "lg"))/2, 398, heading, "lg", premium.ink)
		sub := "Send a message to say hello."
		drawText(im, (700-textWidth(sub, "sm"))/2, 435, sub, "sm", premium.subtle)
	} else {
		if offset > len(messages)-1 {
			offset = len(messages) - 1
		}
		until := len(messages) - offset
		if until < 0 {
			until = 0
		}
		// Show up to four most recent transcript items. Wheel up in chat to
		// navigate older pages without needing an external scroll widget.
		start := until - 4
		if start < 0 {
			start = 0
		}
		shown := messages[start:until]
		// Message bubble height depends on actual visible line wrapping.
		heights := make([]int, len(shown))
		total := 0
		for i, m := range shown {
			lines := wrapLines(m.Body, "md", 395, 2)
			heights[i] = max(48, 21+len(lines)*21) + 9
			total += heights[i]
		}
		y := 496 - total
		if y < 240 {
			y = 240
		}
		if offset > 0 {
			drawText(im, 40, 220, fmt.Sprintf("EARLIER MESSAGES  ·  %d NEWER", offset), "tiny", colors.blue)
		}
		for i, m := range shown {
			mine := m.SenderID == s.Me.ID
			lines := wrapLines(m.Body, "md", 395, 2)
			w := 120
			for _, line := range lines {
				if next := textWidth(line, "md") + 31; next > w {
					w = next
				}
			}
			if w > 438 {
				w = 438
			}
			h := heights[i] - 8
			x := 42
			if mine {
				x = 651 - w
			}
			tint := premium.blueSoft
			ink := premium.ink
			if mine {
				tint = colors.blue
				ink = colors.white
			}
			rounded(im, x, y, w, h, 13, tint)
			if !mine {
				rounded(im, x, y, 3, h, 2, color.RGBA{173, 210, 250, 255})
			}
			for z, line := range lines {
				drawText(im, x+15, y+11+21*z, fit(line, "md", w-27), "md", ink)
			}
			tm := time.Unix(m.CreatedAt, 0).Format("15:04")
			if mine {
				drawText(im, x-42, y+16, tm, "tiny", premium.subtle)
			} else {
				drawText(im, x+w+8, y+16, tm, "tiny", premium.subtle)
			}
			y += heights[i]
		}
	}
	if s.Typing[id] {
		drawText(im, 42, 502, fit(name+" is typing...", "sm", 270), "sm", colors.green)
	}
	if body == "" {
		drawText(im, 54, 597, "Write a message...", "md", premium.subtle)
	} else {
		drawText(im, 54, 597, fit(body, "md", 450), "md", premium.ink)
	}
	if c.hoverOn("chat:send") {
		rounded(im, 542, 577, 123, 59, 13, color.RGBA{4, 99, 228, 255})
		drawText(im, 576, 595, "Send", "lg", colors.white)
		disc(im, 641, 607, 12, color.RGBA{48, 147, 255, 255})
		drawText(im, 635, 593, ">", "lg", colors.white)
	}
	return im
}
func (c *ClientState) paintDirectory(s View) *image.RGBA {
	im := freshSkin("directory")
	c.mu.RLock()
	people := append([]beacon.User(nil), c.contacts...)
	loading := c.directoryLoading
	c.mu.RUnlock()
	if loading {
		drawText(im, 46, 271, "Finding people on your Beacon server...", "md", premium.subtle)
	}
	if !loading && len(people) == 0 {
		disc(im, 239, 339, 31, premium.blueSoft)
		drawText(im, 228, 327, "?", "lg", colors.blue)
		msg := "No new people to add"
		drawText(im, (480-textWidth(msg, "lg"))/2, 396, msg, "lg", premium.ink)
		msg2 := "Ask an administrator to invite someone."
		drawText(im, (480-textWidth(msg2, "sm"))/2, 432, msg2, "sm", premium.subtle)
	}
	for i, p := range people {
		if i >= 5 {
			break
		}
		y := 251 + i*61
		fill := premium.white
		if c.hoverOn(fmt.Sprintf("directory:user:%d", i)) {
			fill = premium.blueSoft
		}
		framed(im, 31, y, 418, 57, 11, fill)
		disc(im, 57, y+28, 19, premium.blueSoft)
		ini := "?"
		if r := []rune(p.DisplayName); len(r) > 0 {
			ini = strings.ToUpper(string(r[0]))
		}
		drawText(im, 50, y+17, ini, "md-bold", colors.blue)
		drawText(im, 94, y+9, fit(p.DisplayName, "md-bold", 255), "md-bold", premium.ink)
		drawText(im, 94, y+31, fit("@"+p.Username, "sm", 230), "sm", premium.subtle)
		rounded(im, 385, y+17, 47, 24, 12, premium.blueSoft)
		drawText(im, 397, y+19, "ADD", "sm", colors.blue)
	}
	return im
}
