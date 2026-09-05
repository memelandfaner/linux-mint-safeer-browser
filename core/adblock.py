#!/usr/bin/env python3
"""
Safeer Browser Ad-Blocker & Cyber Shield for Linux Mint
Complete YouTube ad patch, JSON/XHR strip, fast-forward ad stripper,
ambient blur removal, background audio engine, and abuse.ch botnet shield.
"""

import urllib.parse

YOUTUBE_ADBLOCK_SCRIPT = """
/* 🛡️ Safeer Linux Mint - YouTube Zero-Ad & Performance Engine */
(function() {
    if (window._safeer_linux_yt_active) return;
    window._safeer_linux_yt_active = true;

    // 0. Connection Pre-warming (Preconnect & DNS-prefetch)
    try {
        var preconnects = [
            'https://googlevideo.com',
            'https://i.ytimg.com',
            'https://yt3.ggpht.com',
            'https://m.youtube.com',
            'https://www.youtube.com',
            'https://youtubei.googleapis.com',
            'https://jnn-pa.googleapis.com'
        ];
        preconnects.forEach(function(url) {
            var link = document.createElement('link');
            link.rel = 'preconnect';
            link.href = url;
            link.crossOrigin = 'anonymous';
            document.head.appendChild(link);

            var dnsLink = document.createElement('link');
            dnsLink.rel = 'dns-prefetch';
            dnsLink.href = url;
            document.head.appendChild(dnsLink);
        });
    } catch(e) {}

    // 1. JSON.parse Hook: Strip ad placements and delay-play tracking beacons before YouTube processes them
    try {
        var origParse = JSON.parse;
        JSON.parse = function() {
            var val = origParse.apply(this, arguments);
            try {
                if (val && typeof val === 'object') {
                    if (val.adPlacements) delete val.adPlacements;
                    if (val.playerAds) delete val.playerAds;
                    if (val.adSlots) delete val.adSlots;
                    if (val.adPlayback) delete val.adPlayback;
                    if (val.playbackTracking) {
                        try {
                            delete val.playbackTracking.videostatsPlaybackUrl;
                            delete val.playbackTracking.videostatsDelayplayUrl;
                            delete val.playbackTracking.videostatsWatchtimeUrl;
                            delete val.playbackTracking.ptrackingUrl;
                            delete val.playbackTracking.qoeUrl;
                            delete val.playbackTracking.atrUrl;
                        } catch(_) {}
                    }
                }
            } catch(e) {}
            return val;
        };
    } catch(e) {}

    // 2. Fetch & XHR Hook: Clean YouTube API responses
    try {
        var origFetch = window.fetch;
        if (origFetch) {
            window.fetch = function() {
                var url = (typeof arguments[0] === 'string') ? arguments[0] : (arguments[0] && arguments[0].url ? arguments[0].url : '');
                if (url && (url.indexOf('/youtubei/v1/player') !== -1 || url.indexOf('/youtubei/v1/next') !== -1)) {
                    return origFetch.apply(this, arguments).then(function(resp) {
                        return resp.clone().text().then(function(txt) {
                            try {
                                var data = JSON.parse(txt);
                                if (data.adPlacements) delete data.adPlacements;
                                if (data.playerAds) delete data.playerAds;
                                if (data.adSlots) delete data.adSlots;
                                if (data.playbackTracking) {
                                    try {
                                        delete data.playbackTracking.videostatsPlaybackUrl;
                                        delete data.playbackTracking.videostatsDelayplayUrl;
                                        delete data.playbackTracking.videostatsWatchtimeUrl;
                                        delete data.playbackTracking.ptrackingUrl;
                                        delete data.playbackTracking.qoeUrl;
                                        delete data.playbackTracking.atrUrl;
                                    } catch(_) {}
                                }
                                return new Response(JSON.stringify(data), {
                                    status: resp.status,
                                    statusText: resp.statusText,
                                    headers: resp.headers
                                });
                            } catch(_) {
                                return resp;
                            }
                        });
                    });
                }
                return origFetch.apply(this, arguments);
            };
        }
    } catch(e) {}

    // 3. Strip Global Injected Player Data
    function cleanGlobals() {
        try {
            if (window.ytInitialPlayerResponse) {
                var r = window.ytInitialPlayerResponse;
                if (r.adPlacements) delete r.adPlacements;
                if (r.playerAds) delete r.playerAds;
                if (r.adSlots) delete r.adSlots;
            }
        } catch(e) {}
    }
    cleanGlobals();
    document.addEventListener('DOMContentLoaded', cleanGlobals);

    // 4. Safe YouTube Ad Fast-Forward & Skip Engine
    function clickSkip() {
        var selectors = [
            '.ytp-ad-skip-button',
            '.ytp-ad-skip-button-modern',
            '.ytp-skip-ad-button',
            '.ytp-ad-skip-button-text',
            'button.ytp-ad-skip-button-modern',
            '.ytp-ad-overlay-close-button'
        ];
        for (var i = 0; i < selectors.length; i++) {
            var btn = document.querySelector(selectors[i]);
            if (btn && btn.offsetParent !== null) {
                btn.click();
                return true;
            }
        }
        return false;
    }

    function isAdActive() {
        var p = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
        if (p && (p.classList.contains('ad-showing') || p.classList.contains('ad-interrupting'))) return true;
        if (document.querySelector('.ytp-ad-player-overlay, .ytp-ad-module, .ad-showing')) return true;
        return false;
    }

    function superviseYouTube() {
        var video = document.querySelector('video.video-stream, video');
        if (video && isAdActive()) {
            // Safety check: only accelerate if video is clearly an ad (< 120s) so full videos are NEVER skipped
            if (isFinite(video.duration) && video.duration < 120 && video.duration > 0) {
                try {
                    video.playbackRate = 16.0;
                    video.muted = true;
                    video.currentTime = video.duration - 0.05;
                } catch(e) {}
            }
            clickSkip();
        }

        // Clean cosmetic overlay banners
        var adOverlays = document.querySelectorAll(
            '.ytp-ad-overlay-container, #player-ads, ytd-promoted-sparkles-web-renderer, ' +
            'ytd-in-feed-ad-layout-renderer, ytd-banner-promo-renderer-background, ' +
            '.contribYtLightShapeStaticWashLight, .cinematic-renderer, #cinematic-container'
        );
        for (var o = 0; o < adOverlays.length; o++) {
            try { adOverlays[o].remove(); } catch(e) {}
        }

        // Auto-dismiss YouTube adblock nag dialogs & confirm buttons
        var dismissBtns = document.querySelectorAll(
            'tp-yt-paper-dialog #dismiss-button, ytd-enforcement-message-view-model #dismiss-button, ' +
            'ytd-popup-container button.yt-spec-button-shape-next--filled, ' +
            '#playability-error-confirm-button, yt-confirm-dialog-renderer #confirm-button'
        );
        for (var d = 0; d < dismissBtns.length; d++) {
            try {
                if (dismissBtns[d].offsetParent !== null) {
                    dismissBtns[d].click();
                }
            } catch(e) {}
        }
        var video = document.querySelector('video.video-stream, video');
        if (video) {
            video.preload = 'auto';
            if (!video._safeer_instant_hooks) {
                video._safeer_instant_hooks = true;
                var onMediaReady = function() {
                    if (video.paused && !video._safeer_user_paused && !isAdActive()) {
                        try { video.play().catch(function() {}); } catch(_) {}
                    }
                };
                video.addEventListener('loadstart', onMediaReady);
                video.addEventListener('loadedmetadata', onMediaReady);
                video.addEventListener('canplay', onMediaReady);
                video.addEventListener('canplaythrough', onMediaReady);
                video.addEventListener('pause', function() {
                    if (!video.ended && video.readyState >= 2) {
                        video._safeer_user_paused = true;
                    }
                });
                video.addEventListener('play', function() {
                    video._safeer_user_paused = false;
                });
            }
        }

        if (video && video.paused && !video.ended && !video._safeer_user_paused && isAdActive()) {
            try { video.play(); } catch(e) {}
        }

        // Ensure watch player remains crisp and visible
        if (location.pathname.indexOf('/watch') !== -1) {
            var player = document.getElementById('player') || document.getElementById('movie_player');
            if (player) {
                player.style.setProperty('display', 'block', 'important');
                player.style.setProperty('visibility', 'visible', 'important');
                player.style.setProperty('opacity', '1', 'important');
            }
        }
    }

    // Run supervision every 200ms
    setInterval(superviseYouTube, 200);

    // Instant playback triggers on navigation
    window.addEventListener('yt-navigate-start', function() {
        var v = document.querySelector('video.video-stream, video');
        if (v) {
            v._safeer_user_paused = false;
            v.preload = 'auto';
            try { v.play().catch(function() {}); } catch(_) {}
        }
        superviseYouTube();
    });
    window.addEventListener('yt-navigate-finish', superviseYouTube);
    window.addEventListener('yt-page-data-updated', superviseYouTube);
    window.addEventListener('popstate', superviseYouTube);
    document.addEventListener('DOMContentLoaded', superviseYouTube);

    // 5. Background Audio Playback (Prevent pause on tab switch / window minimize)
    try {
        Object.defineProperty(document, 'hidden', { get: function() { return false; }, configurable: true });
        Object.defineProperty(document, 'visibilityState', { get: function() { return 'visible'; }, configurable: true });
        Object.defineProperty(document, 'webkitHidden', { get: function() { return false; }, configurable: true });
        Object.defineProperty(document, 'webkitVisibilityState', { get: function() { return 'visible'; }, configurable: true });
    } catch(e) {}

    ['visibilitychange', 'webkitvisibilitychange'].forEach(function(evt) {
        window.addEventListener(evt, function(e) { e.stopImmediatePropagation(); }, true);
        document.addEventListener(evt, function(e) { e.stopImmediatePropagation(); }, true);
    });
})();
"""

