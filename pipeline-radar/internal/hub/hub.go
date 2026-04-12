package hub

import (
	"encoding/json"
	"log"
	"sync"

	"github.com/gorilla/websocket"
)

// PipelineEvent is the canonical shape for CI/CD notifications (GitHub Actions, etc.).
type PipelineEvent struct {
	Event      string `json:"event"`
	Repository string `json:"repository"`
	Workflow   string `json:"workflow"`
	Job        string `json:"job,omitempty"`
	RunID      string `json:"run_id,omitempty"`
	Status     string `json:"status"`
	Branch     string `json:"branch,omitempty"`
	Commit     string `json:"commit,omitempty"`
	URL        string `json:"url,omitempty"`
	Message    string `json:"message,omitempty"`
	Timestamp  string `json:"timestamp"`
}

// Hub fans out JSON messages to all WebSocket clients.
type Hub struct {
	mu      sync.RWMutex
	clients map[*websocket.Conn]struct{}
}

func New() *Hub {
	return &Hub{clients: make(map[*websocket.Conn]struct{})}
}

func (h *Hub) Register(c *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.clients[c] = struct{}{}
	log.Printf("client connected; total=%d", len(h.clients))
}

func (h *Hub) Unregister(c *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	delete(h.clients, c)
	log.Printf("client disconnected; total=%d", len(h.clients))
}

func (h *Hub) BroadcastJSON(v any) {
	data, err := json.Marshal(v)
	if err != nil {
		log.Printf("marshal broadcast: %v", err)
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	var dead []*websocket.Conn
	for c := range h.clients {
		if err := c.WriteMessage(websocket.TextMessage, data); err != nil {
			log.Printf("write client: %v", err)
			dead = append(dead, c)
		}
	}
	for _, c := range dead {
		delete(h.clients, c)
		_ = c.Close()
	}
}

func (h *Hub) BroadcastEvent(ev PipelineEvent) {
	h.BroadcastJSON(ev)
}

func (h *Hub) ClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}
