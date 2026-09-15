"""Most JS sme slusati samo nase strani.

Vsak zavihek registrira `window.webkit.messageHandlers.safeer`. Dokler handler ni
gledal, kdo poslje sporocilo, je lahko poljubna spletna stran sprozila preusmeritev,
odprla uvoz zaznamkov (ki bere Firefoxove in Chromove datoteke) ali pogovorno okno za
privzeti brskalnik. Ta preizkus to zapira: zaupna dejanja samo z nasih strani, stevca
oglasov od kjerkoli (poslje ju nas vbrizgani skript), a z omejeno vrednostjo.
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import safeer_mint


class NasaStran(unittest.TestCase):
    """je_nasa_notranja_stran ne sme nasesti podnizu »/ui/«."""

    def test_domaca_stran_je_nasa(self):
        pot = os.path.join(safeer_mint.BASE_DIR, "ui", "home.html")
        self.assertTrue(safeer_mint.je_nasa_notranja_stran(f"file://{pot}"))

    def test_safeer_protokol_je_nas(self):
        self.assertTrue(safeer_mint.je_nasa_notranja_stran("safeer://home"))
        self.assertTrue(safeer_mint.je_nasa_notranja_stran("safeer://procesi"))

    def test_tuja_datoteka_s_podnizom_ui_ni_nasa(self):
        self.assertFalse(safeer_mint.je_nasa_notranja_stran("file:///tmp/ui/phishing.html"))
        self.assertFalse(safeer_mint.je_nasa_notranja_stran("file:///home/janez/ui/x.html"))

    def test_spletna_stran_ni_nasa(self):
        self.assertFalse(safeer_mint.je_nasa_notranja_stran("https://example.com/ui/x.html"))
        self.assertFalse(safeer_mint.je_nasa_notranja_stran(""))

    def test_is_safe_web_url_ne_dovoli_tuje_datoteke(self):
        self.assertFalse(safeer_mint.is_safe_web_url("file:///tmp/ui/phishing.html"))
        self.assertTrue(safeer_mint.is_safe_web_url("https://safeer.si/"))
        self.assertFalse(safeer_mint.is_safe_web_url("javascript:alert(1)"))


class LaznoSporocilo:
    """Posnema JS vrednost, kot jo dobi handler."""

    def __init__(self, podatki):
        self._json = json.dumps(podatki)

    def get_js_value(self):
        return self

    def to_json(self, _indent):
        return self._json


class LaznePogled:
    def __init__(self, uri):
        self._uri = uri
        self.nalozeni = []

    def get_uri(self):
        return self._uri

    def load_uri(self, url):
        self.nalozeni.append(url)


class Most(unittest.TestCase):
    """on_js_message: kaj sme tuja stran in kaj samo nasa."""

    def okno(self):
        """Najmanjsi mozni objekt z metodami, ki jih handler klice."""
        okno = mock.Mock(spec=[
            "set_as_default_browser", "open_settings_dialog", "open_customizer_dialog",
            "open_portals_dialog", "open_portal_editor_dialog", "open_bookmarks_import_dialog",
            "toggle_sidebar_panel", "update_ui_language", "update_shield_button_label",
            "get_active_webview", "config", "ZAUPNA_DEJANJA",
        ])
        okno.ZAUPNA_DEJANJA = safeer_mint.SafeerMintBrowser.ZAUPNA_DEJANJA
        okno.config = mock.Mock(spec=["set", "increment_ads_blocked", "increment_threats_blocked"])
        okno.get_active_webview.return_value = None
        return okno

    def poslji(self, okno, podatki, izvor):
        pogled = LaznePogled(izvor)
        safeer_mint.SafeerMintBrowser.on_js_message(okno, None, LaznoSporocilo(podatki), pogled)
        return pogled

    def test_tuja_stran_ne_more_preusmeriti(self):
        okno = self.okno()
        pogled = self.poslji(okno, {"action": "navigate", "url": "https://zlo.example/"},
                             "https://napadalec.example/")
        self.assertEqual(pogled.nalozeni, [], "tuja stran ne sme premakniti zavihka")

    def test_tuja_stran_ne_more_odpreti_uvoza_zaznamkov(self):
        okno = self.okno()
        self.poslji(okno, {"action": "open_sidebar", "service": "import_bookmarks"},
                    "https://napadalec.example/")
        okno.open_bookmarks_import_dialog.assert_not_called()

    def test_tuja_stran_ne_more_zahtevati_privzetega_brskalnika(self):
        okno = self.okno()
        self.poslji(okno, {"action": "set_default_browser"}, "https://napadalec.example/")
        okno.set_as_default_browser.assert_not_called()

    def test_tuja_stran_ne_more_zamenjati_jezika(self):
        okno = self.okno()
        self.poslji(okno, {"action": "set_language", "language": "de"},
                    "https://napadalec.example/")
        okno.config.set.assert_not_called()

    def test_nasa_domaca_stran_sme_vse_to(self):
        okno = self.okno()
        domaca = "file://" + os.path.join(safeer_mint.BASE_DIR, "ui", "home.html")

        pogled = self.poslji(okno, {"action": "navigate", "url": "https://safeer.si/"}, domaca)
        self.assertEqual(pogled.nalozeni, ["https://safeer.si/"])

        self.poslji(okno, {"action": "open_sidebar", "service": "import_bookmarks"}, domaca)
        okno.open_bookmarks_import_dialog.assert_called_once()

        self.poslji(okno, {"action": "set_default_browser"}, domaca)
        okno.set_as_default_browser.assert_called_once()

    def test_nasa_stran_ne_more_na_javascript_naslov(self):
        okno = self.okno()
        domaca = "file://" + os.path.join(safeer_mint.BASE_DIR, "ui", "home.html")
        pogled = self.poslji(okno, {"action": "navigate", "url": "javascript:alert(1)"}, domaca)
        self.assertEqual(pogled.nalozeni, [], "tudi nasa stran ne sme na javascript:")

    def test_stevec_oglasov_dela_z_vsake_strani(self):
        """Poslje ga nas vbrizgani skript, zato ga ne smemo zavrniti."""
        okno = self.okno()
        self.poslji(okno, {"action": "increment_ads", "count": 3}, "https://24ur.com/")
        okno.config.increment_ads_blocked.assert_called_once_with(3)

    def test_stevca_ni_mogoce_napihniti(self):
        okno = self.okno()
        self.poslji(okno, {"action": "increment_ads", "count": 10 ** 9}, "https://zlo.example/")
        okno.config.increment_ads_blocked.assert_called_once_with(100)

    def test_brez_posiljatelja_zaupna_dejanja_ne_gredo(self):
        """Ce izvora ne moremo ugotoviti, zaupnega dejanja ne izvedemo."""
        okno = self.okno()
        safeer_mint.SafeerMintBrowser.on_js_message(
            okno, None, LaznoSporocilo({"action": "set_default_browser"}), None)
        okno.set_as_default_browser.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
