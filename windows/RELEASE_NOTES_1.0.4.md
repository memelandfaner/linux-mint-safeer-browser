# Safeer Browser for Windows 1.0.4

Lighter page scripts:

- The browser's periodic page scripts (anti-adblock walls, cosmetic cleanup, invisible-overlay shield) no longer poll the whole page on fixed timers: a scan waits for an idle moment, does nothing while the tab is hidden, and is scheduled from how long the last one took. The overlay shield now asks the browser for the few elements on top instead of walking every element — the same cost on a ten-node page and on a social feed with a hundred thousand nodes.
- The anti-adblock script is not injected on Facebook, Messenger and Instagram at all (they have no such walls, and their pages are the heaviest to scan).

Slovensko: Skripte za čiščenje oglasov in prekrivnih slojev ne pregledujejo več cele strani po urniku, ampak takrat, ko je brskalnik prost, in nikoli v skritih zavihkih; zaščita pred nevidnimi prekrivnimi sloji je zdaj enako hitra na ogromnih straneh (Facebook, Instagram), skripta proti zidovom za blokiranje oglasov pa se tam sploh ne vbrizga.
