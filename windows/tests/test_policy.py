import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from safeer_windows import policy  # noqa: E402


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "settings.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_defaults_and_round_trip(self):
        store = policy.SettingsStore(self.path)
        self.assertTrue(store.get("adblock_enabled"))
        self.assertEqual(store.get("doh_provider"), "cloudflare")
        store.set("search_engine", "google")
        store.set("future_key", {"kept": True})
        again = policy.SettingsStore(self.path)
        self.assertEqual(again.get("search_engine"), "google")
        self.assertEqual(again.get("future_key"), {"kept": True})

    def test_corrupt_file_falls_back_to_defaults(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{broken")
        store = policy.SettingsStore(self.path)
        self.assertEqual(store.get("custom_portals"), policy.DEFAULT_PORTALS)

    def test_unknown_search_engine_is_reset(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"search_engine": "nope"}, handle)
        self.assertEqual(policy.SettingsStore(self.path).get("search_engine"), "duckduckgo")

    def test_data_directories_follow_windows_variables(self):
        env = {"APPDATA": r"C:\Users\m\AppData\Roaming", "LOCALAPPDATA": r"C:\Users\m\AppData\Local"}
        self.assertTrue(policy.data_dir(env).endswith("Safeer Browser"))
        self.assertIn("Local", policy.profile_dir(env))
        self.assertEqual(policy.data_dir({"SAFEER_WINDOWS_DATA_DIR": "/x"}), "/x")

    def test_dns_and_gpu_flags(self):
        store = policy.SettingsStore(self.path)
        self.assertEqual(policy.doh_template(store), "https://cloudflare-dns.com/dns-query")
        store.set("doh_provider", "off")
        self.assertIsNone(policy.doh_template(store))
        store.set("hardware_acceleration", False)
        self.assertEqual(policy.chromium_flags("--foo", store), "--foo --disable-gpu")

    def test_language(self):
        self.assertEqual(policy.ui_language("auto", "sl_SI"), "sl")
        self.assertEqual(policy.ui_language("auto", "Slovenian_Slovenia"), "sl")
        self.assertEqual(policy.ui_language("auto", "de_DE"), "en")
        self.assertEqual(policy.ui_language("de"), "en")


class AddressBarTests(unittest.TestCase):
    def test_resolution(self):
        cases = {
            "": ("empty", ""),
            "home": ("home", policy.HOME_URL),
            "youtube.com": ("url", "https://youtube.com"),
            "safeer.si/browser": ("url", "https://safeer.si/browser"),
            "localhost:8080": ("url", "http://localhost:8080"),
            "192.168.1.10": ("url", "http://192.168.1.10"),
            "hello world": ("search", "https://duckduckgo.com/?q=hello+world"),
            "what is 2.5": ("search", "https://duckduckgo.com/?q=what+is+2.5"),
            "javascript:alert(1)": ("search", "https://duckduckgo.com/?q=javascript%3Aalert%281%29"),
            r"C:\Users\x y\a.html": ("url", "file:///C:/Users/x%20y/a.html"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(policy.resolve_input(text), expected)

    def test_tracking_parameters_are_stripped_from_typed_urls(self):
        self.assertEqual(policy.resolve_input("https://example.com/?utm_source=x&id=2"), ("url", "https://example.com/?id=2"))
        self.assertEqual(policy.resolve_input("https://example.com/?utm_source=x", tracking_protection=False)[1],
                         "https://example.com/?utm_source=x")

    def test_threats_open_the_block_page(self):
        threat = sorted(policy.adblock.ABUSE_CH_BLOCKED_DOMAINS)[0]
        kind, url = policy.resolve_input(threat + "/x")
        self.assertEqual(kind, "blocked")
        self.assertTrue(url.startswith(policy.HOME_URL + "blocked?url="))

    def test_search_engine_choice(self):
        self.assertEqual(policy.resolve_input("a b", "youtube")[1], "https://www.youtube.com/results?search_query=a+b")

    def test_request_and_navigation_decisions(self):
        self.assertEqual(policy.request_decision("https://securepubads.g.doubleclick.net/x.js", False, "https://news.si/", True), "block-ad")
        self.assertEqual(policy.request_decision("https://securepubads.g.doubleclick.net/x.js", False, "https://news.si/", False), "allow")
        threat = sorted(policy.adblock.ABUSE_CH_BLOCKED_DOMAINS)[0]
        self.assertEqual(policy.request_decision(f"https://{threat}/", True, "", False), "block-threat")
        self.assertEqual(policy.request_decision("https://challenges.cloudflare.com/x", False, "", True), "allow")
        self.assertEqual(policy.request_decision("safeer://home/", True, "", True), "allow")
        self.assertEqual(policy.navigation_scheme_allowed("https://a.si"), "allow")
        self.assertEqual(policy.navigation_scheme_allowed("mailto:a@b.si"), "external")
        self.assertEqual(policy.navigation_scheme_allowed("ms-msdt:/id"), "deny")
        self.assertEqual(policy.navigation_scheme_allowed("search-ms:query=x"), "deny")

    def test_cookie_allow_list_and_user_agent(self):
        self.assertTrue(policy.third_party_cookie_allowed("challenges.cloudflare.com"))
        self.assertFalse(policy.third_party_cookie_allowed("tracker.example"))
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) QtWebEngine/6.8.1 Chrome/122.0 Safari/537.36"
        self.assertNotIn("QtWebEngine", policy.clean_user_agent(ua))
        self.assertIn("Chrome/122.0", policy.clean_user_agent(ua))

    def test_unique_download_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "a.txt"), "w").close()
            self.assertEqual(policy.unique_filename(tmp, "a.txt"), "a (1).txt")
            self.assertEqual(policy.unique_filename(tmp, '..\\evil:name?.exe'), "evil_name_.exe")


