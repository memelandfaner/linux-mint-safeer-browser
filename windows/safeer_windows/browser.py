"""Safeer Browser for Windows: Qt WebEngine (Chromium) user interface."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional

from PySide6.QtCore import (QBuffer, QByteArray, QCoreApplication, QEvent, QIODevice, QObject, QSize, QStandardPaths,
                            Qt, QTimer, QUrl)
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWebEngineCore import (QWebEngineDownloadRequest, QWebEnginePage, QWebEngineProfile, QWebEngineScript,
                                     QWebEngineSettings, QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor,
                                     QWebEngineUrlRequestJob, QWebEngineUrlScheme, QWebEngineUrlSchemeHandler)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QMessageBox, QPushButton, QTabBar, QTabWidget, QToolBar,
                               QToolButton, QVBoxLayout, QWidget)

from . import policy

TEXT: Dict[str, Dict[str, str]] = {
    "sl": {
        "address": "Išči ali vpiši spletni naslov",
        "new_tab": "Nov zavihek", "new_window": "Novo okno", "private_window": "Novo zasebno okno",
        "private": "Zasebno", "back": "Nazaj", "forward": "Naprej", "reload": "Osveži", "stop": "Ustavi",
        "home": "Domača stran", "add_home": "Dodaj stran na domačo stran", "added_home": "Stran je dodana na domačo stran.",
        "menu": "Meni", "downloads": "Prenosi", "find": "Najdi na strani", "reader": "Bralni način",
        "zoom_in": "Povečaj", "zoom_out": "Pomanjšaj", "zoom_reset": "Običajna velikost", "fullscreen": "Celozaslonski način",
        "settings": "Nastavitve", "default_browser": "Nastavi kot privzeti brskalnik", "import": "Uvozi zaznamke",
        "clear_data": "Počisti podatke brskanja", "devtools": "Orodja za razvijalce", "about": "O brskalniku",
        "reopen_tab": "Znova odpri zaprt zavihek", "quit": "Izhod",
        "shield": "Blokirani oglasi in grožnje", "language": "Jezik", "search_engine": "Iskalnik",
        "startup": "Ob zagonu", "startup_home": "Odpri domačo stran", "startup_restore": "Obnovi zadnje zavihke",
        "adblock": "Blokiraj oglase in sledilce", "adguard": "Napredna zaščita pred anti-adblock zidovi",
        "tracking": "Odstrani sledilne parametre iz povezav", "gpc": "Pošlji signal Global Privacy Control",
        "cookies": "Blokiraj piškotke tretjih oseb", "dark": "Temni način za vse strani",
        "gpu": "Strojno pospeševanje (velja po ponovnem zagonu)",
        "dns": "Šifriran DNS (DoH)", "dns_off": "Izklopljeno (sistemski DNS)", "dns_note": "Sprememba DNS velja po ponovnem zagonu.",
        "download_location": "Vprašaj, kam shraniti prenose",
        "cleared": "Podatki brskanja so počiščeni.", "clear_confirm": "Izbrišem piškotke, predpomnilnik in zgodovino obiskov?",
        "imported": "Uvoženih strani: {count}", "import_none": "Na tem računalniku nisem našel zaznamkov Chroma, Edga, Brava, Vivaldija, Opere ali Firefoxa.",
        "find_placeholder": "Najdi…", "close": "Zapri", "open_folder": "Odpri mapo", "no_downloads": "Ni prenosov.",
        "done": "končano", "failed": "prekinjeno", "download_started": "Prenos se je začel: {name}",
        "permission": "Stran {origin} želi dostop do: {what}. Dovolim?",
        "perm_camera": "kamere", "perm_mic": "mikrofona", "perm_camera_mic": "kamere in mikrofona", "perm_screen": "zaslona",
        "perm_location": "lokacije", "perm_notifications": "obvestil", "perm_clipboard": "odložišča", "perm_other": "posebne funkcije",
        "external": "Odprem povezavo v drugem programu?\n{url}", "crashed": "Stran se je nepričakovano zaprla. Pritisni F5 za ponovno nalaganje.",
        "portal_title": "Ime strani", "portal_url": "Spletni naslov", "add_portal": "Dodaj priljubljeno stran",
        "edit_portals": "Uredi priljubljene strani", "remove": "Odstrani", "move_up": "Gor", "move_down": "Dol",
        "invalid_url": "Vpiši veljaven spletni naslov (http ali https).",
        "about_text": "Safeer Browser za Windows {version}\nQt WebEngine {qt}\n\nZaščita pred oglasi in znanimi grožnjami. Filtri ne zagotavljajo popolne zaščite.",
        "default_help": "Windows odpre nastavitve privzetih aplikacij. Izberi Safeer Browser za HTTP, HTTPS in datoteke .html.",
    },
    "en": {
        "address": "Search or enter web address",
        "new_tab": "New tab", "new_window": "New window", "private_window": "New private window",
        "private": "Private", "back": "Back", "forward": "Forward", "reload": "Reload", "stop": "Stop",
        "home": "Home", "add_home": "Add page to the start page", "added_home": "Page added to the start page.",
        "menu": "Menu", "downloads": "Downloads", "find": "Find on page", "reader": "Reader mode",
        "zoom_in": "Zoom in", "zoom_out": "Zoom out", "zoom_reset": "Actual size", "fullscreen": "Full screen",
        "settings": "Settings", "default_browser": "Make default browser", "import": "Import bookmarks",
        "clear_data": "Clear browsing data", "devtools": "Developer tools", "about": "About",
        "reopen_tab": "Reopen closed tab", "quit": "Exit",
        "shield": "Blocked ads and threats", "language": "Language", "search_engine": "Search engine",
        "startup": "On startup", "startup_home": "Open the start page", "startup_restore": "Restore last tabs",
        "adblock": "Block ads and trackers", "adguard": "Advanced anti-adblock wall protection",
        "tracking": "Remove tracking parameters from links", "gpc": "Send Global Privacy Control",
        "cookies": "Block third-party cookies", "dark": "Dark mode for all pages",
        "gpu": "Hardware acceleration (after restart)",
        "dns": "Encrypted DNS (DoH)", "dns_off": "Off (system DNS)", "dns_note": "DNS changes apply after a restart.",
        "download_location": "Ask where to save downloads",
        "cleared": "Browsing data cleared.", "clear_confirm": "Delete cookies, cache and visited links?",
        "imported": "Imported sites: {count}", "import_none": "No Chrome, Edge, Brave, Vivaldi, Opera or Firefox bookmarks were found on this computer.",
        "find_placeholder": "Find…", "close": "Close", "open_folder": "Open folder", "no_downloads": "No downloads.",
        "done": "done", "failed": "interrupted", "download_started": "Download started: {name}",
        "permission": "{origin} wants to use your {what}. Allow?",
        "perm_camera": "camera", "perm_mic": "microphone", "perm_camera_mic": "camera and microphone", "perm_screen": "screen",
        "perm_location": "location", "perm_notifications": "notifications", "perm_clipboard": "clipboard", "perm_other": "special feature",
        "external": "Open this link in another application?\n{url}", "crashed": "The page stopped unexpectedly. Press F5 to reload.",
        "portal_title": "Site name", "portal_url": "Web address", "add_portal": "Add favourite site",
        "edit_portals": "Edit favourite sites", "remove": "Remove", "move_up": "Up", "move_down": "Down",
        "invalid_url": "Enter a valid web address (http or https).",
        "about_text": "Safeer Browser for Windows {version}\nQt WebEngine {qt}\n\nProtection against ads and known threats. Filters are not a complete guarantee.",
        "default_help": "Windows opens Default apps. Choose Safeer Browser for HTTP, HTTPS and .html files.",
    },
}

STYLE = """
QMainWindow, QWidget#chrome { background: #101814; color: #f1f5f9; }
QToolBar { background: #101814; border: 0; padding: 4px 6px; spacing: 4px; }
QToolButton { color: #e2e8f0; background: transparent; border: 1px solid transparent; border-radius: 8px;
              padding: 3px 8px; font-size: 16px; min-width: 22px; }
QToolButton:hover { background: #1f2d26; border-color: #2f4238; }
QToolButton:disabled { color: #4b5b52; }
QToolButton::menu-indicator { image: none; }
QLineEdit#address { background: #19241e; color: #f8fafc; border: 1px solid #2f4238; border-radius: 16px;
                    padding: 6px 14px; font-size: 14px; selection-background-color: #4b7d2a; }
QLineEdit#address:focus { border-color: #87cf3e; }
QLabel#shield { color: #9bd478; padding: 0 8px; font-weight: 600; }
QTabWidget::pane { border: 0; }
QTabBar { background: #0b120e; }
QTabBar::tab { background: #0b120e; color: #adbbb2; padding: 7px 12px; border: 0; min-width: 110px; max-width: 220px; }
QTabBar::tab:selected { background: #19241e; color: #f8fafc; border-top: 2px solid #87cf3e; }
QTabBar::tab:hover:!selected { background: #141e18; }
QTabBar::close-button { subcontrol-position: right; padding: 2px; border-radius: 4px; }
QTabBar::close-button:hover { background: #2f4238; }
QWidget#findbar { background: #19241e; border-top: 1px solid #2f4238; }
QWidget#findbar QLineEdit { background: #101814; color: #f1f5f9; border: 1px solid #2f4238; border-radius: 8px; padding: 4px 8px; }
QStatusBar { background: #0b120e; color: #adbbb2; }
QMenu { background: #19241e; color: #f1f5f9; border: 1px solid #2f4238; }
QMenu::item:selected { background: #2f4238; }
QDialog { background: #101814; color: #f1f5f9; }
QDialog QLabel, QDialog QCheckBox { color: #f1f5f9; }
QComboBox, QListWidget, QDialog QLineEdit { background: #19241e; color: #f1f5f9; border: 1px solid #2f4238; border-radius: 6px; padding: 4px; }
QPushButton { background: #19241e; color: #f1f5f9; border: 1px solid #50616b; border-radius: 8px; padding: 6px 14px; }
QPushButton:hover { background: #20312d; border-color: #6b7c86; }
QPushButton:default { background: #9bd478; color: #0b120e; border-color: #9bd478; }
"""


def make_icon(name: str, color: str = "#e2e8f0", fill: str = "none") -> QIcon:
    icon = QIcon()
    for mode, stroke in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, "#4b5b52")):
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(policy.icon_svg(name, stroke, fill if mode == QIcon.Mode.Normal else "none").encode("utf-8")), "SVG")
        if not pixmap.isNull():
            icon.addPixmap(pixmap, mode)
    return icon


def tab_close_style() -> str:
    folder = os.path.join(policy.data_dir(), "ui")
    try:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "tab-close.svg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(policy.icon_svg("close", "#adbbb2", size=16))
    except OSError:
        return ""
    return 'QTabBar::close-button { image: url("%s"); }\n' % path.replace("\\", "/")


def tr(browser: "SafeerBrowserApp", key: str, **values: Any) -> str:
    text = TEXT.get(browser.lang, TEXT["en"]).get(key) or TEXT["en"].get(key, key)
    return text.format(**values) if values else text


# ---------------------------------------------------------------------------
# WebEngine plumbing
# ---------------------------------------------------------------------------

def register_schemes() -> None:
    scheme = QWebEngineUrlScheme(QByteArray(b"safeer"))
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    # Secure but not local: the start page may show remote favicons; host actions are only
    # accepted while the top-level page itself is safeer://home.
    scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme)
    QWebEngineUrlScheme.registerScheme(scheme)


def apply_dns_mode(settings: policy.SettingsStore) -> str:
    template = policy.doh_template(settings)
    if not template:
        return "system"
    try:
        from PySide6.QtWebEngineCore import QWebEngineGlobalSettings
    except ImportError:
        return "unavailable"
    try:
        mode = QWebEngineGlobalSettings.DnsMode()
        mode.secureMode = QWebEngineGlobalSettings.SecureDnsMode.SecureOnly
        mode.serverTemplates = [template]
        result = QWebEngineGlobalSettings.setDnsMode(mode)
        if result is False:
            return "rejected"
        return "secure-only:" + template
    except Exception as error:  # pragma: no cover - depends on the Qt build
        return f"error:{type(error).__name__}:{error}"


class SafeerSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, browser: "SafeerBrowserApp"):
        super().__init__(browser)
        self.browser = browser

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:
        url = job.requestUrl()
        try:
            query = url.query(QUrl.ComponentFormattingOption.FullyEncoded)
            result = policy.scheme_resource(url.host(), url.path(), query, self.browser.lang)
        except OSError:
            result = None
        if result is None:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        mime, data = result
        buffer = QBuffer(job)
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(QByteArray(mime.encode("ascii")), buffer)


class ShieldInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, browser: "SafeerBrowserApp"):
        super().__init__(browser)
        self.browser = browser

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        url = info.requestUrl().toString()
        is_main = info.resourceType() == QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame
        decision = policy.request_decision(url, is_main, info.firstPartyUrl().toString(),
                                           bool(self.browser.settings.get("adblock_enabled")))
        if decision != "allow":
            info.block(True)
            self.browser.note_blocked(url, decision)
            return
        if self.browser.settings.get("gpc_dnt_enabled") and url.startswith(("http://", "https://")):
            info.setHttpHeader(QByteArray(b"Sec-GPC"), QByteArray(b"1"))
            info.setHttpHeader(QByteArray(b"DNT"), QByteArray(b"1"))


class SafeerPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, window: "BrowserWindow", parent: QObject):
        super().__init__(profile, parent)
        self.window_ref = window
        self.opened_as_popup = False
        self.committed_navigation = False

    def acceptNavigationRequest(self, url: QUrl, nav_type: QWebEnginePage.NavigationType, is_main_frame: bool) -> bool:
        return self.window_ref.accept_navigation(self, url, nav_type, is_main_frame)

    def createWindow(self, window_type: QWebEnginePage.WebWindowType) -> Optional[QWebEnginePage]:
        return self.window_ref.create_page_for_window(self, window_type)

    # Page dialogs block the event loop; in an automated run nobody can close them.
    def javaScriptAlert(self, origin, message: str) -> None:
        if self.window_ref.app.smoke:
            print(f"[smoke] alert: {message}", flush=True)
            return
        super().javaScriptAlert(origin, message)

    def javaScriptConfirm(self, origin, message: str) -> bool:
        if self.window_ref.app.smoke:
            print(f"[smoke] confirm declined: {message}", flush=True)
            return False
        return super().javaScriptConfirm(origin, message)

    def javaScriptPrompt(self, origin, message: str, default: str):
        if self.window_ref.app.smoke:
            print(f"[smoke] prompt declined: {message}", flush=True)
            return False, ""
        return super().javaScriptPrompt(origin, message, default)

    def javaScriptConsoleMessage(self, level, message: str, line: int, source: str) -> None:
        if message.startswith(policy.BRIDGE_PREFIX):
            payload = policy.parse_bridge_message(message)
            if payload is not None:
                self.window_ref.app.on_bridge_message(self, payload)


class Tabs(QTabWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setTabBar(TabBar(self))


class TabBar(QTabBar):
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            index = self.tabAt(event.position().toPoint())
            if index >= 0:
                self.tabCloseRequested.emit(index)
                return
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class SafeerBrowserApp(QObject):
    def __init__(self, qt_app: QApplication, settings: policy.SettingsStore, dns_status: str, smoke: bool = False):
        super().__init__()
        self.qt_app = qt_app
        self.settings = settings
        self.dns_status = dns_status
        self.smoke = smoke
        self.lang = policy.ui_language(settings.get("language"))
        self.windows: List[BrowserWindow] = []
        self.downloads: List[QWebEngineDownloadRequest] = []
        self.blocked_log: List[Dict[str, str]] = []
        self.closed_tabs: List[str] = []
        self.cookie_filter_status = "not-set"
        self.server: Optional[QLocalServer] = None
        self._counter_dirty = False
        self.download_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation) \
            or os.path.join(os.path.expanduser("~"), "Downloads")

        self.scheme_handler = SafeerSchemeHandler(self)
        self.interceptor = ShieldInterceptor(self)
        self.profile = QWebEngineProfile("SafeerBrowser", self)
        storage = policy.profile_dir()
        self.profile.setPersistentStoragePath(storage)
        self.profile.setCachePath(os.path.join(storage, "Cache"))
        self.private_profile: Optional[QWebEngineProfile] = None
        self.configure_profile(self.profile)

        # Signed Safeer threat feed: an extra, verified layer next to the built-in list.
        self.threat_intel = policy.threat_intel.ThreatIntelService(policy.threat_intel_dir())
        policy.adblock.register_threat_matcher(self.threat_intel.match)
        if not smoke:
            self.threat_intel.start()

        self.save_timer = QTimer(self)
        self.save_timer.setInterval(4000)
        self.save_timer.timeout.connect(self.flush_counters)
        self.save_timer.start()
        qt_app.setStyleSheet(STYLE + tab_close_style())
        self.icons = {name: make_icon(name) for name in policy.ICON_SHAPES}
        self.icons["star_filled"] = make_icon("star", "#9bd478", "#9bd478")
        icon_path = self.icon_path()
        if icon_path:
            qt_app.setWindowIcon(QIcon(icon_path))

    # -- profiles -----------------------------------------------------------
    @staticmethod
    def icon_path() -> str:
        try:
            return policy.shared_path("assets/icon.png")
        except FileNotFoundError:
            return ""

    def configure_profile(self, profile: QWebEngineProfile) -> None:
        profile.setHttpUserAgent(policy.clean_user_agent(profile.httpUserAgent()))
        profile.installUrlSchemeHandler(QByteArray(b"safeer"), self.scheme_handler)
        profile.setUrlRequestInterceptor(self.interceptor)
        profile.setDownloadPath(self.download_dir)
        profile.downloadRequested.connect(self.on_download_requested)
        settings = profile.settings()
        attr = QWebEngineSettings.WebAttribute
        settings.setAttribute(attr.FullScreenSupportEnabled, True)
        settings.setAttribute(attr.JavascriptCanOpenWindows, False)
        settings.setAttribute(attr.PluginsEnabled, False)
        settings.setAttribute(attr.PdfViewerEnabled, True)
        settings.setAttribute(attr.ScrollAnimatorEnabled, True)
        settings.setAttribute(attr.FocusOnNavigationEnabled, True)
        settings.setAttribute(attr.LocalContentCanAccessRemoteUrls, False)
        self.apply_profile_preferences(profile)
        self.install_cookie_filter(profile)

    def apply_profile_preferences(self, profile: QWebEngineProfile) -> None:
        dark = getattr(QWebEngineSettings.WebAttribute, "ForceDarkMode", None)
        if dark is not None:
            profile.settings().setAttribute(dark, bool(self.settings.get("force_dark_mode")))
        scripts = profile.scripts()
        scripts.clear()
        for spec in policy.script_specs(self.settings):
            script = QWebEngineScript()
            script.setName(spec["name"])
            script.setSourceCode(spec["source"])
            script.setWorldId(0)  # QWebEngineScript.MainWorld
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation if spec["at_start"]
                                     else QWebEngineScript.InjectionPoint.DocumentReady)
            script.setRunsOnSubFrames(bool(spec["all_frames"]))
            scripts.insert(script)

    def install_cookie_filter(self, profile: QWebEngineProfile) -> None:
        def cookie_filter(request) -> bool:
            try:
                if not self.settings.get("block_third_party_cookies") or not request.thirdParty:
                    return True
                return policy.third_party_cookie_allowed(request.origin.host())
            except Exception:
                return True

        try:
            profile.cookieStore().setCookieFilter(cookie_filter)
            self.cookie_filter_status = "active"
        except (AttributeError, TypeError) as error:
            self.cookie_filter_status = f"unavailable:{error}"

    def get_private_profile(self) -> QWebEngineProfile:
        if self.private_profile is None:
            self.private_profile = QWebEngineProfile(self)
            self.configure_profile(self.private_profile)
        return self.private_profile

    def refresh_preferences(self) -> None:
        self.lang = policy.ui_language(self.settings.get("language"))
        for profile in filter(None, (self.profile, self.private_profile)):
            self.apply_profile_preferences(profile)
        for window in self.windows:
            window.retranslate()
            window.refresh_home_tabs()

    # -- windows ------------------------------------------------------------
    def new_window(self, urls: Optional[List[str]] = None, private: bool = False, restore: bool = False) -> "BrowserWindow":
        window = BrowserWindow(self, private=private)
        self.windows.append(window)
        opened = False
        if restore and not private and self.settings.get("startup") == "restore":
            for url in self.settings.get("last_session") or []:
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    window.new_tab(url, switch=not opened)
                    opened = True
        for url in urls or []:
            window.open_input(url, new_tab=True)
            opened = True
        if not opened:
            window.new_tab(policy.HOME_URL)
        geometry = self.settings.get("window_geometry")
        if geometry and not private and len(self.windows) == 1:
            window.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
        else:
            window.resize(1280, 820)
        window.show()
        return window

    def window_closed(self, window: "BrowserWindow") -> None:
        if window in self.windows:
            if not window.private and len([w for w in self.windows if not w.private]) == 1:
                self.settings.set("window_geometry", bytes(window.saveGeometry().toBase64()).decode("ascii"), save=False)
                self.settings.set("last_session", window.session_urls(), save=False)
                self.settings.save()
            self.windows.remove(window)

    def active_window(self) -> Optional["BrowserWindow"]:
        active = QApplication.activeWindow()
        for window in self.windows:
            if window is active:
                return window
        return self.windows[-1] if self.windows else None

    # -- single instance ----------------------------------------------------
    @staticmethod
    def server_name() -> str:
        try:
            user = getpass.getuser()
        except Exception:
            user = "user"
        return "SafeerBrowser-" + re.sub(r"[^A-Za-z0-9_.-]", "_", user)

    @classmethod
    def forward_to_running_instance(cls, urls: List[str]) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(cls.server_name())
        if not socket.waitForConnected(400):
            return False
        socket.write(QByteArray(json.dumps({"urls": urls}).encode("utf-8") + b"\n"))
        socket.waitForBytesWritten(1500)
        socket.disconnectFromServer()
        return True

    def start_instance_server(self) -> None:
        QLocalServer.removeServer(self.server_name())
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.on_instance_connection)
        self.server.listen(self.server_name())

    def on_instance_connection(self) -> None:
        while self.server is not None and self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.readyRead.connect(lambda s=socket: self.on_instance_data(s))

    def on_instance_data(self, socket: QLocalSocket) -> None:
        raw = bytes(socket.readAll()).decode("utf-8", "replace")
        socket.disconnectFromServer()
        try:
            urls = json.loads(raw.strip().splitlines()[0]).get("urls", [])
        except (ValueError, IndexError, AttributeError):
            urls = []
        window = self.active_window()
        if window is None:
            self.new_window(urls)
            return
        for url in urls:
            window.open_input(url, new_tab=True)
        if not urls:
            window.new_tab(policy.HOME_URL)
        window.setWindowState((window.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        window.raise_()
        window.activateWindow()

    # -- shield counters ----------------------------------------------------
    def note_blocked(self, url: str, decision: str) -> None:
        key = "total_threats_blocked" if decision == "block-threat" else "total_ads_blocked"
        self.settings.set(key, int(self.settings.get(key) or 0) + 1, save=False)
        self._counter_dirty = True
        self.blocked_log.append({"url": url, "decision": decision})
        del self.blocked_log[:-500]
        for window in self.windows:
            window.update_shield()

    def flush_counters(self) -> None:
        if self._counter_dirty:
            self._counter_dirty = False
            self.settings.save()

    # -- start page bridge --------------------------------------------------
    def on_bridge_message(self, page: SafeerPage, payload: Dict[str, Any]) -> None:
        action = payload.get("action")
        if action == "increment_ads":
            try:
                count = max(0, min(int(payload.get("count", 1)), 50))
            except (TypeError, ValueError):
                count = 0
            if count:
                self.settings.set("total_ads_blocked", int(self.settings.get("total_ads_blocked") or 0) + count, save=False)
                self._counter_dirty = True
            return
        if page.url().scheme() != "safeer":
            return
        window = page.window_ref
        if action == "navigate":
            window.open_input(str(payload.get("url") or ""), page=page)
        elif action == "set_language":
            language = str(payload.get("language") or "")
            if language in ("sl", "en", "de", "es", "fr", "it"):
                self.settings.set("language", language)
                self.refresh_preferences()
        elif action == "set_default_browser":
            window.make_default_browser()
        elif action == "open_sidebar":
            service = payload.get("service")
            targets = {"messenger": "https://www.messenger.com", "gmail": "https://mail.google.com/mail/"}
            if service in targets:
                window.new_tab(targets[service])
            elif service in ("settings", "customizer"):
                window.open_settings()
            elif service == "import_bookmarks":
                window.import_bookmarks()
            elif service == "edit_portals":
                window.edit_portals()
            elif service == "add_portal":
                window.add_portal_dialog()

    # -- downloads ----------------------------------------------------------
    def on_download_requested(self, download: QWebEngineDownloadRequest) -> None:
        window = self.active_window()
        directory = download.downloadDirectory() or self.download_dir
        name = policy.unique_filename(directory, download.downloadFileName())
        if self.settings.get("ask_download_location") and not self.smoke and window is not None:
            from PySide6.QtWidgets import QFileDialog
            chosen, _ = QFileDialog.getSaveFileName(window, tr(self, "downloads"), os.path.join(directory, name))
            if not chosen:
                download.cancel()
                return
            directory, name = os.path.dirname(chosen), os.path.basename(chosen)
        download.setDownloadDirectory(directory)
        download.setDownloadFileName(name)
        download.accept()
        self.downloads.append(download)
        if window is not None:
            window.statusBar().showMessage(tr(self, "download_started", name=name), 5000)
            window.close_empty_popup(download)

    # -- shutdown -----------------------------------------------------------
    def shutdown(self) -> None:
        self.threat_intel.stop()
        self.flush_counters()
        self.settings.save()
        for window in list(self.windows):
            window.dispose_tabs()
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        for profile in filter(None, (self.private_profile, self.profile)):
            profile.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class BrowserWindow(QMainWindow):
    def __init__(self, app: SafeerBrowserApp, private: bool = False):
        super().__init__()
        self.app = app
        self.private = private
        self.profile = app.get_private_profile() if private else app.profile
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.devtools: Optional[QWebEngineView] = None
        self.find_text = ""

        self.tabs = Tabs(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_current_changed)
        self.new_tab_button = QToolButton(self)
        self.new_tab_button.setIcon(app.icons["plus"])
        self.new_tab_button.clicked.connect(lambda: self.new_tab(policy.HOME_URL))
        self.tabs.setCornerWidget(self.new_tab_button, Qt.Corner.TopRightCorner)

        self.toolbar = QToolBar(self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self.back_button = self._tool("back", lambda: self.current_view() and self.current_view().back())
        self.forward_button = self._tool("forward", lambda: self.current_view() and self.current_view().forward())
        self.reload_button = self._tool("reload", self.reload_or_stop)
        self.home_button = self._tool("home", lambda: self.load_in_current(policy.HOME_URL))
        self.address = QLineEdit(self)
        self.address.setObjectName("address")
        self.address.setClearButtonEnabled(True)
        self.address.returnPressed.connect(lambda: self.open_input(self.address.text()))
        self.toolbar.addWidget(self.address)
        self.shield_label = QLabel(self)
        self.shield_label.setObjectName("shield")
        self.toolbar.addWidget(self.shield_label)
        self.star_button = self._tool("star", self.add_current_to_home)
        self.downloads_button = self._tool("download", self.show_downloads)
        self.menu_button = QToolButton(self)
        self.menu_button.setIcon(app.icons["menu"])
        self.menu_button.setIconSize(QSize(18, 18))
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu = QMenu(self)
        self.menu_button.setMenu(self.menu)
        self.toolbar.addWidget(self.menu_button)

        self.find_bar = self._build_find_bar()
        container = QWidget(self)
        container.setObjectName("chrome")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        layout.addWidget(self.find_bar)
        self.setCentralWidget(container)
        self.statusBar().setSizeGripEnabled(False)
        self._install_shortcuts()
        self.retranslate()
        self.update_shield()

    # -- construction helpers ---------------------------------------------
    def _tool(self, icon: str, callback) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(self.app.icons[icon])
        button.setIconSize(QSize(18, 18))
        button.clicked.connect(callback)
        self.toolbar.addWidget(button)
        return button

    def _build_find_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("findbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 4, 8, 4)
        self.find_input = QLineEdit(bar)
        self.find_input.textChanged.connect(lambda text: self.find(text))
        self.find_input.returnPressed.connect(lambda: self.find(self.find_input.text()))
        previous = QToolButton(bar)
        previous.setIcon(self.app.icons["up"])
        previous.clicked.connect(lambda: self.find(self.find_input.text(), backward=True))
        following = QToolButton(bar)
        following.setIcon(self.app.icons["down"])
        following.clicked.connect(lambda: self.find(self.find_input.text()))
        close = QToolButton(bar)
        close.setIcon(self.app.icons["close"])
        close.clicked.connect(self.hide_find)
        row.addWidget(self.find_input, 1)
        row.addWidget(previous)
        row.addWidget(following)
        row.addWidget(close)
        bar.hide()
        return bar

    def _install_shortcuts(self) -> None:
        bindings = [
            ("Ctrl+T", lambda: self.new_tab(policy.HOME_URL)),
            ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+F4", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+Shift+T", self.reopen_closed_tab),
            ("Ctrl+N", lambda: self.app.new_window()),
            ("Ctrl+Shift+N", lambda: self.app.new_window(private=True)),
            ("Ctrl+L", self.focus_address), ("F6", self.focus_address), ("Alt+D", self.focus_address),
            ("Ctrl+R", self.reload), ("F5", self.reload),
            ("Ctrl+Shift+R", lambda: self.current_view() and self.current_view().page().triggerAction(QWebEnginePage.WebAction.ReloadAndBypassCache)),
            ("Ctrl+F", self.show_find),
            ("Ctrl+Tab", lambda: self.cycle_tab(1)), ("Ctrl+Shift+Tab", lambda: self.cycle_tab(-1)),
            ("Ctrl+PgDown", lambda: self.cycle_tab(1)), ("Ctrl+PgUp", lambda: self.cycle_tab(-1)),
            ("Alt+Left", lambda: self.current_view() and self.current_view().back()),
            ("Alt+Right", lambda: self.current_view() and self.current_view().forward()),
            ("Alt+Home", lambda: self.load_in_current(policy.HOME_URL)),
            ("Ctrl+D", self.add_current_to_home), ("Ctrl+J", self.show_downloads),
            ("Ctrl++", lambda: self.zoom(0.1)), ("Ctrl+=", lambda: self.zoom(0.1)),
            ("Ctrl+-", lambda: self.zoom(-0.1)), ("Ctrl+0", lambda: self.zoom(0)),
            ("F11", self.toggle_fullscreen), ("F12", self.toggle_devtools), ("Ctrl+Shift+I", self.toggle_devtools),
        ]
        for index in range(1, 9):
            bindings.append((f"Ctrl+{index}", lambda i=index: self.tabs.setCurrentIndex(min(i, self.tabs.count()) - 1)))
        bindings.append(("Ctrl+9", lambda: self.tabs.setCurrentIndex(self.tabs.count() - 1)))
        escape = QShortcut(QKeySequence("Escape"), self.find_input)
        escape.setContext(Qt.ShortcutContext.WidgetShortcut)
        escape.activated.connect(self.hide_find)
        self._shortcuts = [escape]
        for sequence, callback in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def retranslate(self) -> None:
        app = self.app
        self.setWindowTitle(policy.APP_NAME + (f" — {tr(app, 'private')}" if self.private else ""))
        self.address.setPlaceholderText(tr(app, "address"))
        for button, key in ((self.back_button, "back"), (self.forward_button, "forward"), (self.reload_button, "reload"),
                            (self.home_button, "home"), (self.star_button, "add_home"),
                            (self.downloads_button, "downloads"), (self.menu_button, "menu"), (self.new_tab_button, "new_tab")):
            button.setToolTip(tr(app, key))
        self.shield_label.setToolTip(tr(app, "shield"))
        self.find_input.setPlaceholderText(tr(app, "find_placeholder"))
        self.menu.clear()
        entries = [
            ("new_tab", "Ctrl+T", lambda: self.new_tab(policy.HOME_URL)),
            ("new_window", "Ctrl+N", lambda: self.app.new_window()),
            ("private_window", "Ctrl+Shift+N", lambda: self.app.new_window(private=True)),
            ("reopen_tab", "Ctrl+Shift+T", self.reopen_closed_tab),
            None,
            ("downloads", "Ctrl+J", self.show_downloads),
            ("find", "Ctrl+F", self.show_find),
            ("reader", "", self.reader_mode),
            ("zoom_in", "Ctrl++", lambda: self.zoom(0.1)),
            ("zoom_out", "Ctrl+-", lambda: self.zoom(-0.1)),
            ("zoom_reset", "Ctrl+0", lambda: self.zoom(0)),
            ("fullscreen", "F11", self.toggle_fullscreen),
            None,
            ("import", "", self.import_bookmarks),
            ("clear_data", "", self.clear_browsing_data),
            ("default_browser", "", self.make_default_browser),
            ("settings", "", self.open_settings),
            ("devtools", "F12", self.toggle_devtools),
            ("about", "", self.show_about),
            None,
            ("quit", "", self.app.qt_app.closeAllWindows),
        ]
        for entry in entries:
            if entry is None:
                self.menu.addSeparator()
                continue
            key, shortcut, callback = entry
            action = QAction(tr(app, key) + (f"\t{shortcut}" if shortcut else ""), self.menu)
            action.triggered.connect(callback)
            self.menu.addAction(action)
        self.update_nav_state()

    # -- tabs -----------------------------------------------------------------
    def current_view(self) -> Optional[QWebEngineView]:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, QWebEngineView) else None

    def views(self) -> List[QWebEngineView]:
        return [self.tabs.widget(i) for i in range(self.tabs.count()) if isinstance(self.tabs.widget(i), QWebEngineView)]

    def create_view(self) -> QWebEngineView:
        view = QWebEngineView(self.tabs)
        page = SafeerPage(self.profile, self, view)
        view.setPage(page)
        view.titleChanged.connect(lambda title, v=view: self.on_title_changed(v, title))
        view.iconChanged.connect(lambda icon, v=view: self.tabs.setTabIcon(self.tabs.indexOf(v), icon))
        view.urlChanged.connect(lambda url, v=view: self.on_url_changed(v, url))
        view.loadStarted.connect(lambda v=view: self.on_load_state(v, True))
        view.loadFinished.connect(lambda ok, v=view: self.on_load_finished(v, ok))
        page.linkHovered.connect(lambda url: self.statusBar().showMessage(url, 4000) if url else self.statusBar().clearMessage())
        page.fullScreenRequested.connect(self.on_fullscreen_request)
        page.renderProcessTerminated.connect(lambda status, code, v=view: self.on_render_terminated(v, status, code))
        page.windowCloseRequested.connect(lambda v=view: self.close_tab(self.tabs.indexOf(v)))
        if hasattr(page, "permissionRequested"):
            page.permissionRequested.connect(lambda permission, p=page: self.on_permission(p, permission))
        else:  # Qt < 6.8
            page.featurePermissionRequested.connect(lambda origin, feature, p=page: self.on_feature_permission(p, origin, feature))
        return view

    def new_tab(self, url: str = policy.HOME_URL, switch: bool = True, after_current: bool = False) -> QWebEngineView:
        view = self.create_view()
        index = self.tabs.currentIndex() + 1 if after_current and self.tabs.count() else self.tabs.count()
        self.tabs.insertTab(index, view, tr(self.app, "new_tab"))
        if switch:
            self.tabs.setCurrentIndex(index)
        if url:
            view.load(QUrl(url))
        if switch and url == policy.HOME_URL:
            QTimer.singleShot(0, self.focus_address)
        return view

    def close_tab(self, index: int) -> None:
        view = self.tabs.widget(index)
        if not isinstance(view, QWebEngineView):
            return
        url = view.url().toString()
        if url.startswith(("http://", "https://")) and not self.private:
            self.app.closed_tabs.append(url)
            del self.app.closed_tabs[:-25]
        if self.devtools is not None and view.page().devToolsPage() is not None:
            view.page().setDevToolsPage(None)
        self.tabs.removeTab(index)
        view.page().deleteLater()
        view.deleteLater()
        if self.tabs.count() == 0:
            self.close()

    def reopen_closed_tab(self) -> None:
        if self.app.closed_tabs:
            self.new_tab(self.app.closed_tabs.pop())

    def cycle_tab(self, step: int) -> None:
        if self.tabs.count():
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % self.tabs.count())

    def dispose_tabs(self) -> None:
        if self.devtools is not None:
            self.devtools.deleteLater()
            self.devtools = None
        while self.tabs.count():
            view = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if isinstance(view, QWebEngineView):
                view.page().deleteLater()
                view.deleteLater()

    def session_urls(self) -> List[str]:
        return [v.url().toString() for v in self.views() if v.url().scheme() in ("http", "https")]

    # -- navigation -----------------------------------------------------------
    def open_input(self, text: str, new_tab: bool = False, page: Optional[QWebEnginePage] = None) -> None:
        settings = self.app.settings
        if os.path.isabs(text or "") and os.path.exists(text):
            target, kind = QUrl.fromLocalFile(text).toString(), "url"
        else:
            kind, target = policy.resolve_input(text, settings.get("search_engine"),
                                                bool(settings.get("tracking_protection_enabled")))
        if kind == "empty":
            return
        if new_tab:
            self.new_tab(target)
            return
        if page is not None:
            page.load(QUrl(target))
        else:
            self.load_in_current(target)

    def load_in_current(self, url: str) -> None:
        view = self.current_view()
        if view is None:
            self.new_tab(url)
            return
        view.load(QUrl(url))
        view.setFocus()

    def tab_index_for_page(self, page: QWebEnginePage) -> int:
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if isinstance(view, QWebEngineView) and view.page() is page:
                return index
        return -1

    def accept_navigation(self, page: SafeerPage, url: QUrl, nav_type, is_main_frame: bool) -> bool:
        if not is_main_frame:
            return True
        text = url.toString()
        allowed = policy.navigation_scheme_allowed(text)
        if allowed == "external":
            QTimer.singleShot(0, lambda: self.confirm_external(url))
            return False
        if allowed == "deny":
            return False
        scheme = url.scheme().lower()
        if scheme == "file" and nav_type != QWebEnginePage.NavigationType.NavigationTypeTyped \
                and page.url().scheme() != "file":
            return False
        if scheme not in ("http", "https") or policy.adblock.is_passthrough_host(text):
            page.committed_navigation = True
            return True
        if policy.adblock.is_threat_domain(text):
            self.app.note_blocked(text, "block-threat")
            QTimer.singleShot(0, lambda: page.load(QUrl(policy.blocked_page_url(text))))
            return False
        bank_verdict = policy.adblock.fake_bank_verdict(text)
        if bank_verdict is not None:  # 🏦 BankGuard: the address imitates a bank
            self.app.note_blocked(text, "block-threat")
            warning = policy.fake_bank_page_url(text, bank_verdict)
            QTimer.singleShot(0, lambda: page.load(QUrl(warning)))
            return False
        if self.app.settings.get("adblock_enabled") and policy.adblock.is_ad_domain(text):
            self.app.note_blocked(text, "block-ad")
            if page.opened_as_popup and not page.committed_navigation:
                QTimer.singleShot(0, lambda: self.close_tab(self.tab_index_for_page(page)))
            return False
        if (self.app.settings.get("tracking_protection_enabled")
                and nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked):
            cleaned = policy.adblock.strip_tracking_parameters(text)
            if cleaned != text:
                QTimer.singleShot(0, lambda: page.load(QUrl(cleaned)))
                return False
        page.committed_navigation = True
        return True

    def create_page_for_window(self, opener: SafeerPage, window_type) -> QWebEnginePage:
        kind = QWebEnginePage.WebWindowType
        background = window_type == kind.WebBrowserBackgroundTab
        view = self.new_tab("", switch=not background, after_current=True)
        page = view.page()
        if isinstance(page, SafeerPage):
            page.opened_as_popup = window_type in (kind.WebDialog, kind.WebBrowserWindow)
        return page

    def close_empty_popup(self, download: QWebEngineDownloadRequest) -> None:
        page = download.page() if hasattr(download, "page") else None
        index = self.tab_index_for_page(page) if page is not None else -1
        if index >= 0 and self.tabs.count() > 1:
            view = self.tabs.widget(index)
            if isinstance(view, QWebEngineView) and not view.history().canGoBack() and view.url().isEmpty():
                QTimer.singleShot(0, lambda: self.close_tab(self.tabs.indexOf(view)))

    def confirm_external(self, url: QUrl) -> None:
        if self.app.smoke:  # an automated run has nobody to answer a modal dialog
            print(f"[smoke] external link declined: {url.toString()}", flush=True)
            return
        answer = QMessageBox.question(self, policy.APP_NAME, tr(self.app, "external", url=url.toString()))
        if answer == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(url)

    def reload(self) -> None:
        view = self.current_view()
        if view is not None:
            view.reload()

    def reload_or_stop(self) -> None:
        view = self.current_view()
        if view is None:
            return
        if view.property("loading"):
            view.stop()
        else:
            view.reload()

    def focus_address(self) -> None:
        self.address.setFocus()
        self.address.selectAll()

    # -- view events ----------------------------------------------------------
    def on_title_changed(self, view: QWebEngineView, title: str) -> None:
        index = self.tabs.indexOf(view)
        if index < 0:
            return
        url = view.url().toString()
        label = title if title and title != url else (tr(self.app, "home") if url.startswith("safeer://") else url or tr(self.app, "new_tab"))
        self.tabs.setTabText(index, label[:28] + ("…" if len(label) > 28 else ""))
        self.tabs.setTabToolTip(index, label)
        if view is self.current_view():
            self.setWindowTitle(f"{label} — {policy.APP_NAME}" + (f" ({tr(self.app, 'private')})" if self.private else ""))

    def on_url_changed(self, view: QWebEngineView, url: QUrl) -> None:
        if view is self.current_view() and not self.address.hasFocus():
            self.address.setText(policy.display_url(url.toString()))
        self.update_nav_state()

    def on_load_state(self, view: QWebEngineView, loading: bool) -> None:
        view.setProperty("loading", loading)
        if loading:
            view.setProperty("bankCheck", int(view.property("bankCheck") or 0) + 1)  # cancels a pending page check
        if view is self.current_view():
            self.reload_button.setIcon(self.app.icons["stop" if loading else "reload"])
            self.reload_button.setToolTip(tr(self.app, "stop" if loading else "reload"))

    def on_load_finished(self, view: QWebEngineView, ok: bool) -> None:
        self.on_load_state(view, False)
        if view.url().scheme() == "safeer" and view.url().path() in ("", "/"):
            self.push_home_state(view)
        if ok:
            self.schedule_fake_bank_check(view)
        self.update_nav_state()

    def schedule_fake_bank_check(self, view: QWebEngineView) -> None:
        """🏦 BankGuard: after loading, a page with password, code or card fields that presents itself as a bank
        on a foreign host gets the fake bank warning. Runs locally in an isolated script world."""
        url = view.url().toString()
        if policy.adblock.is_local_page(url):
            # an HTML file opened in the browser (an attachment saved from mail): checked by content
            if policy.adblock.is_fake_bank_host_allowed(url):
                return
        elif not url.startswith(("https://", "http://")) or policy.adblock.is_real_bank_host(url):
            return
        script = policy.adblock.bank_guard_page_script()
        if not script:
            return
        history = view.history()
        if history.canGoForward() and history.canGoBack() and \
                policy.returned_from_fake_bank_warning(history.forwardItem().url().toString(), url):
            QTimer.singleShot(0, view.back)  # Back from the warning skips the fake page instead of warning again
            return
        generation = int(view.property("bankCheck") or 0) + 1
        view.setProperty("bankCheck", generation)

        def current() -> bool:
            try:
                return int(view.property("bankCheck") or 0) == generation and view.url().toString() == url
            except RuntimeError:  # the tab was closed
                return False

        def on_signals(signals: Any) -> None:
            if not current():
                return
            verdict = policy.fake_bank_page_verdict(url, signals)
            if verdict is None:
                return
            view.setProperty("bankCheck", generation + 1)  # one warning per page
            self.app.note_blocked(url, "block-threat")
            view.load(QUrl(policy.fake_bank_page_url(url, verdict, after_load=True)))

        def run() -> None:
            if current():
                view.page().runJavaScript(script, 1, on_signals)  # 1 = QWebEngineScript.ApplicationWorld (isolated from the page)

        QTimer.singleShot(0, run)
        QTimer.singleShot(2500, run)  # pages that draw their login form later

    def push_home_state(self, view: QWebEngineView) -> None:
        state = json.dumps(policy.home_state(self.app.settings), ensure_ascii=False)
        view.page().runJavaScript(f"window.safeerWindowsInit && window.safeerWindowsInit({state});")

    def refresh_home_tabs(self) -> None:
        for view in self.views():
            if view.url().scheme() == "safeer":
                self.push_home_state(view)

    def on_current_changed(self, index: int) -> None:
        view = self.current_view()
        if view is None:
            return
        self.address.setText(policy.display_url(view.url().toString()))
        self.on_load_state(view, bool(view.property("loading")))
        self.on_title_changed(view, view.title())
        self.update_nav_state()
        if self.find_bar.isVisible():
            self.find(self.find_input.text())

    def update_nav_state(self) -> None:
        view = self.current_view()
        history = view.history() if view is not None else None
        self.back_button.setEnabled(bool(history and history.canGoBack()))
        self.forward_button.setEnabled(bool(history and history.canGoForward()))
        is_web = bool(view is not None and view.url().scheme() in ("http", "https"))
        self.star_button.setEnabled(is_web)

    def update_shield(self) -> None:
        settings = self.app.settings
        total = int(settings.get("total_ads_blocked") or 0) + int(settings.get("total_threats_blocked") or 0)
        self.shield_label.setText(f"🛡 {total:,}".replace(",", "."))

    def on_render_terminated(self, view: QWebEngineView, status, code: int) -> None:
        normal = QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus
        if status != normal:
            self.statusBar().showMessage(tr(self.app, "crashed"), 15000)

    def on_fullscreen_request(self, request) -> None:
        request.accept()
        on = request.toggleOn()
        self.toolbar.setVisible(not on)
        self.tabs.tabBar().setVisible(not on)
        self.statusBar().setVisible(not on)
        if on:
            self.showFullScreen()
        else:
            self.showNormal()

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            view = self.current_view()
            if view is not None:
                view.page().triggerAction(QWebEnginePage.WebAction.ExitFullScreen)
            self.toolbar.setVisible(True)
            self.tabs.tabBar().setVisible(True)
            self.statusBar().setVisible(True)
            self.showNormal()
        else:
            self.showFullScreen()

    # -- permissions ----------------------------------------------------------
    def _ask_permission(self, origin: str, what_key: str) -> bool:
        if self.app.smoke:
            return False
        answer = QMessageBox.question(self, policy.APP_NAME, tr(self.app, "permission", origin=origin, what=tr(self.app, what_key)))
        return answer == QMessageBox.StandardButton.Yes

    def on_permission(self, page: QWebEnginePage, permission) -> None:
        from PySide6.QtWebEngineCore import QWebEnginePermission
        kinds = QWebEnginePermission.PermissionType
        mapping = {
            getattr(kinds, "MediaAudioCapture", None): "perm_mic",
            getattr(kinds, "MediaVideoCapture", None): "perm_camera",
            getattr(kinds, "MediaAudioVideoCapture", None): "perm_camera_mic",
            getattr(kinds, "DesktopVideoCapture", None): "perm_screen",
            getattr(kinds, "DesktopAudioVideoCapture", None): "perm_screen",
            getattr(kinds, "Geolocation", None): "perm_location",
            getattr(kinds, "Notifications", None): "perm_notifications",
            getattr(kinds, "ClipboardReadWrite", None): "perm_clipboard",
        }
        what = mapping.get(permission.permissionType(), "perm_other")
        if self._ask_permission(permission.origin().host() or permission.origin().toString(), what):
            permission.grant()
        else:
            permission.deny()

    def on_feature_permission(self, page: QWebEnginePage, origin: QUrl, feature) -> None:
        features = QWebEnginePage.Feature
        mapping = {
            features.MediaAudioCapture: "perm_mic", features.MediaVideoCapture: "perm_camera",
            features.MediaAudioVideoCapture: "perm_camera_mic", features.Geolocation: "perm_location",
            features.Notifications: "perm_notifications",
        }
        granted = self._ask_permission(origin.host(), mapping.get(feature, "perm_other"))
        policy_value = QWebEnginePage.PermissionPolicy.PermissionGrantedByUser if granted \
            else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        page.setFeaturePermission(origin, feature, policy_value)

    # -- tools ----------------------------------------------------------------
    def show_find(self) -> None:
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find(self) -> None:
        self.find_bar.hide()
        view = self.current_view()
        if view is not None:
            view.page().findText("")

    def find(self, text: str, backward: bool = False) -> None:
        view = self.current_view()
        if view is None:
            return
        if backward:
            view.page().findText(text, QWebEnginePage.FindFlag.FindBackward)
        else:
            view.page().findText(text)

    def zoom(self, delta: float) -> None:
        view = self.current_view()
        if view is not None:
            view.setZoomFactor(1.0 if delta == 0 else max(0.25, min(5.0, round(view.zoomFactor() + delta, 2))))

    def reader_mode(self) -> None:
        view = self.current_view()
        if view is not None and view.url().scheme() in ("http", "https"):
            view.page().runJavaScript(policy.reader.READER_MODE_JS)

    def toggle_devtools(self) -> None:
        view = self.current_view()
        if view is None:
            return
        if self.devtools is not None and self.devtools.isVisible():
            self.devtools.close()
            return
        if self.devtools is None:
            self.devtools = QWebEngineView()
            self.devtools.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            self.devtools.setPage(QWebEnginePage(self.profile, self.devtools))
            self.devtools.resize(1000, 700)
        view.page().setDevToolsPage(self.devtools.page())
        self.devtools.setWindowTitle(f"{tr(self.app, 'devtools')} — {view.title()}")
        self.devtools.show()

    def add_current_to_home(self) -> None:
        view = self.current_view()
        if view is None or view.url().scheme() not in ("http", "https"):
            return
        portal = policy.make_portal(view.title(), view.url().toString())
        if portal is None:
            return
        portals, added = policy.merge_portals(list(self.app.settings.get("custom_portals") or []), [portal])
        if added:
            self.app.settings.set("custom_portals", portals)
            self.refresh_all_home_tabs()
        self.statusBar().showMessage(tr(self.app, "added_home"), 4000)
        self.star_button.setIcon(self.app.icons["star_filled"])
        QTimer.singleShot(1500, lambda: self.star_button.setIcon(self.app.icons["star"]))

    def refresh_all_home_tabs(self) -> None:
        for window in self.app.windows:
            window.refresh_home_tabs()

    def add_portal_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(tr(self.app, "add_portal"))
        form = QFormLayout(dialog)
        title = QLineEdit(dialog)
        address = QLineEdit(dialog)
        address.setPlaceholderText("https://")
        form.addRow(tr(self.app, "portal_title"), title)
        form.addRow(tr(self.app, "portal_url"), address)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        portal = policy.make_portal(title.text(), address.text())
        if portal is None:
            QMessageBox.warning(self, policy.APP_NAME, tr(self.app, "invalid_url"))
            return
        portals, _ = policy.merge_portals(list(self.app.settings.get("custom_portals") or []), [portal])
        self.app.settings.set("custom_portals", portals)
        self.refresh_all_home_tabs()

    def edit_portals(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(tr(self.app, "edit_portals"))
        dialog.resize(520, 460)
        layout = QVBoxLayout(dialog)
        listing = QListWidget(dialog)
        portals = [dict(p) for p in self.app.settings.get("custom_portals") or []]

        def render(selected: int = -1) -> None:
            listing.clear()
            for portal in portals:
                item = QListWidgetItem(f"{portal.get('mark') or '🌐'}  {portal.get('title') or portal.get('url')}\n{portal.get('url')}")
                listing.addItem(item)
            if 0 <= selected < listing.count():
                listing.setCurrentRow(selected)

        def move(step: int) -> None:
            row = listing.currentRow()
            target = row + step
            if 0 <= row < len(portals) and 0 <= target < len(portals):
                portals[row], portals[target] = portals[target], portals[row]
                render(target)

        def remove() -> None:
            row = listing.currentRow()
            if 0 <= row < len(portals):
                portals.pop(row)
                render(min(row, len(portals) - 1))

        render()
        layout.addWidget(listing)
        row_layout = QHBoxLayout()
        for key, callback in (("move_up", lambda: move(-1)), ("move_down", lambda: move(1)), ("remove", remove)):
            button = QPushButton(tr(self.app, key), dialog)
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            row_layout.addWidget(button)
        layout.addLayout(row_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.app.settings.set("custom_portals", portals)
            self.refresh_all_home_tabs()

    def import_bookmarks(self) -> None:
        items, stats = policy.import_windows_bookmarks()
        if not items:
            QMessageBox.information(self, policy.APP_NAME, tr(self.app, "import_none"))
            return
        portals, added = policy.merge_portals(list(self.app.settings.get("custom_portals") or []), items)
        self.app.settings.set("custom_portals", portals)
        self.refresh_all_home_tabs()
        detail = ", ".join(f"{name}: {count}" for name, count in stats.items())
        QMessageBox.information(self, policy.APP_NAME, tr(self.app, "imported", count=added) + f"\n{detail}")

    def clear_browsing_data(self) -> None:
        answer = QMessageBox.question(self, policy.APP_NAME, tr(self.app, "clear_confirm"))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.profile.clearHttpCache()
        self.profile.cookieStore().deleteAllCookies()
        self.profile.clearAllVisitedLinks()
        self.app.closed_tabs.clear()
        QMessageBox.information(self, policy.APP_NAME, tr(self.app, "cleared"))

    def make_default_browser(self) -> None:
        if sys.platform == "win32":
            target = QUrl("ms-settings:defaultapps?registeredAppUser=" + urllib.parse.quote(policy.APP_NAME))
            if not QDesktopServices.openUrl(target):
                QDesktopServices.openUrl(QUrl("ms-settings:defaultapps"))
        QMessageBox.information(self, policy.APP_NAME, tr(self.app, "default_help"))

    def show_about(self) -> None:
        from PySide6 import __version__ as pyside_version
        QMessageBox.about(self, policy.APP_NAME, tr(self.app, "about_text", version=policy.APP_VERSION, qt=pyside_version))

    def open_settings(self) -> None:
        SettingsDialog(self).exec()

    def show_downloads(self) -> None:
        DownloadsDialog(self).exec()

    # -- close ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        self.app.window_closed(self)
        self.dispose_tabs()
        super().closeEvent(event)


class SettingsDialog(QDialog):
    def __init__(self, window: BrowserWindow):
        super().__init__(window)
        self.window_ref = window
        app = window.app
        settings = app.settings
        self.setWindowTitle(tr(app, "settings"))
        self.setMinimumWidth(520)
        form = QFormLayout(self)

        self.language = QComboBox(self)
        for code, label in (("auto", "Auto / Samodejno"), ("sl", "Slovenščina"), ("en", "English")):
            self.language.addItem(label, code)
        self._select(self.language, settings.get("language") if settings.get("language") in ("auto", "sl", "en") else "auto")
        form.addRow(tr(app, "language"), self.language)

        self.engine = QComboBox(self)
        for key, engine in policy.search_engines().items():
            self.engine.addItem(engine["name"], key)
        self._select(self.engine, settings.get("search_engine"))
        form.addRow(tr(app, "search_engine"), self.engine)

        self.startup = QComboBox(self)
        self.startup.addItem(tr(app, "startup_home"), "home")
        self.startup.addItem(tr(app, "startup_restore"), "restore")
        self._select(self.startup, settings.get("startup"))
        form.addRow(tr(app, "startup"), self.startup)

        self.checks: Dict[str, QCheckBox] = {}
        for key, label in (("adblock_enabled", "adblock"), ("adguard_protection_enabled", "adguard"),
                           ("tracking_protection_enabled", "tracking"), ("gpc_dnt_enabled", "gpc"),
                           ("block_third_party_cookies", "cookies"), ("force_dark_mode", "dark"),
                           ("ask_download_location", "download_location"), ("hardware_acceleration", "gpu")):
            box = QCheckBox(tr(app, label), self)
            box.setChecked(bool(settings.get(key)))
            self.checks[key] = box
            form.addRow(box)

        self.dns = QComboBox(self)
        for key, label in (("cloudflare", "Cloudflare (1.1.1.1)"), ("quad9", "Quad9 (9.9.9.9)"),
                           ("google", "Google (8.8.8.8)"), ("off", tr(app, "dns_off"))):
            self.dns.addItem(label, key)
        self._select(self.dns, settings.get("doh_provider"))
        form.addRow(tr(app, "dns"), self.dns)
        note = QLabel(tr(app, "dns_note"), self)
        note.setStyleSheet("color:#adbbb2")
        form.addRow(note)

        tools = QHBoxLayout()
        for key, callback in (("import", window.import_bookmarks), ("clear_data", window.clear_browsing_data),
                              ("default_browser", window.make_default_browser)):
            button = QPushButton(tr(app, key), self)
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            tools.addWidget(button)
        form.addRow(tools)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _select(combo: QComboBox, value: Any) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def save(self) -> None:
        app = self.window_ref.app
        settings = app.settings
        settings.set("language", self.language.currentData(), save=False)
        settings.set("search_engine", self.engine.currentData(), save=False)
        settings.set("startup", self.startup.currentData(), save=False)
        settings.set("doh_provider", self.dns.currentData(), save=False)
        for key, box in self.checks.items():
            settings.set(key, box.isChecked(), save=False)
        settings.save()
        app.refresh_preferences()
        self.accept()


class DownloadsDialog(QDialog):
    def __init__(self, window: BrowserWindow):
        super().__init__(window)
        self.app = window.app
        self.setWindowTitle(tr(self.app, "downloads"))
        self.resize(560, 380)
        layout = QVBoxLayout(self)
        self.listing = QListWidget(self)
        self.listing.itemDoubleClicked.connect(self.open_item)
        layout.addWidget(self.listing)
        row = QHBoxLayout()
        folder = QPushButton(tr(self.app, "open_folder"), self)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.app.download_dir)))
        close = QPushButton(tr(self.app, "close"), self)
        close.clicked.connect(self.accept)
        row.addWidget(folder)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.render)
        self.timer.start(500)
        self.render()

    def render(self) -> None:
        self.listing.clear()
        if not self.app.downloads:
            self.listing.addItem(tr(self.app, "no_downloads"))
            return
        states = QWebEngineDownloadRequest.DownloadState
        for download in reversed(self.app.downloads):
            name = download.downloadFileName()
            received, total = download.receivedBytes(), download.totalBytes()
            if download.state() == states.DownloadCompleted:
                status = tr(self.app, "done")
            elif download.state() in (states.DownloadCancelled, states.DownloadInterrupted):
                status = tr(self.app, "failed")
            elif total > 0:
                status = f"{received * 100 // total}% ({received / 1048576:.1f} / {total / 1048576:.1f} MB)"
            else:
                status = f"{received / 1048576:.1f} MB"
            item = QListWidgetItem(f"{name} — {status}")
            item.setData(Qt.ItemDataRole.UserRole, os.path.join(download.downloadDirectory(), name))
            self.listing.addItem(item)

    def open_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="SafeerBrowser", add_help=True)
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--data-dir")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--report")
    parser.add_argument("--screenshot")
    parser.add_argument("--online", action="store_true")
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    args = parse_args(argv[1:])
    if args.version:
        message = f"{policy.APP_NAME} {policy.APP_VERSION}"
        if sys.stdout is not None:
            print(message)
        if args.report:
            with open(args.report, "w", encoding="utf-8") as handle:
                handle.write(message + "\n")
        return 0
    if args.data_dir:
        os.environ["SAFEER_WINDOWS_DATA_DIR"] = os.path.abspath(args.data_dir)

    settings = policy.SettingsStore()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = policy.chromium_flags(os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", ""), settings)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Safeer.Browser")
        except (AttributeError, OSError):
            pass

    register_schemes()
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    QCoreApplication.setOrganizationName("Safeer")
    QCoreApplication.setApplicationName(policy.APP_NAME)
    QCoreApplication.setApplicationVersion(policy.APP_VERSION)
    qt_app = QApplication(argv[:1])
    qt_app.setQuitOnLastWindowClosed(True)

    if not args.smoke_test and SafeerBrowserApp.forward_to_running_instance(args.urls):
        return 0

    started = time.monotonic()
    if args.smoke_test:
        return smoke_main(qt_app, settings, args, started)
    dns_status = apply_dns_mode(settings)
    browser = SafeerBrowserApp(qt_app, settings, dns_status)
    browser.start_instance_server()
    browser.new_window(args.urls, restore=True)
    code = qt_app.exec()
    browser.shutdown()
    return code


def smoke_main(qt_app: QApplication, settings: policy.SettingsStore, args: argparse.Namespace, started: float) -> int:
    """The automated run: every failure ends in the report, never in a dialog or a silent timeout."""
    import traceback

    from .smoke import SmokeRunner, arm_hard_watchdog, report_crash, stage

    # armed before anything that can block, so a startup hang is reported instead of timing out
    arm_hard_watchdog(args.report, float(os.environ.get("SAFEER_SMOKE_TIMEOUT", "420")) + 60)
    try:
        stage("dns")
        dns_status = apply_dns_mode(settings)
        stage(f"browser ({dns_status})")
        browser = SafeerBrowserApp(qt_app, settings, dns_status, smoke=True)
        runner = SmokeRunner(browser, args, started)
        QTimer.singleShot(0, runner.start)
        stage("event loop")
        qt_app.exec()
        browser.shutdown()
        return runner.exit_code
    except BaseException:  # noqa: BLE001 - the report is the only channel out of a windowed build
        report_crash(args.report, traceback.format_exc())
        return 1
