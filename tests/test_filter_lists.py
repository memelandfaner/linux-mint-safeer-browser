"""EasyList as a WebKit content filter: the list agent (no network) and, where WebKitGTK is installed
(the CI container, a developer's Linux Mint), the real rule compiler on every rule shape we generate."""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import filter_lists, webkit_filters  # noqa: E402

EASYLIST = "[Adblock Plus 2.0]\n! Title: EasyList\n" + "\n".join(f"||ad{i}.example^" for i in range(1200)) + \
    "\n@@||ok.example^$document\n/ads/banner.$image\n||t.example^$third-party,script\n"


class ConverterCopyTests(unittest.TestCase):
    def test_desktop_copy_matches_the_catalogue_module_shape(self):
        rules = webkit_filters.convert(EASYLIST.splitlines(), never_block_domains=["nlb.si"])
        self.assertEqual(len(rules), 1200 + 1 + 1 + 1 + 1)
        self.assertEqual(rules[-1]["trigger"]["if-domain"], ["*nlb.si"])
        self.assertEqual(rules[-1]["action"]["type"], "ignore-previous-rules")


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="safeer-filter-lists-"))
        self.delivered = []
        self.responses = []

    def fetch(self, url, etag, last_modified):
        self.responses.append((url, etag, last_modified))
        if etag == "v1":
            return 304, b"", "v1", ""
        return 200, EASYLIST.encode("utf-8"), "v1", ""

    def agent(self, **kw):
        return filter_lists.FilterListAgent(self.dir, on_rules=lambda text, source: self.delivered.append((json.loads(text), source)),
                                            never_block_domains=["nlb.si"], fetch=self.fetch, first_delay=999, **kw)

    def test_download_convert_save_and_conditional_reload(self):
        a = self.agent()
        self.assertFalse(a.load_saved(), "nothing saved yet")
        self.assertTrue(a.update_now())
        self.assertEqual(len(self.delivered), 1)
        rules, source = self.delivered[0]
        self.assertEqual(source, "download")
        self.assertEqual(a.rule_count, len(rules))
        self.assertTrue((self.dir / "easylist.txt").is_file() and (self.dir / "easylist.meta.json").is_file())
        self.assertFalse(a.update_now(), "304 = unchanged")
        self.assertEqual(self.responses[-1][1], "v1", "the saved ETag is sent")
        self.assertEqual(len(self.delivered), 1)
        b = self.agent()
        self.assertTrue(b.load_saved())
        self.assertEqual(self.delivered[-1][1], "saved")
        self.assertEqual(b.status()["rules"], a.rule_count)

    def test_error_pages_and_damaged_files_keep_the_previous_list(self):
        a = self.agent()
        self.assertTrue(a.update_now())
        a.fetch = lambda url, etag, lm: (200, b"<html>login</html>", "", "")
        self.assertFalse(a.update_now())
        self.assertIn("HTML", a.last_error)
        a.fetch = lambda url, etag, lm: (200, b"[Adblock]\n||a.example^\n", "", "")
        self.assertFalse(a.update_now(), "too short")
        a.fetch = lambda url, etag, lm: (_ for _ in ()).throw(OSError("offline"))
        self.assertFalse(a.update_now())
        self.assertEqual(len(self.delivered), 1)
        (self.dir / "easylist.txt").write_bytes(b"[Adblock]\n" + b"||x.example^\n" * 2000)
        with self.assertRaises(filter_lists.ListRejected):
            self.agent().load_saved()

    def test_start_returns_at_once_and_delivers_the_saved_list_in_the_background(self):
        a = self.agent()
        a.update_now()
        b = self.agent()
        started = time.monotonic()
        self.assertTrue(b.start())
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(b.loaded.wait(10))
        b.stop()
        self.assertEqual(self.delivered[-1][1], "saved")


def _webkit():
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import GLib, WebKit2

        return GLib, WebKit2
    except Exception:  # noqa: BLE001 - not installed here
        return None, None


SHAPES = [
    "||ads.example^", "||ads.example^$third-party,script", "||ads.example^$~third-party", "||ads.example^$image,stylesheet",
    "||ads.example^$~image", "||ads.example^$domain=news.example|blog.example", "||ads.example^$domain=~mail.example",
    "||ads.example/path/*/x^", "|http://banner.example/", ".gif|", "-ad-sidebar.$image", "&adzone=", "/ads/banner.$image",
    "||i.example^$important", "@@||cdn.example/ok.js$script", "@@||ok.example^$document", "@@||shop.example^",
    "||x.example^$xmlhttprequest,subdocument,font,media,object,websocket,ping,other", "||weird-chars.example/a+b(c)d?e=f",
]


@unittest.skipIf(_webkit()[1] is None, "WebKitGTK is not installed")
class WebKitCompileTests(unittest.TestCase):
    """WebKit refuses the whole list when one rule uses a construct its compiler does not know."""

    def compile(self, rules):
        GLib, WebKit2 = _webkit()
        store = WebKit2.UserContentFilterStore.new(tempfile.mkdtemp(prefix="safeer-filter-store-"))
        outcome = {}
        loop = GLib.MainLoop()

        def done(store, result, _data):
            try:
                outcome["filter"] = store.save_finish(result)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = str(exc)
            loop.quit()

        store.save("safeer-test", GLib.Bytes.new(webkit_filters.to_json(rules).encode("utf-8")), None, done, None)
        GLib.timeout_add_seconds(120, loop.quit)
        loop.run()
        return outcome

    def test_every_rule_shape_compiles(self):
        rules = webkit_filters.convert(SHAPES, never_block_domains=["nlb.si", "gov.si"])
        self.assertEqual(len(rules), len(SHAPES) + 1, "every shape must survive conversion")
        outcome = self.compile(rules)
        self.assertNotIn("error", outcome, outcome.get("error"))
        self.assertIsNotNone(outcome.get("filter"))

    def test_a_large_host_list_compiles(self):
        rules = webkit_filters.convert([f"||ad{i}.example^" for i in range(20000)])
        outcome = self.compile(rules)
        self.assertNotIn("error", outcome, outcome.get("error"))


if __name__ == "__main__":
    unittest.main()
