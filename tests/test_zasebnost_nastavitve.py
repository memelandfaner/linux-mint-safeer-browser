"""Kar README obljublja, mora biti v kodi.

Ta preizkus bere kodo, ker nastavitev brez zagnanega WebKita ni mogoce vprasati.
Lovita ga dve vrsti napake: tiho poslabsanje nastavitve in trditev v README, ki ji
koda ne sledi.
"""
import os
import re
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
GLAVNA = (KOREN / "safeer_mint.py").read_text(encoding="utf-8")
README = (KOREN / "README.md").read_text(encoding="utf-8")


class Piskotki(unittest.TestCase):

    def test_tretje_osebe_so_blokirane(self):
        self.assertIn("CookieAcceptPolicy.NO_THIRD_PARTY", GLAVNA,
                      "README obljublja blokado piskotkov tretjih oseb")
        self.assertNotIn("CookieAcceptPolicy.ALWAYS", GLAVNA)

    def test_readme_to_obljublja(self):
        self.assertTrue(
            re.search(r"(tretjih oseb|third-party)", README, re.I),
            "ce trditve ni vec v README, popravi tudi ta preizkus")


class NastavitveWebKita(unittest.TestCase):

    def test_razvijalska_orodja_niso_vedno_vklopljena(self):
        self.assertNotIn("set_enable_developer_extras(True)", GLAVNA,
                         "razvijalska orodja naj vklopi uporabnik, ne mi za vsako stran")

    def test_stran_ne_odpira_oken_sama(self):
        self.assertIn("set_javascript_can_open_windows_automatically(False)", GLAVNA)

    def test_websql_je_izklopljen(self):
        self.assertIn("set_enable_html5_database(False)", GLAVNA)

    def test_kar_je_bilo_ze_prav_ostane(self):
        self.assertIn("set_enable_hyperlink_auditing(False)", GLAVNA)
        self.assertIn("set_enable_dns_prefetching(False)", GLAVNA)


class MostJS(unittest.TestCase):

    def test_zaupna_dejanja_so_nasteta(self):
        self.assertIn("ZAUPNA_DEJANJA", GLAVNA)
        for dejanje in ("navigate", "set_default_browser", "open_sidebar", "set_language"):
            self.assertIn(f'"{dejanje}"', GLAVNA)

    def test_handler_pozna_posiljatelja(self):
        self.assertIn("def on_js_message(self, content_mgr, js_result, posiljatelj=None)", GLAVNA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
