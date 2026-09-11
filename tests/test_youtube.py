import subprocess
import unittest
from core.adblock import YOUTUBE_ADBLOCK_SCRIPT


class YouTubeTests(unittest.TestCase):
    def test_short_content_is_not_an_ad_and_user_media_settings_return(self):
        start = YOUTUBE_ADBLOCK_SCRIPT.index("    function isAdActive()")
        end = YOUTUBE_ADBLOCK_SCRIPT.index("    // Adaptive supervision", start)
        code = YOUTUBE_ADBLOCK_SCRIPT[start:end]
        fixture = r"""
const assert = require('assert');
let active = false;
const listeners = [];
const video = {
  duration: 60, currentTime: 10, playbackRate: 1.5, muted: false, paused: false,
  readyState: 4, ended: false, tagName: 'VIDEO', _safeer_user_paused: false,
  addEventListener() {}, play() { this.paused = false; return Promise.resolve(); }
};
const player = { classList: { contains() { return active; } }, style: { setProperty() {} } };
const cinematic = { removed: false, remove() { this.removed = true; } };
const document = {
  getElementById() { return player; },
  querySelector(s) {
    if (String(s).includes('video.video-stream') || s === 'video') return video;
    return null;
  },
  querySelectorAll(s) {
    if (String(s).includes('cinematic')) return [cinematic];
    return [];
  },
  addEventListener(type, fn) { listeners.push([type, fn]); }
};
const window = {};
const location = { pathname: '/watch' };
function clickSkip() {}
global.document = document;
"""
        checks = r"""
assert.strictEqual(isAdActive(), false);
superviseYouTube();
assert.strictEqual(video.currentTime, 10);
assert.strictEqual(video.playbackRate, 1.5);
assert.strictEqual(cinematic.removed, false);

active = true;
superviseYouTube();
assert.strictEqual(video.currentTime, 10);
assert.strictEqual(video.muted, false);
assert.strictEqual(video.playbackRate, 1.5);

video.muted = true;
active = false;
superviseYouTube();
assert.strictEqual(video.muted, true);

video.paused = true;
video._safeer_user_paused = true;
boostPlayback();
assert.strictEqual(video.paused, true);

video._safeer_user_paused = false;
boostPlayback();
assert.strictEqual(video.paused, false);

assert.ok(listeners.some(([type]) => type === 'pause'));
assert.ok(listeners.some(([type]) => type === 'playing'));
assert.strictEqual(typeof watchPlayerClass, 'function');
"""
        subprocess.run(["node", "-e", fixture + code + checks], check=True)


