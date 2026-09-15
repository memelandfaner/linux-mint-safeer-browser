#!/usr/bin/env python3
"""
Safeer: uporabniške skripte (.user.js).

Beremo glavo ``==UserScript==`` v obliki, kot jo pišejo za Greasemonkey in
Tampermonkey, in iz nje sestavimo natanko to, kar WebKit potrebuje:
seznam dovoljenih in prepovedanih naslovov, čas vbrizga in okvirje.

Kar podpremo, podpremo do konca; česar ne, povemo naravnost -- skripta, ki
zahteva funkcijo, ki je nimamo, se ne vklopi tiho, ampak pove, kaj ji manjka.

Podprto v tej različici:
    @name @namespace @version @description @author
    @match @include @exclude @exclude-match   (kje skripta teče)
    @run-at document-start | document-end | document-idle
    @noframes
    @grant GM_addStyle, GM_getValue, GM_setValue, GM_deleteValue,
           GM_listValues, GM_log, GM_info, none

Še ni podprto (skripta se ne vklopi, dokler tega ni):
    GM_xmlhttpRequest, GM_openInTab, GM_notification, GM_download,
    GM_registerMenuCommand, GM_setClipboard, @require, @resource
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

ZACETEK_GLAVE = "==UserScript=="
KONEC_GLAVE = "==/UserScript=="

# Funkcije, ki jih zna ta različica.
PODPRTA_DOVOLJENJA = frozenset({
    "none",
    "GM_addStyle",
    "GM_getValue", "GM_setValue", "GM_deleteValue", "GM_listValues",
    "GM_log", "GM_info",
    "GM.getValue", "GM.setValue", "GM.deleteValue", "GM.listValues", "GM.info",
})

# Funkcije, ki jih skripte pogosto zahtevajo, mi pa jih (še) nimamo.
ZNANA_NEPODPRTA_DOVOLJENJA = frozenset({
    "GM_xmlhttpRequest", "GM.xmlHttpRequest",
    "GM_openInTab", "GM.openInTab",
    "GM_notification", "GM.notification",
    "GM_download", "GM.download",
    "GM_registerMenuCommand", "GM_unregisterMenuCommand",
    "GM_setClipboard", "GM.setClipboard",
    "GM_getResourceText", "GM_getResourceURL",
    "GM_addValueChangeListener", "GM_removeValueChangeListener",
    "unsafeWindow",
})

CASI_VBRIZGA = ("document-start", "document-end", "document-idle")


def _vrstice_glave(koda: str) -> Optional[List[str]]:
    """Vrne vrstice med ==UserScript== in ==/UserScript==, ali None, če glave ni."""
    if not koda:
        return None
    zacetek = None
    for st, vrstica in enumerate(koda.splitlines()):
        golo = vrstica.strip()
        if zacetek is None:
            if golo.startswith("//") and ZACETEK_GLAVE in golo:
                zacetek = st
        elif golo.startswith("//") and KONEC_GLAVE in golo:
            return koda.splitlines()[zacetek + 1:st]
    return None


def razclenii_glavo(koda: str) -> Dict:
    """
    Razčleni glavo uporabniške skripte.

    Vrne slovar tudi takrat, kadar glave ni (``ima_glavo`` je takrat False) --
    tako lahko starejše skripte brez glave še naprej delujejo po starem.
    """
    podatki: Dict = {
        "ima_glavo": False,
        "name": "", "namespace": "", "version": "", "description": "", "author": "",
        "matches": [], "excludes": [],
        "run_at": "document-end",
        "noframes": False,
        "grants": [],
        "connects": [],
        "requires": [],
        "neznane_kljuce": [],
    }
    vrstice = _vrstice_glave(koda)
    if vrstice is None:
        return podatki
    podatki["ima_glavo"] = True

    for vrstica in vrstice:
        golo = vrstica.strip()
        if not golo.startswith("//"):
            continue
        golo = golo[2:].strip()
        if not golo.startswith("@"):
            continue
        deli = golo[1:].split(None, 1)
        kljuc = deli[0].strip().lower()
        vrednost = deli[1].strip() if len(deli) > 1 else ""

        if kljuc in ("name", "namespace", "version", "description", "author"):
            if not podatki[kljuc]:            # prva navedba obvelja
                podatki[kljuc] = vrednost
        elif kljuc in ("match", "include"):
            if vrednost:
                podatki["matches"].append(vrednost)
        elif kljuc in ("exclude", "exclude-match"):
            if vrednost:
                podatki["excludes"].append(vrednost)
        elif kljuc == "run-at":
            v = vrednost.lower()
            podatki["run_at"] = v if v in CASI_VBRIZGA else "document-end"
        elif kljuc == "noframes":
            podatki["noframes"] = True
        elif kljuc == "grant":
            if vrednost and vrednost not in podatki["grants"]:
                podatki["grants"].append(vrednost)
        elif kljuc == "connect":
            if vrednost:
                podatki["connects"].append(vrednost)
        elif kljuc == "require":
            if vrednost:
                podatki["requires"].append(vrednost)
        elif kljuc in ("resource", "icon", "updateurl", "downloadurl", "supporturl",
                       "homepage", "homepageurl", "website", "source", "license",
                       "compatible", "incompatible", "antifeature", "top-level-await",
                       "sandbox", "unwrap", "nocompat"):
            pass                              # poznamo jih, a nanje ne vplivajo
        else:
            podatki["neznane_kljuce"].append(kljuc)

    return podatki


def manjkajoca_dovoljenja(podatki: Dict) -> List[str]:
    """
    Katera dovoljenja skripta zahteva, mi pa jih še nimamo.
    Prazen seznam pomeni, da skripto lahko poženemo v celoti.
    """
    manjka = []
    for g in podatki.get("grants", []):
        if g in PODPRTA_DOVOLJENJA:
            continue
        manjka.append(g)
    if podatki.get("requires"):
        manjka.append("@require")
    return manjka


def vzorec_v_webkit(vzorec: str) -> Optional[str]:
    """
    Pretvori @match ali @include v vzorec, kot ga razume WebKit.

    Vrne None, kadar vzorec pomeni »vse strani« (WebKit to izrazi s praznim
    seznamom), in prazen niz, kadar vzorca ne znamo pretvoriti.
    """
    if vzorec is None:
        return ""
    v = vzorec.strip()
    if not v:
        return ""
    if v in ("<all_urls>", "*", "*://*/*", "http*://*/*"):
        return None
    # Golo ime domene (tako so bile shranjene starejše Safeerjeve skripte).
    if re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", v):
        return f"*://*.{v}/*"
    if "://" not in v:
        return ""
    shema, _, ostanek = v.partition("://")
    shema = shema.lower()
    if shema in ("http*", "*"):
        shema = "*"
    if shema not in ("http", "https", "*"):
        return ""                              # file://, ftp://, javascript: -- ne
    if not ostanek:
        return ""
    if "/" not in ostanek:
        ostanek += "/*"
    return f"{shema}://{ostanek}"


def seznama_naslovov(podatki: Dict, zdruzljivi_vzorec: str = "") -> Tuple[Optional[List[str]], List[str]]:
    """
    Sestavi (dovoljeni, prepovedani) seznam naslovov za WebKit.

    dovoljeni = None pomeni »povsod«; prazen seznam pomeni, da skripta nikjer
    ne teče (kadar noben vzorec ni uporaben).
    """
    viri = list(podatki.get("matches") or [])
    if not viri and zdruzljivi_vzorec:
        viri = [zdruzljivi_vzorec]

    dovoljeni: List[str] = []
    povsod = False
    for v in viri:
        pretvorjen = vzorec_v_webkit(v)
        if pretvorjen is None:
            povsod = True
        elif pretvorjen:
            dovoljeni.append(pretvorjen)

    prepovedani: List[str] = []
    for v in podatki.get("excludes") or []:
        pretvorjen = vzorec_v_webkit(v)
        if pretvorjen is None:
            prepovedani.append("*://*/*")
        elif pretvorjen:
            prepovedani.append(pretvorjen)

    if povsod:
        return None, prepovedani
    return dovoljeni, prepovedani


def notranji_blok_seznam(base_dir: str) -> List[str]:
    """
    Naslovi, na katerih uporabniška skripta ne sme teči nikoli.

    Naše notranje strani upravljajo brskalnik (zaznamki, privzeti brskalnik,
    jezik), zato tja tuja koda ne spada, tudi če jo je uporabnik namestil sam.
    """
    mapa = os.path.realpath(os.path.join(base_dir, "ui"))
    return ["safeer://*", f"file://{mapa}/*", f"file://{mapa}*"]


def _js_niz(vrednost) -> str:
    """Varno vgnezdi vrednost v JavaScript (tudi </script> ne more ubežati)."""
    return json.dumps(vrednost, ensure_ascii=False).replace("</", "<\\/")


def predpona_gm(script_id: str, podatki: Dict, vrednosti: Dict, most: str = "safeer_gm") -> str:
    """
    JavaScript, ki ga postavimo pred skripto: da ji natanko tiste funkcije,
    ki jih je zahtevala z @grant, in nič več.

    Vrednosti so vgnezdene kot posnetek ob vbrizgu, zato je GM_getValue
    sinhron tako kot pri Tampermonkeyju; pisanje gre po mostu in je asinhrono.
    """
    dovoljenja = set(podatki.get("grants") or [])
    # Brez @grant (ali z @grant none) skripta dobi samo GM_info in GM_log.
    naj_bo = lambda ime: ime in dovoljenja  # noqa: E731

    info = {
        "script": {
            "name": podatki.get("name") or "",
            "namespace": podatki.get("namespace") or "",
            "version": podatki.get("version") or "",
            "description": podatki.get("description") or "",
            "matches": podatki.get("matches") or [],
            "runAt": podatki.get("run_at") or "document-end",
        },
        "scriptHandler": "Safeer",
        "version": "1",
    }

    kosi = [
        "(function () {",
        "  'use strict';",
        f"  const SAFEER_ID = {_js_niz(script_id)};",
        f"  const SAFEER_VALUES = {_js_niz(vrednosti or {})};",
        f"  const GM_info = {_js_niz(info)};",
        "  const SAFEER_BRIDGE = (op, payload) => {",
        "    try {",
        f"      window.webkit.messageHandlers[{_js_niz(most)}].postMessage(",
        "        JSON.stringify({ id: SAFEER_ID, op: op, payload: payload })",
        "      );",
        "    } catch (e) { /* most ni na voljo: skripta naj vseeno tece */ }",
        "  };",
        "  const GM_log = (...a) => console.log('[Safeer userscript]', ...a);",
    ]

    if naj_bo("GM_addStyle") or naj_bo("GM.addStyle"):
        kosi += [
            "  const GM_addStyle = (css) => {",
            "    const el = document.createElement('style');",
            "    el.textContent = String(css);",
            "    (document.head || document.documentElement).appendChild(el);",
            "    return el;",
            "  };",
        ]
    if naj_bo("GM_getValue") or naj_bo("GM.getValue"):
        kosi += [
            "  const GM_getValue = (k, privzeto) =>",
            "    Object.prototype.hasOwnProperty.call(SAFEER_VALUES, k) ? SAFEER_VALUES[k] : privzeto;",
        ]
    if naj_bo("GM_setValue") or naj_bo("GM.setValue"):
        kosi += [
            "  const GM_setValue = (k, v) => {",
            "    SAFEER_VALUES[String(k)] = v;",
            "    SAFEER_BRIDGE('set', { key: String(k), value: v });",
            "  };",
        ]
    if naj_bo("GM_deleteValue") or naj_bo("GM.deleteValue"):
        kosi += [
            "  const GM_deleteValue = (k) => {",
            "    delete SAFEER_VALUES[String(k)];",
            "    SAFEER_BRIDGE('delete', { key: String(k) });",
            "  };",
        ]
    if naj_bo("GM_listValues") or naj_bo("GM.listValues"):
        kosi += ["  const GM_listValues = () => Object.keys(SAFEER_VALUES);"]

    # Sodobni GM.* vmesnik z obljubami, iz istih funkcij.
    gm_pari = []
    if naj_bo("GM_getValue") or naj_bo("GM.getValue"):
        gm_pari.append("getValue: (k, d) => Promise.resolve(GM_getValue(k, d))")
    if naj_bo("GM_setValue") or naj_bo("GM.setValue"):
        gm_pari.append("setValue: (k, v) => Promise.resolve(GM_setValue(k, v))")
    if naj_bo("GM_deleteValue") or naj_bo("GM.deleteValue"):
        gm_pari.append("deleteValue: (k) => Promise.resolve(GM_deleteValue(k))")
    if naj_bo("GM_listValues") or naj_bo("GM.listValues"):
        gm_pari.append("listValues: () => Promise.resolve(GM_listValues())")
    if naj_bo("GM_addStyle") or naj_bo("GM.addStyle"):
        gm_pari.append("addStyle: (c) => Promise.resolve(GM_addStyle(c))")
    gm_pari.append("info: GM_info")
    gm_pari.append("log: GM_log")
    kosi.append("  const GM = { " + ", ".join(gm_pari) + " };")

    return "\n".join(kosi) + "\n"


def sestavi_vir(script_id: str, koda: str, podatki: Dict, vrednosti: Dict,
                most: str = "safeer_gm") -> str:
    """Predpona z dovoljenji + uporabnikova koda, vse v svojem zaprtju."""
    return predpona_gm(script_id, podatki, vrednosti, most) + "\n" + (koda or "") + "\n})();\n"


def pripravi(script: Dict, vrednosti: Dict, base_dir: str, most: str = "safeer_gm") -> Dict:
    """
    Iz shranjene skripte pripravi vse, kar potrebuje WebKit.

    Vrne slovar z izvorno kodo, časom vbrizga, okvirji in obema seznamoma
    naslovov, ali ``napaka`` s pojasnilom, kadar skripte ne smemo pognati.
    """
    koda = script.get("code") or ""
    podatki = razclenii_glavo(koda)
    manjka = manjkajoca_dovoljenja(podatki)
    if manjka:
        return {"napaka": "manjkajoca_dovoljenja", "manjka": manjka, "glava": podatki}

    dovoljeni, prepovedani = seznama_naslovov(podatki, script.get("pattern", ""))
    if dovoljeni is not None and not dovoljeni:
        return {"napaka": "ni_veljavnega_vzorca", "manjka": [], "glava": podatki}

    prepovedani = list(prepovedani) + notranji_blok_seznam(base_dir)

    return {
        "napaka": "",
        "glava": podatki,
        "vir": sestavi_vir(script.get("id", "script"), koda, podatki, vrednosti, most),
        "run_at": podatki["run_at"] if podatki["ima_glavo"] else (
            "document-start" if script.get("run_at") == "start" else "document-end"),
        "vsi_okvirji": not podatki.get("noframes", False),
        "dovoljeni": dovoljeni,
        "prepovedani": prepovedani,
    }
