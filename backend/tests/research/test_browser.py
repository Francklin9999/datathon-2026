"""web.browse through AgentCore Browser: capture rules, session lifecycle, protocol pieces (no network)."""
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from aplomb.ledger import Ledger
from aplomb.research import ResearchContext, ResearchError, ResearchService, research_tool_handlers
from aplomb.research.browser import (
    BROWSER_IDENTIFIER,
    CDP,
    AgentCoreBrowser,
    BrowserPage,
    RenderedPage,
    WebSocket,
    accept_key,
    browse,
    encode_frame,
    signed_stream_headers,
    task_passages,
    task_terms,
)
from botocore.credentials import Credentials

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
CTX = ResearchContext("RUN-browse", NOW.date())
BOC = "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/"
TEXT = ("The Bank of Canada sets the policy interest rate eight times a year. "
        "On October 29, 2026 the Bank held its target for the overnight rate at 2.25%.")


def dns(host, port, **kwargs):
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def page(url, text=TEXT, links=(), final=None, status=200, title="Policy interest rate", content_type="text/html"):
    # The markup names the address, as real pages differ: identical markup is one document.
    html = f"<html><head><link rel=canonical href='{final or url}'></head><body>{text}</body></html>"
    return RenderedPage(final or url, status, content_type, title, text, html, tuple(links))


class FakeBrowser:
    """Stands in for AgentCoreBrowser: renders from a table, counts sessions."""

    def __init__(self, pages):
        self.pages, self.sessions, self.rendered = pages, 0, []

    @contextmanager
    def session(self, deadline):
        self.sessions += 1
        outer = self

        class Page:
            def render(self, url, deadline):
                outer.rendered.append(url)
                if url not in outer.pages:
                    raise ResearchError("navigation_failed")
                return outer.pages[url]
        yield Page()


def service():
    return ResearchService(None, lambda: NOW, resolver=dns)


def run(svc, browser, task="policy interest rate overnight", start=BOC, max_pages=5, ctx=CTX):
    return browse(svc, browser, task, start, max_pages, ctx, time.monotonic() + 30)


def test_browse_captures_allowlisted_pages_as_run_documents_and_follows_task_links():
    rates = "https://www.bankofcanada.ca/rates/interest-rates/"
    browser = FakeBrowser({
        BOC: page(BOC, links=[(rates, "Interest rates"), ("https://www.bankofcanada.ca/careers/", "Careers"),
                              ("https://evil.example.com/rate", "policy rate"), ("http://www.bankofcanada.ca/rate", "rate")]),
        rates: page(rates, text="Overnight rate target: 2.25%. Policy rate history.", title="Interest rates"),
    })
    svc = service()
    data = run(svc, browser)
    assert [p["url"] for p in data["pages"]] == [BOC, rates]
    assert browser.rendered == [BOC, rates]  # careers (no task word), off-list host and http never opened
    assert data["browser"] == BROWSER_IDENTIFIER and data["stopped"] == "no_relevant_links"
    assert "interest rate" in data["pages"][0]["passages"][0]["text"]
    # A browsed page is a document of the run: a verbatim quote from it can be saved and verified.
    ledger = Ledger(CTX.run_id, str(CTX.as_of), clock=lambda: NOW.isoformat().replace("+00:00", "Z"))
    evidence = dict(type="official_release", title="Policy interest rate", publisher="Bank of Canada", url=BOC,
                    quote="held its target for the overnight rate at 2.25%",
                    claim={"en": "Policy rate held", "fr": "Taux directeur maintenu"}, subject={"type": "country", "id": "CAN"})
    eid = svc.save_evidence(evidence, data["pages"][0]["document_ref"], CTX, ledger)
    assert ledger.get_evidence(eid).verification.status == "verified"
    assert ledger.get_evidence(eid).publisher == "Bank of Canada"


def test_start_url_must_be_allowlisted_https_and_is_checked_before_any_session():
    browser = FakeBrowser({})
    for url in ("https://evil.example.com/", "http://www.bankofcanada.ca/", "https://www.bankofcanada.ca.evil.test/", None):
        with pytest.raises(ResearchError):
            run(service(), browser, start=url)
    assert browser.sessions == 0


def test_replay_never_opens_a_browser():
    browser = FakeBrowser({BOC: page(BOC)})
    with pytest.raises(ResearchError, match="replay"):
        run(service(), browser, ctx=ResearchContext("RUN-old", NOW.date(), mode="replay"))
    assert browser.sessions == 0


def test_a_page_that_redirects_off_the_allowlist_is_not_captured():
    browser = FakeBrowser({BOC: page(BOC, final="https://tracker.example.net/landing")})
    svc = service()
    with pytest.raises(ResearchError, match="left_allowlisted_domains"):
        run(svc, browser)
    assert not svc.documents


def test_error_pages_and_downloads_are_skipped():
    other = "https://www.bankofcanada.ca/rates/policy-rate.pdf"
    browser = FakeBrowser({BOC: page(BOC, links=[(other, "policy rate pdf")]),
                           other: page(other, content_type="application/pdf")})
    data = run(service(), browser)
    assert [p["url"] for p in data["pages"]] == [BOC]
    assert data["skipped"] == [{"url": other, "reason": "unsupported_content_type"}]
    with pytest.raises(ResearchError, match="http_404"):
        run(service(), FakeBrowser({BOC: page(BOC, status=404)}))


