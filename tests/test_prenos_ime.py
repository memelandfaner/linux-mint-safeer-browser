"""Ime prenesene datoteke ne sme zapustiti mape Prenosi.

Ime predlaga streznik (glava Content-Disposition). Dokler je slo neposredno v
os.path.join, je `../../.bashrc` ali `/etc/cron.d/x` pisalo mimo mape -- privzeto
brez vprasanja uporabniku.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import safeer_mint

varno = safeer_mint.varno_ime_datoteke


class VarnoIme(unittest.TestCase):

    def test_navadno_ime_ostane(self):
        self.assertEqual(varno("porocilo.pdf"), "porocilo.pdf")
        self.assertEqual(varno("Safeer Browser 1.0.26.deb"), "Safeer Browser 1.0.26.deb")

    def test_pot_navzgor_se_oklesti(self):
        self.assertEqual(varno("../../.bashrc"), ".bashrc")
        self.assertEqual(varno("../../../etc/passwd"), "passwd")

    def test_absolutna_pot_se_oklesti(self):
        self.assertEqual(varno("/etc/cron.d/zlo"), "zlo")

    def test_obrnjene_posevnice(self):
        self.assertEqual(varno(r"..\\..\\Windows\\zlo.exe"), "zlo.exe")

    def test_same_pike_dobijo_privzeto_ime(self):
        self.assertEqual(varno(".."), "prenos_datoteke")
        self.assertEqual(varno("."), "prenos_datoteke")
        self.assertEqual(varno(""), "prenos_datoteke")
        self.assertEqual(varno("../"), "prenos_datoteke")

    def test_nadzorni_znaki_izpadejo(self):
        # chr(10) je nova vrstica, chr(0) niclni znak -- oba lahko pride v glavi.
        self.assertEqual(varno("racun" + chr(10) + ".pdf"), "racun.pdf")
        self.assertEqual(varno("racun" + chr(0) + ".pdf"), "racun.pdf")
        self.assertEqual(varno("racun" + chr(9) + ".pdf"), "racun.pdf")

    def test_obrnjena_posevnica_je_locilo_poti(self):
        """Windows pot: zadnji del je ime datoteke."""
        self.assertEqual(varno("racun" + chr(92) + "n.pdf"), "n.pdf")

    def test_predolgo_ime_se_skrajsa(self):
        dolgo = "a" * 400 + ".pdf"
        izid = varno(dolgo)
        self.assertLessEqual(len(izid.encode("utf-8")), 200)
        self.assertTrue(izid.endswith(".pdf"))

    def test_sumniki_prezivijo(self):
        self.assertEqual(varno("račun za september.pdf"), "račun za september.pdf")


class PotVMapi(unittest.TestCase):
    """get_unique_download_path mora ostati v podani mapi."""

    def pot(self, mapa, ime):
        return safeer_mint.SafeerMintBrowser.get_unique_download_path(None, mapa, ime)

    def test_ostane_v_mapi(self):
        mapa = "/home/janez/Prenosi"
        for zlobno in ("../../.bashrc", "/etc/passwd", r"..\\..\\x.exe", "..", ""):
            izid = self.pot(mapa, zlobno)
            self.assertEqual(os.path.dirname(izid), mapa,
                             f"{zlobno!r} je pobegnil iz mape: {izid}")

    def test_navadno_ime_dela(self):
        izid = self.pot("/home/janez/Prenosi", "slika.png")
        self.assertEqual(izid, "/home/janez/Prenosi/slika.png")


if __name__ == "__main__":
    unittest.main(verbosity=2)
