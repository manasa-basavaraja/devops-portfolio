import io
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List

import pytest

from src.grafana import Grafana, GrafanaError


class FakeResponse:
    def __init__(self, body: bytes):
        self._buf = io.BytesIO(body)

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc) -> None:
        self._buf.close()


def _fake_opener(response_body: Dict[str, Any], captured: List[Dict[str, Any]]):
    """Build an opener that records each request and returns a fixed body."""

    def _opener(req: urllib.request.Request, timeout: float):
        captured.append({
            "method": req.get_method(),
            "url": req.full_url,
            "headers": dict(req.header_items()),
            "body": json.loads(req.data.decode("utf-8")) if req.data else None,
            "timeout": timeout,
        })
        return FakeResponse(json.dumps(response_body).encode("utf-8"))

    return _opener


def test_upsert_dashboard_posts_envelope():
    captured: List[Dict[str, Any]] = []
    g = Grafana(url="http://grafana.local", token="abc123")
    result = g.upsert_dashboard(
        {"uid": "demo", "title": "Demo"},
        opener=_fake_opener({"uid": "demo", "version": 4, "url": "/d/demo"}, captured),
    )

    assert len(captured) == 1
    call = captured[0]
    assert call["method"] == "POST"
    assert call["url"] == "http://grafana.local/api/dashboards/db"
    assert call["headers"]["Authorization"] == "Bearer abc123"
    assert call["headers"]["Content-type"] == "application/json"
    assert call["body"]["overwrite"] is True
    assert call["body"]["dashboard"]["uid"] == "demo"
    assert result == {"uid": "demo", "version": 4, "url": "/d/demo"}


def test_upsert_dashboard_includes_folder_uid_when_set():
    captured: List[Dict[str, Any]] = []
    g = Grafana(url="http://grafana.local", folder_uid="services")
    g.upsert_dashboard(
        {"uid": "demo"},
        opener=_fake_opener({"uid": "demo"}, captured),
    )
    assert captured[0]["body"]["folderUid"] == "services"


def test_upsert_dashboard_omits_auth_header_without_token():
    captured: List[Dict[str, Any]] = []
    g = Grafana(url="http://grafana.local")
    g.upsert_dashboard(
        {"uid": "demo"},
        opener=_fake_opener({"uid": "demo"}, captured),
    )
    headers = captured[0]["headers"]
    assert "Authorization" not in headers


def test_health_get_request():
    captured: List[Dict[str, Any]] = []
    g = Grafana(url="http://grafana.local")
    out = g.health(opener=_fake_opener({"database": "ok", "version": "10.4.0"}, captured))
    assert captured[0]["method"] == "GET"
    assert captured[0]["url"].endswith("/api/health")
    assert out == {"database": "ok", "version": "10.4.0"}


def test_http_error_is_translated():
    g = Grafana(url="http://grafana.local")

    def failing_opener(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"message":"nope"}')
        )

    with pytest.raises(GrafanaError, match="HTTP 401"):
        g.upsert_dashboard({"uid": "demo"}, opener=failing_opener)


def test_url_error_is_translated():
    g = Grafana(url="http://grafana.invalid")

    def failing_opener(req, timeout):
        raise urllib.error.URLError("connection refused")

    with pytest.raises(GrafanaError, match="connection refused"):
        g.health(opener=failing_opener)


def test_url_strips_trailing_slash():
    captured: List[Dict[str, Any]] = []
    g = Grafana(url="http://grafana.local/")
    g.health(opener=_fake_opener({"database": "ok"}, captured))
    assert captured[0]["url"] == "http://grafana.local/api/health"
