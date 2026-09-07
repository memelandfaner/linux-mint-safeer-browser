# Relevant prior knowledge reviewed

Reviewed Gemini skills safeer-threat-and-adblock-engine, linux-mint-desktop-app-engineering and web-debugging-and-devtools, plus README.md/GEMINI.md in the user's novo-znanje project. That folder is an Android TV project; its hardware-specific rules are not Linux settings.

Useful principles: one authoritative playback action, generation-aware delayed work, preserve pause/seek state, do not infer playback failure from missing messages, do not repeatedly force volume, keep credentials out of source, and validate on the actual rendering engine.

Observed corrections to older guidance: ad domains are not evidence of botnets; removal of all player metadata is too broad; playback integrity/heartbeat data must survive; native and cosmetic threat counters must not be conflated. No claim of universal zero-ad or instantaneous playback is justified by short samples. The attached external review is a list of findings to verify, not authorization to disable the user's requested ad protection or to modify unrelated TV/router projects.

Remaining review work includes limiting the JavaScript bridge, download filename validation, and replacing placeholder threat data with maintained verified feeds. These are not represented as completed in 1.0.14.
