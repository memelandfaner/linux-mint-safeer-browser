# Safeer Linux 1.0.21

Update of the protection against web traps (Safeer Shield):

- Fake online banks: an address that imitates a bank (`nlb-klik-prijava.com`, `otpbamka.si`, look-alike letters from another alphabet) is stopped with a warning. After every page load a small script in an isolated JavaScript world checks for visible password, SMS code or card fields, so a page on a foreign address that presents itself as a bank gets the same warning. The dialog offers "Back to safety", "Open <real bank site>" and "Continue anyway" (this session only).
- Real banks work undisturbed: Slovenian banks and savings banks, their banking groups, PayPal, Revolut, N26, Wise and the pages used for logins and card payments (Bankart, Halcom, SI-PASS, 3-D Secure) are never blocked by ad rules or phishing entries and run without cosmetic, anti-popup and background-tab scripts. Confirmed malware on a compromised server is still blocked.
- The verified, signed Safeer threat list (Ed25519) is loaded on a background thread, so the window no longer waits for it, and is checked for updates about 12 seconds after every start, then every 6 hours.
- Return to installed programs: links that belong to a program instead of a web page, such as the return to the Claude app after signing in with Google (`claude://`), `mailto:` or meeting links, were silently blocked. Safeer now asks "Open <program>?", can remember the answer for that site and hands the link to the program registered in the desktop. Web, file, script and data links still never leave the browser.
- YouTube and YouTube Music: the "Video paused. Continue watching?" prompt no longer appears. Its timers arrive with the player data and are moved beyond any real session before the player reads them; the existing confirmation stays as a fallback and now always resumes the player's video, not a hover preview.

All checks run locally; no address or page content leaves the computer.

Slovensko: Posodobljena zaščita pred spletnimi pastmi. Opozorilo pred lažnimi spletnimi bankami z gumbom za pravo stran banke, prave banke in plačilne strani delujejo nemoteno, podpisan seznam nevarnih strani pa se naloži v ozadju in ob vsakem zagonu preveri brez upočasnitve okna. Povezave, ki pripadajo nameščenim programom (npr. vrnitev v aplikacijo Claude po prijavi z Googlom), Safeer po potrditvi odpre v tem programu. YouTube in YouTube Music ne ustavita več predvajanja z vprašanjem »Želite nadaljevati z ogledom?«.
