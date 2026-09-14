"""Povezava z domacim Safeer Hubom za linuxov brskalnik.

Brez zunanjih knjiznic: paket safeer-browser zahteva samo GTK in WebKit, zato bi
vsaka nova odvisnost otezila namestitev in flatpak. WebSocket je zato napisan tu,
s standardno knjiznico -- gre za majhen del protokola RFC 6455 (besedilni okvirji,
maskiranje, ping/pong, zapiranje).

Vse ostalo (seznanitev, vstopnica, odkrivanje) je navaden HTTP prek urllib.

Nacela so ista kot v Androidu:
 - brskalnik deluje brez Huba; ce ga ni, se ne zgodi nic,
 - zeton naprave ostane v datoteki z dovoljenji 0600 in nikoli ne gre v stran,
 - povezava se odpre sele z enokratno vstopnico.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import ssl
import struct
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

PRIVZETA_VRATA = 8990
# Uporabnik naj vidi kratko domace ime, ne naslova IP. Staro ime ostane takoj za njim,
# ker ga imajo ze seznanjene naprave shranjeno in jim ne sme nic odpasti.
PRIVZETI_GOSTITELJ = "safeer.local"
STARO_IME_GOSTITELJA = "safeer-hub.local"
POT_VSTOPNICE = "/cast/ticket"
POT_WS = "/cast/ws"
POT_ZDRAVJA = "/cast/health"

# Zgornja meja sporocila s Huba. Brez nje lahko streznik (ali kdor se zanj izdaja)
# napove 4 GiB in nam napolni pomnilnik.
NAJVECJE_SPOROCILO = 1024 * 1024

# Koliko tisine prenesemo, preden povezavo razglasimo za mrtvo. Sami posiljamo
# ping pogosteje od tega, zato tisina pomeni, da Huba res ni vec.
BRALNI_TIMEOUT = 70.0
PING_VSAKIH = 25.0
ZAMIKI_PONOVNEGA_POSKUSA = (2.0, 5.0, 10.0, 20.0, 40.0, 60.0)

NASTAVITVE_MAPA = os.path.expanduser("~/.config/safeer-browser")
NASTAVITVE_POT = os.path.join(NASTAVITVE_MAPA, "link.json")


# ----------------------------------------------------------------------
# Nastavitve naprave
# ----------------------------------------------------------------------

def _ime_naprave() -> str:
    try:
        return socket.gethostname() or "racunalnik"
    except Exception:
        return "racunalnik"


def id_naprave() -> str:
    ime = _ime_naprave().split(".")[0].lower()
    cisto = "".join(z if (z.isalnum() or z in "-_") else "-" for z in ime)
    return "pc-" + (cisto or "safeer")


class Nastavitve:
    """Majhna shramba ob brskalniku. Zeton je dostopen samo uporabniku (0600)."""

    def __init__(self, pot: str = NASTAVITVE_POT) -> None:
        self.pot = pot
        self.podatki: Dict[str, object] = {}
        self.naloži()

    def naloži(self) -> None:
        try:
            with open(self.pot, "r", encoding="utf-8") as d:
                self.podatki = json.load(d)
        except Exception:
            self.podatki = {}

    def shrani(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.pot), exist_ok=True)
            zacasna = self.pot + ".tmp"
            with open(zacasna, "w", encoding="utf-8") as d:
                json.dump(self.podatki, d, ensure_ascii=False, indent=2)
            os.chmod(zacasna, 0o600)
            os.replace(zacasna, self.pot)
        except Exception:
            pass

    def get(self, kljuc: str, privzeto=None):
        return self.podatki.get(kljuc, privzeto)

    def set(self, kljuc: str, vrednost) -> None:
        self.podatki[kljuc] = vrednost
        self.shrani()


# ----------------------------------------------------------------------
# Odkrivanje in seznanitev (navaden HTTP)
# ----------------------------------------------------------------------

def _osnova(naslov: str) -> str:
    """Iz ws:// ali http:// naredi osnovo http://gostitelj:vrata."""
    u = urlparse(naslov)
    shema = "https" if u.scheme in ("wss", "https") else "http"
    gostitelj = u.netloc or u.path
    return f"{shema}://{gostitelj}"


