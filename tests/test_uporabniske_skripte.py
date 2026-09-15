#!/usr/bin/env python3
"""
Uporabniške skripte: glava, vzorci naslovov in dovoljenja.

Kar je tu preverjeno, smemo obljubiti; kar ni, ne.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import userscripts  # noqa: E402

GLAVA = """// ==UserScript==
// @name         Safeer YouTube Cleaner
// @namespace    safeer
// @version      1.2
// @description  Skrije komentarje
// @match        https://www.youtube.com/*
// @match        https://m.youtube.com/*
// @exclude      https://www.youtube.com/live_chat*
// @run-at       document-start
// @noframes
// @grant        GM_addStyle
// @grant        GM_getValue
// ==/UserScript==

GM_addStyle('#comments { display: none !important; }');
"""


class PreizkusGlave(unittest.TestCase):

    def test_prebere_vsa_polja(self):
        g = userscripts.razclenii_glavo(GLAVA)
        self.assertTrue(g["ima_glavo"])
        self.assertEqual(g["name"], "Safeer YouTube Cleaner")
        self.assertEqual(g["version"], "1.2")
        self.assertEqual(g["matches"], ["https://www.youtube.com/*", "https://m.youtube.com/*"])
        self.assertEqual(g["excludes"], ["https://www.youtube.com/live_chat*"])
        self.assertEqual(g["run_at"], "document-start")
        self.assertTrue(g["noframes"])
        self.assertEqual(g["grants"], ["GM_addStyle", "GM_getValue"])

    def test_brez_glave(self):
        g = userscripts.razclenii_glavo("console.log('zdravo');")
        self.assertFalse(g["ima_glavo"])
        self.assertEqual(g["matches"], [])

    def test_neveljaven_run_at_pade_na_document_end(self):
        g = userscripts.razclenii_glavo(
            "// ==UserScript==\n// @run-at kadarkoli\n// ==/UserScript==\n")
        self.assertEqual(g["run_at"], "document-end")

    def test_include_steje_kot_match(self):
        g = userscripts.razclenii_glavo(
            "// ==UserScript==\n// @include https://example.com/*\n// ==/UserScript==\n")
        self.assertEqual(g["matches"], ["https://example.com/*"])


class PreizkusVzorcev(unittest.TestCase):

    def test_navadni_vzorci_ostanejo(self):
        self.assertEqual(userscripts.vzorec_v_webkit("https://www.youtube.com/*"),
                         "https://www.youtube.com/*")
        self.assertEqual(userscripts.vzorec_v_webkit("*://*.example.com/*"),
                         "*://*.example.com/*")

    def test_vse_strani(self):
        for v in ("<all_urls>", "*", "*://*/*", "http*://*/*"):
            with self.subTest(v=v):
                self.assertIsNone(userscripts.vzorec_v_webkit(v))

    def test_golo_ime_domene(self):
        self.assertEqual(userscripts.vzorec_v_webkit("rtvslo.si"), "*://*.rtvslo.si/*")

    def test_manjkajoca_pot_se_dopolni(self):
        self.assertEqual(userscripts.vzorec_v_webkit("https://example.com"),
                         "https://example.com/*")

    def test_nevarne_sheme_so_zavrnjene(self):
        for v in ("file:///etc/passwd", "safeer://home", "javascript:alert(1)",
                  "ftp://example.com/*", "", "   "):
            with self.subTest(v=v):
                self.assertEqual(userscripts.vzorec_v_webkit(v), "")

    def test_http_zvezdica_je_katerakoli_shema(self):
        self.assertEqual(userscripts.vzorec_v_webkit("http*://example.com/*"),
                         "*://example.com/*")


class PreizkusSeznamov(unittest.TestCase):

    def test_iz_glave(self):
        g = userscripts.razclenii_glavo(GLAVA)
        dovoljeni, prepovedani = userscripts.seznama_naslovov(g)
        self.assertEqual(dovoljeni, ["https://www.youtube.com/*", "https://m.youtube.com/*"])
        self.assertEqual(prepovedani, ["https://www.youtube.com/live_chat*"])

    def test_stara_skripta_brez_glave_uporabi_svoj_vzorec(self):
        g = userscripts.razclenii_glavo("console.log(1);")
        dovoljeni, _ = userscripts.seznama_naslovov(g, "rtvslo.si")
        self.assertEqual(dovoljeni, ["*://*.rtvslo.si/*"])

    def test_brez_uporabnega_vzorca_ostane_prazno(self):
        g = userscripts.razclenii_glavo(
            "// ==UserScript==\n// @match file:///*\n// ==/UserScript==\n")
        dovoljeni, _ = userscripts.seznama_naslovov(g)
        self.assertEqual(dovoljeni, [])

    def test_nase_strani_so_vedno_prepovedane(self):
        blok = userscripts.notranji_blok_seznam("/home/janez/safeer-lms")
        self.assertIn("safeer://*", blok)
        self.assertTrue(any(b.startswith("file:///home/janez/safeer-lms/ui") for b in blok))


class PreizkusDovoljenj(unittest.TestCase):

    def test_podprta_gredo_skozi(self):
        g = userscripts.razclenii_glavo(GLAVA)
        self.assertEqual(userscripts.manjkajoca_dovoljenja(g), [])

    def test_nepodprta_so_nastete(self):
        g = userscripts.razclenii_glavo(
            "// ==UserScript==\n// @grant GM_xmlhttpRequest\n// @grant GM_addStyle\n// ==/UserScript==\n")
        self.assertEqual(userscripts.manjkajoca_dovoljenja(g), ["GM_xmlhttpRequest"])

    def test_require_steje_kot_manjkajoce(self):
        g = userscripts.razclenii_glavo(
            "// ==UserScript==\n// @require https://code.jquery.com/jquery.min.js\n// ==/UserScript==\n")
        self.assertIn("@require", userscripts.manjkajoca_dovoljenja(g))


class PreizkusPredpone(unittest.TestCase):

    def test_da_samo_zahtevane_funkcije(self):
        g = userscripts.razclenii_glavo(GLAVA)
        js = userscripts.predpona_gm("script_1", g, {"a": 1})
        self.assertIn("const GM_addStyle", js)
        self.assertIn("const GM_getValue", js)
        self.assertNotIn("const GM_setValue", js)
        self.assertNotIn("const GM_deleteValue", js)

    def test_brez_grantov_ni_gm_funkcij(self):
        g = userscripts.razclenii_glavo(
            "// ==UserScript==\n// @match https://example.com/*\n// ==/UserScript==\n")
        js = userscripts.predpona_gm("script_1", g, {})
        self.assertNotIn("const GM_addStyle", js)
        self.assertNotIn("const GM_setValue", js)
        self.assertIn("const GM_log", js)

    def test_vrednosti_so_vgnezdene_varno(self):
        g = userscripts.razclenii_glavo(GLAVA)
        js = userscripts.predpona_gm("script_1", g, {"x": "</script><script>alert(1)</script>"})
        self.assertNotIn("</script>", js)
        self.assertIn("<\\/script>", js)

    def test_vrednosti_so_dosegljive_kot_posnetek(self):
        g = userscripts.razclenii_glavo(GLAVA)
        js = userscripts.predpona_gm("script_1", g, {"kljuc": "vrednost"})
        self.assertIn(json.dumps({"kljuc": "vrednost"}, ensure_ascii=False), js)


class PreizkusPriprave(unittest.TestCase):

    BASE = "/home/janez/safeer-lms"

    def test_cela_priprava(self):
        rezultat = userscripts.pripravi(
            {"id": "script_1", "code": GLAVA, "pattern": "*", "run_at": "end"}, {}, self.BASE)
        self.assertEqual(rezultat["napaka"], "")
        self.assertEqual(rezultat["run_at"], "document-start")
        self.assertFalse(rezultat["vsi_okvirji"])          # @noframes
        self.assertEqual(rezultat["dovoljeni"],
                         ["https://www.youtube.com/*", "https://m.youtube.com/*"])
        self.assertIn("safeer://*", rezultat["prepovedani"])
        self.assertIn("GM_addStyle", rezultat["vir"])
        self.assertTrue(rezultat["vir"].rstrip().endswith("})();"))

    def test_skripta_z_nepodprto_funkcijo_se_ne_pripravi(self):
        koda = ("// ==UserScript==\n// @match https://example.com/*\n"
                "// @grant GM_xmlhttpRequest\n// ==/UserScript==\nGM_xmlhttpRequest({});\n")
        rezultat = userscripts.pripravi({"id": "s", "code": koda}, {}, self.BASE)
        self.assertEqual(rezultat["napaka"], "manjkajoca_dovoljenja")
        self.assertEqual(rezultat["manjka"], ["GM_xmlhttpRequest"])

    def test_skripta_brez_uporabnega_vzorca_se_ne_pripravi(self):
        koda = "// ==UserScript==\n// @match file:///*\n// ==/UserScript==\n"
        rezultat = userscripts.pripravi({"id": "s", "code": koda}, {}, self.BASE)
        self.assertEqual(rezultat["napaka"], "ni_veljavnega_vzorca")

    def test_stara_skripta_brez_glave_dela_naprej(self):
        rezultat = userscripts.pripravi(
            {"id": "s", "code": "console.log('zdravo');", "pattern": "rtvslo.si", "run_at": "start"},
            {}, self.BASE)
        self.assertEqual(rezultat["napaka"], "")
        self.assertEqual(rezultat["run_at"], "document-start")
        self.assertEqual(rezultat["dovoljeni"], ["*://*.rtvslo.si/*"])


if __name__ == "__main__":
    unittest.main()
