# Safeer Browser — Linux Mint & Ubuntu Edition 🛡️

[![Release](https://img.shields.io/badge/Release-v1.0.5-emerald?style=flat-square)](https://github.com/memelandfaner/linux-mint-safeer-browser/releases/tag/v1.0.5)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux_Mint_%7C_Ubuntu_%7C_Debian-87cf3e?style=flat-square)](https://github.com/memelandfaner/linux-mint-safeer-browser)
[![Package](https://img.shields.io/badge/Package-.deb_(all_%7C_amd64)-cyan?style=flat-square)](https://github.com/memelandfaner/linux-mint-safeer-browser/releases/tag/v1.0.5)
[![Web](https://img.shields.io/badge/Spletna_stran-Linux_Izdaja-87cf3e?style=flat-square)](https://memelandfaner.github.io/-safeer-browser/linux/)

> **Ultra lahek, suveren in energetsko varčen Linux brskalnik, ki se odpre v `~/Prenosi/<naslov>.pdf`.ol sekunde, porabi 3-krat manj RAM-a kot Chrome/Firefox in ima vgrajen Instant YouTube predvajalnik brez oglasov `~/Prenosi/<naslov>.pdf`.er lokalni ščit pred zlonamernimi domenami.**

---

## ⚡ Zakaj izbrati Safeer na Linux Mintu?

| Metrika / Lastnost | 🛡️ Safeer Browser | Google Chrome | Mozilla Firefox |
| :--- | :--- | :--- | :--- |
| **Čas hladnega zagona** | **< 0.5 s** (hipen) | 2.4 s | 1.9 s |
| **Poraba RAM (3 zavihki + YT)** | **~180 MB** | 680 MB | 590 MB |
| **Obremenitev `~/Prenosi/<naslov>.pdf`.rocesorja pri zvoku** | **< 1.5% CPU** | 8–15% CPU | 6–12% CPU |
| **YouTube v `~/Prenosi/<naslov>.pdf`.zadju** | **Brezplačno & 0 oglasov** | Ustavitev `~/Prenosi/<naslov>.pdf`. Oglasi | Oglasi |
| **Lokalna varnost (C2 ščit)** | **Vgrajen O(k) Trie (abuse.ch)** | Osnovni filter | Osnovni filter |
| **Telemetrija & sledenje** | **0 % (100% lokalno)** | Googlovo sledenje | Telemetrija |
| **Namestitveni paket** | **1.1 MB (.deb)** | ~110 MB | ~90 MB |

---

## 📦 Namestitev `~/Prenosi/<naslov>.pdf`.Priporočeno)

### 1. Nativni Debian / Ubuntu / Linux Mint paket (`.deb`):
Najnovejšo različico prenesite s strani [GitHub Releases](https://github.com/memelandfaner/linux-mint-safeer-browser/releases/tag/v1.0.5) ali namestite z enim ukazom:

```bash
# Namestitev `~/Prenosi/<naslov>.pdf`. uradnim upraviteljem apt:
sudo apt install ./safeer-browser_1.0.5_all.deb
```
*Ali pa datoteko `.deb` preprosto dvokliknite v `~/Prenosi/<naslov>.pdf`.pravitelju datotek (Gdebi / Upravitelj programov).*

Paket avtomatsko:
- Namesti zaganjalnik `/usr/bin/safeer` in bližnjico v `~/Prenosi/<naslov>.pdf`.eni programov.
- Registrira Safeer kot alternativo za sistemski privzeti brskalnik (`x-www-browser` in `gnome-www-browser`).
- Poveže MIME tipe za spletne povezave (`http`, `https`).

### Kontrolne vsote (SHA-256):
```text
5982d545b88d9f49df41b64f3705a1a7d8b426e09c6bd92e82aa46b528e5efb9  safeer-browser_1.0.5_all.deb
5982d545b88d9f49df41b64f3705a1a7d8b426e09c6bd92e82aa46b528e5efb9  safeer-browser_1.0.5_amd64.deb
80c6b35bc4ba2410853b326002ada20486cd47189f1d10f63382c024f46e3067  safeer-browser-linux.tar.gz
```

---

## 📥 1-Klik Uvoz Zaznamkov `~/Prenosi/<naslov>.pdf`.Zero-Friction Migration)

Pozabite na nerodno ročno izvažanje datotek. Safeer ob kliku na **📥 Uvozi zaznamke** na domači strani samodejno pregleda vaš sistem in ponudi:
- 🦊 **1-Klik uvoz iz Firefoxa**: Neposredno branje iz profila `~/.mozilla/firefox/*/places.sqlite`.
- 🌐 **1-Klik uvoz iz Chroma / Brave / Chromium**: Branje iz `~/.config/*/Bookmarks`.
- ⚡ **Samodejno združevanje brez duplikatov**: Zaznamki se samodejno opremijo z visoko-ločljivostnimi **favicon** ikonami in razporedijo med priljubljene portale.
- 📂 **Netscape HTML izvoz**: Za vse ostale brskalnike (Opera, Vivaldi, Safari).

---

## 🛡️ Varnost in funkcije za vsakdanjo rabo

1. **YouTube v `~/Prenosi/<naslov>.pdf`.zadju z minimalno porabo procesorja**:
   - Poslušajte glasbo in podcaste med tipkanjem kode, pisanjem dokumentov `~/Prenosi/<naslov>.pdf`.li prevajanjem v `~/Prenosi/<naslov>.pdf`.erminalu. Ventilatorji prenosnika ostanejo tihi.
2. **Kibernetski ščit $O(k)$ Reverse Domain Trie (abuse.ch)**:
   - Podmikrosekundna lokalna blokada nevarnih C2 botnetov `~/Prenosi/<naslov>.pdf`.Feodo, CobaltStrike, Dridex), izsiljevalske programske opreme (URLhaus) in lažnega predstavljanja (Phishing Army).
3. **Awesomebar za razvijalce**:
   - Hitri skoki na lokalna razvojna vrata (`:3000`, `:8080`, `:5173`, `localhost`) z enim pritiskom.
4. **Customizer Studio & Teme**:
   - Izbirajte med 4 temami (*Mint Emerald*, *Midnight*, *Cyberpunk Neon*, *AMOLED Black*), urejajte lasten CSS ali poganjajte Tampermonkey-združljive uporabniške skripte (UserScripts).
5. **Safeer Dock (Stranska orodna vrstica - F4)**:
   - Hitri dostop do Facebook Messengerja, Gmaila ali poljubne spletne aplikacije brez zapuščanja trenutnega zavihka.


6. **Iskanje po strani (Ctrl+F)**:
   - Hitro iskanje besedila z nativnim WebKit FindControllerjem, realno-časovnim števcem zadetkov `~/Prenosi/<naslov>.pdf`.n bližnjicami (Enter, Shift+Enter, Esc).
7. **Tiskanje in shranjevanje v `~/Prenosi/<naslov>.pdf`.DF (Ctrl+P)**:
   - Nativni GTK Print Dialog z avtomatskim predlogom imena datoteke v `~/Prenosi/<naslov>.pdf`.
8. **Obnova seje (Session Restore)**:
   - Samodejno shranjevanje odprtih zavihkov `~/Prenosi/<naslov>.pdf`.b zaprtju in vprašanje za obnovo ob ponovnem zagonu.
9. **Živi števec blokiranih groženj (Shields Counter)**:
   - Dinamični prikaz števila nevarnih domen in sledilcev `~/Prenosi/<naslov>.pdf`.eposredno na gumbu v `~/Prenosi/<naslov>.pdf`.rodni vrstici (npr. 🛡️ 5).

---

## 🛠️ Gradnja iz kode in razvoj (Developers)

Za razvijalce, ki želijo prispevati ali zagnati brskalnik neposredno iz izvorne kode:

```bash
# Zagon neposredno iz izvorne kode:
./safeer-mint.sh

# Izdelava .deb paketa z dpkg-deb:
./build_deb.sh

# Namestitev `~/Prenosi/<naslov>.pdf`. domačo mapo uporabnika (~/.local):
./install.sh
```

---

## 🌟 Odprta koda & Vabilo k prilagajanju (Fork & Freedom)

> **Kdor obvladuje brskalnik, določa svoja pravila spleta.**  
> Safeer je 100 % odprtokoden pod licenco [Apache License 2.0](LICENSE). Spodbujamo vas, da kodo klonirate (Fork), jo prilagodite svojim specifičnim potrebam, preizkusite nove zamisli ter soustvarjate svoboden, suveren internet.

---

## ⚖️ Pravno obvestilo (Security Disclaimer)
- **Varnostni sloj**: **Safeer is a security layer, not a guarantee against all online threats.** Noben filter ne more zagotoviti 100 % zaščite pred neznanimi grožnjami (Zero-Day). Safeer deluje kot lokalni varnostni sloj, ki bistveno zmanjšuje tveganje in blokira znana škodljiva vozlišča ter sledilce.
- **Uradni repozitorij**: [https://github.com/memelandfaner/linux-mint-safeer-browser](https://github.com/memelandfaner/linux-mint-safeer-browser)
- **Prenosi in izdaje**: [GitHub Releases v1.0.5](https://github.com/memelandfaner/linux-mint-safeer-browser/releases/tag/v1.0.5)