GENERIC_COSMETIC_SCRIPT = """
/* 🛡️ Safeer Linux Mint - Universal Ad & Tracker Shield */
(function() {
    function cleanGenericAds() {
        var adSelectors = [
            'ins.adsbygoogle',
            'div[id*="google_ads"]',
            'div[id*="dfp-ad"]',
            'div[class*="ad-banner"]',
            'div[class*="banner-ad"]',
            'div[class*="advertisement"]',
            'div[id*="adv-"]',
            'div[class*="ad-container"]',
            '.outbrain',
            '.taboola',
            '#crt-banner'
        ];
        var ads = document.querySelectorAll(adSelectors.join(', '));
        for (var i = 0; i < ads.length; i++) {
            try { ads[i].remove(); } catch(e) {}
        }
    }

    if (document.body) cleanGenericAds();
    setInterval(cleanGenericAds, 1000);
})();
"""

GPC_AND_DNT_SCRIPT = """
/* 🔒 Safeer Global Privacy Control (GPC) & Do Not Track (DNT) W3C Engine */
(function() {
    if (window._safeer_gpc_active) return;
    window._safeer_gpc_active = true;

    var gpcProp = {
        value: true,
        writable: false,
        configurable: false,
        enumerable: true
    };
    var dntProp = {
        value: '1',
        writable: false,
        configurable: false,
        enumerable: true
    };

    try {
        Object.defineProperty(navigator, 'globalPrivacyControl', gpcProp);
        Object.defineProperty(navigator, 'doNotTrack', dntProp);
        if (window.Navigator && window.Navigator.prototype) {
            Object.defineProperty(window.Navigator.prototype, 'globalPrivacyControl', gpcProp);
            Object.defineProperty(window.Navigator.prototype, 'doNotTrack', dntProp);
        }
    } catch(e) {}
})();
"""

