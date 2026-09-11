"""Qt-free browser policy for Safeer Browser for Windows.

Everything here is plain Python so it can be unit tested on any system:
shared Safeer filters, address-bar resolution, user-script wrapping,
the safeer:// start page, settings and bookmark import.
"""

from __future__ import annotations

import copy
import glob
import html
import html.parser  # noqa: F401  (used by the shared bookmark importer)
import importlib.util
import json
import locale
import ntpath
import os
import re
import shutil
import sqlite3
import sys
import secrets
import tempfile
import threading
import time
import urllib.parse
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

APP_NAME = "Safeer Browser"
APP_ID = "SafeerBrowser"
HOME_URL = "safeer://home/"
BRIDGE_PREFIX = "__safeer_bridge__:"
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Shared Safeer sources (core/, ui/, assets/) from the repository or the bundle
# ---------------------------------------------------------------------------

def resource_roots() -> List[str]:
    roots = []
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(os.path.join(bundle, "shared"))
    roots.append(os.path.abspath(os.path.join(PACKAGE_DIR, "..", "..")))
    return roots


def shared_path(relative: str) -> str:
    parts = relative.split("/")
    for root in resource_roots():
        candidate = os.path.join(root, *parts)
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(f"Safeer resource not found: {relative}")


def _load_shared_module(name: str):
    path = shared_path(f"core/{name}.py")
    spec = importlib.util.spec_from_file_location(f"safeer_shared_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


adblock = _load_shared_module("adblock")
shared_config = _load_shared_module("config")
bookmarks = _load_shared_module("bookmarks_importer")
reader = _load_shared_module("reader")
threat_intel = _load_shared_module("threat_intel")


def read_version() -> str:
    try:
        with open(shared_path("windows/VERSION"), encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return "0.0.0"


APP_VERSION = read_version()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

DEFAULT_PORTALS = [
    {"id": "p1", "title": "YouTube", "url": "https://www.youtube.com", "mark": "▶️"},
    {"id": "p2", "title": "YouTube Music", "url": "https://music.youtube.com", "mark": "🎵"},
    {"id": "p3", "title": "24ur.com", "url": "https://www.24ur.com", "mark": "📰"},
    {"id": "p4", "title": "RTV SLO", "url": "https://www.rtvslo.si", "mark": "🇸🇮"},
    {"id": "p5", "title": "RTV 365", "url": "https://365.rtvslo.si", "mark": "🎬"},
    {"id": "p6", "title": "Wikipedia", "url": "https://www.wikipedia.org", "mark": "🌐"},
    {"id": "p7", "title": "GitHub", "url": "https://github.com", "mark": "🐙"},
    {"id": "p8", "title": "safeer.si", "url": "https://safeer.si", "mark": "🛡️"},
]

DEFAULT_SETTINGS: Dict[str, Any] = {
    "language": "auto",
    "search_engine": "duckduckgo",
    "startup": "home",
    "adblock_enabled": True,
    "adguard_protection_enabled": True,
    "tracking_protection_enabled": True,
    "gpc_dnt_enabled": True,
    "block_third_party_cookies": True,
    "doh_provider": "cloudflare",
    "custom_doh_url": "",
    "force_dark_mode": False,
    "hardware_acceleration": True,
    "ask_download_location": False,
    "custom_portals": DEFAULT_PORTALS,
    "total_ads_blocked": 0,
    "total_threats_blocked": 0,
    "last_session": [],
    "window_geometry": "",
}

DOH_TEMPLATES = {
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "quad9": "https://dns.quad9.net/dns-query",
    "google": "https://dns.google/dns-query",
}


def _windows_folder(env: Dict[str, str], variable: str, fallback: str) -> str:
    value = env.get(variable)
    if value:
        return os.path.join(value, APP_NAME)
    return os.path.join(os.path.expanduser("~"), fallback)


def data_dir(env: Optional[Dict[str, str]] = None) -> str:
    env = dict(os.environ if env is None else env)
    if env.get("SAFEER_WINDOWS_DATA_DIR"):
        return env["SAFEER_WINDOWS_DATA_DIR"]
    return _windows_folder(env, "APPDATA", os.path.join(".config", "safeer-windows"))


def profile_dir(env: Optional[Dict[str, str]] = None) -> str:
    env = dict(os.environ if env is None else env)
    if env.get("SAFEER_WINDOWS_DATA_DIR"):
        return os.path.join(env["SAFEER_WINDOWS_DATA_DIR"], "Profile")
    return os.path.join(_windows_folder(env, "LOCALAPPDATA", os.path.join(".local", "share", "safeer-windows")), "Profile")


def threat_intel_dir(env: Optional[Dict[str, str]] = None) -> str:
    env = dict(os.environ if env is None else env)
    if env.get("SAFEER_WINDOWS_DATA_DIR"):
        return os.path.join(env["SAFEER_WINDOWS_DATA_DIR"], "ThreatIntel")
    return os.path.join(_windows_folder(env, "LOCALAPPDATA", os.path.join(".local", "share", "safeer-windows")), "ThreatIntel")


class SettingsStore:
    """JSON settings with atomic writes; unknown keys from newer versions are preserved."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.path.join(data_dir(), "settings.json")
        self.values: Dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                self.values.update(stored)
        except (OSError, ValueError):
            pass
        if not isinstance(self.values.get("custom_portals"), list):
            self.values["custom_portals"] = copy.deepcopy(DEFAULT_PORTALS)
        if self.values.get("search_engine") not in search_engines():
            self.values["search_engine"] = "duckduckgo"

    def save(self) -> bool:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            temporary = self.path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(self.values, handle, indent=2, ensure_ascii=False)
            os.replace(temporary, self.path)
            return True
        except OSError:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, DEFAULT_SETTINGS.get(key, default))

    def set(self, key: str, value: Any, save: bool = True) -> None:
        self.values[key] = value
        if save:
            self.save()


def ui_language(setting: str, system_locale: Optional[str] = None) -> str:
    if setting in ("sl", "en"):
        return setting
    if setting in ("de", "es", "fr", "it"):
        return "en"
    if system_locale is None:
        try:
            system_locale = locale.getlocale()[0] or ""
        except (ValueError, TypeError):
            system_locale = ""
        if not system_locale and sys.platform == "win32":
            try:
                import ctypes
                system_locale = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
            except (AttributeError, OSError):
                system_locale = ""
    lowered = (system_locale or "").lower()
    return "sl" if lowered.startswith(("sl", "slovenian")) else "en"


def home_language(setting: str) -> str:
    if setting in ("sl", "en", "de", "es", "fr", "it"):
        return setting
    return ui_language(setting)


def doh_template(settings: SettingsStore) -> Optional[str]:
    provider = settings.get("doh_provider")
    if provider == "custom":
        custom = str(settings.get("custom_doh_url") or "").strip()
        return custom if custom.lower().startswith("https://") else None
    return DOH_TEMPLATES.get(provider)


def chromium_flags(existing: str, settings: SettingsStore) -> str:
    flags = existing.split() if existing else []
    if not settings.get("hardware_acceleration") and "--disable-gpu" not in flags:
        flags.append("--disable-gpu")
    return " ".join(flags)


# ---------------------------------------------------------------------------
# Search and address bar
# ---------------------------------------------------------------------------

def search_engines() -> Dict[str, Dict[str, str]]:
    engines = copy.deepcopy(shared_config.SEARCH_ENGINES)
    engines["youtube"] = {"name": "YouTube", "url": "https://www.youtube.com/results?search_query=", "icon": "▶️"}
    return engines


_IPV4 = re.compile(r"^(\d{1,3})(\.\d{1,3}){3}$")
_SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")
_WINDOWS_PATH = re.compile(r"^(?:[a-zA-Z]:[\\/]|\\\\[^\\]+\\)")


def _host_part(text: str) -> str:
    host = re.split(r"[/?#]", text, maxsplit=1)[0]
    if host.startswith("[") and "]" in host:
        return host[1:host.index("]")]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def looks_like_address(text: str) -> bool:
    if not text or any(ch.isspace() for ch in text):
        return False
    host = _host_part(text).lower().rstrip(".")
    if not host:
        return False
    if host == "localhost" or _IPV4.match(host):
        return True
    labels = host.split(".")
    if len(labels) < 2 or any(not label for label in labels):
        return False
    if not all(re.match(r"^[a-z0-9¡-￿-]+$", label) for label in labels):
        return False
    top = labels[-1]
    return bool(re.match(r"^(?:[a-z¡-￿]{2,63}|xn--[a-z0-9-]+)$", top))


def search_url(query: str, engine: str) -> str:
    engines = search_engines()
    base = engines.get(engine, engines["duckduckgo"])["url"]
    return base + urllib.parse.quote_plus(query)


def blocked_page_url(url: str) -> str:
    return HOME_URL + "blocked?url=" + urllib.parse.quote(url, safe="")


def resolve_input(text: str, engine: str = "duckduckgo", tracking_protection: bool = True) -> Tuple[str, str]:
    """Turns address-bar text into (kind, url). kind: empty, home, url, search, blocked."""
    value = (text or "").strip()
    if not value:
        return "empty", ""
    lowered = value.lower()
    if lowered in ("home", "safeer://home", "safeer://home/", "about:home", "about:newtab"):
        return "home", HOME_URL
    if lowered in ("about:blank",):
        return "url", "about:blank"
    if _WINDOWS_PATH.match(value):
        path = value.replace("/", "\\")
        return "url", "file:///" + urllib.parse.quote(path.replace("\\", "/").lstrip("/"), safe="/:")
    scheme_match = _SCHEME.match(value)
    url = ""
    if scheme_match and "://" in value[:len(scheme_match.group(0)) + 2]:
        scheme = scheme_match.group(1).lower()
        if scheme in ("http", "https"):
            url = value
        elif scheme == "file":
            return "url", value
        elif scheme == "safeer":
            return "home", HOME_URL
        else:
            return "search", search_url(value, engine)
    elif looks_like_address(value):
        host = _host_part(value).lower()
        prefix = "http://" if host == "localhost" or _IPV4.match(host) else "https://"
        url = shared_config.normalize_web_url(prefix + value) or ""
    if not url:
        return "search", search_url(value, engine)
    if adblock.is_threat_domain(url):
        return "blocked", blocked_page_url(url)
    bank_verdict = adblock.fake_bank_verdict(url)
    if bank_verdict is not None:
        return "blocked", fake_bank_page_url(url, bank_verdict)
    if tracking_protection:
        url = adblock.strip_tracking_parameters(url)
    return "url", url


def display_url(url: str) -> str:
    if not url or url.startswith(HOME_URL.rstrip("/")) and "blocked" not in url:
        return ""
    return url


def request_decision(url: str, resource_is_main_frame: bool, first_party: str, adblock_enabled: bool) -> str:
    """Returns allow, block-ad or block-threat for a network request."""
    lowered = (url or "").lower()
    if not lowered.startswith(("http://", "https://", "ws://", "wss://")):
        return "allow"
    if adblock.is_passthrough_host(url):
        return "allow"
    if adblock.is_threat_domain(url):
        return "block-threat"
    if adblock_enabled and adblock.is_ad_domain(url) and not adblock.is_ad_domain(first_party or ""):
        return "block-ad"
    return "allow"


def navigation_scheme_allowed(url: str) -> str:
    """allow, external (ask before handing to Windows) or deny for a main-frame navigation."""
    scheme = (urllib.parse.urlsplit(url or "").scheme or "").lower()
    if scheme in ("http", "https", "safeer", "about", "blob", "data", "file"):
        return "allow"
    if scheme in ("mailto", "tel"):
        return "external"
    return "deny"


COOKIE_THIRD_PARTY_ALLOWED = (
    "challenges.cloudflare.com", "turnstile.com", "hcaptcha.com", "recaptcha.net",
    "accounts.google.com", "accounts.youtube.com", "google.com", "youtube.com", "gstatic.com",
    "login.microsoftonline.com", "login.live.com", "appleid.apple.com", "x.ai", "grok.com",
)


def third_party_cookie_allowed(origin_host: str) -> bool:
    host = (origin_host or "").lower().rstrip(".")
    return any(host == allowed or host.endswith("." + allowed) for allowed in COOKIE_THIRD_PARTY_ALLOWED)


def clean_user_agent(user_agent: str) -> str:
    return re.sub(r"\s*QtWebEngine/[\d.]+", "", user_agent or "").strip()


def unique_filename(directory: str, name: str) -> str:
    base = os.path.basename((name or "").replace("\\", "/")) or "download"
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base).strip(" .") or "download"
    stem, ext = os.path.splitext(base)
    candidate, counter = base, 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{stem} ({counter}){ext}"
        counter += 1
    return candidate


# ---------------------------------------------------------------------------
# User scripts shared with the Linux edition
# ---------------------------------------------------------------------------

def pattern_to_regex(pattern: str) -> str:
    """Converts a WebKit/Chromium style URL pattern (e.g. *://*.youtube.com/*) to a regex string."""
    match = re.match(r"^(\*|[a-zA-Z][a-zA-Z0-9+.-]*)://([^/]*)(/.*)?$", pattern)
    if not match:
        raise ValueError(f"Unsupported URL pattern: {pattern}")
    scheme, host, path = match.groups()

    def escape(text: str) -> str:
        return re.sub(r"([.+?^${}()|\[\]\\/])", r"\\\1", text)

    if scheme == "file":
        return r"^file://.*$"
    scheme_rx = "https?" if scheme == "*" else escape(scheme.lower())
    if host == "*":
        host_rx = r"[^/?#]*"
    elif host.startswith("*."):
        host_rx = r"(?:[^/?#]*\.)?" + escape(host[2:].lower()) + r"(?::\d+)?"
    else:
        host_rx = escape(host.lower()) + r"(?::\d+)?"
    path_rx = ".*" if path is None else ".*".join(escape(piece) for piece in path.split("*"))
    return "^" + scheme_rx + "://" + host_rx + path_rx + "$"


def adapt_linux_script(source: str) -> str:
    """Routes the WebKit message bridge of the Linux scripts to the Windows console bridge."""
    adapted = source.replace(
        "window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer",
        "true",
    )
    return adapted.replace("window.webkit.messageHandlers.safeer.postMessage(", "__safeerPost(")


def wrap_script(source: str, include: Optional[Iterable[str]], exclude: Optional[Iterable[str]], top_frame_only: bool = False) -> str:
    include_rx = json.dumps([pattern_to_regex(p) for p in (include or [])])
    exclude_rx = json.dumps([pattern_to_regex(p) for p in (exclude or [])])
    prelude = (
        "(function () {\n"
        "var __safeerUrl = String(location.href);\n"
        "function __safeerMatches(list) { for (var i = 0; i < list.length; i++) { "
        "if (new RegExp(list[i], 'i').test(__safeerUrl)) return true; } return false; }\n"
        f"var __safeerInclude = {include_rx}, __safeerExclude = {exclude_rx};\n"
        "if (__safeerInclude.length && !__safeerMatches(__safeerInclude)) return;\n"
        "if (__safeerMatches(__safeerExclude)) return;\n"
        + ("if (window.top !== window) return;\n" if top_frame_only else "")
        + "function __safeerPost(message) { try { console.log('" + BRIDGE_PREFIX + "' + JSON.stringify(message)); } catch (e) {} }\n"
    )
    return prelude + adapt_linux_script(source) + "\n})();\n"


HOOKSHOT_SITES = ("pushsquare.com", "nintendolife.com", "purexbox.com", "timeextension.com", "digitalfoundry.net")
YOUTUBE_PATTERNS = ["*://*.youtube.com/*", "*://youtube.com/*"]


def script_specs(settings: SettingsStore) -> List[Dict[str, Any]]:
    """Script list mirroring the Linux edition (name, source, start|ready, all_frames)."""
    auth = list(adblock.AUTH_SCRIPT_EXCLUSIONS)
    specs: List[Dict[str, Any]] = []

    def add(name, source, include, exclude, at_start, all_frames):
        specs.append({
            "name": name,
            "source": wrap_script(source, include, exclude, top_frame_only=not all_frames),
            "at_start": at_start,
            "all_frames": all_frames,
        })

    if settings.get("gpc_dnt_enabled"):
        add("safeer-gpc", adblock.GPC_AND_DNT_SCRIPT, None, auth, True, True)
    if settings.get("adblock_enabled"):
        add("safeer-youtube-adblock", adblock.YOUTUBE_ADBLOCK_SCRIPT,
            YOUTUBE_PATTERNS + ["*://*.googlevideo.com/*"],
            auth + ["*://accounts.youtube.com/*", "*://accounts.google.com/*", "*://myaccount.google.com/*"], True, True)
    add("safeer-youtube-keep-watching", adblock.YOUTUBE_KEEP_WATCHING_SCRIPT,
        YOUTUBE_PATTERNS, auth + ["*://accounts.youtube.com/*"], True, False)
    if settings.get("adblock_enabled"):
        add("safeer-hookshot-inserts", adblock.HOOKSHOT_INSERTS_SCRIPT,
            [f"*://{d}/*" for site in HOOKSHOT_SITES for d in (site, "*." + site)], None, True, False)
    if settings.get("adblock_enabled") and settings.get("adguard_protection_enabled"):
        add("safeer-adguard", adblock.ADGUARD_PROTECTION_SCRIPT, None,
            auth + ["*://*.google.com/*", "*://*.google.si/*", "*://*.banka.si/*"], True, True)
    if settings.get("adblock_enabled"):
        add("safeer-cosmetic", adblock.GENERIC_COSMETIC_SCRIPT, None,
            auth + ["*://*.google.com/*", "*://*.google.si/*", "*://*.facebook.com/*", "*://*.messenger.com/*", "*://*.banka.si/*"],
            False, True)
        add("safeer-anti-clickjacking", adblock.ANTI_CLICKJACKING_SCRIPT, None, auth + ["file://*"], False, True)
    return specs


def parse_bridge_message(message: str) -> Optional[Dict[str, Any]]:
    if not message.startswith(BRIDGE_PREFIX):
        return None
    try:
        payload = json.loads(message[len(BRIDGE_PREFIX):])
    except ValueError:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("action"), str):
        return None
    return payload


# ---------------------------------------------------------------------------
# safeer:// start page (reuses the Linux ui/home.* files)
# ---------------------------------------------------------------------------

HOME_ADAPTER_JS = r"""
/* Safeer Browser for Windows: host bridge and edition labels for the shared start page. */
(function () {
    var PREFIX = '__safeer_bridge__:';
    var bridge = { postMessage: function (message) { try { console.log(PREFIX + JSON.stringify(message)); } catch (e) {} } };
    try { window.webkit = { messageHandlers: { safeer: bridge } }; } catch (e) {}
    var defaultBrowser = { sl: '🌐 Privzeti brskalnik', en: '🌐 Default browser', de: '🌐 Standardbrowser',
        es: '🌐 Navegador predeterminado', fr: '🌐 Navigateur par défaut', it: '🌐 Browser predefinito' };
    try {
        Object.keys(homeI18n).forEach(function (lang) {
            homeI18n[lang].shield_subtitle = lang === 'sl' ? 'Brskalnik za Windows' : 'Made for Windows';
            homeI18n[lang].quick_default = defaultBrowser[lang] || defaultBrowser.en;
        });
    } catch (e) {}
    var windowsPortals = null;
    try {
        var sharedActivePortals = getActivePortals;
        window.getActivePortals = function () { return windowsPortals || sharedActivePortals(); };
    } catch (e) {}
    window.safeerWindowsInit = function (state) {
        state = state || {};
        if (Array.isArray(state.portals)) { windowsPortals = state.portals; }
        try { if (state.engine) { setEngine(state.engine); } } catch (e) {}
        try { changeHomeLanguage(state.language || 'sl', false); } catch (e) {}
        try { setShieldMetrics(state.ads || 0, state.threats || 0); } catch (e) {}
        try { renderPortals(); } catch (e) {}
        try { changeHomeLanguage(state.language || 'sl', false); } catch (e) {}
        document.documentElement.setAttribute('data-safeer-ready', '1');
    };
})();
"""

STORAGE_GUARD_JS = r"""
(function () {
    try { window.localStorage.getItem('safeer'); } catch (e) {
        var memory = {};
        var fallback = {
            getItem: function (k) { return Object.prototype.hasOwnProperty.call(memory, k) ? memory[k] : null; },
            setItem: function (k, v) { memory[k] = String(v); },
            removeItem: function (k) { delete memory[k]; }
        };
        try { Object.defineProperty(window, 'localStorage', { value: fallback, configurable: true }); } catch (err) {}
    }
})();
"""

_HOME_FILES = {
    "home.css": ("ui/home.css", "text/css"),
    "home.js": ("ui/home.js", "application/javascript"),
    "assets/safeer-mark.svg": ("assets/safeer-mark.svg", "image/svg+xml"),
    "assets/icon.png": ("assets/icon.png", "image/png"),
}

UI_STRINGS: Dict[str, Dict[str, str]] = {
    "sl": {
        "blocked_title": "Stran je blokirana",
        "blocked_text": "Safeer je ustavil povezavo, ker je naslov na seznamu znanih groženj (zlonamerna koda, botneti ali lažno predstavljanje).",
        "blocked_back": "Nazaj na varno",
        "blocked_home": "Domača stran",
        "fake_bank_title": "Lažna spletna banka",
        "fake_bank_text": "Ta stran ni prava spletna banka, predstavlja pa se kot {bank}. Na njej ne vpisujte uporabniškega imena, "
                          "gesla, kode SMS ali podatkov kartice. Do banke vedno dostopajte z vpisom uradnega naslova ali prek uradne aplikacije.",
        "fake_bank_open": "Odpri pravo stran: {domain}",
        "fake_bank_continue": "Vseeno nadaljuj (samo za to sejo)",
    },
    "en": {
        "blocked_title": "Page blocked",
        "blocked_text": "Safeer stopped this connection because the address is on a list of known threats (malware, botnets or phishing).",
        "blocked_back": "Go back to safety",
        "blocked_home": "Home",
        "fake_bank_title": "Fake online bank",
        "fake_bank_text": "This is not a real online bank, although it presents itself as {bank}. Do not enter your user name, "
                          "password, SMS code or card details here. Always open your bank by typing its official address or use its official app.",
        "fake_bank_open": "Open the real site: {domain}",
        "fake_bank_continue": "Continue anyway (this session only)",
    },
}


def home_html() -> str:
    with open(shared_path("ui/home.html"), encoding="utf-8") as handle:
        page = handle.read()
    page = page.replace("Safeer Browser — Linux Mint Edition", "Safeer Browser")
    page = page.replace("Linux Mint Suverena Izdaja", "Brskalnik za Windows")
    page = page.replace('<span class="shield-status">Linux Mint</span>', '<span class="shield-status">Windows</span>')
    page = page.replace('>🌐 Privzeti brskalnik</button>', ' data-i18n="quick_default">🌐 Privzeti brskalnik</button>')
    page = page.replace('<script src="home.js"></script>',
                        '<script src="storage-guard.js"></script>\n  <script src="home.js"></script>\n'
                        '  <script src="windows-adapter.js"></script>')
    return page


def blocked_html(url: str, lang: str) -> str:
    strings = UI_STRINGS.get(lang, UI_STRINGS["en"])
    safe_url = html.escape(url or "", quote=True)
    return f"""<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8"><title>{html.escape(strings['blocked_title'])}</title>
<style>
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#101814;color:#f1f5f9;font-family:"Segoe UI",system-ui,sans-serif}}
main{{max-width:620px;padding:40px;border:1px solid rgba(248,113,113,.45);border-radius:20px;background:#19241e}}
h1{{margin:0 0 12px;color:#fca5a5;font-size:28px}} p{{line-height:1.6;color:#cbd5e1}}
code{{display:block;margin:18px 0;padding:12px;border-radius:10px;background:#0b120e;color:#fecaca;word-break:break-all}}
a{{display:inline-block;margin-right:12px;padding:10px 18px;border-radius:12px;background:#9bd478;color:#0b120e;font-weight:600;text-decoration:none}}
a.secondary{{background:transparent;color:#f1f5f9;border:1px solid #50616b}}
</style></head>
<body><main data-safeer-blocked="1"><h1>🛡️ {html.escape(strings['blocked_title'])}</h1>
<p>{html.escape(strings['blocked_text'])}</p><code>{safe_url}</code>
<a href="javascript:history.length>1?history.back():location.replace('{HOME_URL}')">{html.escape(strings['blocked_back'])}</a>
<a class="secondary" href="{HOME_URL}">{html.escape(strings['blocked_home'])}</a></main></body></html>"""


# ---------------------------------------------------------------------------
# 🏦 Safeer BankGuard: warning page for fake online banks
# ---------------------------------------------------------------------------

_FAKE_BANK_WARNINGS: Dict[str, Tuple[str, Any, int, float]] = {}  # token -> (url, verdict, back steps, expiry)
_FAKE_BANK_LOCK = threading.Lock()
FAKE_BANK_TOKEN_SECONDS = 600


def fake_bank_page_url(url: str, verdict: Any, after_load: bool = False) -> str:
    """safeer:// warning page for a fake bank. Everything shown comes from the token, never from the URL,
    so no web page can craft a Safeer warning with a false "real site"."""
    token = secrets.token_urlsafe(24)
    now = time.monotonic()
    with _FAKE_BANK_LOCK:
        for key in [k for k, entry in _FAKE_BANK_WARNINGS.items() if entry[3] < now]:
            del _FAKE_BANK_WARNINGS[key]
        while len(_FAKE_BANK_WARNINGS) >= 64:
            del _FAKE_BANK_WARNINGS[next(iter(_FAKE_BANK_WARNINGS))]
        _FAKE_BANK_WARNINGS[token] = (url, verdict, 2 if after_load else 1, now + FAKE_BANK_TOKEN_SECONDS)
    return HOME_URL + "fake-bank?token=" + token


def _fake_bank_entry(query: str, consume: bool = False):
    token = urllib.parse.parse_qs(query or "").get("token", [""])[0]
    with _FAKE_BANK_LOCK:
        entry = _FAKE_BANK_WARNINGS.pop(token, None) if consume else _FAKE_BANK_WARNINGS.get(token)
    if entry is None or entry[3] < time.monotonic():
        return None, ""
    return entry, token


def fake_bank_html(query: str, lang: str) -> str:
    entry, token = _fake_bank_entry(query)
    if entry is None:
        return blocked_html("", lang)
    url, verdict, back, _expiry = entry
    strings = UI_STRINGS.get(lang, UI_STRINGS["en"])
    domain = html.escape(verdict.official_domain, quote=True)
    back_href = f"javascript:history.length>{back}?history.go(-{back}):location.replace('{HOME_URL}')"
    return f"""<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8"><title>{html.escape(strings['fake_bank_title'])}</title>
<style>
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#101814;color:#f1f5f9;font-family:"Segoe UI",system-ui,sans-serif}}
main{{max-width:620px;padding:40px;border:1px solid rgba(248,113,113,.45);border-radius:20px;background:#19241e}}
h1{{margin:0 0 12px;color:#fca5a5;font-size:28px}} p{{line-height:1.6;color:#cbd5e1}}
code{{display:block;margin:18px 0;padding:12px;border-radius:10px;background:#0b120e;color:#fecaca;word-break:break-all}}
a{{display:inline-block;margin:0 12px 12px 0;padding:10px 18px;border-radius:12px;background:#9bd478;color:#0b120e;font-weight:600;text-decoration:none}}
a.real{{background:#22c55e}} a.secondary{{background:transparent;color:#94a3b8;border:1px solid #50616b;font-weight:400}}
</style></head>
<body><main data-safeer-blocked="1" data-safeer-fake-bank="{html.escape(verdict.bank_id, quote=True)}">
<h1>🏦 {html.escape(strings['fake_bank_title'])}</h1>
<p>{html.escape(strings['fake_bank_text'].format(bank=verdict.bank_name))}</p><code>{html.escape(url, quote=True)}</code>
<a href="{back_href}">{html.escape(strings['blocked_back'])}</a>
<a class="real" href="https://{domain}/">{html.escape(strings['fake_bank_open'].format(domain=verdict.official_domain))}</a>
<a class="secondary" id="continue" href="{HOME_URL}fake-bank-continue?token={urllib.parse.quote(token)}">{html.escape(strings['fake_bank_continue'])}</a>
</main></body></html>"""


def fake_bank_continue(query: str) -> Optional[str]:
    """The user continues past the warning: the host is allowed for this session. Returns the address to open."""
    entry, _token = _fake_bank_entry(query, consume=True)
    if entry is None:
        return None
    url = entry[0]
    adblock.allow_fake_bank_host(url)
    return url


def fake_bank_page_verdict(url: str, signals: Any):
    """BankGuard verdict for a loaded page (signals from adblock.bank_guard_page_script()), or None."""
    return adblock.fake_bank_page_verdict(url, signals if isinstance(signals, dict) else None)


def scheme_resource(host: str, path: str, query: str, lang: str = "sl") -> Optional[Tuple[str, bytes]]:
    """Content for safeer://home/... requests; None means not found."""
    if (host or "").lower() != "home":
        return None
    name = (path or "/").lstrip("/")
    if name in ("", "home.html", "index.html"):
        return "text/html", home_html().encode("utf-8")
    if name == "blocked":
        target = urllib.parse.parse_qs(query or "").get("url", [""])[0]
        return "text/html", blocked_html(target, lang).encode("utf-8")
    if name == "fake-bank":
        return "text/html", fake_bank_html(query, lang).encode("utf-8")
    if name == "fake-bank-continue":
        target = fake_bank_continue(query)
        if not target or not target.lower().startswith(("http://", "https://")):
            return "text/html", blocked_html("", lang).encode("utf-8")
        safe = html.escape(target, quote=True)
        return "text/html", (f'<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={safe}">'
                             f'<a href="{safe}">{safe}</a>').encode("utf-8")
    if name == "windows-adapter.js":
        return "application/javascript", HOME_ADAPTER_JS.encode("utf-8")
    if name == "storage-guard.js":
        return "application/javascript", STORAGE_GUARD_JS.encode("utf-8")
    if name in _HOME_FILES:
        relative, mime = _HOME_FILES[name]
        with open(shared_path(relative), "rb") as handle:
            return mime, handle.read()
    return None


ICON_SHAPES = {
    "back": '<polyline points="15 18 9 12 15 6"/>',
    "forward": '<polyline points="9 18 15 12 9 6"/>',
    "reload": '<path d="M20 12a8 8 0 1 1-2.34-5.66"/><polyline points="20 4 20 9 15 9"/>',
    "stop": '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
    "home": '<path d="M4 11.5 12 4.5l8 7"/><path d="M6.5 10v9.5h11V10"/>',
    "star": '<polygon points="12 3.5 14.6 9 20.5 9.6 16 13.6 17.3 19.5 12 16.5 6.7 19.5 8 13.6 3.5 9.6 9.4 9"/>',
    "download": '<path d="M12 4v11"/><polyline points="7 10.5 12 15.5 17 10.5"/><path d="M5 19.5h14"/>',
    "menu": '<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "up": '<polyline points="6 15 12 9 18 15"/>',
    "down": '<polyline points="6 9 12 15 18 9"/>',
    "close": '<line x1="7" y1="7" x2="17" y2="17"/><line x1="17" y1="7" x2="7" y2="17"/>',
}


def icon_svg(name: str, color: str = "#e2e8f0", fill: str = "none", size: int = 48) -> str:
    """Simple line icons (drawn for Safeer) as SVG markup."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="{fill}" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'{ICON_SHAPES[name]}</svg>')


def home_state(settings: SettingsStore) -> Dict[str, Any]:
    return {
        "language": home_language(settings.get("language")),
        "engine": settings.get("search_engine"),
        "ads": int(settings.get("total_ads_blocked") or 0),
        "threats": int(settings.get("total_threats_blocked") or 0),
        "portals": list(settings.get("custom_portals") or []),
    }


# ---------------------------------------------------------------------------
# Favourite sites and bookmark import
# ---------------------------------------------------------------------------

def make_portal(title: str, url: str) -> Optional[Dict[str, Any]]:
    kind, resolved = resolve_input(url, tracking_protection=False)
    if kind != "url" or not resolved.startswith(("http://", "https://")):
        return None
    item = bookmarks.build_portal_item(resolved, title or "")
    if not item:
        return None
    item["id"] = "p_" + uuid.uuid4().hex[:8]
    return item


def _normalized(url: str) -> str:
    return re.sub(r"/+$", "", (url or "").strip()).lower()


def merge_portals(existing: List[Dict[str, Any]], incoming: Iterable[Dict[str, Any]], limit: int = 60) -> Tuple[List[Dict[str, Any]], int]:
    merged = list(existing)
    seen = {_normalized(p.get("url", "")) for p in merged}
    added = 0
    for item in incoming:
        key = _normalized(item.get("url", ""))
        if not key or key in seen or len(merged) >= limit:
            continue
        entry = dict(item)
        entry.setdefault("id", "p_" + uuid.uuid4().hex[:8])
        merged.append(entry)
        seen.add(key)
        added += 1
    return merged, added


def windows_bookmark_sources(env: Optional[Dict[str, str]] = None) -> Dict[str, List[str]]:
    env = dict(os.environ if env is None else env)
    local = env.get("LOCALAPPDATA", "")
    roaming = env.get("APPDATA", "")
    chromium = {
        "Google Chrome": (local, ("Google", "Chrome", "User Data")),
        "Microsoft Edge": (local, ("Microsoft", "Edge", "User Data")),
        "Brave": (local, ("BraveSoftware", "Brave-Browser", "User Data")),
        "Vivaldi": (local, ("Vivaldi", "User Data")),
        "Opera": (roaming, ("Opera Software", "Opera Stable")),
    }
    sources: Dict[str, List[str]] = {}
    for name, (root, parts) in chromium.items():
        if not root:
            continue
        base = os.path.join(root, *parts)
        files = sorted(set(glob.glob(os.path.join(base, "*", "Bookmarks")) + glob.glob(os.path.join(base, "Bookmarks"))))
        if files:
            sources[name] = files
    if roaming:
        firefox = sorted(glob.glob(os.path.join(roaming, "Mozilla", "Firefox", "Profiles", "*", "places.sqlite")))
        if firefox:
            sources["Firefox"] = firefox
    return sources


def read_firefox_bookmarks(places: str) -> List[Dict[str, Any]]:
    """Reads a copy of places.sqlite (Firefox keeps the original locked while running)."""
    workdir = tempfile.mkdtemp(prefix="safeer-firefox-")
    items: List[Dict[str, Any]] = []
    try:
        copy_path = os.path.join(workdir, "places.sqlite")
        shutil.copyfile(places, copy_path)
        for suffix in ("-wal", "-shm"):
            if os.path.exists(places + suffix):
                shutil.copyfile(places + suffix, copy_path + suffix)
        connection = sqlite3.connect(copy_path)
        try:
            rows = connection.execute(
                "SELECT b.title, p.url, f.title FROM moz_bookmarks b JOIN moz_places p ON b.fk = p.id "
                "LEFT JOIN moz_bookmarks f ON b.parent = f.id WHERE b.type = 1 AND p.url LIKE 'http%' "
                "ORDER BY b.dateAdded DESC"
            ).fetchall()
        finally:
            connection.close()
        for title, url, folder in rows:
            item = bookmarks.build_portal_item(url or "", title or "", folder or "")
            if item:
                items.append(item)
    except (OSError, sqlite3.Error):
        return []
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return items


def import_windows_bookmarks(env: Optional[Dict[str, str]] = None) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    collected: List[Dict[str, Any]] = []
    stats: Dict[str, int] = {}
    for browser, files in windows_bookmark_sources(env).items():
        found: List[Dict[str, Any]] = []
        for path in files:
            if browser == "Firefox":
                found.extend(read_firefox_bookmarks(path))
            else:
                found.extend(bookmarks.import_from_chromium_profiles(path))
        if found:
            stats[browser] = len(found)
            collected.extend(found)
    unique, _ = merge_portals([], collected, limit=10000)
    return unique, stats


def file_url_to_path(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(parsed.path)
    if re.match(r"^/[a-zA-Z]:", path):
        return ntpath.normpath(path[1:])
    return path
