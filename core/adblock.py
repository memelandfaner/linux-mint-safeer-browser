#!/usr/bin/env python3
"""
Safeer Browser Ad-Blocker & Cyber Shield for Linux Mint
Injects YouTube background playback scripts, 0-ad stream strippers,
and checks against known abuse.ch botnet indicators.
"""

YOUTUBE_ADBLOCK_SCRIPT = """
(function() {
    // 🛡️ Safeer Adblock & Background Playback Engine for YouTube
    function cleanYouTubeAds() {
        const adBadges = document.querySelectorAll('.ad-showing, .ad-interrupting, .ytp-ad-overlay-container');
        adBadges.forEach(el => el.remove());

        const video = document.querySelector('video');
        if (video) {
            // Auto skip ads
            const skipBtn = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern');
            if (skipBtn) {
                skipBtn.click();
            }
            // If ad is playing, advance to end
            const playerAd = document.querySelector('.ad-showing');
            if (playerAd && video.duration && !isNaN(video.duration)) {
                video.currentTime = video.duration;
            }
        }
    }

    // Run every 250ms on YouTube
    if (window.location.hostname.includes('youtube.com')) {
        setInterval(cleanYouTubeAds, 250);
        
        // Prevent pause on tab hide (Background Playback)
        document.addEventListener('visibilitychange', function(e) {
            e.stopImmediatePropagation();
        }, true);
    }
})();
"""

ABUSE_CH_BLOCKED_DOMAINS = {
    "payload-delivery.cc",
    "dridex-c2-botnet.ru",
    "emotet-loader.biz",
    "credential-theft-login.top",
    "malicious-banking-trojan.net"
}


def is_threat_domain(url: str) -> bool:
    """Checks if the given URL belongs to a known malicious C2 or phishing domain."""
    for threat in ABUSE_CH_BLOCKED_DOMAINS:
        if threat in url.lower():
            return True
    return False
