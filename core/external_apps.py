#!/usr/bin/env python3
"""
Links that open another installed program instead of a web page, for example the return to the
Claude desktop app after signing in (claude://...), mailto:, zoommtg:// or steam://.

Safeer never loads these itself. The browser asks the user first ("claude.ai wants to open
Claude"), can remember the answer for that site and program, and hands the link to the program
registered in the desktop (x-scheme-handler/<scheme>). Web addresses, local files, script and
data URLs and the browser's own pages are never handed to another program.
"""

import re
import time
import urllib.parse

# Never passed to another program.
BLOCKED_SCHEMES = frozenset({
    "http", "https", "ws", "wss", "ftp", "file", "javascript", "vbscript", "data", "blob",
    "about", "filesystem", "view-source", "safeer", "resource", "chrome", "webkit", "jar",
})

MAX_LINK_LENGTH = 16384
MAX_REMEMBERED_SITES = 200
# After the user declines, the same site cannot ask again for this program for a while.
DECLINE_QUIET_SECONDS = 60.0

_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]{0,31}):")


def external_scheme(uri):
    """Returns the lower-case scheme when the link belongs to another program, otherwise None."""
    if not isinstance(uri, str) or not uri or len(uri) > MAX_LINK_LENGTH:
        return None
    if any(ch in uri for ch in "\r\n\t\0") or uri != uri.strip():
        return None
    match = _SCHEME.match(uri)
    if not match:
        return None
    scheme = match.group(1).lower()
    if scheme in BLOCKED_SCHEMES or len(uri) <= len(scheme) + 1:
        return None
    return scheme


def site_of(page_uri):
    """Host of the web page that asked; empty for Safeer's own pages."""
    try:
        parsed = urllib.parse.urlsplit(page_uri or "")
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https"):
        return ""
    return (parsed.hostname or "").rstrip(".").lower()


def is_allowed(permissions, site, scheme):
    """True when the user chose "always allow" for this site and program."""
    if not site or not isinstance(permissions, dict):
        return False
    schemes = permissions.get(site)
    return isinstance(schemes, list) and scheme in schemes


def remember(permissions, site, scheme):
    """Returns a copy of the permissions with this site and program allowed."""
    result = {}
    if isinstance(permissions, dict):
        result = {k: list(v) for k, v in permissions.items() if isinstance(k, str) and isinstance(v, list)}
    if not site or not scheme:
        return result
    schemes = result.pop(site, [])
    if scheme not in schemes:
        schemes.append(scheme)
    result[site] = schemes  # most recently used last
    while len(result) > MAX_REMEMBERED_SITES:
        result.pop(next(iter(result)))
    return result


class ExternalLinkGate:
    """Keeps a page from opening a stream of questions: one at a time, and quiet after a "No"."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._open = False
        self._declined = {}

    def may_ask(self, site, scheme):
        if self._open:
            return False
        until = self._declined.get((site, scheme))
        if until is not None and self._clock() < until:
            return False
        return True

    def asking(self):
        self._open = True

    def answered(self, site, scheme, accepted):
        self._open = False
        if accepted:
            self._declined.pop((site, scheme), None)
        else:
            self._declined[(site, scheme)] = self._clock() + DECLINE_QUIET_SECONDS
