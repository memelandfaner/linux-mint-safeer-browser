"""End-to-end smoke test that drives the real browser window (used by CI on Windows)."""

from __future__ import annotations

import json
import os
import platform
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Generator, List, Optional

from PySide6.QtCore import QObject, QTimer

from . import policy

DOWNLOAD_SIZE = 4096


class Wait:
    def __init__(self, predicate: Callable[[], Any], timeout: float):
        self.predicate = predicate
        self.timeout = timeout


class Js:
    def __init__(self, page, code: str, timeout: float = 10.0):
        self.page = page
        self.code = code
        self.timeout = timeout


class Sleep:
    def __init__(self, seconds: float):
        self.seconds = seconds


class _Handler(BaseHTTPRequestHandler):
    server_version = "SafeerSmoke/1.0"

    def log_message(self, *_args) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self.server.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
        path = self.path.split("?", 1)[0]
        pages = {
            "/after": "<title>After</title><p id='after'>after</p>",
            "/landing": "<title>Landing</title><p>landing</p>",
            "/ads": ("<title>Ads</title>"
                     "<script src='https://securepubads.g.doubleclick.net/tag/js/gpt.js'></script>"
                     "<img src='https://googleads.g.doubleclick.net/pagead/viewthroughconversion/1/?smoke=1'>"
                     "<a id='trk' href='/landing?id=5&utm_source=smoke&fbclid=abc'>tracked link</a>"),
            "/popup": "<title>Popup</title><script>window.__popupResult = window.open('/after');</script>",
        }
        if path == "/download.bin":
            body = bytes(range(256)) * (DOWNLOAD_SIZE // 256)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="safeer-smoke.bin"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path not in pages:
            self.send_error(404)
            return
        body = ("<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>" + pages[path] + "</body></html>").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class SmokeRunner(QObject):
    def __init__(self, browser, args, started: float):
        super().__init__()
        self.browser = browser
        self.args = args
        self.started = started
        self.results: List[Dict[str, Any]] = []
        self.exit_code = 1
        self.finished = False
        self.generator: Optional[Generator] = None
        self.token = 0
        self.server: Optional[ThreadingHTTPServer] = None
        self.base = ""
        self.window = None

    # -- driver ---------------------------------------------------------------
    def start(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.requests = []
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        downloads = os.path.join(policy.data_dir(), "Downloads")
        os.makedirs(downloads, exist_ok=True)
        self.browser.download_dir = downloads
        self.browser.profile.setDownloadPath(downloads)
        QTimer.singleShot(int(float(os.environ.get("SAFEER_SMOKE_TIMEOUT", "420")) * 1000), self.watchdog)
        self.generator = self.scenario()
        self.advance(None)

    def watchdog(self) -> None:
        if not self.finished:
            self.check("watchdog", False, "scenario did not finish in time")
            self.finish()

    def advance(self, value: Any) -> None:
        if self.finished or self.generator is None:
            return
        self.token += 1
        token = self.token
        try:
            command = self.generator.send(value)
        except StopIteration:
            self.finish()
            return
        except Exception:
            self.check("scenario", False, traceback.format_exc())
            self.finish()
            return
        if isinstance(command, Sleep):
            QTimer.singleShot(int(command.seconds * 1000), lambda: self._resume(token, None))
        elif isinstance(command, Js):
            command.page.runJavaScript(command.code, 0, lambda result: self._resume(token, result))
            QTimer.singleShot(int(command.timeout * 1000), lambda: self._resume(token, None))
        elif isinstance(command, Wait):
            deadline = time.monotonic() + command.timeout
            self._poll(token, command, deadline)
        else:
            self.check("scenario", False, f"unknown command {command!r}")
            self.finish()

    def _resume(self, token: int, value: Any) -> None:
        if token != self.token or self.finished:
            return
        self.token += 1  # consume: a late callback or timeout for the same command is ignored
        QTimer.singleShot(0, lambda: self.advance(value))

    def _poll(self, token: int, command: Wait, deadline: float) -> None:
        if token != self.token or self.finished:
            return
        try:
            value = command.predicate()
        except Exception:
            value = False
        if value:
            self._resume(token, value)
        elif time.monotonic() > deadline:
            self._resume(token, False)
        else:
            QTimer.singleShot(150, lambda: self._poll(token, command, deadline))

    def wait_js(self, page, code: str, timeout: float) -> Generator:
        deadline = time.monotonic() + timeout
        result = None
        while time.monotonic() < deadline:
            result = yield Js(page, code)
            if result:
                return result
            yield Sleep(0.3)
        return result

    def check(self, name: str, ok: bool, detail: Any = "", required: bool = True) -> None:
        self.results.append({"name": name, "ok": bool(ok), "required": required, "detail": detail})

    # -- scenario ---------------------------------------------------------------
    def scenario(self) -> Generator:
        browser = self.browser
        window = browser.new_window([])
        self.window = window
        view = window.current_view()
        page = view.page()

        ready = yield from self.wait_js(page, "document.documentElement.getAttribute('data-safeer-ready') === '1' && "
                                              "document.querySelectorAll('#portalsGrid .portal-card').length", 40)
        expected = len(browser.settings.get("custom_portals")) + 1
        self.check("home_page_ready", ready == expected, {"cards": ready, "expected": expected})
        subtitle = yield Js(page, "(document.querySelector('.shield-subtitle')||{}).textContent || ''")
        icons = {name: not window.app.icons[name].pixmap(18, 18).isNull() for name in ("back", "reload", "home", "star", "menu", "close")}
        self.check("toolbar_icons_loaded", all(icons.values()), icons)
        self.check("home_page_windows_label", "Windows" in str(subtitle), subtitle)

        target = self.base + "/after"
        yield Js(page, "window.webkit.messageHandlers.safeer.postMessage({action: 'navigate', url: %s}); true" % json.dumps(target))
        arrived = yield Wait(lambda: view.url().toString() == target, 20)
        title = yield from self.wait_js(page, "document.title === 'After' && document.title", 20)
        self.check("home_bridge_navigates", bool(arrived) and title == "After", view.url().toString())
        gpc_requests = [r for r in self.server.requests if r["path"] == "/after"]
        self.check("gpc_header_sent", bool(gpc_requests) and gpc_requests[-1]["headers"].get("sec-gpc") == "1",
                   gpc_requests[-1]["headers"] if gpc_requests else "no request")
        gpc_js = yield Js(page, "navigator.globalPrivacyControl === true")
        self.check("gpc_script_injected", gpc_js is True, gpc_js)

        window.load_in_current(self.base + "/ads")
        blocked = yield Wait(lambda: [b for b in browser.blocked_log if "doubleclick.net" in b["url"]], 20)
        self.check("ad_requests_blocked", bool(blocked), blocked or browser.blocked_log[-5:])

        loaded = yield from self.wait_js(page, "document.title === 'Ads' && !!document.getElementById('trk')", 20)
        yield Js(page, "document.getElementById('trk').click(); true")
        clean = self.base + "/landing?id=5"
        cleaned = yield Wait(lambda: view.url().toString() == clean, 20)
        self.check("tracking_parameters_removed", bool(loaded) and bool(cleaned), view.url().toString())

        threat = sorted(policy.adblock.ABUSE_CH_BLOCKED_DOMAINS)[0]
        yield Js(page, "location.href = %s; true" % json.dumps(f"http://{threat}/payload"))
        on_block = yield Wait(lambda: view.url().scheme() == "safeer" and view.url().path() == "/blocked", 20)
        marker = yield from self.wait_js(page, "!!document.querySelector('[data-safeer-blocked]')", 15)
        self.check("threat_navigation_blocked", bool(on_block) and bool(marker), view.url().toString())

        window.open_input(f"{threat}/typed")
        typed = yield Wait(lambda: view.url().path() == "/blocked" and "typed" in view.url().query(), 20)
        self.check("threat_typed_address_blocked", bool(typed), view.url().toString())

        tabs_before = window.tabs.count()
        window.load_in_current(self.base + "/popup")
        popup_page = yield from self.wait_js(page, "document.title === 'Popup'", 20)
        yield Sleep(2.5)
        popup_value = yield Js(page, "window.__popupResult === null")
        self.check("scripted_popup_blocked", bool(popup_page) and window.tabs.count() == tabs_before and popup_value is True,
                   {"tabs_before": tabs_before, "tabs_after": window.tabs.count(), "open_returned_null": popup_value})

        count = window.tabs.count()
        extra = window.new_tab(self.base + "/landing")
        opened = yield Wait(lambda: window.tabs.count() == count + 1 and extra.url().toString().endswith("/landing"), 15)
        window.close_tab(window.tabs.indexOf(extra))
        closed = yield Wait(lambda: window.tabs.count() == count, 10)
        self.check("tabs_open_and_close", bool(opened) and bool(closed), window.tabs.count())

        window.load_in_current(clean)
        yield from self.wait_js(page, "document.title === 'Landing'", 20)
        portals_before = len(browser.settings.get("custom_portals"))
        window.add_current_to_home()
        portals_after = len(browser.settings.get("custom_portals"))
        home_view = window.new_tab(policy.HOME_URL)
        cards = yield from self.wait_js(home_view.page(), "document.documentElement.getAttribute('data-safeer-ready') === '1' && "
                                                          "document.querySelectorAll('#portalsGrid .portal-card').length", 30)
        self.check("add_page_to_start_page", portals_after == portals_before + 1 and cards == portals_after + 1,
                   {"before": portals_before, "after": portals_after, "cards": cards})
        window.close_tab(window.tabs.indexOf(home_view))

        target_file = os.path.join(browser.download_dir, "safeer-smoke.bin")
        window.load_in_current(self.base + "/download.bin")
        downloaded = yield Wait(lambda: os.path.exists(target_file) and os.path.getsize(target_file) == DOWNLOAD_SIZE
                                and browser.downloads and browser.downloads[-1].isFinished(), 30)
        self.check("download_saved", bool(downloaded), os.listdir(browser.download_dir))

        scripts_on = browser.profile.scripts().count()
        browser.settings.set("adblock_enabled", False)
        browser.refresh_preferences()
        scripts_off = browser.profile.scripts().count()
        browser.settings.set("adblock_enabled", True)
        browser.refresh_preferences()
        scripts_again = browser.profile.scripts().count()
        self.check("settings_apply_scripts", scripts_on == scripts_again and scripts_off < scripts_on,
                   {"on": scripts_on, "off": scripts_off, "again": scripts_again})

        private = browser.new_window([], private=True)
        private_page = private.current_view().page()
        private_ready = yield from self.wait_js(private_page, "document.documentElement.getAttribute('data-safeer-ready') === '1'", 30)
        self.check("private_window", bool(private_ready) and private.profile.isOffTheRecord(), private.profile.isOffTheRecord())
        private.close()
        yield Sleep(0.5)

        if self.args.online:
            self.check("dns_over_https_mode", browser.dns_status.startswith("secure-only"), browser.dns_status)
            window.load_in_current("https://example.com/")
            example = yield from self.wait_js(page, "document.title.indexOf('Example') >= 0 && document.title", 60)
            self.check("online_https_page", bool(example), example or view.url().toString())

            window.load_in_current("https://www.youtube.com/")
            youtube = yield from self.wait_js(page, "!!(window.__safeerKeepWatching && window._safeer_linux_yt_active) && location.hostname", 90)
            self.check("youtube_scripts_active", bool(youtube), youtube or view.url().toString())

        if self.args.screenshot:
            from .browser import SettingsDialog
            window.load_in_current(policy.HOME_URL)
            yield from self.wait_js(page, "document.documentElement.getAttribute('data-safeer-ready') === '1'", 30)
            yield Sleep(1.5)
            self.check("screenshot_saved", self.capture(window, self.args.screenshot), self.args.screenshot, required=False)
            dialog = SettingsDialog(window)
            dialog.show()
            yield Sleep(1.0)
            settings_shot = os.path.splitext(self.args.screenshot)[0] + "-settings" + os.path.splitext(self.args.screenshot)[1]
            self.check("settings_screenshot_saved", self.capture(dialog, settings_shot), settings_shot, required=False)
            dialog.close()

    @staticmethod
    def capture(widget, path: str) -> bool:
        widget.raise_()
        widget.activateWindow()
        try:
            from PIL import ImageGrab
            geometry = widget.frameGeometry()
            ratio = widget.devicePixelRatioF()
            box = (int(geometry.x() * ratio), int(geometry.y() * ratio),
                   int((geometry.x() + geometry.width()) * ratio), int((geometry.y() + geometry.height()) * ratio))
            ImageGrab.grab(bbox=box, all_screens=True).save(path)
            return True
        except Exception:
            return bool(widget.grab().save(path))

    # -- report -------------------------------------------------------------------
    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        failed = [r["name"] for r in self.results if r["required"] and not r["ok"]]
        self.exit_code = 0 if self.results and not failed else 1
        try:
            from PySide6 import __version__ as pyside_version
            from PySide6.QtCore import qVersion
            try:
                from PySide6.QtWebEngineCore import qWebEngineChromiumVersion, qWebEngineVersion
                engine = {"qtwebengine": qWebEngineVersion(), "chromium": qWebEngineChromiumVersion()}
            except ImportError:
                engine = {}
        except ImportError:  # pragma: no cover
            pyside_version, engine = "?", {}
            qVersion = lambda: "?"  # noqa: E731
        report = {
            "ok": self.exit_code == 0,
            "failed": failed,
            "version": policy.APP_VERSION,
            "elapsed_seconds": round(time.monotonic() - self.started, 1),
            "platform": platform.platform(),
            "pyside": pyside_version,
            "qt": qVersion(),
            "engine": engine,
            "dns": self.browser.dns_status,
            "cookie_filter": self.browser.cookie_filter_status,
            "user_agent": self.browser.profile.httpUserAgent(),
            "scripts": [s["name"] for s in policy.script_specs(self.browser.settings)],
            "results": self.results,
        }
        if self.args.report:
            with open(self.args.report, "w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2, ensure_ascii=False, default=str)
        if self.server is not None:
            self.server.shutdown()
        app = self.browser.qt_app
        QTimer.singleShot(0, app.closeAllWindows)
        QTimer.singleShot(1500, app.quit)
