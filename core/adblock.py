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
        style.textContent = [
            'ytd-ad-slot-renderer',
            'ytd-in-feed-ad-layout-renderer',
            'ytd-promoted-sparkles-web-renderer',
            'ytd-promoted-sparkles-text-search-renderer',
            'ytd-promoted-video-renderer',
            'ytd-display-ad-renderer',
            'ytd-companion-slot-renderer',
            'ytd-action-companion-ad-renderer',
            'ytd-video-masthead-ad-v3-renderer',
            'ytd-banner-promo-renderer',
            'ytd-player-legacy-desktop-watch-ads-renderer',
            '#player-ads',
            'ytd-rich-shelf-renderer[is-playables]',
            'ytd-rich-section-renderer:has(ytd-rich-shelf-renderer[is-playables])',
            'ytd-game-card-renderer',
            '[section-identifier="playables-shelf"]',
            '[is-mini-game-card-shelf]',
            'ytm-game-card-renderer'
        ].join(',') + '{display:none!important;margin:0!important;padding:0!important;min-height:0!important;}';
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
    var stats = window._safeerAdStats = {cleanedResponses:0, removedFields:0, skipClicks:0, idlePrompts:0};
    // playerAds includes autoplay configuration; heartbeat and integrity fields
    // belong to the media protocol. Preserve them and remove only ad slots.
    var adKeys = ['adPlacements', 'adSlots'];
    var playerKeyPattern = /adPlacements|adSlots|youThereRenderer/;
    // YouTube and YouTube Music schedule the idle prompt ("Video paused. Continue watching?")
    // from playerResponse.messages[].youThereRenderer. The renderer stays, only its timers move
    // beyond any real session. 7 days stays below setTimeout's 2^31-1 ms limit (larger values fire at once).
    var IDLE_LIMIT_MS = 604800000;
    function quietIdlePrompt(data) {
        var messages = Array.isArray(data.messages) ? data.messages : [];
        if (data.youThereRenderer) messages = messages.concat([data]);
        if (!messages.length) return 0;
        var changed = 0;
        messages.forEach(function(message) {
            var renderer = message && message.youThereRenderer;
            if (!renderer || typeof renderer !== 'object') return;
            var configData = renderer.configData;
            var targets = [renderer];
            if (configData && typeof configData === 'object') {
                targets.push(configData);
                if (configData.youThereData && typeof configData.youThereData === 'object') targets.push(configData.youThereData);
            }
            targets.forEach(function(target) {
                [['lactThresholdMs', IDLE_LIMIT_MS], ['playbackPauseDelayMs', IDLE_LIMIT_MS], ['promptDelaySec', IDLE_LIMIT_MS / 1000]].forEach(function(field) {
                    if (!Object.prototype.hasOwnProperty.call(target, field[0])) return;
                    var current = Number(target[field[0]]);
                    if (current >= field[1]) return;
                    target[field[0]] = typeof target[field[0]] === 'string' ? String(field[1]) : field[1];
                    changed++;
                });
            });
        });
        return changed;
    }
    function playerChanges() { return stats.removedFields + stats.idlePrompts; }
    function cleanPlayerText(text) {
        if (typeof text !== 'string' || !playerKeyPattern.test(text)) return text;
        var changesBefore = playerChanges();
        var data = cleanPlayerData(nativeParse(text));
        return playerChanges() === changesBefore ? text : nativeStringify(data);
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
        try { stats.idlePrompts += quietIdlePrompt(data); } catch (_) {}
        // Known player response envelopes; do not traverse unrelated page data.
        ['playerResponse', 'player_response', 'response'].forEach(function(key) {
            var value = data[key];
            if (value && typeof value === 'object' && value !== data) cleanPlayerData(value, depth + 1);
            else if (key === 'player_response' && typeof value === 'string') {
                try { data[key] = cleanPlayerText(value); } catch (_) {}
            }
        });
        if (Array.isArray(data)) data.forEach(function(item) { cleanPlayerData(item, depth + 1); });
        // messages carry the idle prompt configuration; they are part of the player response envelope
        if (Array.isArray(data.messages)) data.messages.forEach(function(item) { cleanPlayerData(item, depth + 1); });
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
        return typeof arguments[0] !== 'string' || playerKeyPattern.test(arguments[0]) ? cleanPlayerData(data) : data;
    };
    function isPlayerApi(value) {
        try {
            var url = new URL(value, location.href);
            var host = url.hostname;
            if (!(host === 'youtube.com' || host.endsWith('.youtube.com') || host === 'youtubei.googleapis.com')) return false;
            return /^\/youtubei\/v[0-9]+\/(player|next|reel\/player)(?:\/|$)/.test(url.pathname);
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
            '.ytp-skip-ad-button-container button',
            'button.ytp-ad-skip-button-modern',
            '.ytp-ad-overlay-close-button',
            '.ytp-ad-skip-button-slot button'
        ];
        for (var i = 0; i < selectors.length; i++) {
            var btn = document.querySelector(selectors[i]);
            if (btn && btn.offsetParent !== null && !btn.disabled) {
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
        return false;
    }

    function superviseYouTube() {
        if (isAdActive()) clickSkip();

        var adOverlays = document.querySelectorAll(
            '.ytp-ad-overlay-container, #player-ads, ytd-promoted-sparkles-web-renderer, ' +
            'ytd-in-feed-ad-layout-renderer, ytd-banner-promo-renderer, ytd-video-masthead-ad-v3-renderer'
        );
        var removedOverlays = 0;
        for (var o = 0; o < adOverlays.length; o++) {
            try { adOverlays[o].remove(); removedOverlays++; } catch(e) {}
        }
        if (removedOverlays > 0 && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
            try { window.webkit.messageHandlers.safeer.postMessage({ action: 'increment_ads', count: removedOverlays }); } catch(_) {}
        }

        var dismissBtns = document.querySelectorAll(
            'tp-yt-paper-dialog #dismiss-button, ytd-enforcement-message-view-model #dismiss-button, ' +
            'ytd-enforcement-message-view-model button[aria-label="Dismiss"]'
        );
        for (var d = 0; d < dismissBtns.length; d++) {
            try { if (dismissBtns[d].offsetParent !== null) dismissBtns[d].click(); } catch(e) {}
        }
    }

    function markUserPause(e) {
        var v = e.target;
        if (!v || v.tagName !== 'VIDEO') return;
        v._safeer_user_paused = true;
    }
    function markUserPlay(e) {
        var v = e.target;
        if (!v || v.tagName !== 'VIDEO') return;
        v._safeer_user_paused = false;
    }
    document.addEventListener('pause', markUserPause, true);
    document.addEventListener('playing', markUserPlay, true);

    function boostPlayback() {
        var v = document.querySelector('video.video-stream, video');
        if (v && v.paused && !v._safeer_user_paused && !isAdActive()) {
            var p = v.play();
            if (p && typeof p.catch === 'function') p.catch(function(){});
        }
    }

    function watchPlayerClass() {
        var p = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
        if (!p || p._safeerAdMo) return;
        p._safeerAdMo = new MutationObserver(function() {
            if (isAdActive()) clickSkip();
        });
        p._safeerAdMo.observe(p, { attributes: true, attributeFilter: ['class'] });
    }

    // Adaptive supervision: observer for skip, slow poll only as fallback
    var _ytSupervisorTimer = null;
    function scheduleSupervision(intervalMs) {
        if (_ytSupervisorTimer) clearTimeout(_ytSupervisorTimer);
        _ytSupervisorTimer = setTimeout(function() {
            watchPlayerClass();
            superviseYouTube();
            scheduleSupervision(isAdActive() ? 400 : 4000);
        }, intervalMs);
    }
    scheduleSupervision(300);

    window.addEventListener('yt-navigate-start', function() {
        var v = document.querySelector('video.video-stream, video');
        if (v) { v._safeer_user_paused = false; v.preload = 'auto'; }
        scheduleSupervision(200);
    });
    window.addEventListener('yt-navigate-finish', function() { watchPlayerClass(); boostPlayback(); scheduleSupervision(200); });
    window.addEventListener('yt-page-data-updated', function() { watchPlayerClass(); boostPlayback(); scheduleSupervision(250); });
    window.addEventListener('popstate', function() { watchPlayerClass(); scheduleSupervision(200); });
    document.addEventListener('DOMContentLoaded', function() { watchPlayerClass(); scheduleSupervision(200); });

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
    var host = location.hostname.toLowerCase();
    if (host === 'youtube.com' || host.endsWith('.youtube.com')) return;
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
    var host = location.hostname.toLowerCase();
    if (host === 'youtube.com' || host.endsWith('.youtube.com')) return;
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
        configurable: true,
        enumerable: true
    };
    var dntProp = {
        value: '1',
        writable: false,
        configurable: true,
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
                     "access_token", "id_token", "session", "session_token", "ticket",
                     "service", "continue", "uilel", "passive"}
        segments = {segment.lower() for segment in parsed.path.split("/")}
        netloc = (parsed.netloc or "").lower()
        path_lower = parsed.path.lower()
        if (is_passthrough_host(url)
                or path_lower.startswith("/cdn-cgi/")
                or "challenge-platform" in path_lower
                or netloc.startswith(("accounts.google.", "accounts.youtube.", "myaccount.google."))
                or any(key in protected or key.startswith(("x-amz-", "x-goog-", "oauth_")) for key in keys)
                or segments & {"auth", "oauth", "oauth2", "authorize", "callback", "login",
                               "signin", "sign-in", "servicelogin", "verify", "verification", "reset-password"}):
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


CLOUDFLARE_PASSTHROUGH = (
    "accounts.x.ai",
    "auth.x.ai",
    "grok.com",
    "www.grok.com",
    "x.ai",
    "challenges.cloudflare.com",
    "cloudflare.com",
    "cloudflareinsights.com",
    "turnstile.com",
)


def is_passthrough_host(url: str) -> bool:
    if not url:
        return False
    h = _url_host(url).rstrip(".")
    if not h:
        return False
    for allowed in CLOUDFLARE_PASSTHROUGH:
        if h == allowed or h.endswith("." + allowed):
            return True
    return False


_extra_threat_matchers = []

# Categories that block even on a real bank's host (a compromised server); anything else never does.
CRITICAL_THREAT_CATEGORIES = frozenset({"botnet_c2", "malware"})

_bank_guard_instance = None
_fake_bank_allowed_hosts = set()


def _bank_guard():
    """The shared BankGuard (core/bank_guard.py), loaded once; None when it is unavailable."""
    global _bank_guard_instance
    if _bank_guard_instance is None:
        try:
            import importlib.util
            import os
            import sys

            module = sys.modules.get("safeer_bank_guard")
            if module is None:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bank_guard.py")
                spec = importlib.util.spec_from_file_location("safeer_bank_guard", path)
                module = importlib.util.module_from_spec(spec)
                sys.modules["safeer_bank_guard"] = module  # dataclasses look the module up while it loads
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    del sys.modules["safeer_bank_guard"]
                    raise
            _bank_guard_instance = module.default_guard()
        except Exception:
            _bank_guard_instance = False
    return _bank_guard_instance or None


def is_real_bank_host(url_or_host: str) -> bool:
    """Official bank domains, bank group domains and payment/identity infrastructure (BankGuard catalogue)."""
    guard = _bank_guard()
    host = _url_host(url_or_host) if url_or_host else ""
    return bool(guard and host and guard.is_trusted(host))


def _bank_host(url_or_host: str) -> str:
    """Host in the form BankGuard compares (lower case, no trailing dot, xn-- for Unicode names)."""
    guard = _bank_guard()
    host = _url_host(url_or_host) if url_or_host else ""
    return guard._host(host) if guard and host else ""


def allow_fake_bank_host(url_or_host: str) -> None:
    """The user chose to continue after a fake bank warning: no more warnings for this host in this session."""
    host = _bank_host(url_or_host)
    if host:
        _fake_bank_allowed_hosts.add(host)


def is_fake_bank_host_allowed(url_or_host: str) -> bool:
    return _bank_host(url_or_host) in _fake_bank_allowed_hosts


def fake_bank_verdict(url: str):
    """BankGuard verdict for an address whose host name imitates a bank, or None."""
    guard = _bank_guard()
    if not guard or not url or not url.lower().startswith(("http://", "https://")):
        return None
    host = _bank_host(url)
    if not host or host in _fake_bank_allowed_hosts:
        return None
    try:
        return guard.host_verdict(host)
    except Exception:
        return None


def fake_bank_page_verdict(page_url: str, signals):
    """BankGuard verdict for a loaded page from the signals of bank_guard_page_script(), or None."""
    guard = _bank_guard()
    if not guard or not isinstance(signals, dict) or not page_url:
        return None
    host = _bank_host(page_url)
    reported = guard._host(str(signals.get("host") or ""))
    if not host or host != reported or host in _fake_bank_allowed_hosts:
        return None  # a late answer from a previous page, or allowed by the user
    try:
        return guard.page_verdict(host, signals)
    except Exception:
        return None


def bank_guard_page_script() -> str:
    guard = _bank_guard()
    return guard.page_script if guard else ""


def register_threat_matcher(matcher) -> None:
    """Adds a matcher (url -> category or None), e.g. the signed Safeer threat feed."""
    if matcher not in _extra_threat_matchers:
        _extra_threat_matchers.append(matcher)


def is_threat_domain(url: str) -> bool:
    if is_passthrough_host(url):
        return False
    real_bank = is_real_bank_host(url)
    if not real_bank and _threat_trie.is_blocked(_url_host(url)):
        return True
    for matcher in _extra_threat_matchers:
        try:
            category = matcher(url)
            if category and (not real_bank or category in CRITICAL_THREAT_CATEGORIES):
                return True
        except Exception:
            continue
    return False


def is_ad_domain(url: str) -> bool:
    if is_passthrough_host(url) or is_real_bank_host(url):
        return False
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
    "*://x.ai/*", "*://*.x.ai/*",
    "*://grok.com/*", "*://*.grok.com/*", "*://accounts.x.ai/*", "*://auth.x.ai/*",
    "*://challenges.cloudflare.com/*", "*://*.cloudflare.com/*",
    "*://static.cloudflareinsights.com/*", "*://*.turnstile.com/*",
    "*://accounts.google.com/*", "*://myaccount.google.com/*",
    "*://accounts.youtube.com/*", "*://*.youtube.com/signin*", "*://*.youtube.com/accounts/*", "*://*.youtube.com/redirect*",
    "*://auth.openai.com/*", "*://auth0.openai.com/*",
    "*://chatgpt.com/*", "*://chat.openai.com/*", "*://login.microsoftonline.com/*",
    "*://login.live.com/*", "*://appleid.apple.com/*", "*://*.auth0.com/*",
    "*://*.hcaptcha.com/*", "*://hcaptcha.com/*",
    "*://www.google.com/recaptcha/*", "*://www.recaptcha.net/*",
    "*://*/login*", "*://*/signin*", "*://*/sign-in*", "*://*/oauth/*",
    "*://*/oauth2/*", "*://*/auth/*", "*://*/authorize*",
]


