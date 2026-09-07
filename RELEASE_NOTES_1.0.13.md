# Safeer Linux 1.0.13

Use WebKit's WEB_BROWSER resource cache instead of the local-document cache. Avoid parsing/stringifying unrelated YouTube JSON and periodically scanning every YouTube element for generic overlays. Keep dedicated YouTube ad filtering, general network ad rules, threat blocking, encrypted DNS and normal TLS certificate validation. Install focused connection hints reliably at document start without speculative video downloads.

## Validation

22 unit/regression tests pass, including initial player data, fetch/XHR ad removal, serialized player_response, exact preservation of unchanged JSON, login URLs, default browser associations, threat checks and proxy transport.

Five real songs were measured before and after with the actual GTK/WebKit application, isolated profiles, Quad9 and shields enabled: Get Lucky, Blinding Lights, Shape of You, Hello, A Sky Full Of Stars. Each passed startup and 32 seconds of subsequent playback with zero detected ad states, visible ad slots, media errors or post-start buffering/pause samples. One play request per song, with no repeated forcing, seek or quality change.

Observed first-play times before: 16.71, 19.36, 7.69, 7.43, 19.78 seconds (mean 14.19). After: 20.56, 18.87, 7.73, 7.25, 6.74 seconds (mean 12.23). Initial cookie consent is included for the first song. These sequential network runs do not establish a guaranteed speedup: the first song was slower and Blinding Lights still took about 19 seconds. The startup delay and reported interruption message are not claimed to be fully resolved. Entire songs, future ad variants and the user's signed-in session are outside this test's scope.

Reproduce: `PYTHONPATH=. /usr/bin/python3 tests/youtube_startup.py /tmp/startup-results.json`. Optional video IDs select a smaller run. `SAFEER_TEST_TRACE=1` records DNS timings and public resource paths/status only; query strings and credentials are omitted. Compact results: `tests/results/startup-1.0.13.json`.

Additional diagnostic run of Blinding Lights observed six HTTP 403 responses from a video CDN before successful playback (20.60 seconds). DNS lookups in that run took about 0.11–0.22 seconds. This is evidence of rejected media requests; it does not identify their authentication cause. No certificate, DNS or threat protection was disabled to work around them.