def test_max_pages_and_cache_reuse_without_a_new_session():
    links = [(f"https://www.bankofcanada.ca/rates/{i}/", f"policy rate {i}") for i in range(8)]
    pages = {BOC: page(BOC, links=links), **{url: page(url) for url, _ in links}}
    browser, svc = FakeBrowser(pages), service()
    data = run(svc, browser, max_pages=3)
    assert len(data["pages"]) == 3 and data["stopped"] == "max_pages"
    assert browser.sessions == 1
    again = run(svc, browser, max_pages=3)
    assert browser.sessions == 1  # every page came from the cache: no browser opened
    assert all(p["from_cache"] for p in again["pages"])


def test_site_name_words_do_not_choose_links():
    fed = "https://www.federalreserve.gov/monetarypolicy/openmarket.htm"
    target = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    browser = FakeBrowser({
        fed: page(fed, links=[("https://www.federalreserve.gov/aboutthefed.htm", "About the Federal Reserve"), (target, "FOMC meeting calendars")]),
        target: page(target),
    })
    data = run(service(), browser, task="federal funds rate FOMC meeting", start=fed)
    assert [p["url"] for p in data["pages"]] == [fed, target]


def test_task_terms_and_passages():
    assert task_terms("Find the latest policy rate decision of the Bank, 2.25%") == ["policy", "rate", "decision", "bank", "2.25%"]
    passages = task_passages("x " * 1000 + TEXT + " y" * 1000, ["overnight", "rate"])
    assert passages and "overnight rate" in passages[0]["text"]
    assert passages[0]["offset_ref"].startswith("normalized:")


def test_tool_exists_only_with_a_browser():
    svc = service()
    assert "web.browse" not in research_tool_handlers(svc)
    handlers = research_tool_handlers(svc, browser=FakeBrowser({BOC: page(BOC)}))
    schema, function = handlers["web.browse"]
    ctx = SimpleNamespace(run_id=CTX.run_id, as_of=str(CTX.as_of), historical=False, research_context=CTX, ledger=None,
                          limits=SimpleNamespace(remaining=lambda reserve=0: 30))
    result = function(ctx, **schema(task="policy rate", start_url=BOC).model_dump())
    assert result.ok and result.data["pages"][0]["url"] == BOC
    refused = function(ctx, **schema(task="policy rate", start_url="https://evil.example.com/").model_dump())
    assert not refused.ok and refused.error == "domain_not_allowlisted"


# ----- protocol pieces ------------------------------------------------------------------------

class FakeSocket:
    def __init__(self, incoming=b""):
        self.incoming, self.sent, self.closed = bytearray(incoming), bytearray(), False

    def settimeout(self, value):
        pass

    def recv(self, size):
        chunk = bytes(self.incoming[:size])
        del self.incoming[:size]
        return chunk

    def sendall(self, data):
        self.sent += data

    def close(self):
        self.closed = True


def server_frame(payload: bytes, opcode=0x1, fin=True):
    size = len(payload)
    head = bytes([(0x80 if fin else 0) | opcode])
    if size < 126:
        head += bytes([size])
    elif size < 65536:
        head += bytes([126]) + size.to_bytes(2, "big")
    else:
        head += bytes([127]) + size.to_bytes(8, "big")
    return head + payload


def unmask(frame: bytes) -> bytes:
    size = frame[1] & 0x7F
    offset = 2
    if size == 126:
        size, offset = int.from_bytes(frame[2:4], "big"), 4
    elif size == 127:
        size, offset = int.from_bytes(frame[2:10], "big"), 10
    mask = frame[offset:offset + 4]
    return bytes(b ^ mask[i % 4] for i, b in enumerate(frame[offset + 4:offset + 4 + size]))


def test_websocket_frames_masking_fragments_and_ping():
    assert accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="  # RFC 6455, section 1.3
    for size in (5, 300, 70000):
        frame = encode_frame(b"a" * size, mask=b"\x01\x02\x03\x04")
        assert frame[1] & 0x80 and unmask(frame) == b"a" * size
    big = "x" * 70000
    sock = FakeSocket(server_frame(b"ping!", 0x9) + server_frame(b'{"id": 1, ', 0x1, fin=False)
                      + server_frame(b'"result": {}}', 0x0) + server_frame(big.encode()))
    ws = WebSocket(sock)
    assert json.loads(ws.recv_text(time.monotonic() + 5)) == {"id": 1, "result": {}}
    assert unmask(bytes(sock.sent)) == b"ping!" and sock.sent[0] == 0x8A  # pong answered
    assert ws.recv_text(time.monotonic() + 5) == big
    with pytest.raises(ResearchError, match="closed"):
        WebSocket(FakeSocket(server_frame(b"", 0x8))).recv_text(time.monotonic() + 5)
    with pytest.raises(ResearchError, match="timeout"):
        WebSocket(FakeSocket()).recv_text(time.monotonic() - 1)


