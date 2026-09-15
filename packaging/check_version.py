"""Ena sama verzija na vseh mestih, ki jih vidi uporabnik.

Doslej je preverjal samo kodo in AppStream, zato je README pol meseca svetoval
namestitev razlicice 1.0.14, medtem ko je bila koda ze 1.0.26. Uporabnik, ki mu
recemo »prenesite najnovejso«, si mora prenesti res najnovejso.

Zgodovinskih navedb (odseki »Popravki v1.0.x«, povezave na stare opombe izdaj)
ne preverjamo -- te so pravilno stare.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

r = Path(__file__).resolve().parents[1]
v = (r / "packaging/VERSION").read_text().strip()

assert re.fullmatch(r"\d+\.\d+\.\d+(?:[.+~-][\w.-]+)?", v), v
assert re.search(r'APP_VERSION = "' + re.escape(v) + r'"', (r / "safeer_mint.py").read_text()), \
    "APP_VERSION differs"
assert ET.parse(r / "io.github.memelandfaner.SafeerBrowser.metainfo.xml") \
    .find("releases/release").get("version") == v, "AppStream version differs"

# --- mesta, kjer README in PACKAGING.md uporabniku povejo, kaj naj prenese -----
napake = []

readme = (r / "README.md").read_text(encoding="utf-8")
PRICAKOVANO = [
    (f"badge/Release-v{v}-", "znacka Release v README"),
    (f"releases/tag/v{v}", "povezava na izdajo v README"),
    (f"safeer-browser_{v}_all.deb", "ukaz apt install v README"),
]
for niz, opis in PRICAKOVANO:
    if niz not in readme:
        napake.append(f"README.md: manjka {opis} za razlicico {v} ({niz})")

# Stara oznaka izdaje v povezavah ali ukazu je napaka; omembe v zgodovinskih
# odsekih (»## Popravki v1.0.14«, RELEASE_NOTES_*.md) pustimo pri miru.
for vrstica in readme.splitlines():
    if vrstica.lstrip().startswith("#") or "RELEASE_NOTES_" in vrstica:
        continue
    for stara in re.findall(r"releases/tag/v(\d+\.\d+\.\d+)", vrstica):
        if stara != v:
            napake.append(f"README.md kaze na izdajo v{stara}, koda je {v}: {vrstica.strip()[:90]}")
    for stara in re.findall(r"safeer-browser_(\d+\.\d+\.\d+)_all\.deb", vrstica):
        if stara != v:
            napake.append(f"README.md namescа {stara}, koda je {v}: {vrstica.strip()[:90]}")

pack = (r / "PACKAGING.md").read_text(encoding="utf-8")
for stara in set(re.findall(r"safeer-browser_(\d+\.\d+\.\d+)_all\.deb", pack)) | \
             set(re.findall(r"Safeer-Browser-(\d+\.\d+\.\d+)-x86_64", pack)):
    if stara != v:
        napake.append(f"PACKAGING.md navaja {stara}, koda je {v}")

if napake:
    print("Verzije se ne ujemajo:")
    for n in napake:
        print("  -", n)
    sys.exit(1)

if os.environ.get("GITHUB_REF_TYPE") == "tag":
    assert os.environ["GITHUB_REF_NAME"] == "v" + v, "Release tag differs"

print("Version:", v)
