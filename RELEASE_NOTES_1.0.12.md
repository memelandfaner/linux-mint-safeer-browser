# Safeer Linux 1.0.12

Fixes the reported DuckDuckGo connection failure and YouTube in-player advertisements.

YouTube's initial page can assign player data directly, before a JSON.parse hook or DOM-ready cleanup runs. The filter now cleans the assignment immediately, including serialized player config, fetch/Response.json and XMLHttpRequest responses. It preserves signed media URLs and playback metadata. No media seeking, forced playback speed, TLS bypass or account data copying is used by the ad blocker.

DuckDuckGo intermittently closed TLS connections with G_TLS_ERROR_NOT_TLS and “The TLS connection was non-properly terminated”. Safeer now makes at most one retry for an eligible DuckDuckGo search GET. Forms, account callbacks, certificate errors and newer user navigations are excluded. Persistent failures show a readable error page and warning icon, with a retry button for GET requests. Invalid certificates remain blocked.

Validation:
- 22 regression tests passed, covering initial/fetch/XHR ad data, media preservation, bounded recovery, navigation cancellation, login policy, threats, proxy/DNS, startup and default-browser registration.
- The actual app recovered from the exact reported TLS error injected into the local CONNECT tunnel, including a search from the home-page DuckDuckGo selector. A persistent interruption stopped after one Safeer retry and displayed the error page.
- Live self-signed.badssl.com check was rejected with the certificate warning page; no exception was created.
- The login runtime retained all four popup/POST/cookie flows, verification iframe and login form, while removing the marked ad slot and blocking an unsolicited popup.
- Ten public YouTube videos each played from the beginning and after a seek, with 18+ seconds of initial playback and 20+ seconds after the seek. All ten had advancing content, readyState 4, no media error, no visible ad controls or slots, and no sampled active ad. Final counters recorded 520 removed ad fields. These are field-removal counts, not 520 individual ads.
- Results and one-second observations: tests/results/youtube-1.0.12.json. Video IDs: RQUgq9pqmII, 5NV6Rdv1a3I, dQw4w9WgXcQ, 4NRXx6U8ABQ, JGwWNGJdvx8, YQHsXMglC9A, 9bZkp7q19f0, OPf0YbXqDm0, nfWlot6h_JM, VPRjCeoBqrI.

The ten-video run used an isolated, signed-out profile with Quad9 on the actual Linux desktop. It samples starts and mid-video seeks, not every minute of every video. Future YouTube experiments, personalized ad variants and service outages can require further changes.
