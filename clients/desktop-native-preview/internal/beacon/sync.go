package beacon

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strconv"
)

// Cursor identifies the last message observed by this client. It is scoped to
// one authenticated account/session: never reuse it after changing accounts.
// Event IDs are globally increasing but are only returned for conversations
// the authenticated user participates in.
type Cursor int

// Page is the server's ordered /api/events response.
type Page struct {
	Events     []Message `json:"events"`
	NextCursor int       `json:"next_cursor"`
}

// LatestEventID retrieves the current account's most recent message ID.
// Call this when first enabling live alerts to avoid treating months of old
// messages as fresh notifications. Fetch saved history separately.
func (c *Client) LatestEventID(ctx context.Context) (Cursor, error) {
	var body struct {
		LastMessageID int `json:"last_message_id"`
	}
	if err := c.Get(ctx, "/events/latest", &body); err != nil {
		return 0, err
	}
	if body.LastMessageID < 0 {
		return 0, errors.New("server sent a negative message cursor")
	}
	return Cursor(body.LastMessageID), nil
}

// EventBatch fetches messages after the supplied cursor without marking them
// read on behalf of other devices. A server bug must not silently rewind or
// skip a cursor, because doing so can lose incoming notifications.
func (c *Client) EventBatch(ctx context.Context, after Cursor, limit int) ([]Message, Cursor, error) {
	if after < 0 || limit < 1 || limit > 500 {
		return nil, after, errors.New("invalid message cursor or event page size")
	}
	q := url.Values{"after": {strconv.Itoa(int(after))}, "limit": {strconv.Itoa(limit)}}
	var page Page
	if err := c.Get(ctx, "/events?"+q.Encode(), &page); err != nil {
		return nil, after, err
	}
	newCursor := after
	for _, m := range page.Events {
		if m.ID <= int(newCursor) {
			return nil, after, fmt.Errorf("non-increasing event IDs after %d", newCursor)
		}
		newCursor = Cursor(m.ID)
	}
	if page.NextCursor != int(newCursor) {
		return nil, after, fmt.Errorf("event cursor mismatch: header %d, last %d", page.NextCursor, newCursor)
	}
	if len(page.Events) > limit {
		return nil, after, errors.New("oversized event page from server")
	}
	return page.Events, newCursor, nil
}

// CatchUp walks every available message page, in order, at most maxPages
// pages at a time to bound CPU/network work when a device has been offline.
// It returns the latest *delivered* cursor, even if a later page fails, so
// callers can retry without duplicating earlier events. The callback is run
// in the caller's goroutine and must not directly mutate GUI widgets.
func (c *Client) CatchUp(ctx context.Context, after Cursor, pageSize, maxPages int, deliver func(Message) error) (Cursor, error) {
	if deliver == nil {
		return after, errors.New("missing event receiver")
	}
	if pageSize < 1 || pageSize > 500 || maxPages < 1 || maxPages > 1000 {
		return after, errors.New("invalid catch-up bounds")
	}
	for pageIndex := 0; pageIndex < maxPages; pageIndex++ {
		if err := ctx.Err(); err != nil {
			return after, err
		}
		batch, _, err := c.EventBatch(ctx, after, pageSize)
		if err != nil {
			return after, err
		}
		for _, m := range batch {
			if err := deliver(m); err != nil {
				return after, err
			}
			after = Cursor(m.ID)
		}
		if len(batch) < pageSize {
			return after, nil
		}
	}
	return after, nil
}
