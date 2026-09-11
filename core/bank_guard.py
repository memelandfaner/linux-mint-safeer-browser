"""Safeer BankGuard: real banks stay untouched, fake banks get a warning.

Shared by Safeer Browser for Linux and Windows (Android uses the Kotlin port with the same rules and
the same test cases). Everything runs locally; no page content or address leaves the device.
Source of truth: clients/python/safeer_bank_guard.py and clients/banks/ in safeer-threat-intel; keep the
copies (core/bank_guard.py, core/banks.json, core/bank_guard_page.js) identical.

Three checks, strongest first:

* official hosts: the bank catalogue (banks.json) lists the real banks' domains. Their pages and
  requests are never flagged by BankGuard, and threat rules covering them are ignored.
* host name: a host that is not a real bank but uses a bank's name together with banking words
  (``nlb-klik-prijava.com``), a homoglyph of a bank domain (``xn--nb-...``) or a one-letter typo of a
  distinctive bank domain (``otpbamka.si``).
* page content: a page on any other host that shows a password, one-time code or card number field
  while presenting itself as a bank in its title, site name, main heading or logo (news articles
  and blog posts are skipped).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import namedtuple
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _find(name: str) -> Path:
    for candidate in (_HERE / name, _HERE.parent / "banks" / name):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(name)


CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "ӏ": "l", "ı": "i", "ɩ": "l", "ο": "o", "ν": "v", "κ": "k", "ρ": "p", "τ": "t", "α": "a",
    "0": "o", "1": "l", "3": "e", "5": "s", "@": "a",
})


_EMBEDDED_CONTEXT = ("klik", "banka", "bank", "hranilnica")


def fold(text: str) -> str:
    """Lower case without diacritics (č -> c), for matching only."""
    normalized = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


# reason: lookalike | homoglyph | typosquat | page (a named tuple keeps start-up imports minimal)
Verdict = namedtuple("Verdict", "bank_id bank_name official_domain reason detail")


def _under(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _under_set(host: str, domains: frozenset) -> bool:
    """Like _under for a set: checks the host and each parent domain (fast for per-request checks)."""
    labels = host.split(".")
    return any(".".join(labels[i:]) in domains for i in range(len(labels)))


def _phrase_in(phrase: str, text: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text) is not None


def _damerau_one(a: str, b: str) -> bool:
    """True when a and b differ by exactly one insertion, deletion, substitution or transposition."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):
        if b[:i] + b[i + 1:] == a:
            return True
    return False


