# Safeer Browser for Windows 1.0.1

Update of the protection against web traps:

- Fake online banks: a typed or clicked address that imitates a bank opens a Safeer warning page with "Go back to safety", "Open the real site" and "Continue anyway (this session only)". After every page load a small script in Qt WebEngine's isolated world checks for visible password, SMS code or card fields, so a look-alike login page on any other address gets the same warning; Back from that warning skips the fake page. The warning cannot be forged by web pages: everything it shows comes from a single-use token.
- Real banks work undisturbed: Slovenian banks, their banking groups, PayPal, Revolut, N26, Wise and the pages used for logins and card payments are never blocked as ads or by phishing entries. Confirmed malware on a compromised server is still blocked.
- The verified, signed Safeer threat list (Ed25519) is loaded in the background instead of before the window opens and is checked for updates about 12 seconds after every start, then every 6 hours.
- YouTube and YouTube Music: the "Video paused. Continue watching?" prompt no longer appears. Its timers arrive with the player data and are moved beyond any real session before the player reads them; the confirmation fallback now always resumes the player's video, not a hover preview.

Slovensko: Posodobljena zaščita pred spletnimi pastmi. Opozorilo pred lažnimi spletnimi bankami z gumbom za pravo stran banke, prave banke delujejo nemoteno, podpisan seznam nevarnih strani pa se naloži v ozadju in ob vsakem zagonu preveri brez upočasnitve. YouTube in YouTube Music ne ustavita več predvajanja z vprašanjem »Želite nadaljevati z ogledom?«.