def _bank_script_exclusions():
    """Real banks and payment pages (BankGuard catalogue) run without cosmetic or anti-popup scripts."""
    try:
        import json
        import os

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "banks.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        domains = [d for bank in data["banks"] for d in bank["official"] + bank["family"]] + data["infrastructure"]
        return [pattern for d in domains for pattern in (f"*://{d}/*", f"*://*.{d}/*")]
    except Exception:
        return []


AUTH_SCRIPT_EXCLUSIONS += _bank_script_exclusions()

# Keeps YouTube and YouTube Music playing: refreshes YouTube's activity timestamp and,
# if the idle prompt still appears, confirms it and resumes the paused video.
YOUTUBE_KEEP_WATCHING_SCRIPT = r"""
/* Safeer: keep YouTube and YouTube Music playing without the idle prompt
   ("Video paused. Continue watching?" / "Predvajanje videoposnetka je začasno zaustavljeno"). */
(function () {
    var host = (location.hostname || '').toLowerCase();
    if (!(host === 'youtube.com' || host.slice(-12) === '.youtube.com')) return;
    if (window.top !== window || window.__safeerKeepWatching) return;
    window.__safeerKeepWatching = true;

    // YouTube and YouTube Music show the idle prompt only when Date.now() - window._lact
    // (time of the last user activity) exceeds the limit sent by the server. A getter keeps the
    // value current without timers, which browsers delay for minutes in hidden or minimized windows.
    function markActive() {
        try { window._lact = Date.now(); } catch (e) {}
    }
    try {
        Object.defineProperty(window, '_lact', {
            configurable: true,
            get: function () { return Date.now(); },
            set: function () {}
        });
    } catch (e) {
        markActive();
        setInterval(markActive, 30000);
    }

    var lastUserInput = 0;
    var lastAutoPause = 0;
    var autoPausedVideo = null;
    ['pointerdown', 'mousedown', 'touchstart', 'keydown'].forEach(function (type) {
        window.addEventListener(type, function (ev) {
            if (ev.isTrusted) lastUserInput = Date.now();
        }, true);
    });
    // A pause without user input is how the idle prompt stops playback.
    document.addEventListener('pause', function (ev) {
        var v = ev.target;
        if (!v || v.tagName !== 'VIDEO' || v.ended) return;
        // Hover previews on the home page pause on their own; only the player's video counts.
        var player = playerVideo();
        if (player && v !== player) return;
        if (Date.now() - lastUserInput > 2000) {
            lastAutoPause = Date.now();
            autoPausedVideo = v;
            scanSoon();
        }
    }, true);
    // YouTube announces its dialogs; react in a microtask instead of waiting for a (throttled) timer.
    document.addEventListener('yt-popup-opened', function () { scanSoon(); }, true);

    var PROMPTS = 'ytmusic-you-there-renderer, ytd-you-there-renderer, ytm-you-there-renderer, yt-confirm-dialog-renderer';
    // In priority order: querySelector with a selector list would return the outer wrapper first.
    var BUTTONS = ['#confirm-button button', '#confirm-button tp-yt-paper-button', 'yt-button-renderer button',
        'ytmusic-button-renderer button', 'ytmusic-button-renderer a', 'button', 'tp-yt-paper-button',
        'a[role="button"]', '[role="button"]', '#confirm-button', 'yt-formatted-string.ytmusic-you-there-renderer'];

    // A tab in the background is not laid out, so element sizes are 0 and say nothing about
    // whether the prompt is up. Only the style of the element and its ancestors decides.
    function isShown(el) {
        if (!el || !el.isConnected) return false;
        for (var node = el; node && node.nodeType === 1; node = node.parentElement || hostOf(node)) {
            if (node.hasAttribute('hidden') || node.getAttribute('aria-hidden') === 'true') return false;
            var style = window.getComputedStyle(node);
            if (style && (style.display === 'none' || style.visibility === 'hidden')) return false;
        }
        return true;
    }

    function hostOf(node) {
        var root = node.getRootNode ? node.getRootNode() : null;
        return root && root.host ? root.host : null;
    }

    function playerVideo() {
        return document.querySelector('#movie_player video, ytmusic-player video, video.html5-main-video');
    }

    function mainVideo() {
        var player = playerVideo();
        if (player) return player;
        if (autoPausedVideo && autoPausedVideo.isConnected) return autoPausedVideo;
        return document.querySelector('video');
    }

    function isIdlePrompt(el) {
        if (/YOU-THERE|STILL-WATCHING/.test(el.tagName)) return true;
        // The generic confirm dialog is also used for real questions; accept it only when
        // YouTube paused the video by itself and the user has not just interacted.
        var v = mainVideo();
        return !!v && v.paused && !v.ended &&
            Date.now() - lastAutoPause < 10000 && Date.now() - lastUserInput > 5000;
    }

    function resume() {
        var v = mainVideo();
        if (v && v.paused && !v.ended) {
            try {
                var p = v.play();
                if (p && p.catch) p.catch(function () {});
            } catch (e) {}
        }
        markActive();
    }

    function findPrompts() {
        var found = Array.prototype.slice.call(document.querySelectorAll(PROMPTS));
        // YouTube for TV (youtube.com/tv) uses its own renderer names; look for them only
        // shortly after an unexplained pause so normal pages are not walked every second.
        if (!found.length && Date.now() - lastAutoPause < 15000 && document.body) {
            var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
            for (var n = walker.nextNode(), count = 0; n && count < 20000; n = walker.nextNode(), count++) {
                if (/YOU-THERE|STILL-WATCHING/.test(n.tagName)) found.push(n);
            }
        }
        return found;
    }

    function pressEnter(el) {
        var target = el.querySelector('[tabindex], [role="button"], button') || el;
        try { target.focus(); } catch (e) {}
        ['keydown', 'keyup'].forEach(function (type) {
            var ev = new KeyboardEvent(type, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true });
            (document.activeElement || target).dispatchEvent(ev);
        });
    }

    function scan() {
        var prompts = findPrompts();
        for (var i = 0; i < prompts.length; i++) {
            var el = prompts[i];
            if (!isShown(el) || !isIdlePrompt(el)) continue;
            if (el.__safeerConfirmedAt && Date.now() - el.__safeerConfirmedAt < 3000) continue;
            el.__safeerConfirmedAt = Date.now();
            var clicked = false;
            for (var b = 0; b < BUTTONS.length; b++) {
                var button = el.querySelector(BUTTONS[b]);
                if (button) { button.click(); clicked = true; break; }
            }
            // Resume at once as well: the timer below can be delayed in a hidden window.
            if (clicked) scanSoonResume();
            (function (prompt, wasClicked) {
                setTimeout(function () {
                    // TV layouts react to the remote's Enter key rather than to click().
                    if (!wasClicked || isShown(prompt)) pressEnter(prompt);
                    resume();
                }, 300);
            })(el, clicked);
        }
    }

    function scanSoon() {
        try { Promise.resolve().then(scan); } catch (e) {}
    }

    function scanSoonResume() {
        try { Promise.resolve().then(resume); } catch (e) {}
    }

    var queued = false;
    function queueScan() {
        if (queued) return;
        queued = true;
        setTimeout(function () { queued = false; scan(); }, 250);
    }
    function start() {
        try {
            new MutationObserver(queueScan).observe(document.documentElement, { childList: true, subtree: true });
        } catch (e) {}
        setInterval(scan, 1000);
    }
    if (document.documentElement) start();
    else document.addEventListener('DOMContentLoaded', start);
})();
"""

