# Safeer Linux 1.0.21

Update of the protection against web traps (Safeer Shield):

- Fake online banks: an address that imitates a bank (`nlb-klik-prijava.com`, `otpbamka.si`, look-alike letters from another alphabet) is stopped with a warning. After every page load a small script in an isolated JavaScript world checks for visible password, SMS code or card fields, so a page on a foreign address that presents itself as a bank gets the same warning. The dialog offers "Back to safety", "Open <real bank site>" and "Continue anyway" (this session only).
- Real banks work undisturbed: Slovenian banks and savings banks, their banking groups, PayPal, Revolut, N26, Wise and the pages used for logins and card payments (Bankart, Halcom, SI-PASS, 3-D Secure) are never blocked by ad rules or phishing entries and run without cosmetic, anti-popup and background-tab scripts. Confirmed malware on a compromised server is still blocked.
- The verified, signed Safeer threat list (Ed25519) is loaded on a background thread, so the window no longer waits for it, and is checked for updates about 12 seconds after every start, then every 6 hours.

All checks run locally; no address or page content leaves the computer.

Slovensko: Posodobljena zaščita pred spletnimi pastmi. Opozorilo pred lažnimi spletnimi bankami z gumbom za pravo stran banke, prave banke in plačilne strani delujejo nemoteno, podpisan seznam nevarnih strani pa se naloži v ozadju in ob vsakem zagonu preveri brez upočasnitve okna.
