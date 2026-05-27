"""
Tiny Grafana HTTP client - just the two endpoints we need.

The Grafana HTTP API is well documented and stable, so there is no real
reason to pull in a heavier client library. We use the standard library
``urllib.request`` so the package keeps a small dependency surface and
can be mocked in tests with a single replacement function.

Two operations are exposed:

* :func:`upsert_dashboard` - POST ``/api/dashboards/db`` with
  ``overwrite=true``. The dashboard model from
  :mod:`src.dashboard` is wrapped into the envelope Grafana expects.
* :func:`health` - GET ``/api/health``. Used by ``apply`` as a
  pre-flight to fail early if the URL or token is wrong.

Authentication is via a Grafana API token (Bearer) or - for OSS
deployments without auth - omit the token entirely.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


# Type for the function we use to actually perform an HTTP request.
# Pulled out as a parameter so tests can swap in a fake without touching
# urllib internals. The signature mirrors a tiny subset of urlopen.
HttpOpener = Callable[[urllib.request.Request, float], "urllib.request._UrlopenRet"]


class GrafanaError(Exception):
    """Raised when Grafana returns a non-2xx response or is unreachable."""


@dataclass(frozen=True)
class Grafana:
    """Configured Grafana endpoint."""

    url: str
    token: Optional[str] = None
    folder_uid: Optional[str] = None
    timeout: float = 10.0

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        opener: HttpOpener = urllib.request.urlopen,
    ) -> Dict[str, Any]:
        url = self.url.rstrip("/") + path
        data: Optional[bytes] = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
        try:
            with opener(req, self.timeout) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GrafanaError(
                f"{method} {path} failed: HTTP {exc.code} {exc.reason}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GrafanaError(f"{method} {path} failed: {exc.reason}") from exc

        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise GrafanaError(f"{method} {path} returned non-JSON body") from exc
        if not isinstance(parsed, dict):
            raise GrafanaError(f"{method} {path} returned non-object JSON")
        return parsed

    def health(self, opener: HttpOpener = urllib.request.urlopen) -> Dict[str, Any]:
        return self._request("GET", "/api/health", opener=opener)

    def upsert_dashboard(
        self,
        dashboard: Dict[str, Any],
        message: str = "updated by grafana-slo-forge",
        opener: HttpOpener = urllib.request.urlopen,
    ) -> Dict[str, Any]:
        envelope: Dict[str, Any] = {
            "dashboard": dashboard,
            "overwrite": True,
            "message": message,
        }
        if self.folder_uid:
            envelope["folderUid"] = self.folder_uid
        return self._request("POST", "/api/dashboards/db", body=envelope, opener=opener)
