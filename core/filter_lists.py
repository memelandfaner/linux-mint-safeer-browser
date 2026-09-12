"""Safeer filter lists for Linux: EasyList as a WebKit content blocker.

The agent keeps EasyList on disk, refreshes it on its own thread (conditional GET: an unchanged list costs one
small request) and converts it with core/webkit_filters.py into the JSON that WebKitUserContentFilterStore
compiles into a filter. The filter blocks ad requests inside WebKit's network layer, before any JavaScript
runs and without a Python round trip per request. Real banks (the BankGuard catalogue) are excluded by a
final allow rule, so their pages are never touched.

Nothing here touches GTK or WebKit: the browser receives the JSON through a callback and does the WebKit
part on the main loop. A failed download or a rejected list keeps the previous filter.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import webkit_filters

EASYLIST_URL = "https://easylist.to/easylist/easylist.txt"
FILTER_ID = "safeer-easylist"
FIRST_UPDATE_DELAY_SECONDS = 20
UPDATE_INTERVAL_SECONDS = 6 * 3600
RETRY_SECONDS = 30 * 60
MAX_BYTES = 16 * 1024 * 1024
MIN_RULES = 1000
USER_AGENT = "Safeer"
_LOG_PREFIX = "[FilterLists]"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ListRejected(Exception):
    pass


def check_list(data: bytes) -> list[str]:
    """Lines of an EasyList download; error pages and captive portals are refused."""
    if len(data) > MAX_BYTES:
        raise ListRejected("list too large")
    head = data[:4096].decode("utf-8", "replace").lower()
    if "<html" in head or "<!doctype" in head:
        raise ListRejected("HTML instead of a list")
    if "easylist" not in head and "adblock" not in head:
        raise ListRejected("marker missing")
    lines = data.decode("utf-8", "replace").splitlines()
    rules = [line for line in lines if line.strip() and not line.startswith("!") and not line.startswith("[")]
    if len(rules) < MIN_RULES:
        raise ListRejected(f"only {len(rules)} rules")
    return lines


def default_fetch(url: str, etag: str, last_modified: str):
    """Conditional GET. Returns (status, body, etag, last_modified); status 304 = unchanged."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
    if etag:
        request.add_header("If-None-Match", etag)
    if last_modified:
        request.add_header("If-Modified-Since", last_modified)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https URL
            if response.geturl().split(":", 1)[0].lower() != "https":
                raise ListRejected("redirected away from HTTPS")
            body = response.read(MAX_BYTES + 1)
            return response.status, body, response.headers.get("ETag", ""), response.headers.get("Last-Modified", "")
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return 304, b"", etag, last_modified
        raise


class FilterListAgent:
    """Downloads EasyList, converts it and hands the content blocker JSON to `on_rules(json_text, source)`."""

    def __init__(self, data_dir, on_rules, never_block_domains=(), fetch=default_fetch, url: str = EASYLIST_URL,
                 first_delay: float = FIRST_UPDATE_DELAY_SECONDS, interval: float = UPDATE_INTERVAL_SECONDS,
                 retry: float = RETRY_SECONDS):
        self.data_dir = Path(data_dir)
        self.on_rules = on_rules
        self.never_block_domains = tuple(never_block_domains)
        self.fetch = fetch
        self.url = url
        self.first_delay = first_delay
        self.interval = interval
        self.retry = retry
        self._stop = threading.Event()
        self._thread = None
        self.last_error = ""
        self.rule_count = 0
        self.list_sha256 = ""
        self.fetched_at = 0.0
        self.loaded = threading.Event()

    # -- files -----------------------------------------------------------------------------------
    @property
    def list_path(self) -> Path:
        return self.data_dir / "easylist.txt"

    @property
    def meta_path(self) -> Path:
        return self.data_dir / "easylist.meta.json"

    def _read_meta(self) -> dict:
        try:
            meta = json.loads(self.meta_path.read_text("utf-8"))
            return meta if isinstance(meta, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, data: bytes, etag: str, last_modified: str) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.list_path.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, self.list_path)
        meta = {"sha256": _sha256(data), "etag": etag, "last_modified": last_modified, "fetched_at": time.time(), "url": self.url}
        tmp = self.meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta), "utf-8")
        os.replace(tmp, self.meta_path)

    # -- lifecycle -------------------------------------------------------------------------------
    def start(self) -> bool:
        if self._thread is not None:
            return False
        self._thread = threading.Thread(target=self._run, name="safeer-filter-lists", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            self.load_saved()
        except Exception as exc:  # noqa: BLE001 - a broken cache must never break start-up
            self.last_error = f"{exc.__class__.__name__}: {exc}"
        finally:
            self.loaded.set()
        if self._stop.wait(self.first_delay):
            return
        while not self._stop.is_set():
            self.update_now()
            delay = self.interval if not self.last_error else self.retry
            if self._stop.wait(delay * random.uniform(0.9, 1.1)):
                return

    # -- work ------------------------------------------------------------------------------------
    def load_saved(self) -> bool:
        """The list saved by an earlier run (checked against its SHA-256) is converted and delivered."""
        meta = self._read_meta()
        if not meta or not self.list_path.is_file():
            return False
        data = self.list_path.read_bytes()
        if _sha256(data) != meta.get("sha256"):
            raise ListRejected("saved list is damaged")
        self._deliver(data, "saved")
        self.fetched_at = float(meta.get("fetched_at") or 0)
        return True

    def update_now(self) -> bool:
        """Checks for a newer list; returns True when a new list was installed."""
        meta = self._read_meta()
        try:
            status, body, etag, last_modified = self.fetch(self.url, meta.get("etag", ""), meta.get("last_modified", ""))
            if status == 304:
                self.last_error = ""
                return False
            if status != 200:
                raise ListRejected(f"HTTP status {status}")
            check_list(body)
            self._deliver(body, "download")
            self._write(body, etag or "", last_modified or "")
            self.fetched_at = time.time()
            self.last_error = ""
            return True
        except Exception as exc:  # noqa: BLE001 - keep the previous list on any error
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def _deliver(self, data: bytes, source: str) -> None:
        lines = check_list(data)
        rules = webkit_filters.convert(lines, never_block_domains=self.never_block_domains)
        self.rule_count = len(rules)
        self.list_sha256 = _sha256(data)
        self.on_rules(webkit_filters.to_json(rules), source)

    def status(self) -> dict:
        return {"rules": self.rule_count, "fetched_at": self.fetched_at, "last_error": self.last_error, "sha256": self.list_sha256[:16]}
