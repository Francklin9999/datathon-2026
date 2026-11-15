"""Small bounded transport; fixed provider endpoints, retries, rate limits and byte caps."""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

HOSTS = frozenset({
    "api.weather.gov", "aviationweather.gov", "www.federalregister.gov",
    "raw.githubusercontent.com", "services9.arcgis.com", "ucdpapi.pcr.uu.se",
    "www.gdacs.org", "ghoapi.azureedge.net", "ec.europa.eu", "power.larc.nasa.gov",
})


class _RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.port:
            raise ValueError("Provider redirected outside allowlist")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Transport:
    def __init__(self, *, timeout: float = 25, max_bytes: int = 20_000_000, retries: int = 2, interval: float = 0.5):
        self.timeout, self.max_bytes, self.retries, self.interval = timeout, max_bytes, retries, interval
        self._last = {}

    def __call__(self, url: str) -> bytes:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.port:
            raise ValueError("Provider URL is not allowlisted")
        for attempt in range(self.retries + 1):
            time.sleep(max(0, self.interval - (time.monotonic() - self._last.get(parsed.hostname, 0))))
            self._last[parsed.hostname] = time.monotonic()
            request = urllib.request.Request(url, headers={
                "User-Agent": "AplombDatathon/1.0 (bounded public research ingestion)",
                "Accept": "application/json,text/csv,application/xml",
            })
            try:
                opener = urllib.request.build_opener(_RestrictedRedirect())
                with opener.open(request, timeout=self.timeout) as response:
                    if urlsplit(response.url).hostname not in HOSTS:
                        raise ValueError("Provider redirected outside allowlist")
                    chunks, size, started = [], 0, time.monotonic()
                    while True:
                        chunk = response.read(min(65536, self.max_bytes + 1 - size))
                        if not chunk:
                            return b"".join(chunks)
                        size += len(chunk)
                        if size > self.max_bytes:
                            raise ValueError("Provider payload exceeds byte cap")
                        chunks.append(chunk)
                        if time.monotonic() - started > self.timeout:
                            raise TimeoutError("Provider total read deadline exceeded")
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    raise
                time.sleep(min(8, 2 ** attempt))
            except (TimeoutError, urllib.error.URLError):
                if attempt == self.retries:
                    raise
                time.sleep(min(8, 2 ** attempt))
        raise RuntimeError("Provider retry exhausted")
