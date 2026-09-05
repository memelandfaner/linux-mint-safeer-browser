# Safeer Browser — Linux Mint Edition 🛡️

### **Safeer Browser v1.0.4 — Stable Release**
*Odprtokodni namizni brskalnik z večslojno kibernetsko zaščito, blokado oglasov, 1-klik uvozom zaznamkov in nativnim Debian paketom.*

> ⚠️ **Safeer is a security layer, not a guarantee against all online threats.**  
> Safeer deluje kot lokalni varnostni sloj, ki bistveno zmanjšuje tveganje in blokira znana škodljiva vozlišča, zlonamerne domene in sledilce; ne zagotavlja zaščite pred vsemi novimi ali neznanimi grožnjami (Zero-Day).

**Varnejši na spletu. Brez oglasov.**

---

## 🌟 Odprta Koda, Navdih in Spodbuda k Lastnemu Razvoju (Fork & Customize)

> **Kdor obvladuje brskalnik, določa pravila spleta.**  
> Milijon uporabnikov ima milijon različnih potreb, okusov in prioritet. Safeer je 100 % odprtokoden projekt pod licenco [Apache License 2.0](LICENSE) prav zato, da služi kot odprta platforma in navdih za skupnost.  
>  
> 👉 **Vabljeni k ustvarjanju lastnih vejic (Fork)!**  
> Vzemite izvorno kodo v svoje roke, prilagodite varnostne sezname, spremenite grafično podobo, dodajte lastne bližnjice ali preizkusite nove eksperimentalne funkcionalnosti. Internet je boljši, ko ima vsakdo možnost ustvariti brskalnik po svojih lastnih željah in potrebah.

---

## 🛡️ Varnostne in Zasebnostne Zmožnosti

1. **1-Klik Uvoz Zaznamkov (Bookmarks Importer)**:
   - Hitra in enostavna migracija iz brskalnikov Firefox, Google Chrome, Brave, Chromium ali Edge.
   - Brskalnik samodejno prepozna kategorije, priredi ustrezne ikone (YouTube, Glasba, Novice, GitHub, AI itd.) in živahne barvne poudarke ter prepreči podvajanje obstoječih povezav.

2. **W3C Global Privacy Control (GPC) & Do Not Track (DNT)**:
   - Avtomatsko uveljavljanje spletnih standardov zasebnosti (`navigator.globalPrivacyControl = true`, `navigator.doNotTrack = '1'`) ob zagonu vsakega dokumenta.

3. **Odstranjevanje Sledilnih Parametrov (Query Tracker Stripping)**:
   - Samodejno čiščenje nadzornih parametrov (`utm_source`, `utm_medium`, `fbclid`, `gclid`, `si`, `mc_eid`, `msclkid`, `twclid`, itd.) ob navigaciji in klikih na povezave ob ohranitvi ključnih iskalnih parametrov (`q`, `v`, `id`, `page`).

4. **Kibernetski Ščit $O(k)$ Reverse Domain Trie (abuse.ch & Phishing Army)**:
   - Podmikrosekundno preverjanje domen pred C2 botneti (Feodo Tracker - Dridex, Emotet, QakBot, TrickBot, IcedID, CobaltStrike, Redline), zlonamerno kodo (URLhaus, ThreatFox) in spletnim ribarjenjem (Phishing Army).

5. **Ščit pred Clickjackingom in Nevidnimi Prekrivnimi Pastmi**:
   - Samodejna zaznava in nevtralizacija nevidnih celozaslonskih `z-index > 999` prevlek na pretočnih in prenosnih straneh.

6. **YouTube Zero-Ad & Zvok v Ozadju**:
   - Samodejno odstranjevanje oglasov, preskakovanje oglasnih pasic, zapiranje pojavnih oken in nemoteno predvajanje glasbe v ozadju z minimiziranim oknom.

7. **Modularni "Safeer Dock" (Stranska Orodna Vrstica)**:
   - 💬 **Facebook Messenger** (`https://www.messenger.com`) – stranski predal za klepet brez zapuščanja trenutnega zavihka.
   - ✉️ **Gmail** (`https://mail.google.com`) – hiter dostop do e-pošte.
   - ➕ **Dodajanje poljubnih spletnih strani**: Enostavno dodajanje in urejanje lastnih spletnih aplikacij (WhatsApp, Telegram, Discord, ChatGPT).
   - Tipka `F4` za takojšen vklop/izklop stranskega predala.

8. **Customizer Studio & Teme**:
   - Vgrajene teme (Midnight, Mint Emerald, Cyberpunk Neon, AMOLED Black), lasten CSS urejevalnik in podpora za uporabniške skripte (UserScripts v slogu Tampermonkey).

9. **6 Svetovnih Jezikov (i18n)**:
   - Popolna večjezičnost: slovenščina (`sl`), angleščina (`en`), nemščina (`de`), španščina (`es`), francoščina (`fr`) in italijanščina (`it`).

---

## 🚀 Namestitev in Zagon

### 1. Nativna namestitev (.deb paket - priporočeno za Linux Mint & Ubuntu):
```bash
sudo apt install ./safeer-browser_1.0.4_amd64.deb
```
Ali enostavno dvokliknite na preneseno `.deb` datoteko v Upravitelju datotek (Gdebi / Upravitelj programov).

### 2. Izdelava lastnega .deb paketa:
```bash
./build_deb.sh
```

### 3. Zagon brez namestitve (izvorna koda / razvoj):
```bash
./safeer-mint.sh
```

### 4. Namestitev v uporabniški profil (`~/.local`):
```bash
./install.sh
```

---

## ⚖️ Pravno Obvestilo in Omejitev Odgovornosti (Disclaimer)

- **Varnostna omejitev**: **Safeer is a security layer, not a guarantee against all online threats.** Noben spletni brskalnik ali varnostni filter ne more zagotoviti 100 % ali absolutne zaščite pred vsemi novimi, ciljanimi ali še neznanimi grožnjami (Zero-Day). Safeer deluje kot lokalni varnostni sloj, ki bistveno zmanjšuje tveganje in blokira znana škodljiva vozlišča, zlonamerne domene in sledilce.
- **Licenca in Prilagajanje (Forking)**: Projekt je izdan pod licenco [Apache License 2.0](LICENSE). Prosto ga klonirajte, delite, predelujte in prilagajajte po lastnih željah in potrebah.
- **Repozitorij**: [https://github.com/memelandfaner/linux-mint-safeer-browser](https://github.com/memelandfaner/linux-mint-safeer-browser)
