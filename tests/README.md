# Linux regression checks

Run `PYTHONPATH=. /usr/bin/python3 -m unittest discover -s tests -v` with Python GI, Soup 3, WebKitGTK 4.1 and Node installed. The tests exercise actual resolver/proxy and JavaScript functions.

Live checks on 2026-09-06 used the actual SafeerMintBrowser class in isolated temporary profiles with Quad9 enabled. BBC loaded with 69 decoded images and no reserved BBC ad slots; RTV loaded with 23 decoded images. A self-signed certificate was rejected with `Unacceptable TLS certificate`. Native WebKitGTK 2.52.6 / GStreamer 1.24.2 crashed during YouTube playback with the original aggressive media supervision; a baseline without scripts and the revised full app played successfully. The revised full-app sample had readyState 4, paused=false, currentTime 8.57 and no video error at the observation point, with no matched ad slots remaining. Observation delays are not page load benchmarks.

The ad-domain regression uses the exact reported tpc.googlesyndication.com/sodar URL and invokes the native navigation policy handler to ensure it ignores the ad frame without opening a threat dialog.

These are bounded checks, not a guarantee that all websites, videos or future ads will work. No user profile, credentials or browsing history was included in the fixtures.

Longer full-app repeat: at 70.22 seconds after navigation the media clock was 46.15 seconds, paused=false, readyState=4, error=null, with no matched ad slots. No crash occurred in that run.

1.0.9 startup regression: the earlier isolated profiles omitted enabled sidebar integrations. Added a GTK test with enabled/disabled saved integrations, two tooltip branches, active styling, click dispatch and repeated dock rebuild. Run on a graphical display to execute this test (otherwise it is skipped). All ten tests passed on the desktop, and the installed launcher started with the existing user profile without clearing its data.

1.0.10 login regression: `PYTHONPATH=. /usr/bin/python3 tests/login_runtime.py` opens an isolated test profile and local fixture server. Version 1.0.9 returned no opener callbacks and removed both the iframe challenge and generic login modal. The fix passed four callback flows (direct popup, cross-origin popup with cookie separation, initially blank popup navigated later, named-window POST with its original query and body). First-party cookies remained available, script close returned to one tab, challenge/modal remained, the marked ad slot was removed, and a delayed unsolicited popup was blocked. No real login credentials are used. The unit suite has fifteen tests including signed-URL preservation, POST/redirect policy and threat blocking on OAuth-shaped URLs.

Live ChatGPT login check exposed an additional block of the browser-generated `about:srcdoc` verification frame, leaving the page at “Just a moment…”. This internal document is now allowed while javascript:, data: and arbitrary local file navigations remain rejected.

After the srcdoc fix, a fresh-profile live check with Quad9 enabled passed the ChatGPT challenge and displayed “Get started | ChatGPT”, including “Continue with Google”, at the 22-second observation. This is not a sign-in completion or a page-load benchmark.

Final public sign-in check: after waiting for the ChatGPT page to finish initializing, “Continue with Google” reached accounts.google.com with the title “Sign in - Google Accounts” and the prompt “Sign in to continue to OpenAI / Email or phone”. This used a new isolated profile with Quad9. No email, password or verification code was entered; authenticated account access remains for the user to confirm.

1.0.11 default browser regression: the installed xdg-settings fix_local_desktop_file sleeps four seconds and appends MimeType after the last Desktop Action. The old UI timeout was three seconds. Added isolated native GIO registration tests checking all four web associations, malformed desktop group repair, action/localized-label preservation, idempotent repeat registration, unrelated PDF defaults and exact-ID/partial-state detection. Eighteen tests passed. The actual UI handler returned True in 0.033 seconds and xdg-settings check returned yes on the user's Cinnamon desktop.

1.0.12: run `tests/network_runtime.py` for home-page DuckDuckGo recovery after an injected TLS EOF, or add `--permanent` to verify exactly one Safeer retry and a readable warning page. Run `tests/youtube_live.py` for the ten-video playback/ad run; observations are committed under tests/results/. See RELEASE_NOTES_1.0.12.md for scope and limits.

1.0.13: `tests/youtube_startup.py /tmp/startup-results.json` measures five songs without repeated play calls. See RELEASE_NOTES_1.0.13.md for timings and limits.
