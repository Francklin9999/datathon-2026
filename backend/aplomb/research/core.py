"""Bounded public-source capture. Remote content is data, never instructions."""
from __future__ import annotations

import hashlib
import http.client
import io
import ipaddress
import json
import queue
import socket
import ssl
import threading
import time
from dataclasses import dataclass, replace
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlsplit


class ResearchError(ValueError):
    pass


@dataclass(frozen=True)
class ResearchContext:
    run_id: str
    as_of: date
    mode: str = "decision"
    # Callers pass the run's pinned snapshot. This fallback only satisfies the DataVersion wire
    # pattern for a context built without one; it names no snapshot.
    data_version: str = "snap-00000000-unpinned"

    def allow(self):
        if self.mode == "replay":
            raise ResearchError("research_unavailable_in_replay")


@dataclass(frozen=True)
class DomainPolicy:
    domain: str
    publisher: str
    tier: int
    rationale: str
    reference: str
    licence: str = "Terms apply; redistribution not established"


POLICIES = tuple(DomainPolicy(*row) for row in [
    ("eonet.gsfc.nasa.gov", "NASA EONET", 1, "Curated natural event metadata, not official event extents", "https://eonet.gsfc.nasa.gov/what-is-eonet", "EONET metadata: visualization and general information only; spatial and temporal extents approximate; linked source rights separate"),
    ("www.bankofcanada.ca", "Bank of Canada", 1, "Official monetary policy releases", "https://www.bankofcanada.ca/terms/", "Bank of Canada website terms; attribution required; third-party exceptions apply"),
    ("www.federalreserve.gov", "Federal Reserve Board", 1, "Official monetary policy releases", "https://www.federalreserve.gov/disclaimer.htm", "Federal Reserve Board website disclaimer; third-party rights may apply"),
    ("www.statcan.gc.ca", "Statistics Canada", 1, "Official statistical releases", "https://www.statcan.gc.ca/en/terms-conditions/open-licence", "Statistics Canada Open Licence; required source and adaptation notices; third-party exceptions apply"),
    ("www150.statcan.gc.ca", "Statistics Canada", 1, "Official statistical releases", "https://www.statcan.gc.ca/en/terms-conditions/open-licence", "Statistics Canada Open Licence; required source and adaptation notices; third-party exceptions apply"),
    ("www.sec.gov", "SEC", 1, "Official US securities regulator", "https://www.sec.gov/about/developer-resources"),
    ("data.sec.gov", "SEC", 1, "Official EDGAR API", "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"),
    ("wikimedia.org", "Wikimedia", 1, "Official page-view counts only", "https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html", "CC0 1.0 (analytics data)"),
    ("www.ishares.com", "iShares", 1, "Issuer holdings", "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf"),
    ("api.gdeltproject.org", "GDELT", 3, "Discovery index; not underlying article verification", "https://www.gdeltproject.org/"),
])


def policy_for(host: str) -> DomainPolicy:
    host = host.lower().rstrip(".")
    for policy in POLICIES:
        if host == policy.domain:  # exact registry; no implicit trust of subdomains
            return policy
    raise ResearchError("domain_not_allowlisted")


def allowed_link(href: str) -> str | None:
    """``href`` without its fragment when it is an https URL on an allow-listed host, else None."""
    url, _ = urldefrag(href)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        return None
    try:
        policy_for(parsed.hostname)
    except ResearchError:
        return None
    return url


def bounded_resolve(host, port, **kwargs):
    output = queue.Queue(maxsize=1)
    def resolve():
        try:
            output.put(socket.getaddrinfo(host, port, **kwargs))
        except Exception as exc:
            output.put(exc)
    threading.Thread(target=resolve, daemon=True).start()
    try:
        result = output.get(timeout=2)
    except queue.Empty as exc:
        raise ResearchError("dns_timeout") from exc
    if isinstance(result, Exception):
        raise ResearchError("dns_unavailable") from result
    return result


