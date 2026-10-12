package beacon

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strconv"
	"testing"
)

func TestCursorSeedAndThreePageCatchup(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer account-one" {
			t.Errorf("bad bearer for %s", r.URL)
		}
		w.Header().Set("Content-Type", "application/json")
		if r.URL.Path == "/api/events/latest" {
			fmt.Fprint(w, `{"last_message_id":7}`)
			return
		}
		if r.URL.Path != "/api/events" {
			t.Errorf("bad route %q", r.URL)
			return
		}
		calls++
		after, _ := strconv.Atoi(r.URL.Query().Get("after"))
		switch after {
		case 0:
			fmt.Fprint(w, `{"events":[{"id":1,"sender_id":2},{"id":2,"sender_id":2}],"next_cursor":2}`)
		case 2:
			fmt.Fprint(w, `{"events":[{"id":4,"sender_id":2},{"id":7,"sender_id":2}],"next_cursor":7}`)
		case 7:
			fmt.Fprint(w, `{"events":[{"id":10,"sender_id":2}],"next_cursor":10}`)
		default:
			t.Errorf("unexpected cursor %d", after)
		}
	}))
	defer server.Close()
	c, _ := NewClient(server.URL)
	c.SetToken("account-one")
	seed, err := c.LatestEventID(context.Background())
	if err != nil || seed != 7 {
		t.Fatalf("seed %d %v", seed, err)
	}
	seen := []int{}
	end, err := c.CatchUp(context.Background(), 0, 2, 5, func(m Message) error { seen = append(seen, m.ID); return nil })
	if err != nil || end != 10 || len(seen) != 5 || calls != 3 {
		t.Fatalf("end=%d err=%v ids=%v calls=%d", end, err, seen, calls)
	}
}
func TestEventStreamRefusesCursorCorruption(t *testing.T) {
	examples := []string{
		`{"events":[{"id":2},{"id":2}],"next_cursor":2}`,
		`{"events":[{"id":1}],"next_cursor":999}`,
		`{"events":[{"id":-1}],"next_cursor":-1}`,
		`{"events":[{"id":1},{"id":2},{"id":3}],"next_cursor":3}`,
	}
	for _, body := range examples {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, body) }))
		c, _ := NewClient(server.URL)
		events, next, err := c.EventBatch(context.Background(), 0, 2)
		server.Close()
		if err == nil || next != 0 || events != nil {
			t.Errorf("accepted corrupt events: %s: %#v %d %v", body, events, next, err)
		}
	}
}
func TestCatchUpFailedCallbackReturnsLastDeliveredCursor(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, `{"events":[{"id":6},{"id":7}],"next_cursor":7}`)
	}))
	defer server.Close()
	c, _ := NewClient(server.URL)
	last, err := c.CatchUp(context.Background(), 5, 2, 2, func(m Message) error {
		if m.ID == 7 {
			return errors.New("window closed")
		}
		return nil
	})
	if last != 6 || err == nil {
		t.Fatalf("got cursor %d, error %v", last, err)
	}
}
func TestCursorInputsFailWithoutNetwork(t *testing.T) {
	c, _ := NewClient("http://127.0.0.1:1")
	if _, _, e := c.EventBatch(context.Background(), -1, 1); e == nil {
		t.Fatal("negative cursor accepted")
	}
	if _, _, e := c.EventBatch(context.Background(), 0, 501); e == nil {
		t.Fatal("large page accepted")
	}
	if _, e := c.CatchUp(context.Background(), 0, 10, 2, nil); e == nil {
		t.Fatal("nil callback accepted")
	}
}

func TestCatchUpRetriesWithoutDuplicatingDeliveredEvents(t *testing.T) {
	failing := true
	service := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		after, _ := strconv.Atoi(r.URL.Query().Get("after"))
		switch after {
		case 10:
			fmt.Fprint(w, `{"events":[{"id":11},{"id":12}],"next_cursor":12}`)
		case 12:
			if failing {
				failing = false
				http.Error(w, "temporary network outage", http.StatusServiceUnavailable)
				return
			}
			fmt.Fprint(w, `{"events":[{"id":13}],"next_cursor":13}`)
		default:
			t.Errorf("unexpected cursor: %d", after)
		}
	}))
	defer service.Close()
	c, _ := NewClient(service.URL)
	observed := []int{}
	onEvent := func(message Message) error {
		observed = append(observed, message.ID)
		return nil
	}
	cursor, err := c.CatchUp(context.Background(), 10, 2, 3, onEvent)
	if err == nil || cursor != 12 {
		t.Fatalf("want retryable failure at 12, got %d %v", cursor, err)
	}
	cursor, err = c.CatchUp(context.Background(), cursor, 2, 3, onEvent)
	if err != nil || cursor != 13 || !reflect.DeepEqual(observed, []int{11, 12, 13}) {
		t.Fatalf("lost or duplicate events: cursor=%d, err=%v, events=%v", cursor, err, observed)
	}
}

func TestCatchUpHonorsPageBudget(t *testing.T) {
	requests := 0
	service := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		after, _ := strconv.Atoi(r.URL.Query().Get("after"))
		fmt.Fprintf(w, `{"events":[{"id":%d}],"next_cursor":%d}`, after+1, after+1)
	}))
	defer service.Close()
	c, _ := NewClient(service.URL)
	cursor, err := c.CatchUp(context.Background(), 0, 1, 3, func(Message) error { return nil })
	if err != nil || cursor != 3 || requests != 3 {
		t.Fatalf("budget overrun: %d %v calls=%d", cursor, err, requests)
	}
}

func TestCancelledContextNeverQueriesEventServer(t *testing.T) {
	c, _ := NewClient("http://127.0.0.1:1")
	ctx, stop := context.WithCancel(context.Background())
	stop()
	_, err := c.CatchUp(ctx, 0, 5, 2, func(Message) error { return nil })
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("want canceled, got %v", err)
	}
}