class BankGuard:
    def __init__(self, catalogue: dict | None = None, page_script: str | None = None):
        data = catalogue if catalogue is not None else json.loads(_find("banks.json").read_text("utf-8"))
        self.banks = data["banks"]
        self.infrastructure = tuple(data["infrastructure"])
        self.context = frozenset(data["context_tokens"])
        self.payment_phrases = tuple(fold(p) for p in data["payment_authentication_phrases"])
        self.page_check_skip = tuple(data.get("page_check_skip", ()))
        self.page_script = page_script if page_script is not None else _find("bank_guard_page.js").read_text("utf-8")
        self._official = {d: b for b in self.banks for d in b["official"]}
        self._trusted = frozenset(d for b in self.banks for d in b["official"] + b["family"]) | frozenset(self.infrastructure)
        self._labels = {}
        for bank in self.banks:
            for domain in bank["official"]:
                self._labels.setdefault(domain.split(".")[0].replace("-", ""), bank)

    # -- official hosts -------------------------------------------------------------------------
    @staticmethod
    def _host(host: str) -> str:
        host = (host or "").strip().lower().rstrip(".")
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        return host

    def official_bank(self, host: str):
        """The bank dict when host is one of the bank's own domains (or a subdomain), else None."""
        host = self._host(host)
        for domain, bank in self._official.items():
            if host == domain or host.endswith("." + domain):
                return bank
        return None

    def is_trusted(self, host: str) -> bool:
        """Official bank domains, bank group domains and payment/identity infrastructure."""
        host = self._host(host)
        return bool(host) and _under_set(host, self._trusted)

    # -- host names -----------------------------------------------------------------------------
    def host_verdict(self, host: str):
        host = self._host(host)
        if not host or "." not in host or self.is_trusted(host) or re.fullmatch(r"[0-9.:]+", host):
            return None
        labels = host.split(".")
        tokens = [t for t in re.split(r"[.\-_]", host) if t]
        context = set(re.split(r"[.\-_]", ".".join(labels[:-1]))) & self.context
        for bank in self.banks:
            hit = next((t for t in bank["tokens"] if t in tokens), None)
            if hit and context:
                return self._verdict(bank, "lookalike", f"'{hit}' with '{sorted(context)[0]}'")
        for label in labels[:-1]:
            if label.startswith("xn--"):
                try:
                    unicode_label = label.encode("ascii").decode("idna")
                except UnicodeError:
                    continue
                skeleton = fold(unicode_label).translate(CONFUSABLES).replace("-", "")
                bank = self._labels.get(skeleton)
                if bank is None:
                    bank = next((b for b in self.banks for t in b["tokens"] if len(t) >= 4 and t in skeleton), None)
                if bank is not None:
                    return self._verdict(bank, "homoglyph", unicode_label)
        for bank in self.banks:
            product = next((t for t in bank["tokens"] if t in tokens and t not in self._labels
                            and any(word in t for word in _EMBEDDED_CONTEXT)), None)
            if product:
                return self._verdict(bank, "lookalike", f"'{product}'")
        registrable = labels[-2] if len(labels) >= 2 else labels[0]
        tld = labels[-1]
        plain = registrable.replace("-", "")
        skeleton = plain.translate(CONFUSABLES)
        if skeleton != plain and skeleton in self._labels:
            bank = self._labels[skeleton]
            if len(skeleton) >= 4 or any(d.endswith("." + tld) for d in bank["official"]):
                return self._verdict(bank, "typosquat", registrable)
        for official_label, bank in self._labels.items():
            same_tld = any(d.split(".")[0].replace("-", "") == official_label and d.endswith("." + tld)
                           for d in bank["official"])
            if len(official_label) >= 6 and same_tld and _damerau_one(plain, official_label):
                return self._verdict(bank, "typosquat", registrable)
        return None

    # -- page content ---------------------------------------------------------------------------
    def page_verdict(self, host: str, signals: dict):
        host = self._host(host or signals.get("host", ""))
        if not signals or not (signals.get("password") or signals.get("otp") or signals.get("card")):
            return None
        if str(signals.get("scheme", "https")) not in ("http", "https") or not host or self.is_trusted(host):
            return None
        if _under(host, self.page_check_skip):
            return None  # brand pages on large platforms show their own login next to a bank's name
        if signals.get("article"):
            return None  # a news article or blog post about a bank, not a login page
        page_text = fold(" ".join(str(signals.get(k, "")) for k in ("title", "site", "headings", "logos", "text")))
        if any(_phrase_in(p, page_text) for p in self.payment_phrases):
            return None  # card payment authentication pages are hosted by payment processors
        prominent = fold(" ".join(str(signals.get(k, "")) for k in ("title", "site", "headings", "logos")))
        for bank in self.banks:
            for name in bank["names"]:
                if _phrase_in(fold(name), prominent):
                    return self._verdict(bank, "page", name)
        return None

    def check(self, host: str, signals: dict | None = None):
        return self.host_verdict(host) or (self.page_verdict(host, signals) if signals else None)

    @staticmethod
    def _verdict(bank: dict, reason: str, detail: str) -> Verdict:
        return Verdict(bank["id"], bank["name"], bank["official"][0], reason, detail)


_default = None


def default_guard() -> BankGuard:
    global _default
    if _default is None:
        _default = BankGuard()
    return _default