def _zahteva(url: str, telo: Optional[dict] = None, zeton: Optional[str] = None,
             timeout: float = 5.0) -> Tuple[int, dict]:
    podatki = None if telo is None else json.dumps(telo).encode("utf-8")
    glave = {"Content-Type": "application/json"}
    if zeton:
        glave["X-Safeer-Token"] = zeton
    zahteva = urllib.request.Request(url, data=podatki,
                                     method="POST" if telo is not None else "GET",
                                     headers=glave)
    try:
        with urllib.request.urlopen(zahteva, timeout=timeout) as odgovor:
            vsebina = odgovor.read().decode("utf-8", "replace")
            try:
                return odgovor.status, json.loads(vsebina) if vsebina else {}
            except json.JSONDecodeError:
                return odgovor.status, {}
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return 0, {}


def _poisci_z_mdns(cas: float = 1.5) -> Optional[str]:
    """Poisce Hub prek mDNS, ce je zeroconf na voljo.

    Knjiznica NI obvezna: paket safeer-browser ostaja odvisen samo od GTK in WebKita.
    Ce je ni, vrnemo None in odkrivanje gre po HTTP poti.
    """
    try:
        from zeroconf import ServiceBrowser, ServiceListener, Zeroconf  # type: ignore
    except Exception:
        return None

    najdeno: List[str] = []

    class Poslusalec(ServiceListener):  # type: ignore[misc]
        def add_service(self, zc, vrsta, ime):
            try:
                info = zc.get_service_info(vrsta, ime, timeout=1000)
            except Exception:
                return
            if info is None:
                return
            naslovi = []
            try:
                naslovi = info.parsed_addresses()
            except Exception:
                pass
            if not naslovi:
                return
            lastnosti = info.properties or {}
            pot = lastnosti.get(b"ws") or lastnosti.get("ws") or POT_WS.encode()
            if isinstance(pot, bytes):
                pot = pot.decode("utf-8", "replace")
            najdeno.append(f"ws://{naslovi[0]}:{info.port}{pot}")

        def update_service(self, zc, vrsta, ime):
            pass

        def remove_service(self, zc, vrsta, ime):
            pass

    zc = None
    try:
        zc = Zeroconf()
        ServiceBrowser(zc, "_safeercast._tcp.local.", Poslusalec())
        konec = time.time() + cas
        while time.time() < konec and not najdeno:
            time.sleep(0.1)
    except Exception:
        return None
    finally:
        if zc is not None:
            try:
                zc.close()
            except Exception:
                pass

    return najdeno[0] if najdeno else None


def je_hub(osnova: str, timeout: float = 2.0) -> bool:
    """Ali na tem naslovu res odgovarja Safeer Hub?

    Ne zadosca, da se nekaj oglasi: na istih vratih je lahko cisto drug streznik.
    Preverimo zato dvoje, kar zna samo Hub:
      - /cast/health vrne 200 ali 401 (zahteva zeton), nikoli 404,
      - /cast/ticket obstaja, a ne kot GET (Hub odgovori 405 ali 401).
    Zetona pri tem ne posiljamo -- to je preverba pred zaupanjem, ne po njem.
    """
    koda, _ = _zahteva(osnova + POT_ZDRAVJA, timeout=timeout)
    if koda not in (200, 401, 403):
        return False
    koda_vstopnice, _ = _zahteva(osnova + POT_VSTOPNICE, timeout=timeout)
    if koda_vstopnice in (0, 404):
        return False
    return True


def poisci_hub(znani: str = "") -> Optional[str]:
    """Vrne naslov WebSocketa Huba ali None.

    Vrstni red je vprasanje zaupanja, ne udobja. Zadnji znani (torej ze potrjeni)
    Hub je vedno prvi: dokler se oglasa, ne pogledamo nikamor drugam. Sele ko ga ni,
    poskusimo mDNS in privzeta imena -- ta so nepreverjena, zato jih klicatelj, ce
    ima zeton, ne sme kar sprejeti (glej `naslov_je_isti`).
    """
    kandidati: List[str] = []
    if znani:
        kandidati.append(_osnova(znani))

    z_mdns = _poisci_z_mdns()
    if z_mdns:
        kandidati.append(_osnova(z_mdns))

    kandidati.append(f"http://{PRIVZETI_GOSTITELJ}:{PRIVZETA_VRATA}")
    kandidati.append(f"http://{STARO_IME_GOSTITELJA}:{PRIVZETA_VRATA}")
    kandidati.append(f"http://127.0.0.1:{PRIVZETA_VRATA}")

    videni = set()
    for osnova in kandidati:
        if osnova in videni:
            continue
        videni.add(osnova)
        if je_hub(osnova):
            gostitelj = osnova.split("://", 1)[1]
            return f"ws://{gostitelj}{POT_WS}"
    return None


