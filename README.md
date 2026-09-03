# Safeer Browser — Linux Mint Edition 🛡️

> *"Milijon ljudi ima milijon različnih osebnosti, želja in potreb, vendar en sam cilj: **imeti odprt in varen internet na dosegu roke**. Zato smo ustvarili ta odprtokodni projekt, kjer lahko vsakdo naredi fork izvorne kode in brskalnik prilagodi po lastnih željah."*

Sodoben, hiter in zasebnosti prijazen namizni spletni brskalnik, razvit posebej za uporabnike operacijskega sistema **Linux Mint** (Cinnamon, MATE, Xfce).

---

## 🌟 Glavne značilnosti

1. **Modularni "Safeer Dock" (Stranska vrstica za klepet in produktivnost)**:
   - 💬 **Facebook Messenger** (`https://www.messenger.com`) – hitro dopisovanje v stranskem predalu brez zapuščanja zavihka.
   - ✉️ **Gmail** (`https://mail.google.com`) – hiter dostop do e-pošte.
   - 📺 **YouTube** (`https://www.youtube.com`) – poslušanje glasbe in videoposnetkov z vgrajenim odstranjevanjem video oglasov in predvajanjem v ozadju.
   - ⚙️ **Urejanje po meri**: Vsako integracijo lahko po lastnih željah vklopite, izklopite ali dodate svojo (WhatsApp, Discord, ChatGPT).

2. **Izkušnja iz Safeer TV, prilagojena za namizni računalnik**:
   - Hitra začetna stran (`safeer://home`) s prikazom ure, datuma, izbiro iskalnikov (*Google, DuckDuckGo, Brave Search, YouTube*) in priljubljenimi portali (*Xplore TV, 24ur, RTV SLO, Filmi*).
   - Števec blokiranih oglasov in prihranjenega časa (Safeer Shield).
   - **Privzeto brez navidezne tipkovnice**: Brskalnik je optimiziran za vašo fizično tipkovnico in miško.
   - **Izbirna navidezna tipkovnica (On-Screen Keyboard)**: Na voljo je z enim klikom na ikono `⌨️ Tipkovnica` v orodni vrstici (za zaslone na dotik ali dostopnost).

3. **100% Nativna integracija v Linux Mint**:
   - Uskajen z Linux Mint temnim načinom (Mint-Y Dark).
   - Nizka poraba pomnilnika RAM in hipen zagon (pogon WebKitGTK 4.1).
   - Chrome User-Agent za 100% združljivost z vsemi Google in Facebook prijavami.

---

## 🚀 Hitri zagon in namestitev

### 1. Zagon brez namestitve:
```bash
./safeer-mint.sh
```

### 2. Namestitev v Linux Mint meni in na namizje:
```bash
./install.sh
```
Po zagonu skripte `install.sh` se bo ikona **Safeer Browser** pojavila:
- Na vašem namizju.
- V meniju programov Linux Mint pod kategorijo **Internet -> Safeer Browser**.

---

## 📁 Struktura projekta

```
linux-mint-safeer-browser/
├── safeer_mint.py          # Glavno grafično jedro (GTK3 + WebKit2)
├── safeer-mint.sh          # Izvršljiv zaganjalnik
├── install.sh              # Skripta za namestitev v sistem
├── safeer-browser.desktop  # Namizna integracija za Linux Mint
├── core/
│   ├── config.py           # Upravitelj nastavitev (~/.config/safeer-mint/settings.json)
│   └── adblock.py          # Blokiranje oglasov in abuse.ch C2 zaščita
├── ui/
│   ├── home.html           # Namizna začetna stran (Safeer DNA)
│   ├── home.css            # Mint-Y Dark stil
│   ├── home.js             # Iskalnik, ura in priljubljeni portali
│   └── keyboard.html       # Izbirna navidezna tipkovnica
└── assets/
    └── icon.png            # Logotip Safeer za Linux Mint
```

---

## 🌍 Odprta koda & Fork

Ta projekt je licenciran pod odprto licenco MIT. Vabljeni, da naredite svojo vejitev (fork) na GitHubu in prispevate svoje izboljšave:
👉 **[https://github.com/memelandfaner/linux-mint-safeer-browser](https://github.com/memelandfaner/linux-mint-safeer-browser)**
