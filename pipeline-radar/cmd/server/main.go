package main

import (
	"embed"
	"encoding/json"
	"flag"
	"io/fs"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gorilla/websocket"
	"github.com/manasa-basavaraja/pipeline-radar/internal/api"
	"github.com/manasa-basavaraja/pipeline-radar/internal/hub"
)

//go:embed all:static
var staticEmbed embed.FS

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		origin := r.Header.Get("Origin")
		if origin == "" {
			return true
		}
		host := r.Host
		return strings.Contains(origin, host) || strings.HasPrefix(origin, "http://localhost") || strings.HasPrefix(origin, "http://127.0.0.1")
	},
}

func main() {
	addr := flag.String("addr", ":8080", "listen address")
	secret := flag.String("secret", os.Getenv("RADAR_WEBHOOK_SECRET"), "optional shared secret; require X-Radar-Secret header on POST /ingest")
	flag.Parse()

	h := hub.New()

	staticFS, err := fs.Sub(staticEmbed, "static")
	if err != nil {
		log.Fatalf("static fs: %v", err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("/api/stats", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"websocket_clients": h.ClientCount()})
	})
	mux.HandleFunc("/ingest", api.WebhookHandler(h, strings.TrimSpace(*secret)))
	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		c, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Printf("upgrade: %v", err)
			return
		}
		h.Register(c)
		defer func() { _ = c.Close() }()
		defer h.Unregister(c)
		_ = c.SetReadDeadline(time.Now().Add(60 * time.Second))
		c.SetPongHandler(func(string) error {
			_ = c.SetReadDeadline(time.Now().Add(120 * time.Second))
			return nil
		})
		for {
			if _, _, err := c.ReadMessage(); err != nil {
				break
			}
		}
	})
	mux.Handle("/", http.FileServer(http.FS(staticFS)))

	log.Printf("pipeline-radar listening on http://localhost%s", *addr)
	log.Fatal(http.ListenAndServe(*addr, mux))
}
