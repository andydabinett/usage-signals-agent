"""The one polite HTTP client used by every ingest module (D11).

- Honest User-Agent with repo URL + CONTACT_EMAIL. Never spoofs a browser UA, never retries a 403 with other headers.
- robots.txt: an RFC 9309 longest-match matcher with `*`/`$` wildcards and percent-decoding decides allow/deny
  (urllib.robotparser is first-match and ignores wildcards, so it is only used for Crawl-delay).
  robots.txt fetch semantics follow RFC 9309: 2xx parse, 4xx => allow all, 5xx/network error => disallow all.
- Per-host rate limit (config/sources.yaml; robots Crawl-delay honoured if larger).
- Retries 429 / 5xx up to 3 times with backoff (Retry-After respected).
- Hard denylist: *.figma.com and *.linkedin.com raise ForbiddenHost before any I/O (Figma AUP §j, LinkedIn ToS).
- Every allowed response is stored in raw_pulls (body capped at 2 MB, email addresses redacted to [email]).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import time
import urllib.robotparser
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from . import REPO_URL, __version__
from .config import load_yaml

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAX_BODY = 2 * 1024 * 1024
UA_TOKEN = "usage-signals-agent"


class ForbiddenHost(RuntimeError):
    pass


class RobotsDisallowed(RuntimeError):
    pass


def redact(text: str) -> str:
    return EMAIL_RE.sub("[email]", text)


def user_agent(contact_email: str | None = None) -> str:
    email = contact_email if contact_email is not None else os.environ.get("CONTACT_EMAIL", "")
    return f"{UA_TOKEN}/{__version__.rsplit('.', 1)[0]} (+{REPO_URL}; {email})"


def is_denied(host: str, denylist: list[str]) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in denylist)


# ---------- robots ----------
def _rule_regex(path: str) -> re.Pattern:
    path = unquote(path)
    anchored = path.endswith("$")
    if anchored:
        path = path[:-1]
    rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in path)
    return re.compile("^" + rx + ("$" if anchored else ""))


@dataclass
class Robots:
    allow_all: bool = False
    disallow_all: bool = False
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow?, pattern)
    crawl_delay: float | None = None
    std: urllib.robotparser.RobotFileParser | None = None

    @classmethod
    def parse(cls, text: str) -> "Robots":
        groups: list[tuple[list[str], list[tuple[str, str]]]] = []
        agents: list[str] = []
        lines: list[tuple[str, str]] = []
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "user-agent":
                if not last_was_agent and agents:
                    groups.append((agents, lines))
                    agents, lines = [], []
                agents.append(v.lower())
                last_was_agent = True
            else:
                if agents:
                    lines.append((k, v))
                last_was_agent = False
        if agents:
            groups.append((agents, lines))
        chosen = None
        for ag, ln in groups:
            if any(a == UA_TOKEN for a in ag):
                chosen = ln
        if chosen is None:
            for ag, ln in groups:
                if "*" in ag:
                    chosen = (chosen or []) + ln
        r = cls()
        for k, v in chosen or []:
            if k in ("allow", "disallow") and v:
                r.rules.append((k == "allow", v))
            elif k == "crawl-delay":
                try:
                    r.crawl_delay = float(v)
                except ValueError:
                    pass
        std = urllib.robotparser.RobotFileParser()
        std.parse(text.splitlines())
        r.std = std
        return r

    def wildcard_allowed(self, path: str) -> bool:
        best: tuple[int, bool] | None = None
        for allow, pat in self.rules:
            if _rule_regex(pat).match(path):
                cand = (len(pat), allow)
                if best is None or cand[0] > best[0] or (cand[0] == best[0] and allow):
                    best = cand
        return True if best is None else best[1]

    def allowed(self, url: str, ua: str = UA_TOKEN) -> bool:
        if self.allow_all:
            return True
        if self.disallow_all:
            return False
        parts = urlsplit(url)
        path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        return self.wildcard_allowed(unquote(path))


# ---------- client ----------
class PoliteClient:
    def __init__(
        self,
        wh: Any | None = None,
        contact_email: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        host_delays: dict[str, float] | None = None,
        default_delay: float | None = None,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        log: Callable[[str], None] | None = None,
    ):
        cfg = load_yaml("sources.yaml")
        self.denylist = [d.lower() for d in cfg["denylist"]]
        self.default_delay = cfg["default_delay"] if default_delay is None else default_delay
        self.host_delays = dict(cfg.get("host_delays") or {})
        if host_delays:
            self.host_delays.update(host_delays)
        self.ua = user_agent(contact_email)
        self.http = httpx.Client(
            headers={"User-Agent": self.ua, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"},
            timeout=30.0, follow_redirects=False, transport=transport,
        )
        self.wh = wh
        self.sleep, self.clock = sleep, clock
        self.max_retries, self.backoff_base = max_retries, backoff_base
        self._robots: dict[str, Robots] = {}
        self._last: dict[str, float] = {}
        self.counts: Counter = Counter()
        self.robots_skips: list[str] = []
        self.errors: list[str] = []
        self.request_log: list[tuple[str, float]] = []  # (url, clock) for tests
        self.log = log or (lambda m: None)

    # rate limit
    def _delay_for(self, host: str) -> float:
        d = self.host_delays.get(host, self.default_delay)
        rb = self._robots.get(host)
        if rb and rb.crawl_delay:
            d = max(d, rb.crawl_delay)
        return d

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            gap = self._delay_for(host) - (self.clock() - last)
            if gap > 0:
                self.sleep(gap)
        self._last[host] = self.clock()

    def _ua_for(self, host: str) -> str | None:
        # SEC fair-access policy documents "Name email" as the declared UA format; supplied via env only (never committed)
        if (host == "sec.gov" or host.endswith(".sec.gov")) and os.environ.get("SEC_USER_AGENT"):
            return os.environ["SEC_USER_AGENT"]
        return None

    def _send(self, method: str, url: str, **kw) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        if (ua := self._ua_for(host)):
            kw.setdefault("headers", {})["User-Agent"] = ua
        self._wait(host)
        self.request_log.append((url, self.clock()))
        self.counts[host] += 1
        return self.http.request(method, url, **kw)

    def robots_for(self, url: str) -> Robots:
        parts = urlsplit(url)
        host = parts.hostname or ""
        if host not in self._robots:
            robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
            try:
                resp = self._send("GET", robots_url)
                if 200 <= resp.status_code < 300:
                    rb = Robots.parse(resp.text)
                elif 300 <= resp.status_code < 500:
                    rb = Robots(allow_all=True)  # RFC 9309 §2.3.1.3 (unavailable)
                else:
                    rb = Robots(disallow_all=True)  # RFC 9309 §2.3.1.4 (unreachable)
            except httpx.HTTPError:
                rb = Robots(disallow_all=True)
            self._robots[host] = rb
        return self._robots[host]

    def check(self, url: str) -> None:
        host = urlsplit(url).hostname or ""
        if is_denied(host, self.denylist):
            raise ForbiddenHost(f"{host} is on the hard denylist (Figma AUP / LinkedIn ToS): {url}")
        if not self.robots_for(url).allowed(url):
            self.robots_skips.append(url)
            self.log(f"robots disallow, skipped: {url}")
            raise RobotsDisallowed(url)

    def _store(self, source: str, url: str, resp: httpx.Response) -> None:
        if self.wh is None:
            return
        body = redact(resp.text[:MAX_BODY]) if resp.content else ""
        self.wh.execute("DELETE FROM raw_pulls WHERE source = %(s)s AND url = %(u)s", {"s": source, "u": url})
        self.wh.load_rows("raw_pulls", [{
            "source": source, "url": url, "fetched_at": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            "status": resp.status_code, "content_type": resp.headers.get("content-type", ""), "body": body,
            "sha256": hashlib.sha256(resp.content or b"").hexdigest(),
        }])

    def get(self, url: str, source: str = "misc", params: dict | None = None, max_redirects: int = 5) -> httpx.Response | None:
        """Returns the response (any status) or None if robots-disallowed. Raises ForbiddenHost for denylisted hosts."""
        if params:
            url = str(httpx.URL(url, params=params))
        for _ in range(max_redirects + 1):
            try:
                self.check(url)
            except RobotsDisallowed:
                return None
            resp = self._get_with_retry(url)
            if resp is None:
                return None
            if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                url = urljoin(url, resp.headers["location"])
                continue
            self._store(source, url, resp)
            if resp.status_code >= 400:
                self.errors.append(f"{resp.status_code} {url}")
            return resp
        self.errors.append(f"too many redirects {url}")
        return None

    def _get_with_retry(self, url: str) -> httpx.Response | None:
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._send("GET", url)
            except httpx.HTTPError as e:
                if attempt == self.max_retries:
                    self.errors.append(f"network {url}: {type(e).__name__}")
                    return None
                self.sleep(self.backoff_base * (2 ** attempt))
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self.max_retries:
                    return resp
                ra = resp.headers.get("retry-after")
                host = urlsplit(url).hostname or ""
                wait = float(ra) if ra and ra.isdigit() else max(self.backoff_base, self._delay_for(host)) * (2 ** attempt)
                self.sleep(min(wait, 120.0))
                continue
            return resp  # includes 403: recorded, never retried with different headers
        return None

    def summary(self) -> dict:
        return {"requests_per_host": dict(self.counts), "robots_skips": list(self.robots_skips), "errors": list(self.errors)}
