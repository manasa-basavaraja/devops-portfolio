const feed = document.getElementById("feed");
const connEl = document.getElementById("conn");
const countEl = document.getElementById("count");
const clientsEl = document.getElementById("clients");

let total = 0;

function wsURL() {
  const p = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${p}//${window.location.host}/ws`;
}

function statusClass(s) {
  const x = (s || "").toLowerCase();
  if (x.includes("success") || x === "ok") return "success";
  if (x.includes("fail") || x.includes("error")) return "failure";
  if (x.includes("cancel")) return "cancelled";
  if (x.includes("progress") || x === "started" || x === "queued") return "in_progress";
  return "";
}

function addEvent(ev) {
  total += 1;
  countEl.textContent = String(total);

  const li = document.createElement("li");
  const badge = document.createElement("span");
  badge.className = "badge " + statusClass(ev.status);
  badge.textContent = ev.status || ev.event || "event";

  const body = document.createElement("div");
  const title = document.createElement("div");
  title.innerHTML = `<strong>${escapeHtml(ev.workflow || "workflow")}</strong> · ${escapeHtml(ev.repository || "")}`;
  const meta = document.createElement("div");
  meta.className = "meta";
  const parts = [
    ev.event && `event: ${ev.event}`,
    ev.job && `job: ${ev.job}`,
    ev.branch && `branch: ${ev.branch}`,
    ev.commit && `commit: ${ev.commit.slice(0, 7)}`,
    ev.run_id && `run: ${ev.run_id}`,
    ev.timestamp && `at: ${ev.timestamp}`,
  ].filter(Boolean);
  meta.textContent = parts.join(" · ");

  body.appendChild(title);
  body.appendChild(meta);

  if (ev.message || ev.url) {
    const msg = document.createElement("div");
    msg.className = "msg";
    if (ev.url) {
      const a = document.createElement("a");
      a.href = ev.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = ev.message || ev.url;
      a.style.color = "#6cb6ff";
      msg.appendChild(a);
    } else {
      msg.textContent = ev.message;
    }
    li.appendChild(msg);
  }

  li.prepend(body);
  li.prepend(badge);
  feed.prepend(li);

  while (feed.children.length > 100) {
    feed.removeChild(feed.lastChild);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function refreshStats() {
  try {
    const r = await fetch("/api/stats");
    const j = await r.json();
    clientsEl.textContent = String(j.websocket_clients ?? "—");
  } catch {
    clientsEl.textContent = "—";
  }
}

function connect() {
  const ws = new WebSocket(wsURL());
  connEl.textContent = "Connecting…";
  connEl.className = "status";

  ws.onopen = () => {
    connEl.textContent = "Live";
    connEl.className = "status live";
    refreshStats();
  };
  ws.onclose = () => {
    connEl.textContent = "Disconnected — retrying…";
    connEl.className = "status dead";
    setTimeout(connect, 2000);
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (e) => {
    try {
      addEvent(JSON.parse(e.data));
    } catch {
      /* ignore */
    }
    refreshStats();
  };
}

setInterval(refreshStats, 5000);
connect();
