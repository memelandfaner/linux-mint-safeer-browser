"""Safeer signed threat feed for the desktop browsers (Linux and Windows).

An additional protection layer next to the built-in threat list in core/adblock.py: the browser
periodically downloads the Ed25519-signed bundle published by Safeer Threat Intelligence
(https://github.com/memelandfaner/safeer-threat-intel), verifies it with core/signed_feed.py and
matches requests locally. Nothing about browsing is ever sent: the only requests are anonymous GETs
of two public files. Every failure keeps the last verified bundle; without any bundle the built-in
list still works exactly as before.
"""

from __future__ import annotations

import importlib.util
import os
import random
import sys
import threading
import time
from pathlib import Path

# Public keys trusted to sign feed manifests: key_id -> base64 Ed25519 public key.
# Empty until the production key is generated on the Safeer worker; with no trusted key the
# signed feed stays disabled and only the built-in protection is used.
TRUSTED_KEYS: dict = {}

BASE_URLS = ("https://intel.safeer.si",)
UPDATE_INTERVAL_SECONDS = 6 * 3600
RETRY_SECONDS = 3600
FIRST_UPDATE_DELAY_SECONDS = 30


def _load_feed_module():
    module = sys.modules.get("safeer_signed_feed")
    if module is not None:
        return module
    path = Path(__file__).with_name("signed_feed.py")
    spec = importlib.util.spec_from_file_location("safeer_signed_feed", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["safeer_signed_feed"] = module
    spec.loader.exec_module(module)
    return module


def default_data_dir(app_dir_name: str) -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / app_dir_name / "threat-intel"


class ThreatIntelService:
    def __init__(self, data_dir, trusted_keys=None, base_urls=BASE_URLS, fetch=None,
                 interval=UPDATE_INTERVAL_SECONDS, retry=RETRY_SECONDS, first_delay=FIRST_UPDATE_DELAY_SECONDS):
        self.feed = _load_feed_module()
        self.trusted_keys = dict(TRUSTED_KEYS if trusted_keys is None else trusted_keys)
        self.store = self.feed.SignedFeedStore(data_dir, "threats", self.trusted_keys, base_urls, fetch=fetch)
        self.interval = interval
        self.retry = retry
        self.first_delay = first_delay
        self._stop = threading.Event()
        self._thread = None
        self.last_check = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.trusted_keys)

    def start(self) -> bool:
        """Loads the stored bundle and starts background updates. Returns False when disabled."""
        if not self.enabled or self._thread is not None:
            return False
        try:
            self.store.load()
        except Exception:  # noqa: BLE001 - a broken cache must never break start-up
            pass
        self._thread = threading.Thread(target=self._run, name="safeer-threat-intel", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def update_now(self) -> bool:
        if not self.enabled:
            return False
        self.last_check = time.time()
        try:
            return self.store.update()
        except Exception as exc:  # noqa: BLE001 - keep the verified bundle on any unexpected error
            self.store.last_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def _run(self) -> None:
        if self._stop.wait(self.first_delay):
            return
        while not self._stop.is_set():
            self.update_now()
            delay = self.interval if not self.store.last_error else self.retry
            if self._stop.wait(delay * random.uniform(0.9, 1.1)):  # jitter spreads load, nothing more
                return

    def match(self, url_or_host: str):
        """Returns the threat category for a URL or host name, or None."""
        if not self.enabled or not url_or_host:
            return None
        try:
            if "://" in url_or_host:
                return self.store.match_url(url_or_host)
            return self.store.match_host(url_or_host.split("/", 1)[0].split(":", 1)[0])
        except Exception:  # noqa: BLE001 - matching must never break navigation
            return None

    def status(self) -> dict:
        bundle = self.store.bundle
        return {
            "enabled": self.enabled,
            "version": bundle.manifest.version if bundle else 0,
            "rules": len(bundle.rules) if bundle else 0,
            "expires_at": bundle.manifest.expires_at.strftime("%Y-%m-%dT%H:%M:%SZ") if bundle else "",
            "last_error": self.store.last_error,
        }
