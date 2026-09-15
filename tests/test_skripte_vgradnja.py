#!/usr/bin/env python3
"""
Vgradnja uporabniških skript v brskalnik.

Del preizkusov bere izvorno kodo: hočemo vedeti, da se skripte res vbrizgajo
v ločen svet in da most do shrambe ni odprt za kogarkoli. Drugi del preveri
shrambo vrednosti, ne da bi se dotaknil uporabnikovih nastavitev.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import ConfigManager  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def izvorna_koda(rel):
    with open(os.path.join(KOREN, rel), encoding="utf-8") as d:
        return d.read()


class PreizkusVbrizga(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.koda = izvorna_koda("safeer_mint.py")

    def test_skripte_gredo_v_locen_svet(self):
        self.assertIn("WebKit2.UserScript.new_for_world(", self.koda)
        self.assertIn('SVET_SKRIPT = "safeer-userscripts"', self.koda)

    def test_most_je_registriran_v_istem_svetu(self):
        self.assertIn("register_script_message_handler_in_world(", self.koda)
        self.assertIn("script-message-received::", self.koda)

    def test_priprava_gre_skozi_modul_z_glavo(self):
        self.assertIn("uporabniske_skripte.pripravi(", self.koda)
        self.assertIn("from core import userscripts as uporabniske_skripte", self.koda)

    def test_starega_slepega_vbrizga_ni_vec(self):
        # Prej se je koda skripte vbrizgala neposredno, brez glave in brez sveta.
        self.assertNotIn('whitelist = None if pattern in ("*", "")', self.koda)

    def test_most_preveri_od_katere_skripte_je_sporocilo(self):
        odsek = self.koda.split("def on_gm_message", 1)[1][:2000]
        self.assertIn("get_user_scripts()", odsek)
        self.assertIn("if script_id not in znane", odsek)

    def test_skripta_brez_podprtih_funkcij_se_ne_vklopi(self):
        self.assertIn("manjkajoca_dovoljenja(glava)", self.koda)
        self.assertIn("def opozori_manjkajoca_dovoljenja", self.koda)


class PreizkusShrambe(unittest.TestCase):
    """Shramba GM_setValue -- na izmišljenih nastavitvah, uporabnikovih se ne dotaknemo."""

    def nastavitve(self):
        cm = ConfigManager.__new__(ConfigManager)
        cm.settings = {}
        cm.save_settings = lambda: None
        return cm

    def test_shrani_prebere_izbrise(self):
        cm = self.nastavitve()
        self.assertTrue(ConfigManager.set_script_value(cm, "s1", "barva", "modra"))
        self.assertEqual(ConfigManager.get_script_values(cm, "s1"), {"barva": "modra"})
        self.assertTrue(ConfigManager.delete_script_value(cm, "s1", "barva"))
        self.assertEqual(ConfigManager.get_script_values(cm, "s1"), {})

    def test_skripte_se_med_seboj_ne_vidijo(self):
        cm = self.nastavitve()
        ConfigManager.set_script_value(cm, "s1", "skrivnost", 1)
        self.assertEqual(ConfigManager.get_script_values(cm, "s2"), {})

    def test_prevelika_vrednost_je_zavrnjena(self):
        cm = self.nastavitve()
        self.assertFalse(ConfigManager.set_script_value(cm, "s1", "velika", "x" * (64 * 1024 + 10)))
        self.assertEqual(ConfigManager.get_script_values(cm, "s1"), {})

    def test_preveliko_stevilo_kljucev_je_zavrnjeno(self):
        cm = self.nastavitve()
        for i in range(200):
            self.assertTrue(ConfigManager.set_script_value(cm, "s1", f"k{i}", i))
        self.assertFalse(ConfigManager.set_script_value(cm, "s1", "cez_mejo", 1))
        # Obstoječega ključa sme prepisati tudi, ko je predal poln.
        self.assertTrue(ConfigManager.set_script_value(cm, "s1", "k0", 42))

    def test_neveljaven_kljuc_je_zavrnjen(self):
        cm = self.nastavitve()
        for kljuc in ("", None, 5, "d" * 201):
            with self.subTest(kljuc=kljuc):
                self.assertFalse(ConfigManager.set_script_value(cm, "s1", kljuc, 1))

    def test_brisanje_skripte_pobrise_njene_vrednosti(self):
        cm = self.nastavitve()
        cm.settings["user_scripts"] = [{"id": "s1", "name": "x"}]
        ConfigManager.set_script_value(cm, "s1", "a", 1)
        ConfigManager.save_user_scripts = lambda _self, s: cm.settings.__setitem__("user_scripts", s)
        ConfigManager.delete_user_script(cm, "s1")
        self.assertEqual(ConfigManager.get_script_values(cm, "s1"), {})


if __name__ == "__main__":
    unittest.main()