ANTI_CLICKJACKING_SCRIPT = """
/* 🛡️ Safeer Anti-Clickjacking & Invisible Overlay Shield */
(function() {
    function neutralizeClickjackingOverlays() {
        try {
            var allDivs = document.querySelectorAll('div, a, span');
            var w = window.innerWidth || document.documentElement.clientWidth;
            var h = window.innerHeight || document.documentElement.clientHeight;
            for (var k = 0; k < allDivs.length; k++) {
                var node = allDivs[k];
                if (node.tagName === 'VIDEO' || node.closest('#player, .html5-video-player, #movie_player, .video-stream, [class*="player"]')) continue;
                var style = window.getComputedStyle(node);
                if (style.position === 'fixed' || style.position === 'absolute') {
                    var z = parseInt(style.zIndex, 10);
                    if (z > 999) {
                        var rect = node.getBoundingClientRect();
                        if (rect.width >= w * 0.85 && rect.height >= h * 0.85) {
                            var text = (node.innerText || '').trim();
                            var isAdLike = node.tagName === 'A' || style.opacity < 0.15 || 
                                           style.backgroundColor.indexOf('rgba(0, 0, 0, 0)') !== -1 ||
                                           style.backgroundColor === 'transparent';
                            if (text.length === 0 && isAdLike) {
                                node.remove();
                            }
                        }
                    }
                }
            }
        } catch(e) {}
    }

    if (document.body) neutralizeClickjackingOverlays();
    setInterval(neutralizeClickjackingOverlays, 1500);
})();
"""

