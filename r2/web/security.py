"""
What stops a web page in another tab, or a DNS rebinding attack, from
driving the daemon through the user's own browser.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from http.cookies import CookieError, SimpleCookie
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ["DEFAULT_HOSTNAMES", "TOKEN_COOKIE", "OriginGuard", "presented_token"]

TOKEN_COOKIE = "r2_token"
DEFAULT_HOSTNAMES = ("127.0.0.1", "localhost", "[::1]")

SECURITY_HEADERS = [
    (b"x-frame-options", b"DENY"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
]


class OriginGuard:
    """
    Refuse any request that did not come from the daemon's own origin.

    The `Host` check defeats DNS rebinding: a name that resolves to 127.0.0.1
    but is not a loopback name gets no further. The `Origin` check stops a
    page open in another tab. Both apply to every route, the UI included,
    because the UI is where the cookie lives.
    """

    def __init__(self, app: ASGIApp, hostnames: Iterable[str] = DEFAULT_HOSTNAMES):
        self.app = app
        self.allowed = frozenset(hostnames)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        host = headers.get("host")
        if host is not None and _hostname(host) not in self.allowed:
            await PlainTextResponse("bad host\n", 403)(scope, receive, send)
            return
        origin = headers.get("origin")
        if origin not in (None, "", "null") and not self._own(origin or ""):
            await PlainTextResponse("bad origin\n", 403)(scope, receive, send)
            return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *SECURITY_HEADERS]
            await send(message)

        await self.app(scope, receive, with_headers)

    def _own(self, origin: str) -> bool:
        try:
            host = urlsplit(origin).hostname
        except ValueError:
            return False
        if host is not None and ":" in host:
            host = f"[{host}]"
        return host in self.allowed


def presented_token(authorization: str | None, cookie: str | None) -> str | None:
    """The token from a bearer header, or from the cookie `/auth` set."""
    if authorization is not None and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    if cookie is None:
        return None
    try:
        jar = SimpleCookie(cookie)
    except CookieError:
        return None
    morsel = jar.get(TOKEN_COOKIE)
    return morsel.value if morsel is not None else None


def same_token(presented: str | None, token: str) -> bool:
    return presented is not None and secrets.compare_digest(presented, token)


def _hostname(host: str) -> str:
    if host.startswith("["):
        end = host.find("]")
        return host if end == -1 else host[: end + 1]
    return host.rsplit(":", 1)[0] if ":" in host else host
