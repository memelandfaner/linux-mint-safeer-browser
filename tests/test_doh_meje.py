#!/usr/bin/env python3
"""
Meje lokalnega DoH posrednika.

Posrednik posluša na 127.0.0.1, zato ga lahko uporabi vsak program na računalniku.
Ti preizkusi dokazujejo, da ga ni mogoče uporabiti kot odskočno desko v lokalno
omrežje (SSRF): povezave na povratne, zasebne, povezavno-lokalne (metapodatki
oblaka) in CGNAT naslove so zavrnjene, prav tako vsa vrata razen HTTP(S).
"""

import os
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.doh_proxy as doh_proxy  # noqa: E402
from core.doh_proxy import (  # noqa: E402
    DOVOLJENA_VRATA,
    LocalDoHProxy,
    je_dovoljena_vrata,
    je_javni_naslov,
)


class LažniVtič:
    """Vtič, ki si samo zapomni, kaj mu je posrednik odgovoril."""

    def __init__(self):
        self.poslano = b""
        self.zaprt = False

    def sendall(self, podatki):
        self.poslano += podatki

    def close(self):
        self.zaprt = True

    def settimeout(self, _):
        pass


class LažniRazreševalnik:
    """Razreševalnik, ki vsako ime prevede v vnaprej določen naslov."""

    provider = "preizkus"

    def __init__(self, naslov):
        self.naslov = naslov
        self.klici = []

    def resolve(self, hostname, timeout=3.5):
        self.klici.append(hostname)
        return self.naslov


class PreizkusJavnihNaslovov(unittest.TestCase):

    def test_javni_naslovi_so_dovoljeni(self):
        for naslov in ("1.1.1.1", "8.8.8.8", "9.9.9.9", "93.184.216.34",
                       "2606:4700:4700::1111"):
            with self.subTest(naslov=naslov):
                self.assertTrue(je_javni_naslov(naslov))

    def test_povratni_in_zasebni_naslovi_so_zavrnjeni(self):
        for naslov in ("127.0.0.1", "127.1.2.3", "::1", "0.0.0.0",
                       "10.0.0.5", "172.16.0.1", "192.168.1.1",
                       "fd00::1", "fe80::1"):
            with self.subTest(naslov=naslov):
                self.assertFalse(je_javni_naslov(naslov))

    def test_metapodatki_oblaka_so_zavrnjeni(self):
        # 169.254.169.254 je naslov, s katerega se v oblakih berejo poverilnice.
        self.assertFalse(je_javni_naslov("169.254.169.254"))
        self.assertFalse(je_javni_naslov("169.254.0.1"))

    def test_cgnat_in_vecvrstni_so_zavrnjeni(self):
        self.assertFalse(je_javni_naslov("100.64.0.1"))
        self.assertFalse(je_javni_naslov("100.127.255.254"))
        self.assertFalse(je_javni_naslov("224.0.0.1"))
        self.assertFalse(je_javni_naslov("240.0.0.1"))

    def test_ipv6_ki_nosi_ipv4_se_presoja_po_ipv4(self):
        self.assertFalse(je_javni_naslov("::ffff:127.0.0.1"))
        self.assertFalse(je_javni_naslov("::ffff:192.168.0.1"))
        self.assertTrue(je_javni_naslov("::ffff:1.1.1.1"))

    def test_kar_ni_naslov_ni_dovoljeno(self):
        for vrednost in ("", "   ", "ni-naslov", "example.com", "1.1.1.1.1", None):
            with self.subTest(vrednost=vrednost):
                self.assertFalse(je_javni_naslov(vrednost))


class PreizkusVrat(unittest.TestCase):

    def test_brskalniska_vrata_so_dovoljena(self):
        for vrata in (80, 443, 8080, 8443):
            with self.subTest(vrata=vrata):
                self.assertTrue(je_dovoljena_vrata(vrata))
        self.assertEqual(DOVOLJENA_VRATA, frozenset({80, 443, 8080, 8443}))

    def test_druga_vrata_so_zavrnjena(self):
        for vrata in (0, 22, 23, 25, 53, 445, 3306, 5432, 6379, 11211, 65535):
            with self.subTest(vrata=vrata):
                self.assertFalse(je_dovoljena_vrata(vrata))

    def test_nesmiselna_vrednost_je_zavrnjena(self):
        for vrednost in (None, "", "abc", "443a"):
            with self.subTest(vrednost=vrednost):
                self.assertFalse(je_dovoljena_vrata(vrednost))


