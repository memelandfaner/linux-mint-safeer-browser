"""Safeer signed feed client: verification, anti-rollback storage and fast matching.

Self-contained (Python standard library only). Uses the ``cryptography`` package for Ed25519 when it
is installed and falls back to a strict RFC 8032 verifier otherwise. Shared by Safeer Browser for
Linux and Windows and used by the backend test suite as the reference client.

Security properties
-------------------
* A manifest is accepted only if an Ed25519 signature from a trusted key covers its exact bytes.
* A bundle is accepted only if its size, SHA-256 and its own Ed25519 signature match the manifest.
* Versions only move forward (anti-rollback); expired manifests are refused.
* Any failure keeps the last verified bundle in use. Stored bundles are re-verified when loaded.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import tempfile
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
BUNDLE_CONTEXT = b"safeer-bundle-v1\n"
MANIFEST_CONTEXT = b"safeer-manifest-v1\n"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_BUNDLE_BYTES = 48 * 1024 * 1024
INDICATOR_TYPES = ("domain", "hostname", "url", "ipv4", "ipv6")
CATEGORIES = ("botnet_c2", "malware", "phishing", "scam", "ads", "tracker")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HOST = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")
_URL = re.compile(r"^https?://[\x21\x23-\x5b\x5d-\x7e]+$")


class FeedVerificationError(Exception):
    """The downloaded data is not acceptable. The previously verified bundle stays in use."""


class RollbackError(FeedVerificationError):
    pass


class ExpiredFeedError(FeedVerificationError):
    pass


class UpToDate(Exception):
    """The server offers the version that is already installed."""


# --------------------------------------------------------------------------------------------------
# Ed25519 verification
# --------------------------------------------------------------------------------------------------

try:  # pragma: no cover - exercised implicitly where cryptography is installed
    from cryptography.exceptions import InvalidSignature as _InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as _Ed25519PublicKey
except Exception:  # pragma: no cover
    _Ed25519PublicKey = None

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _point_add(a, b):
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    aa = (y1 - x1) * (y2 - x2) % _P
    bb = (y1 + x1) * (y2 + x2) % _P
    cc = t1 * 2 * _D * t2 % _P
    dd = z1 * 2 * z2 % _P
    e, f, g, h = bb - aa, dd - cc, dd + cc, bb + aa
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _scalar_mult(scalar, point):
    result = (0, 1, 1, 0)
    while scalar:
        if scalar & 1:
            result = _point_add(result, point)
        point = _point_add(point, point)
        scalar >>= 1
    return result


def _point_equal(a, b):
    x1, y1, z1, _ = a
    x2, y2, z2, _ = b
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _decode_point(data):
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


_BASE = (
    15112221349535400772501151409588531511454012693041857206046113283949847762202,
    46316835694926478169428394003475163141307993866256225615783033603165251855960,
    1,
    46827403850823179245072216630277197565144205554125654976674165829533817101731,
)


def _pure_verify(public: bytes, message: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    point_a = _decode_point(public)
    point_r = _decode_point(signature[:32])
    s = int.from_bytes(signature[32:], "little")
    if point_a is None or point_r is None or s >= _L:
        return False
    k = int.from_bytes(hashlib.sha512(signature[:32] + public + message).digest(), "little") % _L
    left = _scalar_mult(s, _BASE)
    right = _point_add(point_r, _scalar_mult(k, point_a))
    return _point_equal(left, right)


def ed25519_verify(public: bytes, message: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    if _Ed25519PublicKey is not None:
        try:
            _Ed25519PublicKey.from_public_bytes(public).verify(signature, message)
            return True
        except (_InvalidSignature, ValueError):
            return False
    return _pure_verify(public, message, signature)


# --------------------------------------------------------------------------------------------------
# Canonical JSON and verification
# --------------------------------------------------------------------------------------------------

def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _strict_loads(data: bytes):
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise FeedVerificationError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def no_floats(_):
        raise FeedVerificationError("floating point numbers are not allowed")

    try:
        text = data.decode("ascii")
        return json.loads(text, object_pairs_hook=no_duplicates, parse_float=no_floats,
                          parse_constant=no_floats)
    except (UnicodeDecodeError, ValueError) as exc:
        raise FeedVerificationError(f"invalid JSON: {exc}") from exc


def _b64decode(text) -> bytes:
    if not isinstance(text, str):
        raise FeedVerificationError("expected base64 text")
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise FeedVerificationError("invalid base64") from exc


def _parse_time(value) -> datetime:
    if not isinstance(value, str) or not _TIME.match(value):
        raise FeedVerificationError("invalid timestamp")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _int(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise FeedVerificationError(f"invalid {name}")
    return value


def _signature_ok(entry, trusted_keys, context, data) -> bool:
    if not isinstance(entry, dict) or set(entry) != {"alg", "key_id", "sig"} or entry["alg"] != "ed25519":
        return False
    if not isinstance(entry["key_id"], str):
        return False
    public = trusted_keys.get(entry["key_id"])
    if not public:
        return False
    return ed25519_verify(base64.b64decode(public), context + data, _b64decode(entry["sig"]))


@dataclass(frozen=True)
class Manifest:
    feed_type: str
    version: int
    generated_at: datetime
    expires_at: datetime
    rule_count: int
    rules_sha256: str
    bundle_path: str
    bundle_size: int
    bundle_sha256: str
    bundle_signature: dict
    raw_envelope: bytes


def verify_manifest(envelope_bytes: bytes, trusted_keys: dict, feed_type: str, *, installed_version: int = 0,
                    now: datetime | None = None, check_expiry: bool = True) -> Manifest:
    if len(envelope_bytes) > MAX_MANIFEST_BYTES:
        raise FeedVerificationError("manifest too large")
    envelope = _strict_loads(envelope_bytes)
    if not isinstance(envelope, dict) or set(envelope) != {"signed", "signatures"}:
        raise FeedVerificationError("invalid manifest envelope")
    signed = _b64decode(envelope["signed"])
    signatures = envelope["signatures"]
    if not isinstance(signatures, list) or not 1 <= len(signatures) <= 4:
        raise FeedVerificationError("invalid signature list")
    if not any(_signature_ok(entry, trusted_keys, MANIFEST_CONTEXT, signed) for entry in signatures):
        raise FeedVerificationError("manifest signature is not valid for any trusted key")
    manifest = _strict_loads(signed)
    if not isinstance(manifest, dict) or canonical_json(manifest) != signed:
        raise FeedVerificationError("manifest is not in canonical form")
    expected = {"schema_version", "type", "feed_type", "version", "generated_at", "expires_at", "rule_count",
                "rules_sha256", "bundle"}
    if set(manifest) != expected:
        raise FeedVerificationError("unexpected manifest fields")
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["type"] != "safeer-feed-manifest":
        raise FeedVerificationError("unsupported manifest schema")
    if manifest["feed_type"] != feed_type:
        raise FeedVerificationError("manifest is for a different feed")
    version = _int(manifest["version"], "version", 1)
    bundle = manifest["bundle"]
    if not isinstance(bundle, dict) or set(bundle) != {"path", "size", "sha256", "signature"}:
        raise FeedVerificationError("invalid bundle reference")
    if bundle["path"] != f"{feed_type}-{version}.json":
        raise FeedVerificationError("unexpected bundle path")
    size = _int(bundle["size"], "bundle size", 2)
    if size > MAX_BUNDLE_BYTES:
        raise FeedVerificationError("bundle too large")
    if not isinstance(bundle["sha256"], str) or not _HEX64.match(bundle["sha256"]):
        raise FeedVerificationError("invalid bundle hash")
    if not isinstance(manifest["rules_sha256"], str) or not _HEX64.match(manifest["rules_sha256"]):
        raise FeedVerificationError("invalid rules hash")
    generated = _parse_time(manifest["generated_at"])
    expires = _parse_time(manifest["expires_at"])
    if expires <= generated:
        raise FeedVerificationError("manifest expires before it was generated")
    now = now or datetime.now(timezone.utc)
    if check_expiry and now >= expires:
        raise ExpiredFeedError("manifest has expired")
    if version < installed_version:
        raise RollbackError(f"offered version {version} is older than installed {installed_version}")
    return Manifest(feed_type, version, generated, expires, _int(manifest["rule_count"], "rule count"),
                    manifest["rules_sha256"], bundle["path"], size, bundle["sha256"], bundle["signature"],
                    envelope_bytes)


@dataclass(frozen=True)
class Bundle:
    manifest: Manifest
    sources: tuple
    rules: tuple  # (value, indicator_type, category, source_index)


def _valid_rule_value(value: str, kind: str) -> bool:
    if kind in ("domain", "hostname"):
        return bool(_HOST.match(value))
    if kind == "url":
        return len(value) <= 2048 and bool(_URL.match(value))
    try:
        if kind == "ipv4":
            return str(ipaddress.IPv4Address(value)) == value
        if kind == "ipv6":
            return ipaddress.IPv6Address(value).compressed == value
    except ValueError:
        return False
    return False


def verify_bundle(bundle_bytes: bytes, manifest: Manifest, trusted_keys: dict) -> Bundle:
    if len(bundle_bytes) != manifest.bundle_size:
        raise FeedVerificationError("bundle size does not match the manifest")
    if hashlib.sha256(bundle_bytes).hexdigest() != manifest.bundle_sha256:
        raise FeedVerificationError("bundle SHA-256 does not match the manifest")
    if not _signature_ok(manifest.bundle_signature, trusted_keys, BUNDLE_CONTEXT, bundle_bytes):
        raise FeedVerificationError("bundle signature is not valid")
    payload = _strict_loads(bundle_bytes)
    if not isinstance(payload, dict) or canonical_json(payload) != bundle_bytes:
        raise FeedVerificationError("bundle is not in canonical form")
    expected = {"schema_version", "feed_type", "version", "generated_at", "expires_at", "rule_count", "sha256",
                "sources", "rules"}
    if set(payload) != expected or payload["schema_version"] != SCHEMA_VERSION:
        raise FeedVerificationError("unexpected bundle fields")
    if (payload["feed_type"] != manifest.feed_type or payload["version"] != manifest.version
            or _parse_time(payload["expires_at"]) != manifest.expires_at
            or _parse_time(payload["generated_at"]) != manifest.generated_at):
        raise FeedVerificationError("bundle metadata does not match the manifest")
    rules = payload["rules"]
    sources = payload["sources"]
    if not isinstance(rules, list) or not isinstance(sources, list) or not sources:
        raise FeedVerificationError("invalid rules or sources")
    if payload["rule_count"] != len(rules) or manifest.rule_count != len(rules):
        raise FeedVerificationError("rule count mismatch")
    if payload["sha256"] != manifest.rules_sha256 or hashlib.sha256(canonical_json(rules)).hexdigest() != payload["sha256"]:
        raise FeedVerificationError("rules SHA-256 mismatch")
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"id", "name", "license", "url"}:
            raise FeedVerificationError("invalid source entry")
    checked = []
    for rule in rules:
        if (not isinstance(rule, list) or len(rule) != 4 or not isinstance(rule[0], str)
                or rule[1] not in INDICATOR_TYPES or rule[2] not in CATEGORIES
                or isinstance(rule[3], bool) or not isinstance(rule[3], int) or not 0 <= rule[3] < len(sources)
                or not _valid_rule_value(rule[0], rule[1])):
            raise FeedVerificationError(f"invalid rule {str(rule)[:120]}")
        checked.append((rule[0], rule[1], rule[2], rule[3]))
    return Bundle(manifest, tuple(sources), tuple(checked))


# --------------------------------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------------------------------

class ThreatIndex:
    """Constant-time lookups for the four rule kinds. Immutable after construction."""

    def __init__(self, rules=()):
        self._suffix = {}
        self._hosts = {}
        self._urls = {}
        for value, kind, category, _source in rules:
            if kind == "domain":
                node = self._suffix
                for label in reversed(value.split(".")):
                    node = node.setdefault(label, {})
                node.setdefault("\0", category)
            elif kind in ("hostname", "ipv4", "ipv6"):
                self._hosts.setdefault(value, category)
            elif kind == "url":
                self._urls.setdefault(value, category)
        self.size = len(rules)

    def match_host(self, host: str):
        host = (host or "").strip().lower().rstrip(".")
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        if not host:
            return None
        category = self._hosts.get(host)
        if category:
            return category
        node = self._suffix
        for label in reversed(host.split(".")):
            node = node.get(label)
            if node is None:
                return None
            if "\0" in node:
                return node["\0"]
        return None

    def match_url(self, url: str):
        try:
            parts = urlsplit(url)
            host = parts.hostname or ""
        except ValueError:
            return None
        category = self.match_host(host)
        if category or not self._urls or parts.scheme not in ("http", "https"):
            return category
        try:
            port = parts.port
        except ValueError:
            return None
        netloc = f"[{host}]" if ":" in host else host
        if port is not None and not ((parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443)):
            netloc = f"{netloc}:{port}"
        key = f"{parts.scheme}://{netloc}{parts.path or '/'}" + (f"?{parts.query}" if parts.query else "")
        return self._urls.get(key)


# --------------------------------------------------------------------------------------------------
# Storage and updates
# --------------------------------------------------------------------------------------------------

def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _read_limited(url: str, limit: int, timeout: float, opener=None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Safeer", "Accept": "application/json"})
    opener = opener or urllib.request.build_opener(urllib.request.HTTPSHandler())
    with opener.open(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise FeedVerificationError(f"HTTP status {status}")
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > limit:
            raise FeedVerificationError("response too large")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise FeedVerificationError("response too large")
        return data


class SignedFeedStore:
    """Keeps the newest verified bundle of one feed type on disk and in memory."""

    def __init__(self, directory, feed_type: str, trusted_keys: dict, base_urls, timeout: float = 20.0,
                 fetch=None):
        self.directory = Path(directory)
        self.feed_type = feed_type
        self.trusted_keys = dict(trusted_keys)
        self.base_urls = [url.rstrip("/") for url in base_urls]
        self.timeout = timeout
        self._fetch = fetch or (lambda url, limit: _read_limited(url, limit, timeout))
        self._lock = threading.Lock()
        self.bundle = None
        self.index = ThreatIndex()
        self.last_error = ""

    def _files(self, version: int):
        return (self.directory / f"{self.feed_type}-{version}-manifest.json",
                self.directory / f"{self.feed_type}-{version}-bundle.json")

    @property
    def _state_path(self):
        return self.directory / f"{self.feed_type}-state.json"

    def installed_version(self) -> int:
        try:
            state = json.loads(self._state_path.read_text("ascii"))
            value = state.get("version", 0)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
        except (OSError, ValueError, AttributeError):
            return 0

    def load(self) -> bool:
        """Loads and re-verifies the stored bundle. An expired bundle is still used (better than none)."""
        version = self.installed_version()
        if version < 1:
            self.last_error = "no stored feed"
            return False
        manifest_path, bundle_path = self._files(version)
        try:
            manifest = verify_manifest(manifest_path.read_bytes(), self.trusted_keys, self.feed_type,
                                       check_expiry=False)
            if manifest.version != version:
                raise FeedVerificationError("stored manifest does not match the recorded version")
            bundle = verify_bundle(bundle_path.read_bytes(), manifest, self.trusted_keys)
        except (OSError, FeedVerificationError) as exc:
            self.last_error = f"stored feed unavailable: {exc}"
            return False
        with self._lock:
            self.bundle = bundle
            self.index = ThreatIndex(bundle.rules)
        return True

    def _install(self, manifest: Manifest, manifest_bytes: bytes, bundle_bytes: bytes) -> None:
        manifest_path, bundle_path = self._files(manifest.version)
        _atomic_write(bundle_path, bundle_bytes)
        _atomic_write(manifest_path, manifest_bytes)
        # The state file is the commit point: until it is replaced, load() keeps using the old files.
        _atomic_write(self._state_path, json.dumps({"version": manifest.version}).encode("ascii"))
        for old in self.directory.glob(f"{self.feed_type}-*-*.json"):
            parts = old.name.split("-")
            if len(parts) >= 3 and parts[-2].isdigit() and int(parts[-2]) < manifest.version:
                try:
                    old.unlink()
                except OSError:
                    pass

    def update(self, now: datetime | None = None) -> bool:
        """Fetches and installs a newer bundle. Returns True when a new version was installed."""
        installed = self.installed_version()
        errors = []
        for base in self.base_urls:
            try:
                manifest_bytes = self._fetch(f"{base}/v1/{self.feed_type}/latest.json", MAX_MANIFEST_BYTES)
                manifest = verify_manifest(manifest_bytes, self.trusted_keys, self.feed_type,
                                           installed_version=installed, now=now)
                if manifest.version == installed and self.bundle is not None:
                    raise UpToDate()
                bundle_bytes = self._fetch(f"{base}/v1/{self.feed_type}/{manifest.bundle_path}", manifest.bundle_size)
                bundle = verify_bundle(bundle_bytes, manifest, self.trusted_keys)
                index = ThreatIndex(bundle.rules)
                self._install(manifest, manifest_bytes, bundle_bytes)
                with self._lock:
                    self.bundle = bundle
                    self.index = index
                self.last_error = ""
                return True
            except UpToDate:
                self.last_error = ""
                return False
            except Exception as exc:  # network, verification and disk errors keep the current feed
                errors.append(f"{base}: {exc.__class__.__name__}: {exc}")
        self.last_error = "; ".join(errors)
        return False

    def match_url(self, url: str):
        return self.index.match_url(url)

    def match_host(self, host: str):
        return self.index.match_host(host)
