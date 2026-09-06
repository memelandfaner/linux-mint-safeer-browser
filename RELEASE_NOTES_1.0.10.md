# Safeer Linux 1.0.10

Fixes browser-side sign-in failures. New windows now use a related WebKit view and preserve their opener, postMessage callbacks, original navigation request and POST body. The page can close its login window after completion. Automatically opened unsolicited windows remain disabled.

Login, OAuth, SAML and signed links are preserved. Tracking cleanup only replays explicit GET link clicks and retains the original encoding of remaining query values. POST forms and redirects are no longer replayed as GET requests.

Cosmetic and overlay scripts skip identity-provider and verification pages, including Google accounts, ChatGPT/OpenAI authentication and Cloudflare challenges. Generic login modals and containers with interactive forms or challenge iframes are preserved. Cookies remain in the existing shared persistent context; global third-party-cookie blocking, malware checks and TLS validation remain enabled.

Validation: fifteen regression tests and the real-WebKit local login fixture. The fixture fails on 1.0.9 and passes on this release, covering same-origin and cross-origin opener callbacks with cookie separation, delayed popup navigation, POST payload, cookies, window close, preserved forms/challenges, ad removal and unsolicited popup blocking. Google/ChatGPT account sign-in still requires the user's verification; no credentials or sessions were copied and no provider security checks were bypassed.

Live ChatGPT login check exposed an additional block of the browser-generated `about:srcdoc` verification frame, leaving the page at “Just a moment…”. This internal document is now allowed while javascript:, data: and arbitrary local file navigations remain rejected.

After the srcdoc fix, a fresh-profile live check with Quad9 enabled passed the ChatGPT challenge and displayed “Get started | ChatGPT”, including “Continue with Google”, at the 22-second observation. This is not a sign-in completion or a page-load benchmark.
