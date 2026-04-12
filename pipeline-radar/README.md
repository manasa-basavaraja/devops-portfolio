# Pipeline Radar

Real-time **CI/CD visibility**: GitHub Actions posts pipeline events to a small Go service, which **broadcasts over WebSockets** to a browser dashboard. Good for a portfolio piece because it is concrete (you can demo the live feed in a screen recording) and touches **Go**, **Docker**, **GitHub Actions**, and **observability-style** event flow.

## What it does

1. You run **Pipeline Radar** (binary or Docker) somewhere reachable from the internet (VM, homelab, or a tunnel such as [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) / [ngrok](https://ngrok.com/)).
2. Your repo’s **GitHub Actions** workflow sends JSON `POST` requests to `/ingest` when a workflow **starts** and **finishes**.
3. The **dashboard** (same server, static assets) opens a **WebSocket** to `/ws` and shows each event as it arrives.

Optional: set `RADAR_WEBHOOK_SECRET` on the server and store the same value in GitHub as `RADAR_WEBHOOK_SECRET`; workflows send it as header `X-Radar-Secret`.

## Quick start (local)

```bash
cd pipeline-radar
go mod tidy
go run ./cmd/server
```

Open [http://localhost:8080](http://localhost:8080). In another terminal:

```bash
curl -sS -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{"event":"demo","repository":"you/pipeline-radar","workflow":"manual","status":"success","message":"Hello from curl"}'
```

You should see the event appear instantly in the browser.

## Docker

```bash
docker compose up --build
```

## GitHub Actions wiring

Repository secrets:

| Secret | Purpose |
|--------|---------|
| `RADAR_INGEST_URL` | Full URL to your public `/ingest` endpoint, e.g. `https://radar.example.com/ingest` |
| `RADAR_WEBHOOK_SECRET` | Optional; must match server env `RADAR_WEBHOOK_SECRET` |

The included [`.github/workflows/ci.yml`](.github/workflows/ci.yml) notifies Radar on **push** to `main`/`master` (skipped on PRs). If `RADAR_INGEST_URL` is unset, notify steps no-op so forks still pass CI.

## Event JSON shape

```json
{
  "event": "workflow_started",
  "repository": "owner/repo",
  "workflow": "CI",
  "job": "build",
  "run_id": "123456789",
  "status": "in_progress",
  "branch": "main",
  "commit": "abcdef1",
  "url": "https://github.com/owner/repo/actions/runs/123456789",
  "message": "Workflow started",
  "timestamp": "2026-04-09T12:00:00.000000000Z"
}
```

If `timestamp` is omitted, the server sets it (UTC, RFC3339Nano).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard |
| `GET` | `/ws` | WebSocket stream |
| `POST` | `/ingest` | Accept pipeline events (JSON body) |
| `GET` | `/healthz` | Liveness |
| `GET` | `/api/stats` | JSON: `websocket_clients` count |

## Customize the module path

Replace `github.com/yourusername/pipeline-radar` in `go.mod` and all `import` lines with your real module path after you publish the repo.

## Showcase ideas

- Short **README GIF or video**: split screen — Actions run on the left, Radar dashboard on the right.
- Mention **why WebSockets** (low latency fan-out, simple ops) vs polling.
- Optional extension: persist events to SQLite or Postgres and add a “last 24h” chart (keeps the same real-time core).

## License

MIT
