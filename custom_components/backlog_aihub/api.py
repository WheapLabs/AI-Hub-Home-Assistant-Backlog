"""Small HTTP client for the AI Hub Backlog service (``/backlog-api``).

This module only depends on aiohttp, so it can be tested without Home Assistant.

The hub keeps the one and only copy of the Backlog. Every call carries the
hub's Backlog token as a Bearer token. The routes used here:

* ``GET  /sante``       health check, no token needed → ``{"ok": true}``
* ``GET  /historique``  saved copies (small; used to check the token)
* ``GET  /donnees``     the whole document ``{"rev", "quand", "data"}``; answers
  304 to ``If-None-Match: "<rev>"`` when nothing changed
* ``POST /service``     ``{"action": "<name>", "donnees": {...}}`` →
  ``{"rev": n, "reponse": ...}``; the same actions as the ``aihub-backlog``
  command line (exporter, ajouter_tache, ajouter_journal, cocher, repondre,
  verifie, decision_traitee, supprimer)
"""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

API_PREFIX = "/backlog-api"
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


class BacklogError(Exception):
    """Base error of the client."""


class CannotConnect(BacklogError):
    """The hub did not answer (offline, network, TLS certificate, not a Backlog service)."""


class InvalidAuth(BacklogError):
    """The hub refused the token (HTTP 401)."""


class Refused(BacklogError):
    """The hub refused the action (bad field, unknown item…): its message is meant for the user."""

    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def normalize_url(url: str) -> str:
    """Return the Backlog API base URL.

    Accepts the hub's address (``https://hub.example``) or the API address
    (``https://hub.example/backlog-api``); a trailing slash is ignored.
    Raises ValueError when it is not an http(s) URL.
    """
    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("not an http(s) URL")
    path = parts.path.rstrip("/")
    if not path:
        path = API_PREFIX
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


@dataclass
class Snapshot:
    """The document read with GET /donnees."""

    rev: int
    data: dict[str, Any]


class BacklogClient:
    """Talks to one hub."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        token: str,
        ssl_context: ssl.SSLContext | bool | None = None,
    ) -> None:
        self._session = session
        self._url = normalize_url(url)
        self._headers = {"Authorization": f"Bearer {token}"}
        # None = aiohttp's default verification, False = no verification, or a context with the hub's CA.
        self._ssl = ssl_context
        self._etag: str | None = None
        self._snapshot: Snapshot | None = None

    @property
    def url(self) -> str:
        return self._url

    async def _request(
        self, method: str, path: str, *, auth: bool = True, **kwargs: Any
    ) -> tuple[int, bytes, Any]:
        headers = dict(self._headers) if auth else {}
        headers.update(kwargs.pop("headers", {}))
        extra: dict[str, Any] = {}
        if self._ssl is not None:
            extra["ssl"] = self._ssl
        try:
            async with self._session.request(
                method, self._url + path, headers=headers, timeout=TIMEOUT, **extra, **kwargs
            ) as resp:
                return resp.status, await resp.read(), resp.headers
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise CannotConnect(f"{type(err).__name__}: {err}"[:300]) from err

    @staticmethod
    def _json(body: bytes) -> Any:
        try:
            return json.loads(body or b"null")
        except ValueError as err:
            raise CannotConnect("the answer is not JSON (is this the Backlog API address?)") from err

    def _check(self, status: int, body: bytes) -> Any:
        if status == 401:
            raise InvalidAuth("the hub refused the token")
        payload = self._json(body)
        if status == 200:
            return payload
        message = payload.get("erreur") if isinstance(payload, dict) else None
        code = payload.get("code") if isinstance(payload, dict) else None
        if (400 <= status < 500 and status != 404) or code == "not_found":
            raise Refused(status, message or f"HTTP {status}", code)
        raise CannotConnect(f"HTTP {status}" + (f": {message}" if message else ""))

    async def health(self) -> bool:
        """GET /sante (no token)."""
        status, body, _ = await self._request("GET", "/sante", auth=False)
        if status != 200:
            raise CannotConnect(f"HTTP {status} on /sante (is this the Backlog API address?)")
        payload = self._json(body)
        if not (isinstance(payload, dict) and payload.get("ok") is True):
            raise CannotConnect("unexpected answer on /sante (is this the Backlog API address?)")
        return True

    async def validate(self) -> None:
        """Checks the address and the token, as done when the integration is added."""
        await self.health()
        status, body, _ = await self._request("GET", "/historique")
        self._check(status, body)

    async def service(self, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST /service → {"rev": n, "reponse": ...}."""
        status, body, _ = await self._request(
            "POST", "/service", json={"action": action, "donnees": data or {}}
        )
        payload = self._check(status, body)
        if not isinstance(payload, dict) or "rev" not in payload:
            raise CannotConnect("unexpected answer from /service")
        return payload

    async def snapshot(self) -> Snapshot:
        """GET /donnees, reusing the previous copy when the hub answers 304 (nothing changed)."""
        headers = {"If-None-Match": self._etag} if self._etag and self._snapshot else {}
        status, body, resp_headers = await self._request("GET", "/donnees", headers=headers)
        if status == 304 and self._snapshot is not None:
            return self._snapshot
        payload = self._check(status, body)
        if not isinstance(payload, dict) or "rev" not in payload:
            raise CannotConnect("unexpected answer from /donnees")
        self._snapshot = Snapshot(int(payload["rev"]), payload.get("data") or {})
        self._etag = resp_headers.get("ETag")
        return self._snapshot
