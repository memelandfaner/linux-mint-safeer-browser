# Linux regression checks

Run `PYTHONPATH=. /usr/bin/python3 -m unittest discover -s tests -v` with Python GI, Soup 3, WebKitGTK 4.1 and Node installed. The tests exercise actual resolver/proxy and JavaScript functions.

Live checks on 2026-09-06 used the actual SafeerMintBrowser class in isolated temporary profiles with Quad9 enabled. BBC loaded with 69 decoded images and no reserved BBC ad slots; RTV loaded with 23 decoded images. A self-signed certificate was rejected with `Unacceptable TLS certificate`. Native WebKitGTK 2.52.6 / GStreamer 1.24.2 crashed during YouTube playback with the original aggressive media supervision; a baseline without scripts and the revised full app played successfully. The revised full-app sample had readyState 4, paused=false, currentTime 8.57 and no video error at the observation point, with no matched ad slots remaining. Observation delays are not page load benchmarks.

The ad-domain regression uses the exact reported tpc.googlesyndication.com/sodar URL and invokes the native navigation policy handler to ensure it ignores the ad frame without opening a threat dialog.

These are bounded checks, not a guarantee that all websites, videos or future ads will work. No user profile, credentials or browsing history was included in the fixtures.

Longer full-app repeat: at 70.22 seconds after navigation the media clock was 46.15 seconds, paused=false, readyState=4, error=null, with no matched ad slots. No crash occurred in that run.