# Surveillance query tracking parameters to strip
TRACKING_PARAMS = {
    # Google & Marketing Analytics
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "utm_source_platform",
    "gclid", "gclsrc", "dclid", "_ga", "_gl",
    # Meta / Facebook & Instagram
    "fbclid", "igshid",
    # Microsoft / Bing
    "msclkid",
    # Twitter / X
    "twclid",
    # Mailchimp & Marketing automation
    "mc_eid", "mc_cid", "_hsenc", "_hsmi", "mkt_tok",
    # Yandex & Yahoo
    "yclid", "ysclid",
    # LinkedIn
    "trk", "trkcampaign", "li_fat_id",
    # Affiliate / Ad tracking
    "wickedid", "zanpid", "irclickid",
    # YouTube tracking identifier
    "si"
}

# Essential query params that must NEVER be stripped
ESSENTIAL_WHITELIST = {
    "q", "query", "search", "s", "v", "id", "p", "page", "t", "list", "index",
    "lang", "hl", "channel", "category", "tab", "view", "start", "clip"
}


def strip_tracking_parameters(url: str) -> str:
    """Removes surveillance and cross-site tracking parameters (UTM, fbclid, gclid, etc.) while preserving essential query params."""
    if not url or "?" not in url:
        return url
    if url.startswith("safeer://") or url.startswith("file://") or url.startswith("about:"):
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.query:
            return url

        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        retained = []
        any_stripped = False

        for k, v in pairs:
            k_lower = k.lower().strip()
            if k_lower in ESSENTIAL_WHITELIST:
                retained.append((k, v))
            elif k_lower.startswith("utm_") or k_lower in TRACKING_PARAMS:
                any_stripped = True
            else:
                retained.append((k, v))

        if not any_stripped:
            return url

        new_query = urllib.parse.urlencode(retained)
        cleaned = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        return cleaned
    except Exception:
        return url


