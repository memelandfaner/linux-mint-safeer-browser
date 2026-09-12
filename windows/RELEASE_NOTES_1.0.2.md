# Safeer Browser for Windows 1.0.2

Wider net against web traps:

- Fake bank pages sent as an attachment: a bank login page opened from a local file (a downloaded HTML attachment, the "phishing without hosting" pattern reported by SI-CERT) now gets the same warning as a look-alike address; the warning names the real bank and offers its real site.
- Card-number lures: pages that ask for a card number under the guise of a fine, a parcel fee or a tax refund ("pay within 24 hours", "your parcel is waiting") are stopped as a card trap even when no bank is named.
- Tax number and PIN fields count as credentials in the fake-bank check, and every warning reminds you that a bank never calls to ask for codes or to install remote-access software.
- The list of real banks and payment pages is shared with the Linux edition, so both editions exclude the same sites from ad rules and phishing entries.
- Build: unattended test runs no longer stop on a Windows error dialog, and the build libraries are pinned so every package is reproducible.

All checks run locally; no address or page content leaves the computer.

Slovensko: Širša zaščita pred spletnimi pastmi. Lažna banka, ki prispe kot priponka HTML in se odpre z diska, dobi enako opozorilo kot lažni naslov; strani, ki pod pretvezo kazni, paketa ali vračila davka zahtevajo številko kartice, se ustavijo kot past za kartico; davčna številka in PIN veljata za prijavne podatke, opozorilo pa spomni, da banka nikoli ne kliče po kodah ali zahteva namestitve programa za oddaljen dostop.
