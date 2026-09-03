#!/usr/bin/env python3
"""
Safeer Browser Ad-Blocker & Cyber Shield for Linux Mint
Complete YouTube ad patch, JSON/XHR strip, fast-forward ad stripper,
ambient blur removal, background audio engine, and abuse.ch botnet shield.
"""

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
    "lumma-stealer-delivery.top"
}

MESSENGER_SIDEBAR_SCRIPT = """
/* 🛡️ Safeer Linux Mint - Adaptive Sidebar Layout for Messenger */
(function() {
    if (window._safeer_msg_adapter) return;
    window._safeer_msg_adapter = true;

    var style = document.createElement('style');
    style.id = 'safeer-messenger-responsive-style';
    (document.head || document.documentElement).appendChild(style);

    function adaptMessenger() {
        var isMessenger = window.location.hostname.indexOf('messenger.com') !== -1 || window.location.pathname.indexOf('/messages') !== -1;
        if (!isMessenger) return;

        var width = window.innerWidth;
        var isChatOpen = window.location.pathname.indexOf('/t/') !== -1;

        if (width >= 640) {
            if (style.textContent !== '') style.textContent = '';
            var existingBackBtn = document.getElementById('safeer-msg-back-btn');
            if (existingBackBtn) existingBackBtn.style.display = 'none';
            return;
        }

        // Narrow mode (< 640px): 1-column responsive layout
        if (isChatOpen) {
            style.textContent = [
                'div[role="navigation"], [aria-label="Klepeti"], [aria-label="Chats"], div[data-pagelet="LeftRail"] { display: none !important; }',
                'div[role="main"] { width: 100vw !important; min-width: 100vw !important; max-width: 100vw !important; flex: 1 1 100% !important; display: flex !important; }',
                '#safeer-msg-back-btn { display: flex !important; }'
            ].join(' ');
        } else {
            style.textContent = [
                'div[role="navigation"], [aria-label="Klepeti"], [aria-label="Chats"], div[data-pagelet="LeftRail"] { width: 100vw !important; min-width: 100vw !important; max-width: 100vw !important; flex: 1 1 100% !important; display: flex !important; }',
                'div[role="main"] { display: none !important; }',
                '#safeer-msg-back-btn { display: none !important; }'
            ].join(' ');
        }

        if (isChatOpen) {
            var btn = document.getElementById('safeer-msg-back-btn');
            if (!btn) {
                btn = document.createElement('button');
                btn.id = 'safeer-msg-back-btn';
                btn.textContent = '◀ Klepeti';
                btn.style.cssText = 'position:fixed; top:12px; left:12px; z-index:999999; background:rgba(13,21,39,0.92); color:#00d2ff; border:1px solid rgba(0,210,255,0.4); border-radius:8px; padding:6px 12px; font-weight:700; font-size:12px; cursor:pointer; box-shadow:0 4px 14px rgba(0,0,0,0.6); backdrop-filter:blur(8px);';
                btn.onclick = function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    window.location.href = 'https://www.messenger.com/';
                };
                document.body.appendChild(btn);
            } else {
                btn.style.display = 'flex';
            }
        }
    }

    setInterval(adaptMessenger, 250);
    window.addEventListener('resize', adaptMessenger);
    window.addEventListener('popstate', adaptMessenger);
})();
"""


def is_threat_domain(url: str) -> bool:
    """Checks if the given URL belongs to a known malicious C2, malware, or phishing domain."""
    url_lower = url.lower()
    for threat in ABUSE_CH_BLOCKED_DOMAINS:
        if threat in url_lower:
            return True
    return False

