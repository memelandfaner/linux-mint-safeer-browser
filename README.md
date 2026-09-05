# Safeer Browser — Linux Mint Edition 🛡️

### **Safeer Browser v1.0.2 — Stable Release**
*Odprtokodni namizni brskalnik z večslojno kibernetsko zaščito, blokado oglasov in prilagodljivim delovnim okoljem.*

> ⚠️ **Safeer is a security layer, not a guarantee against all online threats.**  
> Safeer deluje kot lokalni varnostni sloj, ki bistveno zmanjšuje tveganje in blokira znana škodljiva vozlišča, zlonamerne domene in sledilce; ne zagotavlja zaščite pred vsemi novimi ali neznanimi grožnjami (Zero-Day).

**Varnejši na spletu. Brez oglasov.**

---

## 🌟 Odprta Koda, Navdih in Spodbuda k Lastnemu Razvoju (Fork & Customize)

> **Kdor obvladuje brskalnik, določa pravila spleta.**  
> Milijon uporabnikov ima milijon različnih potreb, okusov in prioritet. Safeer je 100 % odprtokoden projekt pod licenco [MIT](LICENSE) prav zato, da služi kot odprta platforma in navdih za skupnost.  
>  
> 👉 **Vabljeni k ustvarjanju lastnih vejic (Fork)!**  
> Vzemite izvorno kodo v svoje roke, prilagodite varnostne sezname, spremenite grafično podobo, dodajte lastne bližnjice ali preizkusite nove eksperimentalne funkcionalnosti. Internet je boljši, ko ima vsakdo možnost ustvariti brskalnik po svojih lastnih željah in potrebah.

---

## 🛡️ Varnostne in Zasebnostne Zmožnosti

1. **W3C Global Privacy Control (GPC) & Do Not Track (DNT)**:
   - Avtomatsko uveljavljanje spletnih standardov zasebnosti (`navigator.globalPrivacyControl = true`, `navigator.doNotTrack = '1'`) ob zagonu vsakega dokumenta.

2. **Odstranjevanje Sledilnih Parametrov (Query Tracker Stripping)**:
   - Samodejno čiščenje nadzornih parametrov (`utm_source`, `utm_medium`, `fbclid`, `gclid`, `si`, `mc_eid`, `msclkid`, `twclid`, itd.) ob navigaciji in klikih na povezave ob ohranitvi ključnih iskalnih parametrov (`q`, `v`, `id`, `page`).

3. **Kibernetski Ščit $O(k)$ Reverse Domain Trie (abuse.ch & Phishing Army)**:
   - Podmikrosekundno preverjanje domen pred C2 botneti (Feodo Tracker - Dridex, Emotet, QakBot, TrickBot, IcedID, CobaltStrike, Redline), zlonamerno kodo (URLhaus, ThreatFox) in spletnim ribarjenjem (Phishing Army).

4. **Ščit pred Clickjackingom in Nevidnimi Prekrivnimi Pastmi**:
   - Samodejna zaznava in nevtralizacija nevidnih celozaslonskih `z-index > 999` prevlek na pretočnih in prenosnih straneh.

5. **YouTube Zero-Ad & Zvok v Ozadju**:
   - Samodejno odstranjevanje oglasov, preskakovanje oglasnih pasic, zapiranje pojavnih oken in nemoteno predvajanje glasbe v ozadju z minimiziranim oknom.

6. **Modularni "Safeer Dock" (Stranska Orodna Vrstica)**:
   - 💬 **Facebook Messenger** (`https://www.messenger.com`) – stranski predal za klepet brez zapuščanja trenutnega zavihka.
   - ✉️ **Gmail** (`https://mail.google.com`) – hiter dostop do e-pošte.
   - ➕ **Dodajanje poljubnih spletnih strani**: Enostavno dodajanje in urejanje lastnih spletnih aplikacij (WhatsApp, Telegram, Discord, ChatGPT).
   - Tipka `F4` za takojšen vklop/izklop stranskega predala.

7. **Customizer Studio & Teme**:
   - Vgrajene teme (Midnight, Mint Emerald, Cyberpunk Neon, AMOLED Black), lasten CSS urejevalnik in podpora za uporabniške skripte (UserScripts v slogu Tampermonkey).

8. **6 Svetovnih Jezikov (i18n)**:
   - Popolna večjezičnost: slovenščina (`sl`), angleščina (`en`), nemščina (`de`), španščina (`es`), francoščina (`fr`) in italijanščina (`it`).

---

## 🚀 Hitri Zagon in Namestitev

### 1. Zagon brez namestitve:
```bash
./safeer-mint.sh
```

### 2. Namestitev v sistem Linux Mint (Cinnamon, MATE, Xfce, Ubuntu, Debian):
```bash
./install.sh
```
Skripta `install.sh`:
- Namesti zaganjalnik na namizje in v meni programov pod **Internet -> Safeer Browser**.
- Nastavi terminalski ukaz `safeer` za hitri zagon (`safeer https://example.com`).
- Nastavi enotno instanco preko Unix socketa.

---

## ⚖️ Pravno Obvestilo in Omejitev Odgovornosti (Disclaimer)

- **Varnostna omejitev**: **Safeer is a security layer, not a guarantee against all online threats.** Noben spletni brskalnik ali varnostni filter ne more zagotoviti 100 % ali absolutne zaščite pred vsemi novimi, ciljanimi ali še neznanimi grožnjami (Zero-Day). Safeer deluje kot lokalni varnostni sloj, ki bistveno zmanjšuje tveganje in blokira znana škodljiva vozlišča, zlonamerne domene in sledilce.
- **Licenca in Prilagajanje (Forking)**: Projekt je izdan pod odprto licenco [MIT](LICENSE). Prosto ga klonirajte, delite, predelujte in prilagajajte po lastnih željah in potrebah.
- **Repozitorij**: [https://github.com/memelandfaner/linux-mint-safeer-browser](https://github.com/memelandfaner/linux-mint-safeer-browser)