class PlayerDataTests(unittest.TestCase):
    def test_initial_objects_fetch_xhr_and_signed_media_are_preserved(self):
        start = YOUTUBE_ADBLOCK_SCRIPT.index("    // Remove ad instructions")
        end = YOUTUBE_ADBLOCK_SCRIPT.index("    // 4. Safe YouTube", start)
        fixture = r"""
const assert = require('assert');
const window = globalThis;
const document = { addEventListener() {} };
const location = { href: 'https://www.youtube.com/watch?v=fixture' };
const originalParse = JSON.parse;
const source = {
  adPlacements: [{ adPlacementRenderer: {} }],
  adSlots: [{ adSlotRenderer: {} }],
  playerAds: [{ playerLegacyDesktopWatchAdsRenderer: { playerAdParams: { autoplay: '1', showContentThumbnail: true, enabledEngageTypes: 'fixture' } } }],
  adPlayback: { context: 'fixture-playback' },
  adBreakHeartbeatParams: 'fixture-heartbeat',
  videoDetails: { videoId: 'fixture' },
  streamingData: {
    formats: [{ url: 'https://cdn.test/media?sig=abc&n=def&pot=fixture&x=1' }],
    serverAbrStreamingUrl: 'https://cdn.test/videoplayback?sig=sabr&n=fixture'
  },
  serviceIntegrityDimensions: { poToken: 'fixture-integrity-token' }
};
window.ytInitialPlayerResponse = structuredClone(source);
window.ytplayer = { config: { args: { player_response: JSON.stringify(source) } } };
let reply = '';
window.fetch = () => Promise.resolve(new Response(reply, { status: 200, headers: { 'content-type': 'application/json' } }));
class XMLHttpRequest {
  open() {}
  get responseText() { return reply; }
  get response() { return this.responseType === 'json' ? originalParse(reply) : reply; }
}
window.XMLHttpRequest = XMLHttpRequest;
"""
        checks = r"""
const expected = structuredClone(source);
delete expected.adPlacements;
delete expected.adSlots;
function assertClean(data, label) { assert.deepStrictEqual(data, expected, label); }
assertClean(window.ytInitialPlayerResponse, 'existing initial object');
assertClean(nativeParse(window.ytplayer.config.args.player_response), 'existing serialized config');
window.ytInitialPlayerResponse = structuredClone(source);
assertClean(window.ytInitialPlayerResponse, 'new initial object');
window.ytplayer = { config: { args: { player_response: nativeStringify(source) } } };
assertClean(nativeParse(window.ytplayer.config.args.player_response), 'new serialized config');
window.ytplayer.config.args.player_response = nativeStringify(source);
assertClean(nativeParse(window.ytplayer.config.args.player_response), 'updated serialized args');
assertClean(JSON.parse(nativeStringify(source)), 'JSON.parse');
reply = nativeStringify({ playerResponse: source });
const xhr = new XMLHttpRequest(); xhr.open('GET', '/youtubei/v1/player'); xhr.readyState = 4;
assertClean(nativeParse(xhr.responseText).playerResponse, 'XHR responseText');
assertClean(nativeParse(xhr.response).playerResponse, 'XHR text response');
const jsonXhr = new XMLHttpRequest(); jsonXhr.open('GET', '/youtubei/v1/player'); jsonXhr.readyState = 4; jsonXhr.responseType = 'json';
assertClean(jsonXhr.response.playerResponse, 'XHR JSON response');
const ordinary = new XMLHttpRequest(); ordinary.open('GET', '/other'); ordinary.readyState = 4;
assert.strictEqual(ordinary.responseText, reply);
assert.strictEqual(isPlayerApi('https://youtube.com.evil.test/youtubei/v1/player'), false);
assert.strictEqual(isPlayerApi('https://www.youtube.com/youtubei/v1/player'), true);
assert.strictEqual(isPlayerApi('https://www.youtube.com/youtubei/v1/next'), true);
assert.strictEqual(isPlayerApi('https://www.youtube.com/youtubei/v1/reel/player'), true);
const unchanged = ' { "response": {"comments":[1,2,3]}, "value": 12345678901234567890 } ';
assert.strictEqual(cleanPlayerText(unchanged), unchanged);
assert.strictEqual(cleanPlayerText('{"description":"adPlacements"}'), '{"description":"adPlacements"}');
const configOnly = ' { "playerAds": [], "adPlayback": {}, "adBreakHeartbeatParams": "fixture" } ';
assert.strictEqual(cleanPlayerText(configOnly), configOnly);
const nested = nativeStringify({ player_response: nativeStringify(source) });
assertClean(nativeParse(nativeParse(cleanPlayerText(nested)).player_response), 'nested serialized response');
assertClean(nativeParse(JSON.parse(nested).player_response), 'JSON serialized response');
let revived = JSON.parse('{"x":1}', (key, value) => key === 'x' ? 2 : value);
assert.strictEqual(revived.x, 2);

(async () => {
  const response = await fetch('/youtubei/v1/next');
  const data = await response.json();
  assertClean(data.playerResponse, 'fetch JSON response');
  console.log('PASS: ad placements removed; playback, heartbeat, integrity and signed media preserved');
})().catch(e => { console.error(e); process.exitCode = 1; });
"""
        subprocess.run(["node", "-e", fixture + YOUTUBE_ADBLOCK_SCRIPT[start:end] + checks], check=True)


    def test_idle_prompt_timers_move_beyond_any_session(self):
        start = YOUTUBE_ADBLOCK_SCRIPT.index("    // Remove ad instructions")
        end = YOUTUBE_ADBLOCK_SCRIPT.index("    // 4. Safe YouTube", start)
        fixture = r"""
const assert = require('assert');
const window = globalThis;
const document = { addEventListener() {} };
const location = { href: 'https://music.youtube.com/watch?v=fixture' };
const source = {
  videoDetails: { videoId: 'fixture' },
  messages: [
    { mealbarPromoRenderer: { messageTexts: ['fixture'] } },
    { youThereRenderer: { configData: { youThereData: {
      lactThresholdMs: '1800000', playbackPauseDelayMs: 5000, promptDelaySec: 1800, showPausedActions: [{ fixture: 1 }]
    } } } }
  ]
};
let reply = '';
window.fetch = () => Promise.resolve(new Response(reply, { status: 200, headers: { 'content-type': 'application/json' } }));
"""
        checks = r"""
const MAX_TIMER = 2147483647;
function assertQuiet(data, label) {
  const youThere = data.messages[1].youThereRenderer.configData.youThereData;
  assert.strictEqual(youThere.lactThresholdMs, '604800000', label + ' lact (string kept as string)');
  assert.strictEqual(youThere.playbackPauseDelayMs, 604800000, label + ' pause delay');
  assert.strictEqual(youThere.promptDelaySec, 604800, label + ' prompt delay');
  assert.ok(youThere.playbackPauseDelayMs < MAX_TIMER && youThere.promptDelaySec * 1000 < MAX_TIMER, label + ' timers stay valid');
  assert.deepStrictEqual(youThere.showPausedActions, [{ fixture: 1 }], label + ' dialog actions untouched');
  assert.deepStrictEqual(data.messages[0], source.messages[0], label + ' other messages untouched');
  assert.deepStrictEqual(data.videoDetails, source.videoDetails, label + ' video untouched');
}
window.ytInitialPlayerResponse = structuredClone(source);
assertQuiet(window.ytInitialPlayerResponse, 'initial object');
assertQuiet(JSON.parse(nativeStringify({ playerResponse: source })).playerResponse, 'JSON.parse');
const quiet = cleanPlayerText(nativeStringify(source));
assertQuiet(nativeParse(quiet), 'text');
assert.strictEqual(cleanPlayerText(quiet), quiet, 'already quiet text is returned unchanged');
const noTimers = nativeStringify({ messages: [{ youThereRenderer: { title: 'fixture' } }] });
assert.strictEqual(cleanPlayerText(noTimers), noTimers, 'renderer without timers is not rewritten');
(async () => {
  reply = nativeStringify(source);
  const data = await (await fetch('https://music.youtube.com/youtubei/v1/player?prettyPrint=false')).json();
  assertQuiet(data, 'fetch');
  console.log('PASS: YouTube idle prompt timers moved beyond any session');
})().catch(e => { console.error(e); process.exitCode = 1; });
"""
        subprocess.run(["node", "-e", fixture + YOUTUBE_ADBLOCK_SCRIPT[start:end] + checks], check=True)


if __name__ == "__main__":
    unittest.main()
