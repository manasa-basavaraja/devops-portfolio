package api

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/manasa-basavaraja/pipeline-radar/internal/hub"
)

// WebhookHandler validates optional HMAC later; for now accepts JSON POSTs from trusted CI.
func WebhookHandler(h *hub.Hub, sharedSecret string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
		if err != nil {
			http.Error(w, "read body", http.StatusBadRequest)
			return
		}
		var ev hub.PipelineEvent
		if err := json.Unmarshal(body, &ev); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}
		if sharedSecret != "" {
			got := strings.TrimSpace(r.Header.Get("X-Radar-Secret"))
			if got != sharedSecret {
				http.Error(w, "unauthorized", http.StatusUnauthorized)
				return
			}
		}
		if ev.Timestamp == "" {
			ev.Timestamp = time.Now().UTC().Format(time.RFC3339Nano)
		}
		h.BroadcastEvent(ev)
		log.Printf("webhook: %s %s %s", ev.Event, ev.Workflow, ev.Status)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}
}
