# Safeer Linux 1.0.22

Fewer ads and a wider net against web traps (Safeer Shield):

- EasyList inside the WebKit engine: the full EasyList ad list is converted to a WebKit content filter and compiled once, so ad requests are dropped in the network layer before any script runs, with no per-request round trip. The list is refreshed in the background about 20 seconds after start and every 6 hours (an unchanged list costs one small request); a failed download or a rejected file keeps the previous filter. Real banks and payment pages stay excluded from every rule. Can be switched off with `easylist_enabled` in the settings.
- Fake bank pages sent as an attachment: a bank login page opened from a local file (`file:` or a downloaded HTML attachment, the "phishing without hosting" pattern reported by SI-CERT) now gets the same warning as a look-alike address; the warning names the real bank and offers its real site.
- Card-number lures: pages that ask for a card number under the guise of a fine, a parcel fee or a tax refund ("pay within 24 hours", "your parcel is waiting") are stopped as a card trap even when no bank is named.
- Tax number and PIN fields count as credentials in the fake-bank check, and every warning reminds you that a bank never calls to ask for codes or to install remote-access software.
- Build: Linux packages are built in an Ubuntu 22.04 container on current GitHub runners (AppImage stays compatible with Linux Mint 21 / Ubuntu 22.04) with the Node 24 action releases.

All checks run locally; no address or page content leaves the computer.

Slovensko: Manj oglasov in širša zaščita pred spletnimi pastmi. Celoten seznam EasyList je zdaj vgrajen v WebKit kot prevedeni filter vsebine, zato so oglasni zahtevki ustavljeni v omrežni plasti brez upočasnitve; seznam se osvežuje v ozadju. Lažna banka, ki prispe kot priponka HTML in se odpre z diska, dobi enako opozorilo kot lažni naslov; strani, ki pod pretvezo kazni, paketa ali vračila davka zahtevajo številko kartice, se ustavijo kot past za kartico; davčna številka in PIN veljata za prijavne podatke, opozorilo pa spomni, da banka nikoli ne kliče po kodah ali zahteva namestitve programa za oddaljen dostop.
