# Safeer Browser — Linux Mint & Ubuntu Edition 🛡️

[![Release](https://img.shields.io/badge/Release-v1.0.8-emerald?style=flat-square)](https://github.com/memelandfaner/linux-mint-safeer-browser/releases/tag/v1.0.8)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux_Mint_%7C_Ubuntu_%7C_Debian-87cf3e?style=flat-square)](https://github.com/memelandfaner/linux-mint-safeer-browser)
[![Package](https://img.shields.io/badge/Package-.deb_(all)-cyan?style=flat-square)](https://github.com/memelandfaner/linux-mint-safeer-browser/releases/tag/v1.0.8)
[![Web](https://img.shields.io/badge/Spletna_stran-Linux_Izdaja-87cf3e?style=flat-square)](https://memelandfaner.github.io/-safeer-browser/linux/)

> **Hiter, suveren in energetsko varčen Linux brskalnik, ki se odpre v trenutku, spoštuje zasebnost, blokira sledilce ter ponuja vgrajen YouTube predvajalnik brez oglasov in lokalni ščit pred zlonamernimi domenami.**

---

## ⚡ Zakaj izbrati Safeer na Linux Mintu?

- **Hiter zagon & lahkotnost**: Nativna integracija z GTK3 in WebKit2GTK za gladek odziv brez odvečne navlake.
- **Predvajanje v ozadju**: Poslušanje glasbe in podcastov na YouTubu brez prekinitev ob menjavi zavihkov.
- **Lokalni kibernetski ščit**: Vgrajen $O(k)$ filter za samodejno blokado botnetov, lažnega predstavljanja (phishing) in izsiljevalske programske opreme (abuse.ch viri).
- **Zasebnost po privzetem**: Privzeti iskalnik DuckDuckGo, blokada piškotkov tretjih oseb (3rd-party cookies), brez telemetrije.
- **1-Klik uvoz zaznamkov**: Hitra migracija priljubljenih strani neposredno iz obstoječih profilov Firefoxa ali Chroma.
- **Vrstica in meni priljubljenih (v1.0.7)**: Hiter dostop, dodajanje, urejanje in brisanje priljubljenih spletnih mest z orodnimi bližnjicami (`Ctrl + B`, `Ctrl + Shift + B`).

## 📦 Namestitev

### Nativni Debian paket (`.deb`):
Najnovejšo različico prenesite s strani [GitHub Releases v1.0.8](https://github.com/memelandfaner/linux-mint-safeer-browser/releases/tag/v1.0.8) ali namestite:

```bash
# Namestitev z apt:
sudo apt install ./safeer-browser_1.0.8_all.deb
```
*Ali pa datoteko `.deb` preprosto dvokliknite v upravitelju datotek (Gdebi / Upravitelj programov).*

Paket avtomatsko:
- Vsebuje **AppStream metainfo** (`/usr/share/metainfo/`) za prepoznavo v **Upravitelju programov (mintinstall)**.
- Namesti zaganjalnik `/usr/bin/safeer` in sistemsko bližnjico v meni programov (Internet -> Safeer Browser).
- Se registrira kot varna alternativa med spletnimi brskalniki (brez agresivnega prevzemanja privzetega brskalnika).
- Omogoča enostaven preklop na privzeti brskalnik preko `safeer --set-default` ali v nastavitvah.

### Kontrolne vsote (SHA-256)
Prenesite `SHA256SUMS` iz iste izdaje kot paket in zaženite `sha256sum -c --ignore-missing SHA256SUMS`.

## Popravki v1.0.8

- Šifrirani DNS z delujočim HTTP/2 in brez tihega preklopa na navadni DNS ob neuspehu.
- Ohranjeni začetni podatki povezav in stabilnejše sočasno nalaganje strani.
- Oglasne domene se blokirajo tiho; opozorila o grožnjah so ločena od oglasov.
- Odstranjeni posegi v predvajanje, ki so med preizkusom sprožali zrušitve GStreamerja.
- Podrobnosti in obseg preverjanja: [opombe izdaje](RELEASE_NOTES_1.0.8.md).

---

## 📥 1-Klik Uvoz Zaznamkov (Zero-Friction Migration)

Pozabite na nerodno ročno pretvarjanje datotek. Safeer ob kliku na **📥 Uvozi zaznamke** na domači strani samodejno pregleda vaš sistem in ponudi:
- 🦊 **1-Klik uvoz iz Firefoxa**: Neposredno branje iz profila `~/.mozilla/firefox/*/places.sqlite`.
- 🌐 **1-Klik uvoz iz Chroma / Brave / Chromium**: Branje iz `~/.config/*/Bookmarks`.
- ⚡ **Samodejno združevanje brez duplikatov**: Zaznamki se samodejno opremijo z ikonami in razporedijo med priljubljene portale.
- 📂 **Netscape HTML izvoz**: Za vse ostale brskalnike (Opera, Vivaldi, Safari).

---

## 🛡️ Ključne funkcije za vsakdanjo rabo

1. **YouTube v ozadju z minimalno porabo procesorja**:
   - Poslušajte glasbo in podcaste med delom. Ventilatorji prenosnika ostanejo tihi.
2. **Kibernetski ščit $O(k)$ Reverse Domain Trie (abuse.ch)**:
   - Lokalno blokiranje nevarnih C2 botnetov (Feodo, CobaltStrike, Dridex), izsiljevalske programske opreme (URLhaus) in lažnega predstavljanja (Phishing Army).
3. **Vrstica in plavajoči meni priljubljenih (`Ctrl + B` / `Ctrl + Shift + B`)**:
   - Takojšen dostop do priljubljenih spletnih mest z možnostjo hitrega dodajanja, urejanja ali odstranjevanja neposredno v orodni vrstici.
4. **Mišični spomin in bližnjice**:
   - `Ctrl + T` (nov zavihek), `Ctrl + W` (zapri zavihek), `Ctrl + Shift + T` (obnovi zaprti zavihek), `Ctrl + Tab` (naslednji zavihek), `Ctrl + 1..9` (skok na zavihek), `Alt + Home` (domača stran).
5. **Iskanje po strani (`Ctrl + F`)**:
   - Hitro iskanje besedila z nativnim WebKit FindControllerjem, realno-časovnim števcem zadetkov in bližnjicami.
6. **Tiskanje in shranjevanje v PDF (`Ctrl + P`)**:
   - Nativni GTK tiskalniški dialog z avtomatskim predlogom imena datoteke v `~/Prenosi/<naslov>.pdf`.
7. **Obnova seje (Session Restore)**:
   - Samodejno shranjevanje odprtih zavihkov ob zaprtju in možnost obnove ob ponovnem zagonu.
8. **Nastavitev za privzeti brskalnik (Default Web Browser)**:
   - Izbira je v celoti v vaših rokah: preko obvestilne vrstice ob zagonu, dialoga z nastavitvami ali ukaza `safeer --set-default`.

---

## 🛠️ Gradnja iz kode in razvoj (Developers)

```bash
# Zagon neposredno iz izvorne kode:
./safeer-mint.sh

# Izdelava .deb paketa z dpkg-deb:
./build_deb.sh

# Namestitev v domačo mapo uporabnika (~/.local):
./install.sh
```

---

## 🌟 Odprta koda & Vabilo k prilagajanju (Fork & Freedom)

> **Kdor obvladuje brskalnik, določa svoja pravila spleta.**  
> Safeer je 100 % odprtokoden pod licenco [Apache License 2.0](LICENSE). Spodbujamo vas, da kodo klonirate (Fork), jo prilagodite svojim specifičnim potrebam, preizkusite nove zamisli ter soustvarjate svoboden, suveren internet.

---

## ⚖️ Pravno obvestilo & Namen uporabe (Disclaimer)
- **Varnostni sloj**: **Safeer is a security layer, not a guarantee against all online threats.** Noben filter ne more zagotoviti 100 % zaščite pred neznanimi grožnjami (Zero-Day). Safeer deluje kot lokalni varnostni sloj, ki bistveno zmanjšuje tveganje in blokira znana škodljiva vozlišča ter sledilce.
- **Priporočilo za vsakdanjo rabo**: Safeer je optimiziran za hitro, lahko in varno vsakodnevno spletno brskanje brez oglasov. Za bančne storitve s specifičnimi certifikati ali ponudnike z restriktivnim DRM predvajanjem po potrebi uporabite Firefox.
- **Uradni repozitorij**: [https://github.com/memelandfaner/linux-mint-safeer-browser](https://github.com/memelandfaner/linux-mint-safeer-browser)
- **Prenosi in izdaje**: [GitHub Releases v1.0.8](https://github.com/memelandfaner/linux-mint-safeer-browser/releases/tag/v1.0.8)
