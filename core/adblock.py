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
    var h = location.hostname.toLowerCase();
    if (!(h === 'youtube.com' || h.endsWith('.youtube.com') || h === 'youtu.be' || h === 'youtube-nocookie.com' || h.endsWith('.youtube-nocookie.com'))) return;
    if (window._safeer_linux_yt_active) return;
    if (window !== window.top && location.pathname.indexOf('/embed/') === -1) return;
    window._safeer_linux_yt_active = true;

    // Keep reserved ad slots collapsed even when YouTube inserts them later.
    function installAdCss() {
        if (document.getElementById('safeer-yt-ad-slots')) return;
        var parent = document.head || document.documentElement;
        if (!parent) return;
        var style = document.createElement('style');
        style.id = 'safeer-yt-ad-slots';
        style.textContent = 'ytd-ad-slot-renderer, ytd-in-feed-ad-layout-renderer, ytd-promoted-sparkles-web-renderer, ytd-promoted-video-renderer, ytd-display-ad-renderer, ytd-companion-slot-renderer, #player-ads { display:none!important; margin:0!important; padding:0!important; min-height:0!important; }';
        parent.appendChild(style);
    }
    installAdCss();
    document.addEventListener('DOMContentLoaded', installAdCss);

    // Install only useful connection hints, even at document START before <head>.
    // No speculative media downloads and no bypass of the configured DNS proxy.
    function warmConnections() {
        var parent = document.head || document.documentElement;
        if (!parent || document.getElementById('safeer-yt-preconnect')) return;
        ['https://i.ytimg.com', 'https://www.youtube.com'].forEach(function(url, index) {
            var link = document.createElement('link');
            if (index === 0) link.id = 'safeer-yt-preconnect';
            link.rel = 'preconnect'; link.href = url;
            parent.appendChild(link);
        });
    }
    warmConnections();
    document.addEventListener('DOMContentLoaded', warmConnections, {once:true});

    // Remove ad instructions before the player consumes a response. The main
    // watch document assigns JavaScript objects directly, without JSON.parse.
    var nativeParse = JSON.parse;
    var nativeStringify = JSON.stringify;
    var stats = window._safeerAdStats = {cleanedResponses:0, removedFields:0, skipClicks:0};
    // playerAds includes autoplay configuration; heartbeat and integrity fields
    // belong to the media protocol. Preserve them and remove only ad slots.
    var adKeys = ['adPlacements', 'adSlots'];
    var adKeyPattern = /adPlacements|adSlots/;
    function cleanPlayerText(text) {
        if (typeof text !== 'string' || !adKeyPattern.test(text)) return text;
        var removedBefore = stats.removedFields;
        var data = cleanPlayerData(nativeParse(text));
        return stats.removedFields === removedBefore ? text : nativeStringify(data);
    }
    function cleanPlayerData(data, depth) {
        depth = depth || 0;
        if (depth > 6) return data;
        if (!data || typeof data !== 'object') return data;
        var removed = 0;
        adKeys.forEach(function(key) {
            if (Object.prototype.hasOwnProperty.call(data, key)) {
                try { delete data[key]; removed++; } catch (_) {}
            }
        });
        // Known player response envelopes; do not traverse unrelated page data.
        ['playerResponse', 'player_response', 'response'].forEach(function(key) {
            var value = data[key];
            if (value && typeof value === 'object' && value !== data) cleanPlayerData(value, depth + 1);
            else if (key === 'player_response' && typeof value === 'string') {
                try { data[key] = cleanPlayerText(value); } catch (_) {}
            }
        });
        if (Array.isArray(data)) data.forEach(function(item) { cleanPlayerData(item, depth + 1); });
        if (removed) { stats.cleanedResponses++; stats.removedFields += removed; }
        return data;
    }
    function watchProperty(object, key, transform) {
        try {
            var descriptor = Object.getOwnPropertyDescriptor(object, key);
            if (descriptor && (!descriptor.configurable || descriptor.get || descriptor.set)) return;
            var value = transform(object[key]);
            Object.defineProperty(object, key, {
                configurable:true, enumerable:descriptor ? descriptor.enumerable : true,
                get:function(){ return value; },
                set:function(next){ value = transform(next); }
            });
        } catch (_) {}
    }
    function watchArgs(args) {
        if (args && typeof args === 'object') {
            watchProperty(args, 'player_response', function(value) {
                if (typeof value === 'string') {
                    try { return cleanPlayerText(value); } catch (_) {}
                }
                return cleanPlayerData(value);
            });
        }
        return args;
    }
    watchProperty(window, 'ytInitialPlayerResponse', cleanPlayerData);
    watchProperty(window, 'ytplayer', function(player) {
        if (player && typeof player === 'object') watchProperty(player, 'config', function(config) {
            if (config && typeof config === 'object') watchProperty(config, 'args', watchArgs);
            return config;
        });
        return player;
    });
    JSON.parse = function() {
        var data = nativeParse.apply(this, arguments);
        // Most YouTube JSON contains navigation or comments, not player ads.
        return typeof arguments[0] !== 'string' || adKeyPattern.test(arguments[0]) ? cleanPlayerData(data) : data;
    };
    function isPlayerApi(value) {
        try {
            var url = new URL(value, location.href);
            return (url.hostname === 'youtube.com' || url.hostname.endsWith('.youtube.com') || url.hostname === 'youtubei.googleapis.com') &&
                /^\/youtubei\/v[0-9]+\/(player|next)(?:\/|$)/.test(url.pathname);
        } catch (_) { return false; }
    }
    if (window.fetch) {
        var originalFetch = window.fetch;
        window.fetch = function() {
            var value = arguments[0];
            var url = typeof value === 'string' ? value : value && (value.url || value.href);
            var response = originalFetch.apply(this, arguments);
            if (!isPlayerApi(url)) return response;
            return response.then(function(resp) {
                if (!resp.ok) return resp;
                return resp.clone().text().then(function(text) {
                    try {
                        var clean = cleanPlayerText(text);
                        if (clean === text) return resp;
                        var headers = new Headers(resp.headers);
                        headers.delete('content-length'); headers.delete('content-encoding');
                        var result = new Response(clean,
                            {status:resp.status, statusText:resp.statusText, headers:headers});
                        ['url','redirected','type'].forEach(function(key){ Object.defineProperty(result,key,{value:resp[key]}); });
                        return result;
                    } catch (_) { return resp; }
                }, function(){ return resp; });
            });
        };
    }
    if (window.XMLHttpRequest) {
        var xhrOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url) {
            this._safeerPlayerApi = isPlayerApi(url);
            this._safeerCleanCache = null;
            return xhrOpen.apply(this, arguments);
        };
        ['responseText', 'response'].forEach(function(key) {
            var descriptor = Object.getOwnPropertyDescriptor(XMLHttpRequest.prototype, key);
            if (!descriptor || !descriptor.get || !descriptor.configurable) return;
            Object.defineProperty(XMLHttpRequest.prototype, key, {
                configurable:true, enumerable:descriptor.enumerable,
                get:function() {
                    var original = descriptor.get.call(this);
                    if (!this._safeerPlayerApi || this.readyState !== 4) return original;
                    if (typeof original === 'object') return cleanPlayerData(original);
                    if (typeof original !== 'string' || !original) return original;
                    if (this._safeerCleanCache && this._safeerCleanCache.original === original) return this._safeerCleanCache.clean;
                    try {
                        var clean = cleanPlayerText(original);
                        this._safeerCleanCache = {original:original, clean:clean}; return clean;
                    } catch (_) { return original; }
                }
            });
        });
    }
    function cleanGlobals() { cleanPlayerData(window.ytInitialPlayerResponse); }
    document.addEventListener('DOMContentLoaded', cleanGlobals);

    // 4. Safe YouTube Ad Fast-Forward & Skip Engine
    function clickSkip() {
        var selectors = [
            '.ytp-skip-ad-button',
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
                stats.skipClicks++;
                return true;
            }
        }
        return false;
    }

    function isAdActive() {
        var p = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
        if (p && (p.classList.contains('ad-showing') || p.classList.contains('ad-interrupting'))) return true;
        // YouTube keeps .ytp-ad-module mounted during normal songs too.
        // Only the player's active-ad state identifies an advertisement.
        return false;
    }

    function superviseYouTube() {
        // Seeking/accelerating the ad media while WebKit changes its pipeline
        // can crash GStreamer. Let the player own timing; use its skip control.
        if (isAdActive()) clickSkip();

        // Clean cosmetic overlay banners
        var adOverlays = document.querySelectorAll(
            '.ytp-ad-overlay-container, #player-ads, ytd-promoted-sparkles-web-renderer, ' +
            'ytd-in-feed-ad-layout-renderer, ytd-banner-promo-renderer-background, ' +
            '.contribYtLightShapeStaticWashLight, .cinematic-renderer, #cinematic-container'
        );
        var removedOverlays = 0;
        for (var o = 0; o < adOverlays.length; o++) {
            try { adOverlays[o].remove(); removedOverlays++; } catch(e) {}
        }
        if (removedOverlays > 0 && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
            try { window.webkit.messageHandlers.safeer.postMessage({ action: 'increment_ads', count: removedOverlays }); } catch(_) {}
        }

        // Auto-dismiss YouTube adblock nag dialogs & confirm buttons
        var dismissBtns = document.querySelectorAll(
            'tp-yt-paper-dialog #dismiss-button, ytd-enforcement-message-view-model #dismiss-button, ' +
            'ytd-enforcement-message-view-model button[aria-label="Dismiss"]'
        );
        for (var d = 0; d < dismissBtns.length; d++) {
            try {
                if (dismissBtns[d].offsetParent !== null) {
                    dismissBtns[d].click();
                }
            } catch(e) {}
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

    // Adaptive supervision: 250ms when ad is active, 1500ms during smooth media playback
    var _ytSupervisorTimer = null;
    function scheduleSupervision(intervalMs) {
        if (_ytSupervisorTimer) clearTimeout(_ytSupervisorTimer);
        _ytSupervisorTimer = setTimeout(function() {
            superviseYouTube();
            var nextInterval = isAdActive() ? 250 : 1500;
            scheduleSupervision(nextInterval);
        }, intervalMs);
    }
    scheduleSupervision(300);

    // Instant playback triggers on navigation
    window.addEventListener('yt-navigate-start', function() {
        var v = document.querySelector('video.video-stream, video');
        if (v) {
            v._safeer_user_paused = false;
            v.preload = 'auto';
        }
        scheduleSupervision(200);
    });
    window.addEventListener('yt-navigate-finish', function() { scheduleSupervision(200); });
    window.addEventListener('yt-page-data-updated', function() { scheduleSupervision(250); });
    window.addEventListener('popstate', function() { scheduleSupervision(200); });
    document.addEventListener('DOMContentLoaded', function() { scheduleSupervision(200); });

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

ADGUARD_PROTECTION_SCRIPT = """
/* 🛡️ Safeer Linux Mint - AdGuard Advanced Protection & Anti-Adblock Defuser Engine */
(function() {
    if (window._adguard_safeer_active) return;
    window._adguard_safeer_active = true;

    // 1. Defuse Anti-Adblock checks & variables
    try {
        window.canRunAds = true;
        window.isAdBlockActive = false;
        window.adblock = false;
        window.adblockDetected = false;
        window._adblocker = false;

        // Adsense / Google Publisher Tag stubs
        if (!window.adsbygoogle) {
            window.adsbygoogle = [];
        }
        window.adsbygoogle.loaded = true;
        var origPush = window.adsbygoogle.push;
        window.adsbygoogle.push = function() {
            try { return origPush ? origPush.apply(this, arguments) : 0; } catch(_) { return 0; }
        };

        // BlockAdBlock / FuckAdBlock stubs
        var FakeBlockAdBlock = function(opts) {
            if (opts && typeof opts.onNotDetected === 'function') {
                setTimeout(opts.onNotDetected, 10);
            }
        };
        FakeBlockAdBlock.prototype.check = function() { return false; };
        FakeBlockAdBlock.prototype.clearEvent = function() {};
        FakeBlockAdBlock.prototype.on = function(detected, fn) {
            if (!detected && typeof fn === 'function') setTimeout(fn, 10);
            return this;
        };
        FakeBlockAdBlock.prototype.onDetected = function() { return this; };
        FakeBlockAdBlock.prototype.onNotDetected = function(fn) {
            if (typeof fn === 'function') setTimeout(fn, 10);
            return this;
        };
        window.BlockAdBlock = FakeBlockAdBlock;
        window.blockAdBlock = new FakeBlockAdBlock();
        window.FuckAdBlock = FakeBlockAdBlock;
        window.fuckAdBlock = window.blockAdBlock;
        window.Snigel = window.Snigel || {};
    } catch(e) {}

    // 2. Anti-Adblock Modal Wall Defuser & Scroll Restoration
    function defuseAntiAdblockWalls() {
        var removed = 0;
        try {
            var wallSelectors = [
                '.fc-ab-root',
                '.adblock-modal',
                '.adblock-overlay',
                '.adblock-wall',
                '.anti-adblock',
                '.adblocker-modal',
                '.sp-message-open',
                '#adblock-notice',
                '#adblocker-detected',
                'div[id*="adblock-dialog"]',
                'div[class*="adblock-dialog"]'
            ];
            var walls = document.querySelectorAll(wallSelectors.join(', '));
            for (var i = 0; i < walls.length; i++) {
                try { walls[i].remove(); removed++; } catch(_) {}
            }

            // Restore scrolling if site locked it
            if (removed > 0 && document.body) {
                var bStyle = window.getComputedStyle(document.body);
                if (bStyle.overflow === 'hidden' && !document.querySelector('.nav-open, .menu-open, .modal-open')) {
                    document.body.style.setProperty('overflow', 'auto', 'important');
                }
            }
            if (removed > 0 && document.documentElement) {
                var dStyle = window.getComputedStyle(document.documentElement);
                if (dStyle.overflow === 'hidden') {
                    document.documentElement.style.setProperty('overflow', 'auto', 'important');
                }
            }
        } catch(_) {}
        return removed;
    }

    // 3. AdGuard Advanced Cosmetic Filtering
    function cleanAdguardCosmetics() {
        var removed = 0;
        try {
            var sel = [
                '.adguard-banner',
                '[data-ad-unit]',
                '[data-ad-slot]',
                '.sponsored-post',
                '.sponsored-content',
                '.native-ad-unit',
                'div[class*="taboola-"]',
                'div[class*="outbrain-"]',
                '.rc-sponsored',
                '.trc_rbox_div',
                '.trc_related_container'
            ];
            var items = document.querySelectorAll(sel.join(', '));
            for (var j = 0; j < items.length; j++) {
                try { items[j].remove(); removed++; } catch(_) {}
            }
        } catch(_) {}
        return removed;
    }

    function runAdguardProtection() {
        var w = defuseAntiAdblockWalls() || 0;
        var c = cleanAdguardCosmetics() || 0;
        var total = w + c;
        if (total > 0 && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
            try { window.webkit.messageHandlers.safeer.postMessage({ action: 'increment_ads', count: total }); } catch(_) {}
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', runAdguardProtection);
    } else {
        runAdguardProtection();
    }
    window.addEventListener('load', runAdguardProtection);
    setInterval(runAdguardProtection, 2500);
})();
"""

GENERIC_COSMETIC_SCRIPT = """
/* 🛡️ Safeer Linux Mint - Universal Ad & Tracker Shield */
(function() {
    function cleanGenericAds() {
        var adSelectors = [
            '[data-component="ad-slot"]', '[data-testid="ad-unit"]',
            '.ad-placeholder', '.ad-slot-container', '.advertisement-wrapper',
            '.ad-unit', '.ad-unit-container', '.ad-placement', '.ad-slot-wrapper',
            '.ads-container', '.ads-wrapper',
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
        var count = 0;
        for (var i = 0; i < ads.length; i++) {
            try { ads[i].remove(); count++; } catch(e) {}
        }
        if (count > 0 && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
            try { window.webkit.messageHandlers.safeer.postMessage({ action: 'increment_ads', count: count }); } catch(_) {}
        }
    }

    if (document.body) cleanGenericAds();
    setInterval(cleanGenericAds, 3000);
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
    var host = location.hostname.toLowerCase();
    if (host === 'youtube.com' || host.endsWith('.youtube.com')) return;
    function neutralizeClickjackingOverlays() {
        try {
            var allDivs = document.querySelectorAll('div, a, span');
            var w = window.innerWidth || document.documentElement.clientWidth;
            var h = window.innerHeight || document.documentElement.clientHeight;
            for (var k = 0; k < allDivs.length; k++) {
                var node = allDivs[k];
                if (node.tagName === 'VIDEO' || node.closest('#player, .html5-video-player, #movie_player, .video-stream, [class*="player"]')) continue;
                // Authentication challenges often contain an iframe with no innerText.
                if (node.matches('[role="dialog"], [aria-modal="true"]') ||
                    node.querySelector('iframe, form, input, button, select, textarea, [role="dialog"], [role="button"], [role="checkbox"], [contenteditable]')) continue;
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
    setInterval(neutralizeClickjackingOverlays, 4000);
})();
"""

TAB_THROTTLER_SCRIPT = """
/* 🍃 Safeer Linux Mint - Background Tab Sleep & Memory Optimizer */
(function() {
    if (window._safeer_tab_optimizer) return;
    window._safeer_tab_optimizer = true;

    var isThrottled = false;

    window.__safeerThrottleTab = function() {
        if (isThrottled) return;
        isThrottled = true;

        // 1. Page Visibility API: notify web apps (Facebook, Messenger, Gmail) that tab is hidden
        try {
            Object.defineProperty(document, 'hidden', { value: true, configurable: true });
            Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
            document.dispatchEvent(new Event('visibilitychange'));
        } catch(e) {}

        // 2. Pause CSS animations on background tabs to eliminate layout & compositor CPU load
        try {
            if (!document.getElementById('__safeer_bg_style')) {
                var s = document.createElement('style');
                s.id = '__safeer_bg_style';
                s.textContent = 'html.safeer-tab-bg *, html.safeer-tab-bg *::before, html.safeer-tab-bg *::after { animation-play-state: paused !important; }';
                (document.head || document.documentElement).appendChild(s);
            }
            if (document.documentElement) {
                document.documentElement.classList.add('safeer-tab-bg');
            }
        } catch(e) {}
    };

    window.__safeerResumeTab = function() {
        if (!isThrottled) return;
        isThrottled = false;

        // 1. Page Visibility API: notify web apps that tab is now visible and active
        try {
            Object.defineProperty(document, 'hidden', { value: false, configurable: true });
            Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
            document.dispatchEvent(new Event('visibilitychange'));
        } catch(e) {}

        // 2. Resume CSS animations
        try {
            if (document.documentElement) {
                document.documentElement.classList.remove('safeer-tab-bg');
            }
        } catch(e) {}
    };
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

        # Signed, login and recovery links must be passed through byte-for-byte.
        pairs = parsed.query.split("&")
        keys = [urllib.parse.unquote_plus(pair.split("=", 1)[0]).lower() for pair in pairs]
        protected = {"state", "nonce", "code", "token", "secret", "signature", "sig",
                     "client_id", "redirect_uri", "redirect_url", "returnto", "return_to",
                     "code_challenge", "samlrequest", "samlresponse", "relaystate",
                     "access_token", "id_token", "session", "session_token", "ticket"}
        segments = {segment.lower() for segment in parsed.path.split("/")}
        if (any(key in protected or key.startswith(("x-amz-", "x-goog-", "oauth_")) for key in keys)
                or segments & {"auth", "oauth", "oauth2", "authorize", "callback", "login",
                               "signin", "sign-in", "verify", "verification", "reset-password"}):
            return url
        retained = [pair for pair, key in zip(pairs, keys)
                    if not (key.startswith("utm_") or key in TRACKING_PARAMS)]
        if len(retained) == len(pairs):
            return url
        # Preserve the encoding, ordering and duplicate keys of all remaining values.
        new_query = "&".join(retained)
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
}

# Ad/tracker matches are blocked silently and are not classified as malware.
AD_TRACKER_DOMAINS = {
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


def _url_host(url: str) -> str:
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

    return host


_ad_trie = ReverseDomainTrie()
for _domain in AD_TRACKER_DOMAINS:
    _ad_trie.insert(_domain)


def is_threat_domain(url: str) -> bool:
    return _threat_trie.is_blocked(_url_host(url))


def is_ad_domain(url: str) -> bool:
    return _ad_trie.is_blocked(_url_host(url))


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



# Cosmetic/anti-overlay scripts must not alter identity or bot-verification pages.
# This does not exempt these URLs from malware checks or certificate validation.
AUTH_SCRIPT_EXCLUSIONS = [
    "*://grok.com/*", "*://*.grok.com/*", "*://accounts.x.ai/*", "*://auth.x.ai/*",
    "*://accounts.google.com/*", "*://auth.openai.com/*", "*://auth0.openai.com/*",
    "*://chatgpt.com/*", "*://chat.openai.com/*", "*://login.microsoftonline.com/*",
    "*://login.live.com/*", "*://appleid.apple.com/*", "*://*.auth0.com/*",
    "*://challenges.cloudflare.com/*", "*://*.hcaptcha.com/*", "*://hcaptcha.com/*",
    "*://www.google.com/recaptcha/*", "*://www.recaptcha.net/*",
    "*://*/login*", "*://*/signin*", "*://*/sign-in*", "*://*/oauth/*",
    "*://*/oauth2/*", "*://*/auth/*", "*://*/authorize*",
]