def test_stream_headers_are_sigv4_signed_for_bedrock_agentcore():
    endpoint = "wss://bedrock-agentcore.us-east-1.amazonaws.com/browser-streams/aws.browser.v1/sessions/ABC123/automation"
    headers = signed_stream_headers(endpoint, Credentials("AKIDEXAMPLE", "secret", "token-1"), "us-east-1")
    assert headers["Host"] == "bedrock-agentcore.us-east-1.amazonaws.com"
    day = headers["X-Amz-Date"][:8]
    assert len(headers["X-Amz-Date"]) == 16 and headers["X-Amz-Date"].endswith("Z")
    assert f"Credential=AKIDEXAMPLE/{day}/us-east-1/bedrock-agentcore/aws4_request" in headers["Authorization"]
    assert "x-amz-security-token" in headers["Authorization"] and headers["X-Amz-Security-Token"] == "token-1"


class ScriptedWS:
    """CDP peer: answers each command from a function of (method, params)."""

    def __init__(self, answer):
        self.answer, self.sent, self.queue = answer, [], []

    def send_text(self, text):
        message = json.loads(text)
        self.sent.append(message)
        self.queue.append(json.dumps({"method": "Page.frameNavigated", "params": {}}))  # an event first
        self.queue.append(json.dumps({"id": message["id"], "result": self.answer(message["method"], message["params"])}))

    def recv_text(self, deadline):
        return self.queue.pop(0)

    def close(self):
        pass


def test_page_render_navigates_waits_and_reads_once():
    states = iter(["loading", "complete"])

    def answer(method, params):
        if method == "Target.createTarget":
            return {"targetId": "T1"}
        if method == "Target.attachToTarget":
            return {"sessionId": "S1"}
        if method == "Page.navigate":
            return {"frameId": "F1"}
        if method == "Runtime.evaluate":
            if params["expression"] == "document.readyState":
                return {"result": {"value": next(states)}}
            return {"result": {"value": json.dumps({"href": BOC, "title": "Rate", "contentType": "text/html", "status": 200,
                                                     "text": TEXT, "html": "<html></html>", "links": [[BOC + "x/", "rate"]]})}}
        return {}

    ws = ScriptedWS(answer)
    page_ = BrowserPage(CDP(ws), time.monotonic() + 10, sleep=lambda s: None)
    rendered = page_.render(BOC, time.monotonic() + 10)
    assert rendered.url == BOC and rendered.status == 200 and rendered.links == ((BOC + "x/", "rate"),)
    assert [m["method"] for m in ws.sent] == ["Target.createTarget", "Target.attachToTarget", "Page.navigate",
                                              "Runtime.evaluate", "Runtime.evaluate", "Runtime.evaluate"]
    assert all(m.get("sessionId") == "S1" for m in ws.sent[2:])


class FakeAgentCore:
    def __init__(self, fail_start=None):
        self.fail_start, self.calls = fail_start, []

    def start_browser_session(self, **kw):
        self.calls.append(("start", kw))
        if self.fail_start:
            raise self.fail_start
        return {"sessionId": "SESSION1", "streams": {"automationStream": {
            "streamEndpoint": "wss://bedrock-agentcore.us-east-1.amazonaws.com/browser-streams/aws.browser.v1/sessions/SESSION1/automation",
            "streamStatus": "ENABLED"}}}

    def stop_browser_session(self, **kw):
        self.calls.append(("stop", kw))


def test_session_is_always_stopped_and_access_errors_are_named():
    from botocore.exceptions import ClientError

    client = FakeAgentCore()

    def refuse(url, headers, deadline):
        assert "Authorization" in headers
        raise ResearchError("browser_access_denied")

    browser = AgentCoreBrowser("us-east-1", client=client, credentials=Credentials("AKID", "secret"), connect=refuse)
    with pytest.raises(ResearchError, match="access_denied"):
        with browser.session(time.monotonic() + 5):
            pass
    assert [c[0] for c in client.calls] == ["start", "stop"]
    assert client.calls[0][1]["browserIdentifier"] == BROWSER_IDENTIFIER
    assert client.calls[1][1] == {"browserIdentifier": BROWSER_IDENTIFIER, "sessionId": "SESSION1"}

    denied = FakeAgentCore(ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "StartBrowserSession"))
    with pytest.raises(ResearchError, match="browser_access_denied"):
        with AgentCoreBrowser("us-east-1", client=denied, credentials=Credentials("AKID", "secret")).session(time.monotonic() + 5):
            pass
    assert [c[0] for c in denied.calls] == ["start"]


def test_two_links_to_one_page_capture_it_once():
    target = "https://www.bankofcanada.ca/rates/policy/"
    variant = target + "?utm=x"
    browser = FakeBrowser({BOC: page(BOC, links=[(target, "policy rate"), (variant, "policy rate (again)")]),
                           target: page(target, text="Policy rate page"), variant: page(variant, final=target, text="Policy rate page")})
    data = run(service(), browser)
    assert [p["url"] for p in data["pages"]] == [BOC, target]
    assert data["skipped"] == [{"url": variant, "reason": "duplicate_page"}]