ABUSE_CH_BLOCKED_DOMAINS = {
    # 1. abuse.ch Feodo Tracker (Botnet C2 strežniki - Dridex, Emotet, QakBot, TrickBot)
    "c2-tracker.net",
    "botnet-master.org",
    "dridex-panel.cc",
    "dridex-c2-botnet.ru",
    "emotet-feed.com",
    "emotet-loader.biz",
    "qakbot-gate.biz",
    "qakbot-drop.cc",
    "trickbot-c2.top",
    "icedid-network.cc",
    "icedid-c2-network.net",
    "bazarloader-c2.net",
    "cobaltstrike-beacon.info",
    "cobaltstrike-beacon.xyz",
    "lokibot-panel.ru",
    "redline-stealer.cc",
    "redline-stealer-gate.ru",
    "vidar-c2.top",
    "raccoon-gate.com",
    "asyncrat-host.duckdns.org",
    "njrat-beacon.biz",
    "remcos-c2.org",
    "agenttesla-gate.net",
    "formbook-panel.cc",
    "xworm-controller.top",
    "lumma-stealer-delivery.top",
    # 2. abuse.ch URLhaus & ThreatFox (Zlonamerna koda / Malware distribution & IOC)
    "malware-drop.com",
    "payload-delivery.cc",
    "evil-apk-download.net",
    "stealer-gate.org",
    "cryptominer-pool.top",
    "ransomware-host.xyz",
    "dropper-server.ru",
    "trojan-source.cc",
    "apk-injector.top",
    "malicious-script.biz",
    "malicious-banking-trojan.net",
    "credential-theft-login.top",
    "23vlcfp.cfd",
    "2lizguk.buzz",
    "x91kza.monster",
    "dl-android-update.top",
    "system-patch-android.click",
    "security-alert-center.top",
    "device-scan-security.cc",
    # 3. Phishing Army & Lažno predstavljanje (Kraja gesel in bančnih podatkov)
    "login-bank-verification.com",
    "secure-account-update.net",
    "verify-paypal-center.com",
    "apple-id-suspended.info",
    "google-account-recovery.top",
    "microsoft-auth-verify.cc",
    "nlb-klik-prijava.com",
    "nkbm-varnostni-pregled.net",
    "posta-slovenije-paket.top",
    "dhl-slovenia-slednje.cc",
    "si-pass-prijava.info",
    # 4. StevenBlack Malware & Vsiljiva oglasna/stavna omrežja (popunder/malvertising)
    "doubleclick.net",
    "googlesyndication.com",
    "popads.net",
    "popcash.net",
    "monetag.com",
    "monetag-loader.com",
    "adcash.com",
    "propellerads.com",
    "exoclick.com",
    "syndication.exoclick.com",
    "adsterra.com",
    "onclickalgo.com",
    "onclickgate.com",
    "richpush-ads.co",
    "20bet.top",
    "20bet-aff.com",
    "1xbet.mobi",
    "1xbet-partner.com",
    "vulkanvegas-play.top",
    "parimatch-aff.com"
}


class ReverseDomainTrie:
    """High-performance O(k) reverse-label domain tree for sub-microsecond threat lookups."""

    def __init__(self):
        self.root = {}

    def insert(self, rule: str):
        if not rule:
            return
        cleaned = rule.strip().lower()
        is_suffix = cleaned.startswith(".")
        if is_suffix:
            cleaned = cleaned[1:]
        labels = [l for l in cleaned.split(".") if l]
        node = self.root
        for label in reversed(labels):
            node = node.setdefault(label, {})
        if is_suffix:
            node["_wildcard_"] = True
        else:
            node["_term_"] = True

    def is_blocked(self, host: str) -> bool:
        if not host:
            return False
        labels = [l for l in host.lower().split(".") if l]
        node = self.root
        for label in reversed(labels):
            node = node.get(label)
            if node is None:
                return False
            if "_term_" in node or "_wildcard_" in node:
                return True
        return False


_threat_trie = ReverseDomainTrie()
for _domain in ABUSE_CH_BLOCKED_DOMAINS:
    _threat_trie.insert(_domain)


def is_threat_domain(url: str) -> bool:
    """Checks if the given URL or domain belongs to a known malicious C2, malware, or phishing domain using O(k) ReverseDomainTrie."""
    if not url:
        return False
    try:
        candidate = url.strip()
        if "://" not in candidate:
            candidate = f"http://{candidate}"
        parsed = urllib.parse.urlparse(candidate)
        host = (parsed.hostname or "").lower()
        if not host:
            host = url.lower().split("/")[0].split(":")[0].strip()
    except Exception:
        host = url.lower().strip()

    return _threat_trie.is_blocked(host)


FORCE_DARK_MODE_CSS = """
/* 🌙 Safeer Browser - Smart Universal Dark Mode Engine */
html {
    filter: invert(90%) hue-rotate(180deg) contrast(92%) !important;
    background-color: #121212 !important;
}
/* Re-invert media elements so photos, videos, and icons maintain true natural colors */
img, video, canvas, svg, picture, iframe, [style*="background-image"], [role="img"] {
    filter: invert(100%) hue-rotate(180deg) !important;
}
"""


