# Safeer Linux 1.0.8

DNS now uses libsoup 3 with HTTP/2, bounded responses, certificate validation and HTTPS-only endpoints. Public target lookup failures no longer fall back silently to ordinary DNS; the resolver endpoint itself still needs system DNS bootstrap. Duplicate lookups are coalesced and failures briefly cached.

The local proxy preserves CONNECT payload received with its headers, strips proxy credentials from forwarded HTTP requests, bounds concurrency and closes active connections when stopped.

YouTube preconnect no longer targets bare googlevideo.com, whose certificate does not match that host. A permanently present ad module is no longer treated as proof that a song is an ad. Aggressive automatic playback calls, ad seeking and rate changes were removed after reproducing native GStreamer crashes; the player now owns media timing and normal controls. Cosmetic filtering includes BBC reserved slots and YouTube ad slot containers.

Validation: nine regression tests covering concurrent tunnel payload, HTTP request bodies, DNS failure without plaintext fallback, cached/coalesced failures, and short-song/ad media state, ad/threat classification and silent ad frame navigation. Live DNS queries passed for Quad9, Cloudflare, Google and AdGuard. Desktop WebKit runtime checks are recorded in tests/README.md.

Advertising and tracker domains are classified separately from malware/phishing entries. In particular, tpc.googlesyndication.com is blocked silently as advertising rather than shown in a botnet warning. Genuine threat matches retain their warning, now worded as a local blocklist match rather than claiming every match is an abuse.ch-confirmed C2 server.
