"""Odpornost odjemalca WebSocket na to, kar strezniki v resnici pocnejo.

Vsi trije primeri so bili nekoc napake: mirna povezava je umrla po 10 s, razdeljeno
sporocilo se je vrnilo odsekano in tiho izginilo, napovedana dolzina okvirja pa ni
imela zgornje meje. Preizkusi so tu, da se to ne vrne.

Streznik je pravi vticnik na 127.0.0.1, zato ne potrebujejo ne Huba ne omrezja.
"""
import base64
import hashlib
import json
import socket
import struct
import threading
import time
import unittest

from core import link_hub


def _rokovanje(povezava):
    zahteva = b""
    while b"\r\n\r\n" not in zahteva:
        kos = povezava.recv(1024)
        if not kos:
            return False
        zahteva += kos
    kljuc = ""
    for vrstica in zahteva.decode("latin-1").split("\r\n"):
        if vrstica.lower().startswith("sec-websocket-key:"):
            kljuc = vrstica.split(":", 1)[1].strip()
    sprejem = base64.b64encode(hashlib.sha1(
        (kljuc + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
    povezava.sendall((
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {sprejem}\r\n\r\n"
    ).encode())
    return True


def streznik(ravnaj):
    """Zazene enkratni streznik WebSocket in vrne njegova vrata."""
    posluh = socket.socket()
    posluh.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    posluh.bind(("127.0.0.1", 0))
    posluh.listen(1)
    posluh.settimeout(10)
    vrata = posluh.getsockname()[1]

    def tece():
        try:
            povezava, _ = posluh.accept()
        except Exception:
            return
        try:
            if _rokovanje(povezava):
                ravnaj(povezava)
        except Exception:
            pass
        finally:
            for s in (povezava, posluh):
                try:
                    s.close()
                except Exception:
                    pass

    threading.Thread(target=tece, daemon=True).start()
    return vrata


def _okvir(opcode, telo, fin=True):
    prvi = (0x80 if fin else 0x00) | opcode
    return bytes([prvi, len(telo)]) + telo


class Odpornost(unittest.TestCase):

    def test_tisina_ne_ubije_povezave(self):
        """Hub sme molcati. Rokovanje ima kratek rok, pogovor pa dolgega."""
        def tiho(povezava):
            time.sleep(2.5)
            povezava.sendall(_okvir(0x1, json.dumps({"type": "cast.devices"}).encode()))
            time.sleep(0.5)

        vrata = streznik(tiho)
        odjemalec = link_hub.WsOdjemalec(f"ws://127.0.0.1:{vrata}/cast/ws",
                                         timeout=1.0, bralni_timeout=8.0)
        odjemalec.odpri()
        try:
            sporocilo = odjemalec.prejmi()
        finally:
            odjemalec.zapri()
        self.assertIsNotNone(sporocilo, "2,5 s tisine ne sme pomeniti prekinjene povezave")
        self.assertEqual(json.loads(sporocilo)["type"], "cast.devices")

    def test_razdeljeno_sporocilo_se_sestavi(self):
        """Dolg odgovor sme priti v vec okvirjih; sestaviti ga moramo."""
        celota = json.dumps({"type": "sync.data",
                             "payload": {"category": "bookmarks",
                                         "data": {"items": [{"url": "https://a.si"}]}}})

        def razdeljeno(povezava):
            b = celota.encode()
            povezava.sendall(_okvir(0x1, b[:15], fin=False))
            time.sleep(0.05)
            povezava.sendall(_okvir(0x9, b"utrip"))        # nadzorni okvir vmes
            time.sleep(0.05)
            povezava.sendall(_okvir(0x0, b[15:40], fin=False))
            time.sleep(0.05)
            povezava.sendall(_okvir(0x0, b[40:], fin=True))
            time.sleep(0.5)

        vrata = streznik(razdeljeno)
        odjemalec = link_hub.WsOdjemalec(f"ws://127.0.0.1:{vrata}/cast/ws",
                                         timeout=2.0, bralni_timeout=5.0)
        odjemalec.odpri()
        try:
            sporocilo = odjemalec.prejmi()
        finally:
            odjemalec.zapri()
        self.assertEqual(sporocilo, celota,
                         "razdeljeno sporocilo mora priti nazaj celo")
        self.assertEqual(json.loads(sporocilo)["type"], "sync.data")

    def test_prevelik_okvir_zavrnemo(self):
        """Napovedane dolzine ne verjamemo na besedo."""
        def ogromen(povezava):
            povezava.sendall(bytes([0x81, 127]) + struct.pack("!Q", 4 * 1024**3))
            try:
                while True:
                    povezava.sendall(b"x" * 65536)
            except Exception:
                pass

        vrata = streznik(ogromen)
        odjemalec = link_hub.WsOdjemalec(f"ws://127.0.0.1:{vrata}/cast/ws",
                                         timeout=2.0, bralni_timeout=5.0)
        odjemalec.odpri()
        with self.assertRaises(ConnectionError):
            odjemalec.prejmi()
        odjemalec.zapri()
        self.assertLessEqual(link_hub.NAJVECJE_SPOROCILO, 4 * 1024 * 1024,
                             "meja mora ostati majhna; Hub posilja kratka sporocila")

    def test_meja_velja_tudi_za_sesteto_sporocilo(self):
        """Razdeljenih okvirjev se ne da sesteti mimo meje."""
        kos = b"x" * 60000

        def po_koscih(povezava):
            povezava.sendall(_okvir(0x1, kos, fin=False))
            try:
                while True:
                    povezava.sendall(_okvir(0x0, kos, fin=False))
                    time.sleep(0.001)
            except Exception:
                pass

        vrata = streznik(po_koscih)
        odjemalec = link_hub.WsOdjemalec(f"ws://127.0.0.1:{vrata}/cast/ws",
                                         timeout=2.0, bralni_timeout=5.0)
        odjemalec.odpri()
        with self.assertRaises(ConnectionError):
            odjemalec.prejmi()
        odjemalec.zapri()

    def test_ping_pove_da_povezave_ni(self):
        odjemalec = link_hub.WsOdjemalec("ws://127.0.0.1:1/cast/ws")
        self.assertFalse(odjemalec.ping(), "brez odprtega vticnika ping ne sme uspeti")

    def test_maskiranje_je_obrnljivo(self):
        maska = b"\x01\x02\x03\x04"
        for vzorec in (b"", b"a", b"abc", b"Safeer Link \xc5\xbe" * 500):
            self.assertEqual(
                link_hub._maskiraj(link_hub._maskiraj(vzorec, maska), maska), vzorec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