class PreizkusPripraveCilja(unittest.TestCase):

    def test_lokalni_naslov_je_zavrnjen_pred_povezavo(self):
        razresevalnik = LažniRazreševalnik("127.0.0.1")
        posrednik = LocalDoHProxy(razresevalnik)
        vtic = LažniVtič()

        self.assertIsNone(posrednik._pripravi_cilj(vtic, "zlo.test", 443))
        self.assertIn(b"403", vtic.poslano)
        self.assertTrue(vtic.zaprt)

    def test_metapodatkovni_naslov_je_zavrnjen(self):
        razresevalnik = LažniRazreševalnik("169.254.169.254")
        posrednik = LocalDoHProxy(razresevalnik)
        vtic = LažniVtič()

        self.assertIsNone(posrednik._pripravi_cilj(vtic, "metapodatki.test", 80))
        self.assertIn(b"403", vtic.poslano)

    def test_prepovedana_vrata_ne_sprozijo_niti_razresevanja(self):
        razresevalnik = LažniRazreševalnik("1.1.1.1")
        posrednik = LocalDoHProxy(razresevalnik)
        vtic = LažniVtič()

        self.assertIsNone(posrednik._pripravi_cilj(vtic, "example.com", 22))
        self.assertIn(b"403", vtic.poslano)
        self.assertEqual(razresevalnik.klici, [])

    def test_javni_cilj_gre_naprej(self):
        razresevalnik = LažniRazreševalnik("93.184.216.34")
        posrednik = LocalDoHProxy(razresevalnik)
        vtic = LažniVtič()

        self.assertEqual(posrednik._pripravi_cilj(vtic, "example.com", 443), "93.184.216.34")
        self.assertEqual(vtic.poslano, b"")
        self.assertFalse(vtic.zaprt)

    def test_neuspelo_razresevanje_vrne_502(self):
        razresevalnik = LažniRazreševalnik(None)
        posrednik = LocalDoHProxy(razresevalnik)
        vtic = LažniVtič()

        self.assertIsNone(posrednik._pripravi_cilj(vtic, "ne-obstaja.test", 443))
        self.assertIn(b"502", vtic.poslano)


class PreizkusPosrednikaVZivo(unittest.TestCase):
    """Cel posrednik: CONNECT na ime, ki kaže na lokalni strežnik, ne sme priti skozi."""

    def setUp(self):
        # Strežnik, ki predstavlja napravo v lokalnem omrežju.
        self.zrtev = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.zrtev.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.zrtev.bind(("127.0.0.1", 0))
        self.zrtev.listen(4)
        self.zrtev.settimeout(3.0)
        self.zrtev_vrata = self.zrtev.getsockname()[1]
        self.dosezena = threading.Event()

        def cakaj():
            try:
                povezava, _ = self.zrtev.accept()
                self.dosezena.set()
                povezava.close()
            except OSError:
                pass

        self.nit = threading.Thread(target=cakaj, daemon=True)
        self.nit.start()

        self.posrednik = LocalDoHProxy(LažniRazreševalnik("127.0.0.1"))
        self.vrata = self.posrednik.start()

    def tearDown(self):
        self.posrednik.stop()
        try:
            self.zrtev.close()
        except OSError:
            pass
        self.nit.join(timeout=4)

    def _zahtevaj(self, ukaz: bytes) -> bytes:
        odjemalec = socket.create_connection(("127.0.0.1", self.vrata), timeout=5)
        try:
            odjemalec.sendall(ukaz)
            odjemalec.settimeout(5)
            return odjemalec.recv(1024)
        finally:
            odjemalec.close()

    def test_connect_na_povratni_naslov_je_zavrnjen(self):
        odgovor = self._zahtevaj(b"CONNECT zlo.test:443 HTTP/1.1\r\nHost: zlo.test\r\n\r\n")
        self.assertIn(b"403", odgovor)
        self.assertNotIn(b"200", odgovor)

    def test_connect_na_lokalna_vrata_ne_doseze_streznika(self):
        odgovor = self._zahtevaj(
            f"CONNECT zlo.test:{self.zrtev_vrata} HTTP/1.1\r\nHost: zlo.test\r\n\r\n".encode("latin1")
        )
        self.assertIn(b"403", odgovor)
        time.sleep(0.3)
        self.assertFalse(self.dosezena.is_set(), "posrednik je vzpostavil povezavo v lokalno omrežje")

    def test_navaden_http_zahtevek_na_lokalni_naslov_je_zavrnjen(self):
        odgovor = self._zahtevaj(
            f"GET http://zlo.test:{self.zrtev_vrata}/ HTTP/1.1\r\nHost: zlo.test\r\n\r\n".encode("latin1")
        )
        self.assertIn(b"403", odgovor)
        time.sleep(0.3)
        self.assertFalse(self.dosezena.is_set())

    def test_brez_varovalke_bi_povezava_prisla_skozi(self):
        """
        Protipreizkus (dokaz, da zgornji trije preizkusi res merijo varovalko):
        če varovalko izklopimo, posrednik povezavo v lokalno omrežje vzpostavi.
        """
        prava_naslov = doh_proxy.je_javni_naslov
        prava_vrata = doh_proxy.je_dovoljena_vrata
        doh_proxy.je_javni_naslov = lambda naslov: True
        doh_proxy.je_dovoljena_vrata = lambda vrata: True
        try:
            odgovor = self._zahtevaj(
                f"CONNECT zlo.test:{self.zrtev_vrata} HTTP/1.1\r\nHost: zlo.test\r\n\r\n".encode("latin1")
            )
            self.assertIn(b"200", odgovor)
            self.assertTrue(self.dosezena.wait(3), "protipreizkus ni dosegel lokalnega streznika")
        finally:
            doh_proxy.je_javni_naslov = prava_naslov
            doh_proxy.je_dovoljena_vrata = prava_vrata


if __name__ == "__main__":
    unittest.main()
