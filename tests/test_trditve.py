#!/usr/bin/env python3
"""
Trditve do uporabnika morajo drzati.

Dve pravili, ki ju je postavil Matej (15. 9. 2026):
1. Zmoznost, da na YouTubu ni oglasov, obdrzimo -- ne oglasujemo je.
2. Ne obljubljamo Tampermonkeyjevega API-ja, ker ga nimamo; imamo svoj
   mehanizem za uporabniske skripte in tako ga tudi imenujemo.
"""

import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Besedila, ki jih vidi uporabnik (vmesnik, README, opisi paketov).
BESEDILA = [
    "README.md",
    "PACKAGING.md",
    "SECURITY.md",
    "io.github.memelandfaner.SafeerBrowser.metainfo.xml",
    "build_deb.sh",
    "scripts/build_source_package.sh",
    "core/i18n.py",
    "ui/home.html",
    "ui/home.js",
]

YOUTUBE_OGLASI = re.compile(
    r"(youtube[^.\n]{0,80}(brez oglasov|brez reklam|zero[- ]ad|no ads|ad[- ]free)"
    r"|(brez oglasov|zero[- ]ad|no ads|ad[- ]free)[^.\n]{0,80}youtube)",
    re.IGNORECASE)
TUJE_RAZSIRITVE = re.compile(r"(tampermonkey|greasemonkey|violentmonkey)", re.IGNORECASE)


def preberi(rel):
    pot = os.path.join(KOREN, rel)
    if not os.path.exists(pot):
        return None
    with open(pot, encoding="utf-8") as d:
        return d.read()


class PreizkusTrditev(unittest.TestCase):

    def test_ne_obljubljamo_youtuba_brez_oglasov(self):
        najdeno = []
        for rel in BESEDILA:
            vsebina = preberi(rel)
            if vsebina is None:
                continue
            for st, v in enumerate(vsebina.splitlines(), 1):
                if YOUTUBE_OGLASI.search(v):
                    najdeno.append(f"{rel}:{st}: {v.strip()[:120]}")
        self.assertEqual(najdeno, [], "zmoznost obdrzimo, obljube ne dajemo")

    def test_ne_obljubljamo_tujega_api_ja(self):
        najdeno = []
        for rel in BESEDILA:
            vsebina = preberi(rel)
            if vsebina is None:
                continue
            for st, v in enumerate(vsebina.splitlines(), 1):
                if TUJE_RAZSIRITVE.search(v):
                    najdeno.append(f"{rel}:{st}: {v.strip()[:120]}")
        self.assertEqual(najdeno, [], "svojega mehanizma ne imenujemo po tuji razsiritvi")

    def test_uporabniske_skripte_so_se_vedno_opisane(self):
        # Zmoznost ostaja in jo smemo opisati -- samo s pravim imenom.
        vsebina = preberi("core/i18n.py")
        self.assertIsNotNone(vsebina)
        self.assertIn("user scripts", vsebina.lower())


if __name__ == "__main__":
    unittest.main()