class ScriptTests(unittest.TestCase):
    def test_patterns(self):
        youtube = re.compile(policy.pattern_to_regex("*://*.youtube.com/*"), re.I)
        self.assertTrue(youtube.match("https://www.youtube.com/watch?v=1"))
        self.assertTrue(youtube.match("https://youtube.com/"))
        self.assertFalse(youtube.match("https://notyoutube.com/"))
        self.assertFalse(youtube.match("https://youtube.com.evil.example/"))
        self.assertTrue(re.match(policy.pattern_to_regex("*://*/login*"), "https://a.si/login?next=1"))
        self.assertTrue(re.match(policy.pattern_to_regex("file://*"), "file:///C:/a.html"))
        for pattern in policy.adblock.AUTH_SCRIPT_EXCLUSIONS:
            re.compile(policy.pattern_to_regex(pattern))

    def test_specs_mirror_linux_edition(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = policy.SettingsStore(os.path.join(tmp, "s.json"))
            names = [spec["name"] for spec in policy.script_specs(store)]
            self.assertIn("safeer-youtube-keep-watching", names)
            self.assertIn("safeer-hookshot-inserts", names)
            self.assertIn("safeer-youtube-adblock", names)
            for spec in policy.script_specs(store):
                self.assertNotIn("messageHandlers", spec["source"])
            store.set("adblock_enabled", False)
            reduced = [spec["name"] for spec in policy.script_specs(store)]
            self.assertIn("safeer-youtube-keep-watching", reduced)
            self.assertNotIn("safeer-hookshot-inserts", reduced)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_wrapped_scripts_are_valid_javascript(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = policy.SettingsStore(os.path.join(tmp, "s.json"))
            sources = [spec["source"] for spec in policy.script_specs(store)] + [policy.HOME_ADAPTER_JS, policy.STORAGE_GUARD_JS]
            path = os.path.join(tmp, "scripts.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(sources, handle)
            code = "const vm=require('vm');for(const s of require(process.argv[1])) new vm.Script(s);"
            subprocess.run([shutil.which("node"), "-e", code, path], check=True, timeout=60)

    def test_bridge_messages(self):
        self.assertEqual(policy.parse_bridge_message(policy.BRIDGE_PREFIX + '{"action":"navigate","url":"x"}')["url"], "x")
        self.assertIsNone(policy.parse_bridge_message(policy.BRIDGE_PREFIX + "[1]"))
        self.assertIsNone(policy.parse_bridge_message("hello"))


class StartPageTests(unittest.TestCase):
    def test_home_resources(self):
        mime, body = policy.scheme_resource("home", "/", "")
        page = body.decode("utf-8")
        self.assertEqual(mime, "text/html")
        self.assertIn("windows-adapter.js", page)
        self.assertIn('<span class="shield-status">Windows</span>', page)
        self.assertIn('data-i18n="quick_default"', page)
        self.assertLess(page.index("storage-guard.js"), page.index('src="home.js"'))
        self.assertLess(page.index('src="home.js"'), page.index("windows-adapter.js"))
        for path in ("/home.css", "/home.js", "/assets/safeer-mark.svg", "/windows-adapter.js"):
            self.assertIsNotNone(policy.scheme_resource("home", path, ""), path)
        self.assertIsNone(policy.scheme_resource("home", "/../../core/config.py", ""))
        self.assertIsNone(policy.scheme_resource("evil", "/", ""))

    def test_icons_are_valid_svg(self):
        from xml.dom import minidom
        for name in policy.ICON_SHAPES:
            minidom.parseString(policy.icon_svg(name, fill="#9bd478"))

    def test_block_page_escapes_url(self):
        _mime, body = policy.scheme_resource("home", "/blocked", "url=%22%3E%3Cscript%3Ex%3C%2Fscript%3E", "sl")
        text = body.decode("utf-8")
        self.assertNotIn("<script>x", text)
        self.assertIn("Stran je blokirana", text)

    def test_home_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = policy.SettingsStore(os.path.join(tmp, "s.json"))
            store.set("language", "sl")
            state = policy.home_state(store)
            self.assertEqual(state["language"], "sl")
            self.assertEqual(len(state["portals"]), len(policy.DEFAULT_PORTALS))


class BookmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_portals(self):
        portal = policy.make_portal("Safeer", "safeer.si")
        self.assertEqual(portal["url"], "https://safeer.si")
        self.assertIsNone(policy.make_portal("x", "not a url"))
        merged, added = policy.merge_portals([{"url": "https://safeer.si/"}], [portal, {"url": "https://a.si"}])
        self.assertEqual(added, 1)
        self.assertEqual(len(merged), 2)

    def test_imports_chromium_and_firefox_profiles(self):
        local = os.path.join(self.tmp, "Local")
        roaming = os.path.join(self.tmp, "Roaming")
        edge = os.path.join(local, "Microsoft", "Edge", "User Data", "Default")
        os.makedirs(edge)
        with open(os.path.join(edge, "Bookmarks"), "w", encoding="utf-8") as handle:
            json.dump({"roots": {"bookmark_bar": {"type": "folder", "name": "Bar", "children": [
                {"type": "url", "name": "RTV", "url": "https://www.rtvslo.si/"},
                {"type": "url", "name": "Local", "url": "file:///C:/x.html"}]}}}, handle)
        profile = os.path.join(roaming, "Mozilla", "Firefox", "Profiles", "abc.default")
        os.makedirs(profile)
        connection = sqlite3.connect(os.path.join(profile, "places.sqlite"))
        connection.executescript(
            "CREATE TABLE moz_places(id INTEGER PRIMARY KEY, url TEXT);"
            "CREATE TABLE moz_bookmarks(id INTEGER PRIMARY KEY, type INTEGER, fk INTEGER, parent INTEGER, title TEXT, dateAdded INTEGER);"
            "INSERT INTO moz_places VALUES (1, 'https://www.24ur.com/'), (2, 'https://www.rtvslo.si');"
            "INSERT INTO moz_bookmarks VALUES (1, 2, NULL, 0, 'menu', 0), (2, 1, 1, 1, '24ur', 1), (3, 1, 2, 1, 'RTV', 2);")
        connection.commit()
        connection.close()
        items, stats = policy.import_windows_bookmarks({"LOCALAPPDATA": local, "APPDATA": roaming})
        self.assertEqual(stats, {"Microsoft Edge": 1, "Firefox": 2})
        self.assertEqual(sorted(i["url"] for i in items), ["https://www.24ur.com/", "https://www.rtvslo.si/"])


class SignedThreatFeedTests(unittest.TestCase):
    FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures", "signed_feed"))

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fetch_scenario(self, scenario):
        def fetch(url, limit):
            suffix = "latest" if url.endswith("/latest.json") else "bundle"
            with open(os.path.join(self.FIXTURES, f"{scenario}-{suffix}.json"), "rb") as handle:
                return handle.read()
        return fetch

    def test_threat_intel_directory_is_local_app_data(self):
        env = {"LOCALAPPDATA": r"C:\Users\a\AppData\Local"}
        self.assertTrue(policy.threat_intel_dir(env).endswith("ThreatIntel"))
        self.assertEqual(policy.threat_intel_dir({"SAFEER_WINDOWS_DATA_DIR": self.tmp}),
                         os.path.join(self.tmp, "ThreatIntel"))

    def test_disabled_until_a_production_key_is_trusted(self):
        service = policy.threat_intel.ThreatIntelService(self.tmp)
        self.assertEqual(service.enabled, bool(policy.threat_intel.TRUSTED_KEYS))

    def test_verified_feed_blocks_requests_and_navigation(self):
        with open(os.path.join(self.FIXTURES, "public_key.json"), encoding="utf-8") as handle:
            key = json.load(handle)
        service = policy.threat_intel.ThreatIntelService(self.tmp, trusted_keys={key["key_id"]: key["public_key"]},
                                                         base_urls=["https://intel.test"],
                                                         fetch=self.fetch_scenario("valid-100"))
        self.assertTrue(service.update_now())
        policy.adblock.register_threat_matcher(service.match)
        try:
            self.assertEqual(policy.request_decision("https://login.phish.example/", True, "", False), "block-threat")
            self.assertEqual(policy.request_decision("http://files.example:8080/bin.sh", False, "https://a.si/", False),
                             "block-threat")
            self.assertEqual(policy.request_decision("https://clean.example/", True, "", False), "allow")
            self.assertEqual(policy.resolve_input("phish.example", "duckduckgo")[0], "blocked")
            service.store._fetch = self.fetch_scenario("forged-103")
            self.assertFalse(service.update_now())
            self.assertEqual(policy.request_decision("https://phish.example/", True, "", False), "block-threat")
        finally:
            policy.adblock._extra_threat_matchers.remove(service.match)


class BankGuardPolicyTests(unittest.TestCase):
    def tearDown(self):
        policy.adblock._fake_bank_allowed_hosts.clear()

    def page(self, url):
        parsed = urllib.parse.urlsplit(url)
        mime, body = policy.scheme_resource(parsed.netloc, parsed.path, parsed.query, "sl")
        self.assertEqual(mime, "text/html")
        return body.decode("utf-8")

    def test_typed_fake_bank_address_opens_the_warning(self):
        kind, url = policy.resolve_input("nlb-klik-varnost.net/prijava?x=<b>")
        self.assertEqual(kind, "blocked")
        self.assertTrue(url.startswith(policy.HOME_URL + "fake-bank?token="))
        page = self.page(url)
        self.assertIn('data-safeer-fake-bank="nlb"', page)
        self.assertIn('href="https://nlb.si/"', page)
        self.assertIn("history.go(-1)", page)
        self.assertNotIn("<b>", page)
        self.assertEqual(policy.resolve_input("klik.nlb.si")[0], "url")

    def test_warning_content_cannot_be_forged_by_a_link(self):
        page = self.page(policy.HOME_URL + "fake-bank?token=forged&official=evil.example&bank=NLB")
        self.assertNotIn("evil.example", page)
        self.assertNotIn("data-safeer-fake-bank", page)
        self.assertIsNone(policy.fake_bank_continue("token=forged"))

    def test_continue_allows_the_host_once_for_the_session(self):
        verdict = policy.adblock.fake_bank_verdict("https://otpbamka.si/login")
        warning = policy.fake_bank_page_url("https://otpbamka.si/login", verdict, after_load=True)
        page = self.page(warning)
        self.assertIn("history.go(-2)", page)
        continue_url = re.search(r'id="continue" href="([^"]+)"', page).group(1)
        redirect = self.page(continue_url)
        self.assertIn('content="0;url=https://otpbamka.si/login"', redirect)
        self.assertIsNone(policy.adblock.fake_bank_verdict("https://otpbamka.si/login"))
        self.assertEqual(policy.resolve_input("otpbamka.si/login")[0], "url")
        self.assertNotIn("otpbamka.si", self.page(continue_url), "the continue link works once")

    def test_page_signals_and_real_banks(self):
        signals = {"host": "secure-login.example", "scheme": "https", "password": True, "title": "NLB Klik - prijava"}
        self.assertEqual(policy.fake_bank_page_verdict("https://secure-login.example/", signals).bank_id, "nlb")
        self.assertIsNone(policy.fake_bank_page_verdict("https://secure-login.example/", "not a dict"))
        self.assertIsNone(policy.fake_bank_page_verdict("https://klik.nlb.si/", dict(signals, host="klik.nlb.si")))
        self.assertEqual(policy.request_decision("https://www.nlb.si/static/app.js", False, "https://www.nlb.si/", True), "allow")
        self.assertIn("one-time-code", policy.adblock.bank_guard_page_script())

    def test_windows_bundle_contains_the_bank_catalogue(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "build_windows.py"), encoding="utf-8") as handle:
            build = handle.read()
        for name in ("core/bank_guard.py", "core/banks.json", "core/bank_guard_page.js"):
            self.assertIn(f'("{name}", "shared/core")', build)


if __name__ == "__main__":
    unittest.main()
