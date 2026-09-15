# -*- coding: utf-8 -*-
"""Noben jezik ne sme zaostajati za privzetim.

Ta test je nastal, ker smo v enem dnevu isto vrzel nasli trikrat rocno.
Tece v obstojeci zbirki testov, zato ga ni treba posebej zaganjati.
"""
import os
import subprocess
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKRIPTA = os.path.join(KOREN, "tools", "preveri-prevode.py")


class Prevodi(unittest.TestCase):

    def test_skripta_obstaja(self):
        self.assertTrue(os.path.isfile(SKRIPTA), "manjka tools/preveri-prevode.py")

    def test_vsi_jeziki_imajo_vse_kljuce(self):
        izid = subprocess.run([sys.executable, SKRIPTA, KOREN],
                              capture_output=True, text=True, timeout=120)
        if izid.returncode != 0:
            self.fail("nepopolni prevodi:\n" + izid.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
