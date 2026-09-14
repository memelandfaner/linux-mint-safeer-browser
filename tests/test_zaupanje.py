"""Komu odjemalec zaupa, da je Hub -- in cesa mu ne pove, dokler ni preprican.

Zeton naprave je dolgoziv poverilnik. Odkrivanje prek mDNS ni preverjeno: vsakdo v
omrezju lahko oglasi storitev `_safeercast._tcp.local.`. Zato velja:
 - ze znan (torej potrjen) Hub ima prednost pred vsakim oglasom,
 - naslov, ki ni videti kot Hub, se zavrne,
 - primerjava naslovov loci isti Hub od drugega.

Vsi strezniki tu so ponarejeni in tecejo na 127.0.0.1.
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from core import link_hub


def ponarejen_streznik(ime, dnevnik, zdravje=401, vstopnica=405):
    """Streznik, ki se vede kot Safeer Hub (ali pa kot kdo drug)."""

    class Rocaj(BaseHTTPRequestHandler):
        def _odgovori(self, koda):
            b = json.dumps({"detail": ime}).encode()
            self.send_response(koda)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            dnevnik.append((ime, "GET", self.path,
                            self.headers.get("X-Safeer-Token")))
            if self.path.startswith(link_hub.POT_ZDRAVJA):
                self._odgovori(zdravje)
            elif self.path.startswith(link_hub.POT_VSTOPNICE):
                self._odgovori(vstopnica)
            else:
                self._odgovori(404)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            dnevnik.append((ime, "POST", self.path,
                            self.headers.get("X-Safeer-Token")))
            self._odgovori(200)

        def log_message(self, *a):
            pass

    s = HTTPServer(("127.0.0.1", 0), Rocaj)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, s.server_address[1]


class KdoJeHub(unittest.TestCase):

    def setUp(self):
        self.dnevnik = []
        self._stari_mdns = link_hub._poisci_z_mdns
        self._stari_gostitelj = link_hub.PRIVZETI_GOSTITELJ
        self._stara_vrata = link_hub.PRIVZETA_VRATA
        link_hub._poisci_z_mdns = lambda cas=1.5: None
        link_hub.PRIVZETI_GOSTITELJ = "ta-gostitelj-ne-obstaja.invalid"
        link_hub.PRIVZETA_VRATA = 1
        self.strezniki = []

    def tearDown(self):
        link_hub._poisci_z_mdns = self._stari_mdns
        link_hub.PRIVZETI_GOSTITELJ = self._stari_gostitelj
        link_hub.PRIVZETA_VRATA = self._stara_vrata
        for s in self.strezniki:
            s.shutdown()

    def _hub(self, ime, **kw):
        s, vrata = ponarejen_streznik(ime, self.dnevnik, **kw)
        self.strezniki.append(s)
        return vrata

    def test_znani_hub_ima_prednost_pred_oglasom(self):
        """Nepreverjen oglas ne sme prehiteti Huba, ki ga je lastnik ze potrdil."""
        vrata_pravi = self._hub("PRAVI")
        vrata_lazni = self._hub("LAZNI")
        znani = f"ws://127.0.0.1:{vrata_pravi}/cast/ws"
        link_hub._poisci_z_mdns = lambda cas=1.5: f"ws://127.0.0.1:{vrata_lazni}/cast/ws"

        izbrani = link_hub.poisci_hub(znani)

        self.assertEqual(izbrani, znani)
        self.assertNotIn("LAZNI", [d[0] for d in self.dnevnik],
                         "dokler se znani Hub oglasa, drugih sploh ne vprasamo")

    def test_oglas_pride_na_vrsto_sele_ko_znanega_ni(self):
        vrata_lazni = self._hub("DRUGI")
        link_hub._poisci_z_mdns = lambda cas=1.5: f"ws://127.0.0.1:{vrata_lazni}/cast/ws"

        izbrani = link_hub.poisci_hub("ws://127.0.0.1:1/cast/ws")

        self.assertEqual(izbrani, f"ws://127.0.0.1:{vrata_lazni}/cast/ws",
                         "ko znanega Huba ni, je oglas legitimen kandidat")

    def test_tujec_na_istih_vratih_ni_hub(self):
        """Navaden spletni streznik vrne 404; to ni Safeer Hub."""
        vrata = self._hub("NEK-DRUG-STREZNIK", zdravje=404, vstopnica=404)
        link_hub.PRIVZETI_GOSTITELJ = "127.0.0.1"
        link_hub.PRIVZETA_VRATA = vrata

        self.assertIsNone(link_hub.poisci_hub())
        self.assertFalse(link_hub.je_hub(f"http://127.0.0.1:{vrata}"))

    def test_streznik_brez_poti_vstopnice_ni_hub(self):
        """Zdravje odgovori, vstopnice pa ni -- premalo, da bi mu zaupali zeton."""
        vrata = self._hub("POL-HUB", zdravje=200, vstopnica=404)
        self.assertFalse(link_hub.je_hub(f"http://127.0.0.1:{vrata}"))

    def test_pravi_hub_je_prepoznan(self):
        """Tako se vede Safeer Control: 401 na zdravju, 405 na GET vstopnice."""
        vrata = self._hub("HUB", zdravje=401, vstopnica=405)
        self.assertTrue(link_hub.je_hub(f"http://127.0.0.1:{vrata}"))

    def test_zeton_ne_gre_v_preverjanje(self):
        """Preverba je pred zaupanjem: zetona pri njej ne posljemo nikomur."""
        vrata = self._hub("HUB")
        link_hub.je_hub(f"http://127.0.0.1:{vrata}")
        z_zetonom = [d for d in self.dnevnik if d[3]]
        self.assertEqual(z_zetonom, [], "pri preverjanju naslova zetona ne posiljamo")


class PrimerjavaNaslovov(unittest.TestCase):

    def test_isti_hub(self):
        self.assertTrue(link_hub.naslov_je_isti(
            "ws://192.0.2.10:8990/cast/ws", "http://192.0.2.10:8990"))
        self.assertTrue(link_hub.naslov_je_isti(
            "ws://192.0.2.10:8990/cast/ws", "ws://192.0.2.10:8990/cast/ws?ticket=x"))

    def test_drug_hub(self):
        self.assertFalse(link_hub.naslov_je_isti(
            "ws://192.0.2.10:8990/cast/ws", "ws://192.0.2.11:8990/cast/ws"))
        self.assertFalse(link_hub.naslov_je_isti(
            "ws://192.0.2.10:8990/cast/ws", "ws://192.0.2.10:9999/cast/ws"))
        self.assertFalse(link_hub.naslov_je_isti("", "ws://192.0.2.10:8990/cast/ws"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
