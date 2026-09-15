#!/usr/bin/env python3
"""
Stik v paketu mora biti nas.

V paketu .deb je bil vzdrzevalec »Safeer Sovereign Security Team
<support@safeer.org>«, te domene pa nimamo -- uporabnik bi pisal nekomu drugemu.
Ta preizkus pazi, da se tak naslov ne vrne.
"""

import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STIK = "memelandfaner@users.noreply.github.com"
NASE_DOMENE = ("safeer.si", "users.noreply.github.com", "github.com")

PRESKOCI_MAPE = {".git", "build", "dist", "__pycache__", ".flatpak-builder",
                 ".pytest_cache", "tests"}
PRESKOCI_KONCNICE = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".gz", ".deb",
                     ".flatpak", ".AppImage", ".apk", ".zip")

PAKIRANJE = ("build_deb.sh", "debian/control", "debian/copyright",
             "debian/changelog", "scripts/build_source_package.sh")


def beri(pot):
    try:
        with open(pot, encoding="utf-8") as d:
            return d.read()
    except (UnicodeDecodeError, OSError):
        return None


def besedilne_datoteke():
    for koren, mape, datoteke in os.walk(KOREN):
        mape[:] = [m for m in mape if m not in PRESKOCI_MAPE]
        for ime in datoteke:
            if ime.endswith(PRESKOCI_KONCNICE):
                continue
            pot = os.path.join(koren, ime)
            vsebina = beri(pot)
            if vsebina is not None:
                yield os.path.relpath(pot, KOREN), vsebina


class PreizkusStika(unittest.TestCase):

    def test_v_repozitoriju_ni_tuje_domene(self):
        najdeno = [pot for pot, vsebina in besedilne_datoteke() if "safeer.org" in vsebina]
        self.assertEqual(najdeno, [], "safeer.org ni nasa domena")

    def test_vzdrzevalec_deb_paketa_je_nas(self):
        vsebina = beri(os.path.join(KOREN, "build_deb.sh"))
        vrstice = [v for v in vsebina.splitlines() if v.startswith("Maintainer:")]
        self.assertTrue(vrstice, "build_deb.sh nima vrstice Maintainer")
        for v in vrstice:
            self.assertIn(STIK, v)

    def test_vsi_naslovi_v_pakiranju_so_z_nasih_domen(self):
        naslovi = set()
        for rel in PAKIRANJE:
            vsebina = beri(os.path.join(KOREN, rel))
            if vsebina:
                naslovi.update(re.findall(r"[\w.+-]+@[\w.-]+", vsebina))
        self.assertTrue(naslovi, "v pakiranju ni nobenega naslova")
        for naslov in naslovi:
            with self.subTest(naslov=naslov):
                self.assertTrue(naslov.endswith(NASE_DOMENE), naslov)


if __name__ == "__main__":
    unittest.main()