# Imeni, pod katerima se javlja isti nas Hub. Preimenovanje ne sme nikogar odklopiti.
IMENA_HUBA = (PRIVZETI_GOSTITELJ, STARO_IME_GOSTITELJA)


def naslov_je_isti(a: str, b: str) -> bool:
    """Ali gre za isti Hub? Primerjamo gostitelja in vrata, ne sheme ne poti.

    Nasi dve imeni (safeer.local in staro safeer-hub.local) stejeta za isti Hub --
    sicer bi preimenovanje vsem napravam javilo, da se je Hub preselil.
    """
    if not a or not b:
        return False
    ua, ub = urlparse(_osnova(a)), urlparse(_osnova(b))
    ga, gb = (ua.hostname or "").lower(), (ub.hostname or "").lower()
    if ga in IMENA_HUBA and gb in IMENA_HUBA:
        ga = gb = IMENA_HUBA[0]
    return (ga, ua.port or PRIVZETA_VRATA) == (gb, ub.port or PRIVZETA_VRATA)


def zacni_seznanitev(ws_naslov: str, device_id: str, ime: str) -> Optional[dict]:
    koda, odgovor = _zahteva(_osnova(ws_naslov) + "/cast/pair/start",
                             {"device_id": device_id, "name": ime})
    if koda != 200:
        return None
    return odgovor


def prevzemi_zeton(ws_naslov: str, pair_id: str) -> Optional[str]:
    koda, odgovor = _zahteva(_osnova(ws_naslov) + "/cast/pair/claim", {"pair_id": pair_id})
    if koda != 200:
        return None
    if not odgovor.get("approved"):
        return None
    zeton = odgovor.get("token")
    return zeton if isinstance(zeton, str) and zeton else None


def vzemi_vstopnico(ws_naslov: str, zeton: str) -> Optional[str]:
    koda, odgovor = _zahteva(_osnova(ws_naslov) + POT_VSTOPNICE, {}, zeton=zeton)
    if koda != 200:
        return None
    vstopnica = odgovor.get("ticket")
    return vstopnica if isinstance(vstopnica, str) and vstopnica else None


# ----------------------------------------------------------------------
# Majhen odjemalec WebSocket (RFC 6455, samo kar potrebujemo)
# ----------------------------------------------------------------------