def validate_url(url: str, resolve: Callable = bounded_resolve):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment):
        raise ResearchError("unsafe_url")
    policy_for(parsed.hostname)
    addresses = {item[4][0] for item in resolve(parsed.hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ResearchError("non_public_target")
    return parsed, sorted(addresses)


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


class DeadlineReader(io.RawIOBase):
    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline

    def close(self):
        self.sock.close()
        super().close()

    def readable(self):
        return True

    def readinto(self, buffer):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ResearchError("request_timeout")
        self.sock.settimeout(remaining)
        return self.sock.recv_into(buffer)


class DeadlineSocket:
    """Enforce the same deadline on every header/body read, including slow drip headers."""
    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline
        self.reader = None

    def makefile(self, mode):
        self.reader = io.BufferedReader(DeadlineReader(self.sock, self.deadline))
        return self.reader

    def sendall(self, data):
        self.sock.settimeout(max(.01, self.deadline - time.monotonic()))
        return self.sock.sendall(data)

    def close(self):
        if self.reader is None or self.reader.closed:
            self.sock.close()

    def settimeout(self, value):
        self.sock.settimeout(value)


def contact_user_agent(user_agent: str | None) -> bool:
    """Public sources need a descriptive user agent naming a contact (an https URL or an email)."""
    return bool(user_agent) and len(user_agent) >= 15 and any(c in user_agent for c in ("@", "https://"))


class PublicHTTP:
    """No proxies/cookies/auth; DNS checked once and connection pinned with TLS hostname."""
    def __init__(self, user_agent: str, timeout: float = 12, max_bytes: int = 4_000_000):
        if not contact_user_agent(user_agent):
            raise ValueError("descriptive contact user-agent required")
        self.user_agent, self.timeout, self.max_bytes = user_agent, min(timeout, 15), max_bytes

    def get(self, url: str, *, timeout: float | None = None) -> Response:
        started = time.monotonic()
        parsed, addresses = validate_url(url)
        budget = min(timeout or self.timeout, self.timeout)
        deadline = started + budget
        if time.monotonic() >= deadline:
            raise ResearchError("request_timeout")
        # Connect to validated numeric address; SNI and certificate validate original hostname.
        raw = socket.create_connection((addresses[0], 443), timeout=max(.01, deadline - time.monotonic()))
        connection = http.client.HTTPConnection(parsed.hostname, timeout=budget)
        response = None
        try:
            raw.settimeout(max(.01, deadline - time.monotonic()))
            tls = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
            connection.sock = DeadlineSocket(tls, deadline)
            connection.sock.settimeout(max(.01, deadline - time.monotonic()))
            connection.request("GET", parsed.path + ("?" + parsed.query if parsed.query else ""), headers={
                "Host": parsed.hostname, "User-Agent": self.user_agent,
                "Accept": "application/json,text/html,text/plain,text/csv", "Accept-Encoding": "identity",
            })
            response = connection.getresponse()
            headers = {k.lower(): v for k, v in response.getheaders()}
            if headers.get("content-encoding", "identity") != "identity":
                raise ResearchError("unsupported_encoding")
            if int(headers.get("content-length", "0")) > self.max_bytes:
                raise ResearchError("response_too_large")
            end = deadline
            parts, size = [], 0
            while True:
                if time.monotonic() >= end:
                    raise ResearchError("request_timeout")
                chunk = response.read1(min(65536, self.max_bytes + 1 - size))
                if not chunk:
                    break
                parts.append(chunk)
                size += len(chunk)
                if size > self.max_bytes:
                    raise ResearchError("response_too_large")
            return Response(response.status, headers, b"".join(parts))
        finally:
            if response is not None:
                response.close()
            connection.close()
            raw.close()


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def normalize(text: str) -> str:
    return " ".join(text.split())


@dataclass(frozen=True)
class FetchedDocument:
    document_id: str
    run_id: str
    canonical_url: str
    redirects: tuple[str, ...]
    status: int
    content_type: str
    content_hash: str
    text: str
    retrieved_at: datetime
    published_at: date | None = None
    from_cache: bool = False
    availability: str = "retrieved_only"

    @property
    def text_hash(self):
        return hashlib.sha256(self.text.encode()).hexdigest()


@dataclass(frozen=True)
class QuoteCheck:
    ok: bool
    start: int | None
    end: int | None
    normalized_quote: str
    reason: str


def verify_quote(document: FetchedDocument, quote: str) -> QuoteCheck:
    normalized = normalize(quote)
    start = normalize(document.text).find(normalized)
    ok = bool(normalized) and len(quote) <= 400 and start >= 0
    return QuoteCheck(ok, start if ok else None, start + len(normalized) if ok else None,
                      normalized, "normalized_text_offsets" if ok else "quote_not_verified")


class ResearchService:
    def __init__(self, transport, clock: Callable[[], datetime], cache=None, documents=None,
                 resolver=bounded_resolve, sleep=time.sleep):
        self.transport, self.clock = transport, clock
        self.cache = cache if cache is not None else {}
        self.documents = documents if documents is not None else {}
        self.resolver, self.sleep = resolver, sleep

    def fetch(self, url: str, context: ResearchContext) -> FetchedDocument:
        context.allow()  # before cache, DNS, or transport
        key = ("fetch-v1", url, self.clock().date(), context.as_of, context.mode, context.data_version)
        if key in self.cache:
            document = replace(self.cache[key], run_id=context.run_id, from_cache=True)
        else:
            original, redirects = url, []
            deadline = time.monotonic() + 18
            for hop in range(4):
                validate_url(url, self.resolver)
                try:
                    response = self.transport.get(url, timeout=max(.01, deadline - time.monotonic()))
                except (TimeoutError, socket.timeout) as exc:
                    raise ResearchError("request_timeout") from exc
                except OSError as exc:
                    raise ResearchError("source_unavailable") from exc
                if response.status in (429, 503):
                    wait = response.headers.get("retry-after", "0")
                    delay = float(wait) if wait.isdecimal() else 0
                    if hop == 0 and 0 < delay <= 2 and time.monotonic() + delay < deadline:
                        self.sleep(delay)
                        continue
                    raise ResearchError("rate_limited")
                if response.status in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get("location", ""))
                    redirects.append(url)
                    continue
                if response.status != 200:
                    raise ResearchError("source_unavailable")
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if content_type not in {"application/json", "text/html", "text/plain", "text/csv", "application/xml", "text/xml", "application/rss+xml", "application/atom+xml"}:
                    raise ResearchError("unsupported_content_type")
                if len(response.body) > 4_000_000:
                    raise ResearchError("response_too_large")
                text = response.body.decode("utf-8-sig", errors="replace")
                if content_type == "text/html":
                    parser = TextParser()
                    parser.feed(text)
                    text = " ".join(parser.parts)
                digest = hashlib.sha256(response.body).hexdigest()
                document = FetchedDocument("DOC-" + digest, context.run_id, url, tuple(redirects),
                                           200, content_type, digest, text, self.clock())
                self.cache[key] = document
                break
            else:
                raise ResearchError("redirect_or_retry_limit")
            if time.monotonic() > deadline:
                raise ResearchError("request_timeout")
        self.documents[(context.run_id, document.document_id)] = document
        # Requested URL retained only as lookup; saved evidence always uses canonical URL.
        self.documents[(context.run_id, url)] = document
        self.documents[(context.run_id, document.canonical_url)] = document
        if not document.from_cache:
            self.documents[(context.run_id, original)] = document
        return document

    def json(self, url, context):
        document = self.fetch(url, context)
        try:
            return json.loads(document.text), document
        except (ValueError, TypeError) as exc:
            raise ResearchError("invalid_source_json") from exc

    def save_evidence(self, input: dict, document_ref: str, context: ResearchContext, ledger):
        from aplomb.ledger import DocumentRef
        context.allow()
        document = self.documents.get((context.run_id, document_ref))
        if document is None:
            raise ResearchError("document_not_fetched_in_run")
        if input.get("url") != document.canonical_url:
            raise ResearchError("document_url_mismatch")
        if not input.get("quote") or not verify_quote(document, input["quote"]).ok:
            raise ResearchError("quote_not_verified")
        policy = policy_for(urlsplit(document.canonical_url).hostname)
        evidence = {**input, "tier": policy.tier, "publisher": policy.publisher,
                    "retrieved_at": document.retrieved_at.isoformat().replace("+00:00", "Z"), "published_at": str(document.published_at) if document.published_at else None,
                    "document_ref": document.document_id, "lang": "en", "tool": "research.save_evidence",
                    "licence": policy.licence, "verification": {"status": "unverified", "checks": []}}
        return ledger.add_evidence(evidence, DocumentRef(document.document_id, document.text,
                                                        document.canonical_url, context.run_id))
