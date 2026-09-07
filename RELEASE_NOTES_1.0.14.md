# Safeer Linux 1.0.14

Exclude grok.com and its subdomains, accounts.x.ai and auth.x.ai from cosmetic cleanup, overlay removal and background-tab overrides. Keep threat checks, HTTPS certificate validation and cookie protection. Use the installed WebKit's native user agent consistently rather than a fixed Safari 18 version. Add `--version` for checking which installed copy is running.

Preserve YouTube playerAds configuration, adPlayback, heartbeat and integrity data while removing adPlacements/adSlots. Tests verify original signed media URLs and opaque protocol data remain unchanged. No experimental stream edits, forced reloads, altered timers or codec changes are included.

## Verified and remaining issues

22 regression tests passed. Real WebKit fixtures preserve login UI on the exact xAI check-login URL and on Grok; the same scripts stay active on a deceptive lookalike domain. Existing popup/POST/cookie flows are checked separately.

The public xAI check-login page still returned a Cloudflare block with the corrected browser. This release does not claim to override that server-side decision or to have completed an authenticated Grok model switch.

YouTube diagnostics identified small SABR replies containing the interruption notification and a 4,000–16,000 ms next-request delay. Startup speed remains unresolved. Experimental compatibility approaches were not shipped because they did not reliably improve playback.

The user's system package was still version 1.0.6. Its code contains the exact incorrect abuse.ch C2 alert for googlesyndication reported in the screenshot. Updating only a separate source checkout does not update /usr/lib/safeer-browser; install this package to replace that old copy.

Final five-song run: Get Lucky 14.73 s; Blinding Lights 13.36 s; Shape of You 8.76 s; Hello 14.76 s; A Sky Full Of Stars 13.76 s. All five passed startup plus 32 seconds with no detected ad state, visible ad slot, media error or post-start stall. These bounded observations do not establish a guaranteed speedup or ad-free full songs. Compact results: tests/results/startup-1.0.14.json.

The corrected browser also reached the Google Accounts sign-in page from ChatGPT (no credentials entered). The isolated four-flow popup/POST/cookie/challenge test passed.
