"""Jamstvo, da Safeer Link na Linuxu deluje tudi pri uporabniku z golim paketom.

Paket safeer-browser je odvisen samo od GTK in WebKita. Zeroconf in vse drugo je
neobvezno: ce ga ni, mora odkrivanje delovati po HTTP poti in brskalnik se ne sme
niti zatakniti niti javiti napake. Ta preizkus to dokaze tako, da uvoz zeroconfa
zares onemogoci.
"""
import builtins
import importlib
import sys
import unittest

from core import link_hub

NEOBVEZNE = ("zeroconf", "websockets", "websocket", "requests")


class BrezNeobveznih(unittest.TestCase):
    """Odklopimo neobvezne knjiznice in preverimo, da vse se vedno drzi."""

    def setUp(self):
        self._pravi_uvoz = builtins.__import__

        def brez(ime, *args, **kw):
            koren = ime.split(".")[0]
            if koren in NEOBVEZNE:
                raise ImportError(f"{koren} (namenoma odklopljen v preizkusu)")
            return self._pravi_uvoz(ime, *args, **kw)

        builtins.__import__ = brez
        self._shranjeni = {i: sys.modules.pop(i) for i in list(sys.modules)
                           if i.split(".")[0] in NEOBVEZNE}

    def tearDown(self):
        builtins.__import__ = self._pravi_uvoz
        sys.modules.update(self._shranjeni)

    def test_modul_se_uvozi(self):
        importlib.reload(link_hub)
        self.assertTrue(hasattr(link_hub, "poisci_hub"))
        self.assertTrue(hasattr(link_hub, "WsOdjemalec"))

    def test_mdns_mirno_odpove(self):
        self.assertIsNone(link_hub._poisci_z_mdns(cas=0.2),
                          "brez zeroconfa mora mDNS mirno vrniti None")

    def test_odkrivanje_uporabi_http_pot(self):
        """Brez zeroconfa mora odkrivanje poskusiti HTTP pot in vrniti njen naslov.

        Nadomestni je_hub pove, kateri kandidat "se oglasi", zato preizkus ne
        potrebuje delujocega Huba in tece enako doma kot v CI.
        """
        poskuseni = []
        pravi_je_hub = link_hub.je_hub

        def lazni_je_hub(osnova, timeout=2.0):
            poskuseni.append(osnova)
            return osnova == f"http://127.0.0.1:{link_hub.PRIVZETA_VRATA}"

        link_hub.je_hub = lazni_je_hub
        try:
            naslov = link_hub.poisci_hub()
        finally:
            link_hub.je_hub = pravi_je_hub

        self.assertEqual(naslov,
                         f"ws://127.0.0.1:{link_hub.PRIVZETA_VRATA}{link_hub.POT_WS}",
                         "brez zeroconfa mora odkrivanje vrniti naslov iz HTTP poti")
        self.assertIn(f"http://{link_hub.PRIVZETI_GOSTITELJ}:{link_hub.PRIVZETA_VRATA}",
                      poskuseni, "privzeto ime Huba mora biti med poskusi")

    def test_zivi_hub_najden_brez_zeroconfa(self):
        """Kadar Hub res tece, ga mora odkrivanje najti tudi brez zeroconfa."""
        naslov = link_hub.poisci_hub()
        print("brez zeroconfa najden Hub:", naslov)
        if naslov is None:
            self.skipTest("na tem racunalniku ne tece noben Hub (tako je v CI)")
        self.assertTrue(naslov.startswith("ws://"))


class ZeroconfKadarJe(unittest.TestCase):

    def test_mdns_najde_hub(self):
        try:
            import zeroconf  # noqa: F401
        except Exception:
            self.skipTest("zeroconf ni namescen")
        if link_hub.poisci_hub() is None:
            self.skipTest("na tem racunalniku ne tece noben Hub (tako je v CI)")
        naslov = link_hub._poisci_z_mdns(cas=3.0)
        print("prek mDNS najden Hub:", naslov)
        self.assertIsNotNone(naslov, "Hub se objavlja, mDNS bi ga moral najti")
        self.assertTrue(naslov.startswith("ws://"))
        self.assertTrue(naslov.endswith("/cast/ws"))


class NiTrdihOdvisnosti(unittest.TestCase):

    def test_uvozi_so_znotraj_funkcij(self):
        import pathlib
        besedilo = pathlib.Path(link_hub.__file__).read_text(encoding="utf-8")
        vrh = besedilo.split("def ")[0]
        for ime in NEOBVEZNE:
            self.assertNotIn(f"import {ime}", vrh,
                             f"{ime} ne sme biti uvozen na vrhu datoteke")

    def test_paket_ne_zahteva_novega(self):
        import pathlib
        koren = pathlib.Path(link_hub.__file__).resolve().parent.parent
        control = koren / "debian" / "control"
        if not control.exists():
            self.skipTest("debian/control ni")
        besedilo = control.read_text(encoding="utf-8")
        zahteve = besedilo.split("Depends:", 1)[1].split("Recommends:", 1)[0]
        for ime in ("websockets", "zeroconf", "requests"):
            self.assertNotIn(ime, zahteve,
                             f"python3-{ime} ne sme postati obvezna odvisnost paketa")
        print("OK paket ostaja brez novih obveznih odvisnosti")


if __name__ == "__main__":
    unittest.main(verbosity=2)
