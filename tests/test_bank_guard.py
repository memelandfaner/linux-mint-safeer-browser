"""Safeer BankGuard on the desktop: fake banks get a warning, real banks are never touched.

The rules themselves are tested in safeer-threat-intel (clients/banks/cases.json, same file in
Kotlin and Python). These tests cover the browser glue. Without PyGObject (CI containers) a minimal
stand-in for gi is installed so the GTK handlers can be called with plain test doubles.
"""

import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest import mock

from core import adblock


def _install_gi_stand_in():
    try:
        import gi  # noqa: F401

        return
    except Exception:
        for name in [n for n in sys.modules if n == "gi" or n.startswith("gi.")]:
            del sys.modules[name]

    class Meta(type):
        def __getattr__(cls, name):
            if name.startswith("__"):
                raise AttributeError(name)
            children = cls.__dict__.get("_children")
            if children is None:
                children = {}
                type.__setattr__(cls, "_children", children)
            return children.setdefault(name, Meta(name, (Dummy,), {}))

    class Dummy(metaclass=Meta):
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return lambda *args, **kwargs: Dummy()

        def __call__(self, *args, **kwargs):
            return Dummy()

        def __iter__(self):
            return iter(())

        def __bool__(self):
            return False

    class Repository(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            value = Meta(name, (Dummy,), {})
            setattr(self, name, value)
            return value

    gi = types.ModuleType("gi")
    gi.require_version = lambda *args, **kwargs: None
    gi.repository = Repository("gi.repository")
    sys.modules["gi"] = gi
    sys.modules["gi.repository"] = gi.repository


class CatalogueTests(unittest.TestCase):
    def tearDown(self):
        adblock._fake_bank_allowed_hosts.clear()

    def test_real_banks_are_never_ads_or_threats_from_lists(self):
        for url in ("https://klik.nlb.si/", "https://bankanet.otpbanka.si/", "https://3ds.bankart.si/acs", "https://www.paypal.com/"):
            self.assertTrue(adblock.is_real_bank_host(url), url)
            self.assertFalse(adblock.is_ad_domain(url), url)
            self.assertFalse(adblock.is_threat_domain(url), url)
        self.assertFalse(adblock.is_real_bank_host("https://nlb.si.evil.example/"))

        def mistaken(url):
            return "phishing" if "nlb.si" in url else None

        adblock.register_threat_matcher(mistaken)
        try:
            self.assertFalse(adblock.is_threat_domain("https://www.nlb.si/"), "a mistaken phishing entry never blocks a bank")
        finally:
            adblock._extra_threat_matchers.remove(mistaken)

        def compromised(url):
            return "malware" if "cdn.nlb.si" in url else None

        adblock.register_threat_matcher(compromised)
        try:
            self.assertTrue(adblock.is_threat_domain("https://cdn.nlb.si/payload.exe"), "confirmed malware still blocks")
        finally:
            adblock._extra_threat_matchers.remove(compromised)

    def test_fake_bank_hosts_and_session_choice(self):
        verdict = adblock.fake_bank_verdict("https://nlb-klik-varnost.net/prijava")
        self.assertEqual((verdict.bank_id, verdict.official_domain), ("nlb", "nlb.si"))
        self.assertEqual(adblock.fake_bank_verdict("https://otpbamka.si/").bank_id, "otp")
        self.assertIsNone(adblock.fake_bank_verdict("https://klik.nlb.si/"))
        self.assertIsNone(adblock.fake_bank_verdict("file:///home/user/nlb-klik.html"))
        adblock.allow_fake_bank_host("https://nlb-klik-varnost.net/other")
        self.assertIsNone(adblock.fake_bank_verdict("https://nlb-klik-varnost.net/prijava"))
        self.assertTrue(adblock.is_fake_bank_host_allowed("nlb-klik-varnost.net"))

    def test_unicode_addresses_are_checked_in_their_xn_form(self):
        # Qt prints many internationalized hosts in Unicode, the page reports the xn-- form
        self.assertEqual(adblock.fake_bank_verdict("https://pаypаl-login.com/").reason, "homoglyph")
        signals = {"host": "xn--pypl-login-zqic.com", "scheme": "https", "password": True, "title": "Pay"}
        self.assertIsNone(adblock.fake_bank_page_verdict("https://pаypаl-login.com/", signals))  # no bank name on the page
        signals["title"] = "PayPal"
        self.assertEqual(adblock.fake_bank_page_verdict("https://pаypаl-login.com/", signals).bank_id, "paypal")
        self.assertIsNone(adblock.fake_bank_verdict("https://ljubljanska-delavska-čitalnica.si/"))

    def test_page_verdict_uses_the_page_that_answered(self):
        signals = {"host": "secure-login.example", "scheme": "https", "password": True, "title": "NLB Klik - prijava"}
        self.assertEqual(adblock.fake_bank_page_verdict("https://secure-login.example/x", signals).bank_id, "nlb")
        self.assertIsNone(adblock.fake_bank_page_verdict("https://other.example/", signals))
        self.assertIsNone(adblock.fake_bank_page_verdict("https://secure-login.example/", None))
        self.assertIsNone(adblock.fake_bank_page_verdict("https://klik.nlb.si/", dict(signals, host="klik.nlb.si")))
        self.assertIn("one-time-code", adblock.bank_guard_page_script())

    def test_local_attachment_and_card_lure_pages(self):
        # SI-CERT TZ009: the fake bank page is an HTML attachment opened from mail, so it has no host
        local = {"host": "", "scheme": "file", "password": True, "title": "NLB Klik"}
        verdict = adblock.fake_bank_page_verdict("file:///home/janez/Prejemi/NLB_Klik.html", local)
        self.assertEqual((verdict.bank_id, verdict.reason), ("nlb", "local"))
        self.assertIsNone(adblock.fake_bank_page_verdict("https://secure-login.example/", local), "scheme must match the page")
        self.assertIsNone(adblock.fake_bank_page_verdict("file:///tmp/racun.html", dict(local, title="Moj racun")))
        self.assertIn("priponke", adblock.fake_bank_warning_text(verdict))
        self.assertIn("nikoli ne pokliče", adblock.fake_bank_warning_text(verdict))
        adblock.allow_fake_bank_host("file:///home/janez/Prejemi/NLB_Klik.html")
        self.assertTrue(adblock.is_fake_bank_host_allowed("file:///anything.html"))
        self.assertIsNone(adblock.fake_bank_page_verdict("file:///home/janez/Prejemi/NLB_Klik.html", local))
        # SI-CERT, May 2026: a card form dressed up as a police fine on a fresh domain
        lure = {"host": "kazen-placilo.example", "scheme": "https", "card": True, "title": "Placilo kazni",
                "headings": "Policija - prekrsek", "text": "Kazen 39 EUR placajte s kartico. Stevilka kartice"}
        verdict = adblock.fake_bank_page_verdict("https://kazen-placilo.example/pay", lure)
        self.assertEqual((verdict.bank_id, verdict.reason, verdict.official_domain), ("card", "lure", ""))
        self.assertIn("plačilne kartice", adblock.fake_bank_warning_text(verdict))
        self.assertIn("pretext", adblock.fake_bank_warning_text(verdict, "en"))
        # tax number and PIN fields count as credential fields
        taxid = {"host": "nlb-preverjanje.example", "scheme": "https", "taxid": True, "title": "NLB Klik - preverjanje"}
        self.assertEqual(adblock.fake_bank_page_verdict("https://nlb-preverjanje.example/", taxid).reason, "page")

    def test_bank_pages_run_without_cosmetic_scripts(self):
        self.assertIn("*://*.nlb.si/*", adblock.AUTH_SCRIPT_EXCLUSIONS)
        self.assertIn("*://bankart.si/*", adblock.AUTH_SCRIPT_EXCLUSIONS)

    def test_desktop_copies_match_the_catalogue_files(self):
        from pathlib import Path

        core = Path(adblock.__file__).resolve().parent
        data = json.loads((core / "banks.json").read_text("utf-8"))
        self.assertGreaterEqual(len(data["banks"]), 10)
        self.assertTrue((core / "bank_guard_page.js").read_text("utf-8").startswith("(function ()"))


class BrowserGlueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _install_gi_stand_in()
        import safeer_mint

        cls.mint = safeer_mint

    def tearDown(self):
        adblock._fake_bank_allowed_hosts.clear()

    def navigation(self, uri):
        request = SimpleNamespace(get_uri=lambda: uri, get_http_method=lambda: "GET")
        nav = SimpleNamespace(get_request=lambda: request, get_navigation_type=lambda: None, is_redirect=lambda: False,
                              get_mouse_button=lambda: 1, get_modifiers=lambda: 0)
        calls = []
        decision = SimpleNamespace(get_navigation_action=lambda: nav, ignore=lambda: calls.append("ignore"),
                                   use=lambda: calls.append("use"))
        return decision, calls

    def app(self, **extra):
        config = SimpleNamespace(get=lambda key, default=None: default, increment_ads_blocked=lambda n: None,
                                 increment_threats_blocked=lambda n: None)
        return SimpleNamespace(config=config, show_threat_warning=lambda uri: self.fail("threat dialog"),
                               is_download_url=lambda uri: False, show_fake_bank_warning=lambda *a: None, **extra)

    def test_fake_bank_navigation_is_stopped_and_warned(self):
        scheduled = []
        decision, calls = self.navigation("https://nlb-klik-varnost.net/prijava")
        webview = object()
        with mock.patch.object(self.mint, "GLib", SimpleNamespace(idle_add=lambda *args: scheduled.append(args))):
            handled = self.mint.SafeerMintBrowser.on_decide_policy(
                self.app(), webview, decision, self.mint.WebKit2.PolicyDecisionType.NAVIGATION_ACTION)
        self.assertTrue(handled)
        self.assertEqual(calls, ["ignore"])
        self.assertEqual(len(scheduled), 1)
        _callback, view, uri, verdict, after_load = scheduled[0]
        self.assertIs(view, webview)
        self.assertEqual((uri, verdict.bank_id, after_load), ("https://nlb-klik-varnost.net/prijava", "nlb", False))

    def test_real_bank_navigation_is_not_touched(self):
        decision, calls = self.navigation("https://klik.nlb.si/")
        with mock.patch.object(self.mint, "GLib", SimpleNamespace(idle_add=lambda *args: self.fail("warning scheduled"))):
            self.assertTrue(self.mint.SafeerMintBrowser.on_decide_policy(
                self.app(), object(), decision, self.mint.WebKit2.PolicyDecisionType.NAVIGATION_ACTION))
        self.assertNotIn("ignore", calls)

    def warning(self, response, after_load, can_go_back=True):
        loads, backs = [], []
        webview = SimpleNamespace(load_uri=loads.append, can_go_back=lambda: can_go_back, go_back=lambda: backs.append(True))

        class Dialog:
            def __init__(self, **kwargs):
                self.buttons = []

            def format_secondary_text(self, text):
                self.text = text

            def add_button(self, label, code):
                self.buttons.append((label, code))

            def set_default_response(self, code):
                pass

            def run(self):
                return response

            def destroy(self):
                pass

        gtk = SimpleNamespace(MessageDialog=Dialog, MessageType=SimpleNamespace(WARNING=1), ButtonsType=SimpleNamespace(NONE=0))
        app = SimpleNamespace(increment_shields_blocked=lambda: None)
        verdict = adblock.fake_bank_verdict("https://nkbm-prijava.eu/")
        with mock.patch.object(self.mint, "Gtk", gtk):
            result = self.mint.SafeerMintBrowser.show_fake_bank_warning(app, webview, "https://nkbm-prijava.eu/login", verdict, after_load)
        self.assertFalse(result)  # one-shot idle callback
        return loads, backs

    def test_second_warning_waits_for_the_first(self):
        retried = []
        app = SimpleNamespace(_bank_warning_open=True, show_fake_bank_warning=object())
        verdict = adblock.fake_bank_verdict("https://otpbamka.si/")
        with mock.patch.object(self.mint, "GLib", SimpleNamespace(timeout_add=lambda *args: retried.append(args))):
            self.assertFalse(self.mint.SafeerMintBrowser.show_fake_bank_warning(app, object(), "https://otpbamka.si/", verdict, True))
        self.assertEqual(len(retried), 1)
        self.assertEqual(retried[0][0], 400)
        self.assertEqual(retried[0][3:], ("https://otpbamka.si/", verdict, True))

    def test_warning_choices(self):
        self.assertEqual(self.warning(1, after_load=False), ([], []))
        self.assertEqual(self.warning(1, after_load=True), ([], [True]))
        loads, _ = self.warning(1, after_load=True, can_go_back=False)
        self.assertTrue(loads[0].startswith("file://") and loads[0].endswith("/ui/home.html"))
        self.assertEqual(self.warning(2, after_load=True), (["https://otpbanka.si/"], []))
        self.assertEqual(self.warning(3, after_load=False), (["https://nkbm-prijava.eu/login"], []))
        self.assertIsNone(adblock.fake_bank_verdict("https://nkbm-prijava.eu/"), "continue allows the host for the session")

    def test_page_check_runs_after_load_in_an_isolated_world(self):
        idle, timeouts, scripts = [], [], []
        webview = SimpleNamespace(get_uri=lambda: "https://secure-login.example/",
                                  run_javascript_in_world=lambda script, world, cancellable, callback, data: scripts.append((script, world, data)))
        glib = SimpleNamespace(idle_add=idle.append, timeout_add=lambda ms, fn: timeouts.append((ms, fn)))
        app = SimpleNamespace(on_fake_bank_signals=object())
        with mock.patch.object(self.mint, "GLib", glib):
            self.mint.SafeerMintBrowser.schedule_fake_bank_check(app, webview, "https://secure-login.example/")
            self.mint.SafeerMintBrowser.schedule_fake_bank_check(app, webview, "https://klik.nlb.si/")
            self.mint.SafeerMintBrowser.schedule_fake_bank_check(app, webview, f"file://{self.mint.BASE_DIR}/ui/home.html")
        self.assertEqual(len(idle), 1)
        self.assertEqual(timeouts[0][0], 2500)
        self.assertFalse(idle[0]())
        self.assertEqual(scripts[0][1], "safeer-bankguard")
        self.assertIn("one-time-code", scripts[0][0])
        webview.get_uri = lambda: "https://elsewhere.example/"
        self.assertFalse(timeouts[0][1]())
        self.assertEqual(len(scripts), 1, "no check after the tab moved on")
        with mock.patch.object(self.mint, "GLib", glib):
            webview.get_uri = lambda: "file:///home/janez/Prejemi/NLB_Klik.html"
            self.mint.SafeerMintBrowser.schedule_fake_bank_check(app, webview, "file:///home/janez/Prejemi/NLB_Klik.html")
        self.assertEqual(len(idle), 2, "an HTML file outside the browser's own pages is checked")
        self.assertFalse(idle[1]())
        self.assertEqual(len(scripts), 2)

    def test_signals_open_the_warning_once(self):
        shown = []
        signals = {"host": "secure-login.example", "scheme": "https", "password": True, "title": "NLB Klik"}
        js_value = SimpleNamespace(to_json=lambda indent: json.dumps(signals))
        webview = SimpleNamespace(get_uri=lambda: "https://secure-login.example/", _safeer_bank_check=4,
                                  run_javascript_in_world_finish=lambda result: SimpleNamespace(get_js_value=lambda: js_value))
        app = SimpleNamespace(show_fake_bank_warning=lambda *args: shown.append(args))
        self.mint.SafeerMintBrowser.on_fake_bank_signals(app, webview, object(), (4, "https://secure-login.example/"))
        self.assertEqual(len(shown), 1)
        self.assertTrue(shown[0][3])  # after_load
        self.mint.SafeerMintBrowser.on_fake_bank_signals(app, webview, object(), (4, "https://secure-login.example/"))
        self.assertEqual(len(shown), 1, "stale generation")
        signals["title"] = "Trgovina"
        webview._safeer_bank_check = 7
        self.mint.SafeerMintBrowser.on_fake_bank_signals(app, webview, object(), (7, "https://secure-login.example/"))
        self.assertEqual(len(shown), 1)


if __name__ == "__main__":
    unittest.main()
