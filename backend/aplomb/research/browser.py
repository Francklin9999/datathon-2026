"""Open-web reading through Amazon Bedrock AgentCore Browser (`web.browse`, flag `research_open_web`).

A managed Chrome runs in an AgentCore session; it is driven over the Chrome DevTools Protocol (CDP)
on the session's automation stream, a WebSocket signed with SigV4 (service ``bedrock-agentcore``).
The WebSocket client is a small standard-library one with an absolute deadline on every read, like
``PublicHTTP``: no extra dependency in the Lambda package.

The browser renders pages (JavaScript included) but the capture rules are those of ``web.fetch``:
HTTPS only, exact allow-listed domains for the start page, every followed link and every final URL
after redirects; rendered text is untrusted data; each captured page becomes a document of the run,
so ``research.save_evidence`` can verify a quote against it. A session is opened per call, never
logged in, and always stopped. Links are followed only when their text or address names a term of
the task: the browser reads, it does not wander.

API references: StartBrowserSession / StopBrowserSession (bedrock-agentcore data plane) and the
Chrome DevTools Protocol (Target, Page, Runtime domains).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import socket
import ssl
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Callable, Iterator
from urllib.parse import urldefrag, urlsplit, urlunsplit

from .core import (
    FetchedDocument,
    ResearchContext,
    ResearchError,
    normalize,
    policy_for,
    validate_url,
)

log = logging.getLogger(__name__)

BROWSER_IDENTIFIER = "aws.browser.v1"
SESSION_TIMEOUT_SECONDS = 120
VIEWPORT = {"width": 1280, "height": 1600}
MAX_MESSAGE_BYTES = 16_000_000
MAX_HTML_CHARS = 4_000_000
MAX_LINKS = 400
PAGE_SECONDS = 12
SETTLE_SECONDS = 0.6
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _left(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise ResearchError("browser_timeout")
    return left


# ----------------------------------------------------------------------------------------------
# WebSocket (RFC 6455), client side only
# ----------------------------------------------------------------------------------------------

def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def encode_frame(payload: bytes, opcode: int = 0x1, mask: bytes | None = None) -> bytes:
    """One final, masked client frame (clients must mask every frame)."""
    mask = mask if mask is not None else os.urandom(4)
    size = len(payload)
    header = bytearray([0x80 | opcode])
    if size < 126:
        header.append(0x80 | size)
    elif size < 65536:
        header.append(0x80 | 126)
        header += size.to_bytes(2, "big")
    else:
        header.append(0x80 | 127)
        header += size.to_bytes(8, "big")
    header += mask
    if size:
        key = (mask * (size // 4 + 1))[:size]
        payload = (int.from_bytes(payload, "big") ^ int.from_bytes(key, "big")).to_bytes(size, "big")
    return bytes(header) + payload


class WebSocket:
    """Blocking client over a connected socket; every read honours the caller's deadline."""

    def __init__(self, sock, initial: bytes = b""):
        self.sock, self.buffer = sock, bytearray(initial)

    @classmethod
    def connect(cls, url: str, headers: dict[str, str], deadline: float) -> "WebSocket":
        parsed = urlsplit(url)
        if parsed.scheme != "wss" or not parsed.hostname:
            raise ResearchError("browser_stream_unavailable")
        host, port = parsed.hostname, parsed.port or 443
        raw = socket.create_connection((host, port), timeout=_left(deadline))
        try:
            raw.settimeout(_left(deadline))
            sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        except Exception:
            raw.close()
            raise
        key = base64.b64encode(os.urandom(16)).decode()
        path = (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
        lines = [f"GET {path} HTTP/1.1", "Upgrade: websocket", "Connection: Upgrade",
                 f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13"]
        reserved = {"upgrade", "connection", "sec-websocket-key", "sec-websocket-version"}
        lines += [f"{name}: {value}" for name, value in headers.items() if name.lower() not in reserved]
        try:
            sock.settimeout(_left(deadline))
            sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
            response = bytearray()
            while b"\r\n\r\n" not in response:
                sock.settimeout(_left(deadline))
                chunk = sock.recv(4096)
                if not chunk or len(response) > 65536:
                    raise ResearchError("browser_stream_unavailable")
                response += chunk
            head, _, rest = bytes(response).partition(b"\r\n\r\n")
            status, *header_lines = head.decode("latin-1").split("\r\n")
            received = {k.strip().lower(): v.strip() for k, _, v in (line.partition(":") for line in header_lines)}
            if not status.startswith("HTTP/1.1 101"):
                code = status.split(" ")[1] if " " in status else "?"
                raise ResearchError("browser_access_denied" if code in {"401", "403"} else "browser_stream_unavailable")
            if received.get("sec-websocket-accept") != accept_key(key):
                raise ResearchError("browser_stream_unavailable")
        except Exception:
            sock.close()
            raise
        return cls(sock, rest)

    def _read(self, size: int, deadline: float) -> bytes:
        while len(self.buffer) < size:
            self.sock.settimeout(_left(deadline))
            try:
                chunk = self.sock.recv(65536)
            except (socket.timeout, TimeoutError) as exc:
                raise ResearchError("browser_timeout") from exc
            if not chunk:
                raise ResearchError("browser_stream_closed")
            self.buffer += chunk
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    def send_text(self, text: str) -> None:
        self.sock.sendall(encode_frame(text.encode()))

    def recv_text(self, deadline: float) -> str:
        """Next complete text message; answers pings, rejects close and oversized messages."""
        message, opcode = bytearray(), None
        while True:
            first, second = self._read(2, deadline)
            fin, code = bool(first & 0x80), first & 0x0F
            size = second & 0x7F
            if size == 126:
                size = int.from_bytes(self._read(2, deadline), "big")
            elif size == 127:
                size = int.from_bytes(self._read(8, deadline), "big")
            mask = self._read(4, deadline) if second & 0x80 else None
            if size > MAX_MESSAGE_BYTES or len(message) + size > MAX_MESSAGE_BYTES:
                raise ResearchError("browser_message_too_large")
            payload = self._read(size, deadline) if size else b""
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if code == 0x9:  # ping
                self.sock.sendall(encode_frame(payload, 0xA))
                continue
            if code == 0xA:  # pong
                continue
            if code == 0x8:  # close
                raise ResearchError("browser_stream_closed")
            if code in (0x1, 0x2):
                message, opcode = bytearray(payload), code
            elif code == 0x0 and opcode is not None:
                message += payload
            else:
                raise ResearchError("browser_protocol_error")
            if fin:
                return message.decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self.sock.sendall(encode_frame(b"", 0x8))
        except OSError:
            pass
        finally:
            self.sock.close()


# ----------------------------------------------------------------------------------------------
# Chrome DevTools Protocol over the automation stream
# ----------------------------------------------------------------------------------------------

class CDP:
    def __init__(self, ws):
        self.ws, self.next_id = ws, 0

    def call(self, method: str, params: dict | None, deadline: float, session: str | None = None) -> dict:
        self.next_id += 1
        message = {"id": self.next_id, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        self.ws.send_text(json.dumps(message))
        while True:
            try:
                reply = json.loads(self.ws.recv_text(deadline))
            except ValueError as exc:
                raise ResearchError("browser_protocol_error") from exc
            if reply.get("id") != self.next_id:
                continue  # events and stale replies: navigation is checked by polling instead
            if "error" in reply:
                raise ResearchError("browser_protocol_error")
            return reply.get("result") or {}


@dataclass(frozen=True)
class RenderedPage:
    url: str
    status: int
    content_type: str
    title: str
    text: str
    html: str
    links: tuple[tuple[str, str], ...] = field(default_factory=tuple)


# Read the rendered page once, as data. Nothing on the page is executed by us beyond this read.
EXTRACT = """JSON.stringify((() => {
  const nav = (performance.getEntriesByType('navigation') || [])[0] || {};
  const body = document.body;
  const main = document.querySelector('main, [role="main"], article');
  const mainText = main ? main.innerText : '';
  return {
    href: location.href, title: document.title || '', contentType: document.contentType || '',
    status: nav.responseStatus || 0, text: mainText.length >= 200 ? mainText : (body ? body.innerText : ''),
    html: document.documentElement ? document.documentElement.outerHTML.slice(0, %d) : '',
    links: Array.from(document.links).slice(0, %d)
      .map(a => [a.href, (a.innerText || a.title || a.getAttribute('aria-label') || '').trim().slice(0, 200)])
  };
})())""" % (MAX_HTML_CHARS, MAX_LINKS)


class BrowserPage:
    """One tab in the session, reused for each page of a browse."""

    def __init__(self, cdp: CDP, deadline: float, sleep: Callable[[float], None] = time.sleep):
        self.cdp, self.sleep = cdp, sleep
        self.target = cdp.call("Target.createTarget", {"url": "about:blank"}, deadline)["targetId"]
        self.session = cdp.call("Target.attachToTarget", {"targetId": self.target, "flatten": True}, deadline)["sessionId"]

    def _eval(self, expression: str, deadline: float):
        result = self.cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, deadline, self.session)
        if result.get("exceptionDetails"):
            raise ResearchError("browser_protocol_error")
        return (result.get("result") or {}).get("value")

    def render(self, url: str, deadline: float) -> RenderedPage:
        deadline = min(deadline, time.monotonic() + PAGE_SECONDS)
        navigation = self.cdp.call("Page.navigate", {"url": url}, deadline, self.session)
        if navigation.get("errorText"):
            raise ResearchError("navigation_failed")
        while self._eval("document.readyState", deadline) != "complete":
            self.sleep(min(0.25, _left(deadline)))
        # Let client-side rendering settle a moment, within the page budget.
        self.sleep(min(SETTLE_SECONDS, max(0.0, deadline - time.monotonic() - 1)))
        raw = self._eval(EXTRACT, deadline)
        try:
            data = json.loads(raw)
            links = tuple((str(href), str(text)) for href, text in data.get("links", [])[:MAX_LINKS])
            return RenderedPage(str(data["href"]), int(data.get("status") or 0), str(data.get("contentType") or ""),
                                str(data.get("title") or "")[:300], str(data.get("text") or ""),
                                str(data.get("html") or "")[:MAX_HTML_CHARS], links)
        except (TypeError, ValueError, KeyError) as exc:
            raise ResearchError("browser_protocol_error") from exc

    def close(self, deadline: float) -> None:
        try:
            self.cdp.call("Target.closeTarget", {"targetId": self.target}, deadline)
        except ResearchError:
            pass


# ----------------------------------------------------------------------------------------------
# AgentCore session
# ----------------------------------------------------------------------------------------------

def signed_stream_headers(endpoint: str, credentials, region: str) -> dict[str, str]:
    """SigV4 headers for the automation stream's WebSocket upgrade (a GET on the same path)."""
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    parsed = urlsplit(endpoint)
    https = urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
    request = AWSRequest(method="GET", url=https, headers={"host": parsed.netloc})
    SigV4Auth(credentials, "bedrock-agentcore", region).add_auth(request)
    headers = {"Host": parsed.netloc, "X-Amz-Date": request.headers["X-Amz-Date"],
               "Authorization": request.headers["Authorization"], "User-Agent": "aplomb-research/1.0"}
    if request.headers.get("X-Amz-Security-Token"):
        headers["X-Amz-Security-Token"] = request.headers["X-Amz-Security-Token"]
    return headers


class AgentCoreBrowser:
    """Opens, drives and always stops one AgentCore Browser session per ``web.browse`` call."""

    def __init__(self, region: str, *, client=None, credentials=None,
                 connect: Callable[[str, dict, float], WebSocket] = WebSocket.connect,
                 sleep: Callable[[float], None] = time.sleep):
        self.region, self._client, self._credentials = region, client, credentials
        self.connect, self.sleep = connect, sleep

    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client("bedrock-agentcore", region_name=self.region, config=Config(
                connect_timeout=5, read_timeout=10, retries={"max_attempts": 2, "mode": "standard"}))
        return self._client

    def credentials(self):
        if self._credentials is not None:
            return self._credentials
        import boto3

        credentials = boto3.Session().get_credentials()
        if credentials is None:
            raise ResearchError("browser_access_denied")
        return credentials.get_frozen_credentials()

    @contextmanager
    def session(self, deadline: float) -> Iterator[BrowserPage]:
        from botocore.exceptions import BotoCoreError, ClientError

        client = self.client()
        try:
            started = client.start_browser_session(
                browserIdentifier=BROWSER_IDENTIFIER, name=f"aplomb-{uuid.uuid4().hex[:12]}",
                sessionTimeoutSeconds=SESSION_TIMEOUT_SECONDS, viewPort=VIEWPORT)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            raise ResearchError("browser_access_denied" if code == "AccessDeniedException" else "browser_unavailable") from exc
        except BotoCoreError as exc:
            raise ResearchError("browser_unavailable") from exc
        session_id = started["sessionId"]
        try:
            endpoint = started["streams"]["automationStream"]["streamEndpoint"]
            ws = self.connect(endpoint, signed_stream_headers(endpoint, self.credentials(), self.region), deadline)
            try:
                page = BrowserPage(CDP(ws), deadline, self.sleep)
                try:
                    yield page
                finally:
                    page.close(time.monotonic() + 2)
            finally:
                ws.close()
        finally:
            try:
                client.stop_browser_session(browserIdentifier=BROWSER_IDENTIFIER, sessionId=session_id)
            except Exception:  # the session also expires on its own after SESSION_TIMEOUT_SECONDS
                log.warning("AgentCore browser session %s could not be stopped", session_id)


# ----------------------------------------------------------------------------------------------
# Browse: capture allow-listed pages as run documents
# ----------------------------------------------------------------------------------------------

STOPWORDS = {
    "about", "after", "also", "and", "are", "before", "between", "find", "for", "from", "have", "into",
    "latest", "look", "more", "most", "page", "pages", "read", "recent", "show", "that", "their", "them",
    "then", "there", "these", "this", "what", "when", "where", "which", "with", "within", "would",
    "dans", "des", "les", "pour", "sur", "une", "avec", "plus", "dernier", "derniere", "trouver",
}


def task_terms(task: str) -> list[str]:
    terms: list[str] = []
    for word in re.findall(r"[\w%.-]+", task.casefold()):
        word = word.strip(".-")
        if (len(word) >= 4 or any(c.isdigit() for c in word)) and word not in STOPWORDS and word not in terms:
            terms.append(word)
    return terms[:10]


def task_passages(text: str, terms: list[str], window: int = 1200, count: int = 2) -> list[dict]:
    """Windows of the normalized text holding the most task terms, with offsets into that text."""
    norm = normalize(text)
    folded = norm.casefold()
    hits = sorted(match.start() for term in terms for match in re.finditer(re.escape(term), folded))[:500]
    chosen: list[tuple[int, int]] = []
    for _ in range(count):
        best, best_score = None, 0
        for position in hits:
            start = max(0, position - 150)
            if any(start < end and start + window > begin for begin, end in chosen):
                continue
            segment = folded[start:start + window]
            score = sum(1 for term in terms if term in segment)
            if score > best_score:
                best, best_score = start, score
        if best is None:
            break
        chosen.append((best, min(len(norm), best + window)))
    return [{"text": norm[a:b], "offset_ref": f"normalized:{a}:{b}"} for a, b in sorted(chosen)]


def allowed_link(href: str) -> str | None:
    url, _ = urldefrag(href)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        return None
    try:
        policy_for(parsed.hostname)
    except ResearchError:
        return None
    return url


@dataclass
class _Lazy:
    """Opens the browser session only when a page is not already cached."""
    browser: AgentCoreBrowser
    deadline: float
    page: BrowserPage | None = None
    stack: object = None

    def get(self) -> BrowserPage:
        if self.page is None:
            self.stack = self.browser.session(self.deadline)
            self.page = self.stack.__enter__()
        return self.page

    def close(self):
        if self.stack is not None:
            self.stack.__exit__(None, None, None)


def browse(service, browser: AgentCoreBrowser, task: str, start_url: str | None, max_pages: int,
           context: ResearchContext, deadline: float) -> dict:
    """Render the start page and up to ``max_pages - 1`` linked allow-listed pages that name the task."""
    context.allow()  # before cache, DNS or any session
    if not start_url:
        raise ResearchError("start_url_required")
    validate_url(start_url, service.resolver)
    terms = task_terms(task)
    # Words of the site's own name ("federal", "canada") are on every link: they do not choose one.
    host = (urlsplit(start_url).hostname or "").casefold()
    link_terms = [term for term in terms if term not in host] or terms
    queue, seen = [start_url], {start_url}
    pages, skipped, stopped = [], [], "max_pages"
    lazy = _Lazy(browser, deadline)
    try:
        while queue and len(pages) < max_pages:
            if deadline - time.monotonic() < 3:
                stopped = "time_budget"
                break
            url = queue.pop(0)
            key = ("browse-v1", url, service.clock().date(), context.as_of, context.mode, context.data_version)
            cached = service.cache.get(key)
            if cached is not None:
                document, links, title = cached
                document = replace(document, run_id=context.run_id, from_cache=True)
            else:
                try:
                    rendered = lazy.get().render(url, deadline)
                except ResearchError as exc:
                    if not pages and str(exc) in {"browser_access_denied", "browser_unavailable", "browser_stream_unavailable"}:
                        raise
                    skipped.append({"url": url, "reason": str(exc)})
                    continue
                final = allowed_link(rendered.url)
                if final is None:
                    skipped.append({"url": url, "reason": "left_allowlisted_domains"})
                    continue
                if rendered.status not in (0, 200):
                    skipped.append({"url": url, "reason": f"http_{rendered.status}"})
                    continue
                if rendered.content_type and rendered.content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                    skipped.append({"url": url, "reason": "unsupported_content_type"})
                    continue
                digest = hashlib.sha256(rendered.html.encode("utf-8", errors="replace")).hexdigest()
                redirects = (final,) if final != url else ()
                document = FetchedDocument("DOC-" + digest, context.run_id, final, redirects, 200, "text/html",
                                           digest, rendered.text, service.clock(), availability="rendered_browser")
                links, title = tuple(rendered.links), rendered.title
                service.cache[key] = (document, links, title)
            # Same lookups as web.fetch: research.save_evidence finds the page by URL or reference.
            for lookup in {url, document.canonical_url, document.document_id}:
                service.documents[(context.run_id, lookup)] = document
            # Two links can lead to one page (a redirect, a query string): it is read once.
            if any(p["url"] == document.canonical_url or p["document_ref"] == document.document_id for p in pages):
                skipped.append({"url": url, "reason": "duplicate_page"})
                continue
            seen.add(document.canonical_url)
            pages.append({
                "document_ref": document.document_id, "url": document.canonical_url, "title": title,
                "retrieved_at": document.retrieved_at.isoformat(), "from_cache": document.from_cache,
                "content_hash": document.content_hash, "published_at": None,
                "passages": task_passages(document.text, terms) if terms else [],
            })
            scored, listed = [], set()
            for href, text in links:
                target = allowed_link(href)
                if target is None or target in seen or target in listed:
                    continue
                listed.add(target)
                haystack = f"{text} {urlsplit(target).path}".casefold()
                score = sum(1 for term in link_terms if term in haystack)
                if score:
                    scored.append((-score, len(scored), target))
            for _, _, target in sorted(scored)[: max(0, max_pages - len(pages) - len(queue))]:
                seen.add(target)
                queue.append(target)
        else:
            if len(pages) < max_pages:
                stopped = "no_relevant_links"
    finally:
        lazy.close()
    if not pages:
        raise ResearchError(skipped[0]["reason"] if skipped else "no_page_captured")
    return {"task": task, "pages": pages, "skipped": skipped, "stopped": stopped, "browser": BROWSER_IDENTIFIER,
            "source_warning": "Untrusted rendered page text; claims require saved verified quotes"}
