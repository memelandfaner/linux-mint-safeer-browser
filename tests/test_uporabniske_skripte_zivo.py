#!/usr/bin/env python3
"""
Živi preizkus uporabniških skript v pravem WebKitu.

Dokazuje tri stvari, ki jih na papirju ni mogoče dokazati:
  1. skripta se res izvede na strani, ki jo @match zajame,
  2. na strani, ki je @match ne zajame, se ne izvede,
  3. spletna stran ne vidi funkcij GM_ (skripta teče v ločenem svetu).

Preizkus potrebuje zaslon, zato se v CI (brez zaslona) preskoči.
"""

import http.server
import os
import socketserver
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import userscripts  # noqa: E402

STRAN = b"""<!doctype html>
<html><head><title>zacetek</title></head><body>
<script>
window.addEventListener('load', function () {
  var oznaka = document.documentElement.getAttribute('data-safeer-us') || '0';
  document.title = 'us:' + oznaka +
                   ' gm:' + (typeof GM_addStyle) +
                   ' slogov:' + document.querySelectorAll('style').length;
});
</script>
</body></html>
"""


class Streznik(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(STRAN)))
        self.end_headers()
        self.wfile.write(STRAN)

    def log_message(self, *args):
        pass


def skripta(vzorec):
    return (
        "// ==UserScript==\n"
        "// @name        Safeer zivi preizkus\n"
        f"// @match       {vzorec}\n"
        "// @run-at      document-end\n"
        "// @grant       GM_addStyle\n"
        "// ==/UserScript==\n"
        "GM_addStyle('body { outline: 0 }');\n"
        "document.documentElement.setAttribute('data-safeer-us', '1');\n"
    )


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"),
                     "potrebuje zaslon")
class PreizkusVZivo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        socketserver.TCPServer.allow_reuse_address = True
        cls.streznik = socketserver.TCPServer(("127.0.0.1", 0), Streznik)
        cls.vrata = cls.streznik.server_address[1]
        cls.nit = threading.Thread(target=cls.streznik.serve_forever, daemon=True)
        cls.nit.start()

    @classmethod
    def tearDownClass(cls):
        cls.streznik.shutdown()
        cls.streznik.server_close()

    def naslov(self):
        return f"http://127.0.0.1:{self.vrata}/"

    def poglej(self, vzorec):
        """Naloži stran z vbrizgano skripto in vrne naslov strani po nalaganju."""
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gtk, WebKit2, GLib  # noqa: F401

        koda = skripta(vzorec)
        pripravljeno = userscripts.pripravi(
            {"id": "script_zivi", "code": koda}, {}, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(pripravljeno["napaka"], "")

        upravitelj = WebKit2.UserContentManager()
        upravitelj.add_script(WebKit2.UserScript.new_for_world(
            pripravljeno["vir"],
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.END,
            "safeer-userscripts",
            pripravljeno["dovoljeni"],
            pripravljeno["prepovedani"],
        ))

        pogled = WebKit2.WebView.new_with_user_content_manager(upravitelj)
        okno = Gtk.OffscreenWindow()
        okno.add(pogled)
        okno.show_all()

        izid = {}
        zanka = GLib.MainLoop()

        def ob_nalaganju(_p, dogodek):
            if dogodek == WebKit2.LoadEvent.FINISHED:
                GLib.timeout_add(600, koncaj)

        def koncaj():
            izid["naslov"] = pogled.get_title() or ""
            zanka.quit()
            return False

        pogled.connect("load-changed", ob_nalaganju)
        GLib.timeout_add_seconds(15, lambda: (izid.setdefault("naslov", "IZTEK"), zanka.quit())[1])
        pogled.load_uri(self.naslov())
        zanka.run()

        okno.destroy()
        return izid.get("naslov", "")

    def test_skripta_se_izvede_na_ujemajoci_strani(self):
        naslov = self.poglej("*://127.0.0.1/*")
        self.assertIn("us:1", naslov, f"skripta se ni izvedla (naslov: {naslov})")
        self.assertIn("slogov:1", naslov, f"GM_addStyle ni dodal sloga (naslov: {naslov})")

    def test_stran_ne_vidi_funkcij_gm(self):
        naslov = self.poglej("*://127.0.0.1/*")
        self.assertIn("gm:undefined", naslov,
                      f"stran vidi GM_addStyle -- locen svet ne deluje (naslov: {naslov})")

    def test_na_drugi_strani_se_ne_izvede(self):
        naslov = self.poglej("https://example.com/*")
        self.assertIn("us:0", naslov, f"skripta se je izvedla, kjer ne bi smela (naslov: {naslov})")
        self.assertIn("slogov:0", naslov)


if __name__ == "__main__":
    unittest.main()
