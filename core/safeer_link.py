"""Safeer Link v linuxovem brskalniku.

Ista stran kot na telefonu in televizorju (assets/link/), zato je vedenje povsod
enako. Stran je del programa in ne pride z omrezja; z aplikacijo se pogovarja samo
prek mostu, ki je pripet izkljucno njenemu pogledu -- nobena spletna stran ga ne vidi.

Zeton naprave ostane v ~/.config/safeer-browser/link.json (0600). Stran ga nikoli ne
dobi: vsak klic proti Hubu opravi ta modul.

WebKitGTK ne pozna sinhronicnih klicev iz strani v program, zato most sestavimo iz
dveh delov: stanje program vstavi v stran vnaprej (sinhroni bralci berejo to), dejanja
pa gredo v program prek postMessage in se vrnejo kot odziv.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Dict, List, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, WebKit2, GLib  # noqa: E402

from core import link_hub  # noqa: E402

KATEGORIJA_ZAZNAMKI = "bookmarks"

# Skripta, ki v strani naredi window.SafeerLink. Sinhroni bralci berejo stanje, ki
# ga program vstavi vnaprej; dejanja gredo v program.
MOST_JS = """
(function () {
  if (window.SafeerLink) return;
  window.__safeerLink = window.__safeerLink || {
    stanje: {"znan": false, "seznanjen": false},
    naprave: [],
    stran: {"url": "", "naslov": "", "posljiva": false},
    sinhronizacija: {"zaznamki": {"vklopljena": false, "stevilo": 0}},
    konzola: "",
    jezik: ""
  };
  function poslji(metoda, argumenti) {
    try {
      window.webkit.messageHandlers.safeerLink.postMessage(
        JSON.stringify({ m: metoda, a: argumenti || [] })
      );
    } catch (e) {}
  }
  window.SafeerLink = {
    jeTelevizor: function () { return false; },
    stanje: function () { return JSON.stringify(window.__safeerLink.stanje); },
    naprave: function () { return JSON.stringify(window.__safeerLink.naprave); },
    trenutnaStranJson: function () { return JSON.stringify(window.__safeerLink.stran); },
    sinhronizacijaStanje: function () { return JSON.stringify(window.__safeerLink.sinhronizacija); },
    naslovKonzole: function () { return window.__safeerLink.konzola; },
    jezik: function () { return window.__safeerLink.jezik || ""; },
    potrdiNovNaslov: function () { poslji("potrdiNovNaslov"); },
    pozabiNapravo: function () { poslji("pozabiNapravo"); },
    poisciHub: function () { poslji("poisciHub"); },
    seznani: function () { poslji("seznani"); },
    poveziSe: function () { poslji("poveziSe"); },
    posljiTrenutno: function (id) { poslji("posljiTrenutno", [id]); },
    poslji: function (id, url, naslov) { poslji("poslji", [id, url, naslov]); },
    nadzor: function (id, ukaz, vrednost) { poslji("nadzor", [id, ukaz, vrednost]); },
    nastaviSinhronizacijo: function (vklop) { poslji("nastaviSinhronizacijo", [!!vklop]); },
    odpri: function (url) { poslji("odpri", [url]); },
    zapri: function () { poslji("zapri"); }
  };
})();
"""


class SafeerLink:
    """Okno Safeer Linka in ves pogovor s Hubom."""

    def __init__(self, starsevsko: Optional[Gtk.Window], config,
                 trenutna_stran: Callable[[], Dict[str, str]],
                 odpri_naslov: Callable[[str], None],
                 koren_programa: str) -> None:
        self.starsevsko = starsevsko
        self.config = config
        self.trenutna_stran = trenutna_stran
        self.odpri_naslov = odpri_naslov
        self.koren = koren_programa

        self.nastavitve = link_hub.Nastavitve()
        self.povezava: Optional[link_hub.Povezava] = None
        self.naprave: List[dict] = []
        self.okno: Optional[Gtk.Window] = None
        self.pogled: Optional[WebKit2.WebView] = None
        self._seznanjanje = False
        # Naslov, ki se je javil namesto potrjenega; caka na en uporabnikov dotik.
        self._predlagani_naslov = ""
        # Da iskanje po neuspeli povezavi ne tece v krogu.
        self._po_neuspehu = False
        # Povezovanje sprozi vec poti (nalozena stran, iskanje, seznanitev,
        # vklop sinhronizacije). Brez kljucavnice nastaneta dve povezavi hkrati
        # in Hub vidi napravo dvakrat.
        self._zaklep_povezave = threading.Lock()
        self._dovoljeni_koren = ""

    # ------------------------------------------------------------------
    # Stanje
    # ------------------------------------------------------------------

    def _hub(self) -> str:
        return str(self.nastavitve.get("hub_url", "") or "")

    def _zeton(self) -> Optional[str]:
        z = self.nastavitve.get("control_token")
        return z if isinstance(z, str) and z else None

    def _stanje(self) -> dict:
        return {
            "hub": self._hub(),
            "znan": bool(self._hub()),
            "seznanjen": self._zeton() is not None,
            "naprava": "Safeer (" + link_hub._ime_naprave().split(".")[0] + ")",
            "id": link_hub.id_naprave(),
        }

    def _sinhronizacija(self) -> dict:
        try:
            portali = self.config.get_portals() or []
        except Exception:
            portali = []
        return {
            "zaznamki": {
                "vklopljena": bool(self.nastavitve.get("sync_bookmarks", False)),
                "stevilo": len(portali),
            }
        }

    def _stran(self) -> dict:
        try:
            podatki = self.trenutna_stran() or {}
        except Exception:
            podatki = {}
        url = str(podatki.get("url", "") or "")
        posljiva = url.startswith("http://") or url.startswith("https://")
        return {"url": url, "naslov": str(podatki.get("naslov", "") or ""), "posljiva": posljiva}

    def _jezik(self) -> str:
        """Jezik, ki ga ima uporabnik v brskalniku -- stran govori v njem.

        Najprej vprasamo brskalnikovo nastavitev, sicer okolje (LANG). Vrnemo samo
        dvocrkovno oznako; stran zna slovensko in anglesko, drugo pade na anglesko.
        """
        oznaka = ""
        try:
            oznaka = str(self.config.get("ui_language", "") or "")
        except Exception:
            oznaka = ""
        if not oznaka:
            for kljuc in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
                vrednost = os.environ.get(kljuc, "")
                if vrednost:
                    oznaka = vrednost
                    break
        oznaka = oznaka.replace("-", "_").split(".")[0].split("_")[0].strip().lower()
        return oznaka[:2]

    def _konzola(self) -> str:
        hub = self._hub()
        if not hub:
            return ""
        return link_hub._osnova(hub) + "/console"

    # ------------------------------------------------------------------
    # Okno
    # ------------------------------------------------------------------

    def pokazi(self) -> None:
        if self.okno is not None:
            self.okno.present()
            return

        upravitelj = WebKit2.UserContentManager()
        upravitelj.register_script_message_handler("safeerLink")
        upravitelj.connect("script-message-received::safeerLink", self._na_sporocilo)
        upravitelj.add_script(WebKit2.UserScript(
            MOST_JS,
            WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserScriptInjectionTime.START,
            None, None,
        ))

        pogled = WebKit2.WebView.new_with_user_content_manager(upravitelj)
        nastavitve = pogled.get_settings()
        nastavitve.set_property("enable-javascript", True)
        nastavitve.set_property("enable-developer-extras", False)
        # Stran je nasa in ne potrebuje omrezja; vse gre skozi most.
        nastavitve.set_property("enable-webgl", False)
        pogled.set_background_color(_barva(0x0b, 0x10, 0x17))

        okno = Gtk.Window(title="Safeer Link")
        okno.set_default_size(560, 760)
        if self.starsevsko is not None:
            okno.set_transient_for(self.starsevsko)
        okno.add(pogled)
        okno.connect("destroy", self._na_zaprtje)

        self.okno = okno
        self.pogled = pogled

        pot = os.path.join(self.koren, "assets", "link", "index.html")
        self._dovoljeni_koren = "file://" + os.path.join(self.koren, "assets", "link")
        pogled.connect("decide-policy", self._na_politiko)
        pogled.load_uri("file://" + pot)
        pogled.connect("load-changed", self._na_nalozeno)

        okno.show_all()

    def _na_politiko(self, pogled, odlocitev, vrsta) -> bool:
        """Ta pogled sme prikazati samo stran Safeer Linka.

        Most je pripet pogledu, ne dokumentu: ce bi pogled kdaj odplul na spletno
        stran, bi `window.SafeerLink` dobila tudi ona. Danes stran nikamor ne vodi,
        a varovalo mora biti tu, preden ga bo kdo potreboval -- Android ga ze ima.
        """
        try:
            if vrsta not in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                             WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
                return False
            naslov = odlocitev.get_navigation_action().get_request().get_uri() or ""
            if self._dovoljeni_koren and naslov.startswith(self._dovoljeni_koren):
                return False
            odlocitev.ignore()
            return True
        except Exception:
            try:
                odlocitev.ignore()
            except Exception:
                pass
            return True

    def _na_zaprtje(self, *_args) -> None:
        self.okno = None
        self.pogled = None
        if self.povezava is not None:
            self.povezava.zapri()
            self.povezava = None

    def _na_nalozeno(self, pogled, dogodek) -> None:
        if dogodek != WebKit2.LoadEvent.FINISHED:
            return
        self._osvezi_stanje_v_strani()
        # Ce Huba se ne poznamo, ga poiscemo sami -- uporabniku ni treba nicesar vedeti.
        if not self._hub():
            self._v_ozadju(self._poisci_hub)
        elif self._zeton():
            self._v_ozadju(self._povezi)

    # ------------------------------------------------------------------
    # Most
    # ------------------------------------------------------------------

    def _js(self, koda: str) -> None:
        pogled = self.pogled
        if pogled is None:
            return
        try:
            pogled.run_javascript(koda, None, None, None)
        except Exception:
            pass

    def _osvezi_stanje_v_strani(self) -> None:
        stanje = {
            "stanje": self._stanje(),
            "naprave": self.naprave,
            "stran": self._stran(),
            "sinhronizacija": self._sinhronizacija(),
            "konzola": self._konzola(),
            "jezik": self._jezik(),
        }
        # ensure_ascii=True: imena naprav pridejo z omrezja, U+2028/U+2029 pa sta
        # v JavaScriptu ločilnika vrstic. Ubezimo vsemu, kar ni ASCII.
        self._js("window.__safeerLink = " + json.dumps(stanje, ensure_ascii=True) + ";")

    def _odziv(self, vrsta: str, podatki) -> None:
        """Odziv strani. Vedno na glavni niti in vedno po osvezitvi stanja."""
        def naredi():
            self._osvezi_stanje_v_strani()
            self._js("window.safeerLinkOdziv && window.safeerLinkOdziv("
                     + json.dumps(vrsta) + ", " + json.dumps(podatki, ensure_ascii=True) + ");")
            return False
        GLib.idle_add(naredi)

    def _na_sporocilo(self, upravitelj, rezultat) -> None:
        try:
            besedilo = rezultat.get_js_value().to_string()
            sporocilo = json.loads(besedilo)
        except Exception:
            return
        metoda = sporocilo.get("m")
        argumenti = sporocilo.get("a") or []
        obravnava = {
            "poisciHub": lambda: self._v_ozadju(self._poisci_hub),
            "seznani": lambda: self._v_ozadju(self._seznani),
            "poveziSe": lambda: self._v_ozadju(self._povezi),
            "posljiTrenutno": lambda: self._poslji_trenutno(*argumenti[:1]),
            "poslji": lambda: self._poslji(*argumenti[:3]),
            "nadzor": lambda: self._nadzor(*argumenti[:3]),
            "nastaviSinhronizacijo": lambda: self._v_ozadju(
                lambda: self._nastavi_sinhronizacijo(bool(argumenti[0]) if argumenti else False)),
            "odpri": lambda: self._odpri(*argumenti[:1]),
            "pozabiNapravo": lambda: self._v_ozadju(self._pozabi_napravo),
            "potrdiNovNaslov": lambda: self._v_ozadju(self._potrdi_nov_naslov),
            "zapri": lambda: self.okno.destroy() if self.okno is not None else None,
        }.get(metoda)
        if obravnava is not None:
            try:
                obravnava()
            except Exception as e:  # noqa: BLE001 - stran ne sme podreti brskalnika
                self._odziv("napaka", str(e))

    @staticmethod
    def _v_ozadju(funkcija: Callable[[], None]) -> None:
        threading.Thread(target=funkcija, daemon=True).start()

    # ------------------------------------------------------------------
    # Dejanja
    # ------------------------------------------------------------------

    def _potrdi_nov_naslov(self) -> None:
        """Uporabnik je potrdil, da je Safeer Link na novem naslovu res njegov."""
        naslov = self._predlagani_naslov
        self._predlagani_naslov = ""
        if not naslov:
            return
        self.nastavitve.set("hub_url", naslov)
        self._odziv("hub", {"najden": True, "naslov": naslov})
        if self._zeton():
            self._povezi()

    def _pozabi_napravo(self) -> None:
        """Odklopi TO napravo od Huba: pozabi zeton in naslov.

        Namenoma ne posegamo v druge naprave -- to je uporabnikova odlocitev za
        napravo, ki jo drzi v roki. Ostale se odstrani v Safeer Controlu.
        """
        povezava = self.povezava
        self.povezava = None
        if povezava is not None:
            try:
                povezava.zapri()
            except Exception:
                pass
        for kljuc in ("control_token", "hub_url", "sync_bookmarks",
                      "sync_bookmarks_version"):
            try:
                self.nastavitve.podatki.pop(kljuc, None)
            except Exception:
                pass
        self.nastavitve.shrani()
        self._odziv("pozabljeno", True)

    def _poisci_hub(self) -> None:
        znani = self._hub()
        naslov = link_hub.poisci_hub(znani)
        if not naslov:
            self._odziv("hub", {"najden": False, "naslov": ""})
            return
        # Odkrivanje prek mDNS ni preverjeno: kdorkoli v omrezju lahko oglasi
        # storitev. Ce smo ze seznanjeni, zetona zato ne posljemo naslovu, ki ga
        # lastnik ni potrdil -- raje povemo, kaj se dogaja.
        if self._zeton() and znani and not link_hub.naslov_je_isti(znani, naslov):
            # Naslov se je spremenil (najpogosteje ker je usmerjevalnik podelil nov IP).
            # Zetona ne posljemo kar tako, a uporabnika tudi ne posljemo v ponovno
            # seznanjanje: vprasamo ga enkrat, on pa potrdi z enim dotikom.
            self._predlagani_naslov = naslov
            self._odziv("preseljen", {"naslov": naslov})
            return
        self.nastavitve.set("hub_url", naslov)
        self._odziv("hub", {"najden": True, "naslov": naslov})
        if self._zeton():
            self._povezi()

    def _seznani(self) -> None:
        if self._seznanjanje:
            return
        naslov = self._hub()
        if not naslov:
            self._odziv("napaka", "Hub ni znan. Najprej ga poišči.")
            return
        self._seznanjanje = True
        try:
            zacetek = link_hub.zacni_seznanitev(
                naslov, link_hub.id_naprave(),
                "Safeer (" + link_hub._ime_naprave().split(".")[0] + ")")
            if not zacetek or not zacetek.get("pin"):
                self._odziv("napaka", "Seznanitve ni bilo mogoče začeti.")
                return
            self._odziv("koda", str(zacetek["pin"]))
            pair_id = str(zacetek.get("pair_id", ""))

            # Koda velja pet minut; toliko casa preverjamo, ali jo je potrdil.
            konec = time.time() + 300
            while time.time() < konec and self.okno is not None:
                time.sleep(3)
                zeton = link_hub.prevzemi_zeton(naslov, pair_id)
                if zeton:
                    self.nastavitve.set("control_token", zeton)
                    self._odziv("seznanitev", True)
                    self._povezi()
                    return
            self._odziv("seznanitev", False)
        finally:
            self._seznanjanje = False

    def _povezi(self) -> None:
        with self._zaklep_povezave:
            uspelo = self._povezi_zaklenjeno()
        if uspelo or self._po_neuspehu:
            return
        # Znani naslov se ne oglasi. Preden uporabniku karkoli recemo, poglejmo, ali
        # se Safeer Link javlja kje drugje -- najpogosteje je dobil nov naslov od
        # usmerjevalnika. Sele ce ga ni nikjer, je to zares napaka.
        self._po_neuspehu = True
        try:
            self._poisci_hub()
        finally:
            self._po_neuspehu = False

    def _povezi_zaklenjeno(self) -> bool:
        naslov = self._hub()
        zeton = self._zeton()
        if not naslov or not zeton:
            return True  # ni kaj povezati; to ni neuspeh, ki bi ga bilo treba iskati
        if self.povezava is not None:
            self.povezava.zapri()
            self.povezava = None

        povezava = link_hub.Povezava(
            naslov, zeton, link_hub.id_naprave(),
            "Safeer (" + link_hub._ime_naprave().split(".")[0] + ")",
            sinhronizira=bool(self.nastavitve.get("sync_bookmarks", False)),
        )
        povezava.ob_sporocilu = self._na_sporocilo_huba
        povezava.ob_stanju = lambda povezan: self._odziv("povezava", povezan)
        if povezava.poveži():
            self.povezava = povezava
            return True
        return False

    def _na_sporocilo_huba(self, sporocilo: dict) -> None:
        vrsta = sporocilo.get("type")
        if vrsta == "cast.devices":
            naprave = []
            for d in sporocilo.get("devices") or []:
                naprave.append({
                    "id": d.get("id", ""),
                    "ime": d.get("name", ""),
                    "vloga": d.get("role", "receiver"),
                    "zmoznosti": d.get("capabilities") or [],
                })
            self.naprave = naprave
            self._odziv("naprave", naprave)
        elif vrsta == "cast.status":
            telo = sporocilo.get("payload") or {}
            self._odziv("predvajanje", {
                "naprava": sporocilo.get("device_id", ""),
                "stanje": telo.get("state", "idle"),
                "naslov": telo.get("title", ""),
                "url": telo.get("current_url", ""),
                "polozaj": telo.get("position", 0.0),
                "trajanje": telo.get("duration", 0.0),
            })
        elif vrsta == "sync.data":
            self._prejmi_zaznamke(sporocilo.get("payload") or {})

    def _poslji_trenutno(self, id_naprave: str = "") -> None:
        stran = self._stran()
        if not stran["posljiva"]:
            self._odziv("napaka", "Ta stran ni primerna za pošiljanje.")
            return
        self._poslji(id_naprave, stran["url"], stran["naslov"])

    def _poslji(self, id_naprave: str = "", url: str = "", naslov: str = "") -> None:
        if self.povezava is None:
            self._odziv("napaka", "Povezave s Hubom ni.")
            return
        cist = (url or "").strip()
        if not (cist.startswith("http://") or cist.startswith("https://")):
            self._odziv("napaka", "Poslati je mogoče samo naslove http in https.")
            return
        if self.povezava.poslji_url(id_naprave, cist, naslov or None):
            self._odziv("poslano", {"naprava": id_naprave, "url": cist})
        else:
            self._odziv("napaka", "Pošiljanje ni uspelo.")

    def _nadzor(self, id_naprave: str = "", ukaz: str = "", vrednost: float = 0.0) -> None:
        if self.povezava is None:
            return
        if ukaz == "seek":
            self.povezava.nadzor(id_naprave, "seek", polozaj=float(vrednost or 0))
        elif ukaz == "volume":
            self.povezava.nadzor(id_naprave, "volume", glasnost=float(vrednost or 0))
        else:
            self.povezava.nadzor(id_naprave, ukaz)

    def _odpri(self, url: str = "") -> None:
        cist = (url or "").strip()
        if not (cist.startswith("http://") or cist.startswith("https://")):
            return
        def naredi():
            if self.okno is not None:
                self.okno.destroy()
            try:
                self.odpri_naslov(cist)
            except Exception:
                pass
            return False
        GLib.idle_add(naredi)

    # ------------------------------------------------------------------
    # Sinhronizacija zaznamkov
    # ------------------------------------------------------------------

    def _izvozi_zaznamke(self) -> dict:
        try:
            portali = self.config.get_portals() or []
        except Exception:
            portali = []
        elementi = []
        for p in portali:
            url = str(p.get("url", "") or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                elementi.append({
                    "title": str(p.get("title", "") or ""),
                    "url": url,
                    "icon": str(p.get("mark", "") or "⭐"),
                })
        return {"items": elementi}

    def _prejmi_zaznamke(self, telo: dict) -> None:
        if telo.get("category") != KATEGORIJA_ZAZNAMKI:
            return
        if not self.nastavitve.get("sync_bookmarks", False):
            return
        vsebina = telo.get("data") or {}
        elementi = vsebina.get("items") or []
        pripravljeni = []
        for e in elementi:
            url = str(e.get("url", "") or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                pripravljeni.append({
                    "title": str(e.get("title", "") or url),
                    "url": url,
                    "mark": str(e.get("icon", "") or "⭐"),
                })
        if not pripravljeni:
            return

        # Ta klic pride z niti vticnika, zapis zaznamkov pa je uporabnikova baza,
        # ki jo bere tudi vmesnik. Zato ga opravimo na glavni niti.
        def zdruzi():
            try:
                dodanih, _ = self.config.import_bookmarks_items(pripravljeni)
            except Exception as e:  # noqa: BLE001
                self._odziv("napaka",
                            f"Združevanja zaznamkov ni bilo mogoče končati: {e}")
                return False
            razlicica = telo.get("version")
            if isinstance(razlicica, int) and razlicica > int(
                    self.nastavitve.get("sync_bookmarks_version", 0) or 0):
                self.nastavitve.set("sync_bookmarks_version", razlicica)
            self._odziv("sinhronizacija", {
                "kategorija": KATEGORIJA_ZAZNAMKI,
                "vklopljena": True,
                "dodanih": dodanih,
            })
            return False

        GLib.idle_add(zdruzi)

    def _nastavi_sinhronizacijo(self, vklopljena: bool) -> None:
        self.nastavitve.set("sync_bookmarks", bool(vklopljena))
        if self.povezava is not None:
            self.povezava.zapri()
            self.povezava = None
        if not vklopljena:
            self._odziv("sinhronizacija", {"kategorija": KATEGORIJA_ZAZNAMKI,
                                           "vklopljena": False, "dodanih": 0})
            self._povezi()
            return
        self._povezi()
        if self.povezava is None:
            self._odziv("napaka", "Povezave s Hubom ni.")
            return
        self.povezava.zahtevaj_sync(KATEGORIJA_ZAZNAMKI)
        razlicica = int(self.nastavitve.get("sync_bookmarks_version", 0) or 0) + 1
        self.nastavitve.set("sync_bookmarks_version", razlicica)
        self.povezava.poslji_sync(KATEGORIJA_ZAZNAMKI, razlicica, self._izvozi_zaznamke())
        self._odziv("sinhronizacija", {"kategorija": KATEGORIJA_ZAZNAMKI,
                                       "vklopljena": True, "dodanih": 0})


def _barva(r: int, g: int, b: int):
    from gi.repository import Gdk
    barva = Gdk.RGBA()
    barva.red = r / 255.0
    barva.green = g / 255.0
    barva.blue = b / 255.0
    barva.alpha = 1.0
    return barva