# Push Square, Nintendo Life, Pure Xbox, Time Extension: hide empty ad inserts and the
# "Please disable adblock or subscribe" placeholder (EasyList: ##.insert, ##.insert-label, ##.item-insert).
HOOKSHOT_INSERTS_SCRIPT = r"""
/* Safeer: remove empty ad inserts and the "Please disable adblock or subscribe" placeholders
   on Hookshot Media sites (Push Square, Nintendo Life, Pure Xbox, Time Extension). */
(function () {
    var host = (location.hostname || '').toLowerCase();
    var sites = ['pushsquare.com', 'nintendolife.com', 'purexbox.com', 'timeextension.com', 'digitalfoundry.net'];
    var match = false;
    for (var i = 0; i < sites.length; i++) {
        if (host === sites[i] || host.slice(-(sites[i].length + 1)) === '.' + sites[i]) match = true;
    }
    if (!match || window.__safeerHookshotInserts) return;
    window.__safeerHookshotInserts = true;

    var CSS = '.insert, .insert-label, .item-insert, .for-mobile.below-article, [style*="min-height:250px;"]' +
        '{display:none !important;height:0 !important;min-height:0 !important;margin:0 !important;padding:0 !important}';

    function addStyle() {
        if (document.getElementById('safeer-hookshot-inserts')) return;
        var style = document.createElement('style');
        style.id = 'safeer-hookshot-inserts';
        style.textContent = CSS;
        var parent = document.head || document.documentElement;
        if (parent) parent.appendChild(style);
    }

    var NOTICE = /disable\s+ad\s*block|or\s+subscribe/i;
    function hideNotices() {
        var labels = document.querySelectorAll('span, p, div, strong, small');
        for (var i = 0; i < labels.length; i++) {
            var el = labels[i];
            if (el.__safeerChecked || el.children.length > 2) continue;
            var text = el.textContent || '';
            if (text.length > 80 || !NOTICE.test(text)) continue;
            el.__safeerChecked = true;
            // Hide the whole insert (label plus the reserved subscription box), never the article.
            var box = el.closest('.insert, .item-insert, [class*="insert"], aside, figure') || el.parentElement;
            if (!box || box === document.body || box.tagName === 'ARTICLE' || box.tagName === 'MAIN') box = el;
            box.style.setProperty('display', 'none', 'important');
        }
    }

    function run() { addStyle(); hideNotices(); }
    var queued = false;
    var observing = false;
    function start() {
        run();
        if (observing || !document.documentElement) return;
        observing = true;
        new MutationObserver(function () {
            if (queued) return;
            queued = true;
            setTimeout(function () { queued = false; run(); }, 300);
        }).observe(document.documentElement, { childList: true, subtree: true });
    }
    if (document.documentElement) start();
    document.addEventListener('DOMContentLoaded', start);
})();
"""
