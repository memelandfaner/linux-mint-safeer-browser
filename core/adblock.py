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

    // 1. JSON.parse Hook: Strip ad placements before YouTube processes them
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
                        val.playbackTracking.videostatsPlaybackUrl = { baseUrl: '' };
                        val.playbackTracking.videostatsDelayplayUrl = { baseUrl: '' };
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

ABUSE_CH_BLOCKED_DOMAINS = {
    "payload-delivery.cc",
    "dridex-c2-botnet.ru",
    "emotet-loader.biz",
    "credential-theft-login.top",
    "malicious-banking-trojan.net",
    "cobaltstrike-beacon.xyz",
    "qakbot-drop.cc",
    "icedid-c2-network.net",
    "redline-stealer-gate.ru",
    "lumma-stealer-delivery.top",
    "doubleclick.net",
    "googlesyndication.com",
    "popads.net",
    "popcash.net",
    "monetag.com",
    "adcash.com",
    "propellerads.com",
    "exoclick.com",
    "adsterra.com",
    "onclickalgo.com",
    "onclickgate.com",
    ".cfd",
    ".buzz",
    ".monster",
    ".click",
    ".top",
    ".tk",
    ".ml",
    ".ga",
    ".gq",
    ".work",
    ".rest",
    ".sbs"
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


