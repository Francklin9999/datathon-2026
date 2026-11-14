"""Checksums and version labels shared by ingestion and readers (no ingestion code here)."""

from __future__ import annotations

import hashlib
import re

# schemas.md §1 DataVersion: "snap-" + YYYYMMDD + "-" + label.
VERSION_RE = re.compile(r"^snap-(\d{8})-[a-z0-9][a-z0-9-]{0,40}$")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(data: bytes) -> str:
    """SHA-256 of the content with CRLF normalized to LF.

    Git stores the organizer CSVs with LF; Windows checkouts with ``core.autocrlf`` write CRLF.
    Hashing the LF form makes the manifest identical on every machine and equal to the hash of
    the Git-stored file. The exact local byte hash is recorded too.
    """
    return sha256_hex(data.replace(b"\r\n", b"\n"))