def _maskiraj(telo: bytes, maska: bytes) -> bytes:
    """XOR z masko po RFC 6455. Celostevilska pot je bistveno hitrejsa od zanke."""
    if not telo:
        return telo
    ponovljena = (maska * ((len(telo) + 3) // 4))[:len(telo)]
    return (int.from_bytes(telo, "big")
            ^ int.from_bytes(ponovljena, "big")).to_bytes(len(telo), "big")


class WsOdjemalec:
    """Besedilni WebSocket odjemalec na navadnem vticniku.

    Namenoma zna malo: odpre povezavo, poslje in prejme besedilne okvirje,
    odgovori na ping in se mirno zapre. To je vse, kar Safeer Hub potrebuje.
    """

    def __init__(self, naslov: str, timeout: float = 10.0,
                 bralni_timeout: float = BRALNI_TIMEOUT) -> None:
        self.naslov = naslov
        self.timeout = timeout
        # Rokovanje mora biti hitro, tisina med pogovorom pa ne pomeni napake:
        # zato dve razlicni meji. Prej je ena sama ubijala mirne povezave.
        self.bralni_timeout = bralni_timeout
        self.vticnik: Optional[socket.socket] = None
        self._medpomnilnik = b""
        self._zaklep = threading.Lock()

    def odpri(self) -> None:
        u = urlparse(self.naslov)
        varno = u.scheme == "wss"
        gostitelj = u.hostname or "127.0.0.1"
        vrata = u.port or (443 if varno else 80)
        pot = u.path or "/"
        if u.query:
            pot += "?" + u.query

        s = socket.create_connection((gostitelj, vrata), timeout=self.timeout)
        if varno:
            kontekst = ssl.create_default_context()
            s = kontekst.wrap_socket(s, server_hostname=gostitelj)

        kljuc = base64.b64encode(os.urandom(16)).decode()
        zahteva = (
            f"GET {pot} HTTP/1.1\r\n"
            f"Host: {gostitelj}:{vrata}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {kljuc}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        s.sendall(zahteva.encode())

        glava = b""
        s.settimeout(self.timeout)
        while b"\r\n\r\n" not in glava:
            kos = s.recv(1024)
            if not kos:
                s.close()
                raise ConnectionError("Hub je zaprl povezavo med rokovanjem.")
            glava += kos
        prva = glava.split(b"\r\n", 1)[0].decode("latin-1")
        if "101" not in prva:
            s.close()
            raise ConnectionError(f"Hub je zavrnil povezavo: {prva}")

        self._medpomnilnik = glava.split(b"\r\n\r\n", 1)[1]
        s.settimeout(self.bralni_timeout)
        self.vticnik = s

    def poslji(self, besedilo: str) -> None:
        s = self.vticnik
        if s is None:
            raise ConnectionError("Povezava ni odprta.")
        podatki = besedilo.encode("utf-8")
        okvir = bytearray()
        okvir.append(0x81)  # FIN + besedilni okvir
        maska = os.urandom(4)
        dolzina = len(podatki)
        if dolzina < 126:
            okvir.append(0x80 | dolzina)
        elif dolzina < 65536:
            okvir.append(0x80 | 126)
            okvir += struct.pack("!H", dolzina)
        else:
            okvir.append(0x80 | 127)
            okvir += struct.pack("!Q", dolzina)
        okvir += maska
        okvir += _maskiraj(podatki, maska)
        with self._zaklep:
            s.sendall(bytes(okvir))

    def _preberi(self, koliko: int) -> bytes:
        while len(self._medpomnilnik) < koliko:
            s = self.vticnik
            if s is None:
                raise ConnectionError("Povezava je zaprta.")
            kos = s.recv(4096)
            if not kos:
                raise ConnectionError("Hub je zaprl povezavo.")
            self._medpomnilnik += kos
        vzeto, self._medpomnilnik = self._medpomnilnik[:koliko], self._medpomnilnik[koliko:]
        return vzeto

    def prejmi(self) -> Optional[str]:
        """Vrne naslednje besedilno sporocilo ali None, ko je povezava zaprta.

        Dolgo sporocilo sme priti v vec okvirjih (FIN=0 + nadaljevalni okvirji);
        sestavimo ga, sicer bi ga vrnili odsekanega in ga json.loads tiho zavrgel.
        Napovedano dolzino preverimo, preden karkoli preberemo.
        """
        deli: List[bytes] = []
        vrsta_sporocila = 0
        while True:
            glava = self._preberi(2)
            fin = bool(glava[0] & 0x80)
            vrsta = glava[0] & 0x0F
            dolzina = glava[1] & 0x7F
            maskirano = bool(glava[1] & 0x80)
            if dolzina == 126:
                dolzina = struct.unpack("!H", self._preberi(2))[0]
            elif dolzina == 127:
                dolzina = struct.unpack("!Q", self._preberi(8))[0]
            if dolzina > NAJVECJE_SPOROCILO:
                self.zapri()
                raise ConnectionError(
                    f"Hub je napovedal okvir {dolzina} B, dovoljeno je "
                    f"{NAJVECJE_SPOROCILO} B.")
            maska = self._preberi(4) if maskirano else b""
            telo = self._preberi(dolzina) if dolzina else b""
            if maskirano:
                telo = _maskiraj(telo, maska)

            # Nadzorni okvirji smejo priti sredi razdeljenega sporocila in ga ne
            # prekinejo.
            if vrsta == 0x8:
                return None
            if vrsta == 0x9:
                self._pong(telo)
                continue
            if vrsta == 0xA:  # pong na nas ping
                continue

            if vrsta in (0x1, 0x2):
                deli = [telo]
                vrsta_sporocila = vrsta
            elif vrsta == 0x0:
                if not deli:
                    continue  # nadaljevanje brez zacetka -- zavrzemo
                deli.append(telo)
            else:
                continue

            if sum(len(d) for d in deli) > NAJVECJE_SPOROCILO:
                self.zapri()
                raise ConnectionError("Sporocilo s Huba je preveliko.")

            if fin:
                if vrsta_sporocila == 0x1:
                    return b"".join(deli).decode("utf-8", "replace")
                deli = []  # binarnega ne razumemo; mirno spregledamo

    def ping(self) -> bool:
        """Poslje ping. Vrne False, ce povezave ni vec -- to je nas srcni utrip."""
        s = self.vticnik
        if s is None:
            return False
        maska = os.urandom(4)
        try:
            with self._zaklep:
                s.sendall(bytes([0x89, 0x80]) + maska)
            return True
        except Exception:
            return False

    def _pong(self, telo: bytes) -> None:
        s = self.vticnik
        if s is None:
            return
        maska = os.urandom(4)
        okvir = bytearray([0x8A, 0x80 | min(len(telo), 125)])
        okvir += maska
        okvir += _maskiraj(telo[:125], maska)
        try:
            with self._zaklep:
                s.sendall(bytes(okvir))
        except Exception:
            pass

    def zapri(self) -> None:
        s = self.vticnik
        self.vticnik = None
        if s is None:
            return
        try:
            with self._zaklep:
                s.sendall(b"\x88\x80" + os.urandom(4))
        except Exception:
            pass
        try:
            s.close()
        except Exception:
            pass


# ----------------------------------------------------------------------
# Povezava z Hubom v svoji niti
# ----------------------------------------------------------------------

class Povezava:
    """Odpre povezavo s Hubom in v svoji niti posluša sporočila.

    Odzivi se vracajo prek `ob_sporocilu`; klicatelj poskrbi, da jih prenese
    na glavno nit (v GTK z GLib.idle_add).
    """

    def __init__(self, ws_naslov: str, zeton: str, device_id: str, ime: str,
                 sinhronizira: bool = False) -> None:
        self.ws_naslov = ws_naslov
        self.zeton = zeton
        self.device_id = device_id
        self.ime = ime
        self.sinhronizira = sinhronizira
        self.odjemalec: Optional[WsOdjemalec] = None
        self.nit: Optional[threading.Thread] = None
        self.nit_utripa: Optional[threading.Thread] = None
        self.tece = False
        self.ob_sporocilu: Optional[Callable[[dict], None]] = None
        self.ob_stanju: Optional[Callable[[bool], None]] = None
        # Zapiranje je namerno dejanje; vse drugo je izpad, po katerem se vrnemo.
        self._ustavljen = False
        self._budilka = threading.Event()

    def _odpri(self) -> bool:
        """Ena vzpostavitev: vstopnica, rokovanje, prijava. Brez cakanja."""
        vstopnica = vzemi_vstopnico(self.ws_naslov, self.zeton)
        if not vstopnica:
            return False
        locilo = "&" if "?" in self.ws_naslov else "?"
        naslov = f"{self.ws_naslov}{locilo}ticket={vstopnica}"
        odjemalec = WsOdjemalec(naslov)
        try:
            odjemalec.odpri()
        except Exception:
            return False

        prijava = {
            "id": str(int(time.time() * 1000)),
            "type": "cast.register",
            "payload": {
                "device_id": self.device_id,
                "name": self.ime,
                "role": "sender",
            },
        }
        if self.sinhronizira:
            prijava["payload"]["capabilities"] = ["sync"]
        try:
            odjemalec.poslji(json.dumps(prijava))
        except Exception:
            odjemalec.zapri()
            return False

        self.odjemalec = odjemalec
        self.tece = True
        return True

    def poveži(self) -> bool:
        """Prvi poskus. Ce uspe, povezavo od tu naprej vzdrzujemo sami."""
        self._ustavljen = False
        self._budilka.clear()
        if not self._odpri():
            return False

        self.nit = threading.Thread(target=self._zanka, daemon=True)
        self.nit.start()
        self.nit_utripa = threading.Thread(target=self._srcni_utrip, daemon=True)
        self.nit_utripa.start()
        if self.ob_stanju:
            self.ob_stanju(True)
        return True

    def _cakaj(self, sekunde: float) -> bool:
        """Prekinljivo cakanje. Vrne True, ce je medtem prislo zaprtje."""
        return self._budilka.wait(timeout=sekunde)

    def _srcni_utrip(self) -> None:
        """Redni ping. Brez njega tisina ni locljiva od prekinjenega omrezja."""
        while not self._ustavljen:
            if self._cakaj(PING_VSAKIH):
                return
            odjemalec = self.odjemalec
            if odjemalec is not None and self.tece:
                if not odjemalec.ping():
                    # Povezave ni vec; bralec bo to opazil in se povezal znova.
                    try:
                        odjemalec.zapri()
                    except Exception:
                        pass

    def _zanka(self) -> None:
        """Poslusa in se po izpadu sama vrne. Konca samo, ko klicatelj zapre."""
        poskus = 0
        while not self._ustavljen:
            self._poslusaj()
            self.tece = False
            if self._ustavljen:
                break
            if self.ob_stanju:
                self.ob_stanju(False)
            zamik = ZAMIKI_PONOVNEGA_POSKUSA[
                min(poskus, len(ZAMIKI_PONOVNEGA_POSKUSA) - 1)]
            if self._cakaj(zamik):
                break
            if self._odpri():
                poskus = 0
                if self.ob_stanju:
                    self.ob_stanju(True)
            else:
                poskus += 1
        self.tece = False

    def _poslusaj(self) -> None:
        try:
            while self.tece and self.odjemalec is not None:
                besedilo = self.odjemalec.prejmi()
                if besedilo is None:
                    break
                try:
                    sporocilo = json.loads(besedilo)
                except json.JSONDecodeError:
                    continue
                if self.ob_sporocilu:
                    self.ob_sporocilu(sporocilo)
        except Exception:
            pass
        finally:
            odjemalec = self.odjemalec
            self.odjemalec = None
            if odjemalec is not None:
                try:
                    odjemalec.zapri()
                except Exception:
                    pass

    def poslji(self, sporocilo: dict) -> bool:
        if not self.tece or self.odjemalec is None:
            return False
        try:
            self.odjemalec.poslji(json.dumps(sporocilo))
            return True
        except Exception:
            return False

    def poslji_url(self, cilj: str, url: str, naslov: Optional[str] = None) -> bool:
        return self.poslji({
            "id": str(int(time.time() * 1000)),
            "type": "cast.url",
            "target": cilj,
            "payload": {"url": url, "title": naslov or "", "start_position": 0.0},
        })

    def nadzor(self, cilj: str, dejanje: str, polozaj: Optional[float] = None,
               glasnost: Optional[float] = None) -> bool:
        telo: Dict[str, object] = {"action": dejanje}
        if polozaj is not None:
            telo["position"] = polozaj
        if glasnost is not None:
            telo["volume"] = glasnost
        return self.poslji({
            "id": str(int(time.time() * 1000)),
            "type": "cast.control",
            "target": cilj,
            "payload": telo,
        })

    def poslji_sync(self, kategorija: str, razlicica: int, vsebina: dict) -> bool:
        return self.poslji({
            "id": str(int(time.time() * 1000)),
            "type": "sync.data",
            "target": "all",
            "payload": {
                "category": kategorija,
                "version": razlicica,
                "timestamp": time.time(),
                "data": vsebina,
            },
        })

    def zahtevaj_sync(self, kategorija: str, od_razlicice: Optional[int] = None) -> bool:
        telo: Dict[str, object] = {"category": kategorija}
        if od_razlicice is not None:
            telo["since_version"] = od_razlicice
        return self.poslji({
            "id": str(int(time.time() * 1000)),
            "type": "sync.request",
            "payload": telo,
        })

    def zapri(self) -> None:
        """Namerno zaprtje: po tem se ne povezujemo vec."""
        self._ustavljen = True
        self.tece = False
        self._budilka.set()
        odjemalec = self.odjemalec
        self.odjemalec = None
        if odjemalec is not None:
            odjemalec.zapri()
