import subprocess
import unittest
from core.adblock import YOUTUBE_ADBLOCK_SCRIPT

class YouTubeTests(unittest.TestCase):
    def test_short_content_is_not_an_ad_and_user_media_settings_return(self):
        start=YOUTUBE_ADBLOCK_SCRIPT.index("    function isAdActive()")
        end=YOUTUBE_ADBLOCK_SCRIPT.index("    // Adaptive supervision",start)
        code=YOUTUBE_ADBLOCK_SCRIPT[start:end]
        fixture="""
const assert=require('assert');
let active=false;
const video={duration:60,currentTime:10,playbackRate:1.5,muted:false,paused:false,readyState:4,ended:false,addEventListener(){},play(){return Promise.resolve()}};
const player={classList:{contains(){return active}},style:{setProperty(){}}};
const document={getElementById(){return player},querySelector(s){if(s.includes('video.video-stream'))return video; if(s.includes('.ytp-ad-module'))return {}; return null},querySelectorAll(){return []}};
const window={};const location={pathname:'/watch'};function clickSkip(){};
"""
        checks="""
assert.strictEqual(isAdActive(),false);
superviseYouTube();assert.strictEqual(video.currentTime,10);assert.strictEqual(video.playbackRate,1.5);
active=true;superviseYouTube();assert.strictEqual(video.currentTime,10);assert.strictEqual(video.muted,false);assert.strictEqual(video.playbackRate,1.5);
video.muted=true;active=false;superviseYouTube();assert.strictEqual(video.muted,true);
"""
        subprocess.run(['node','-e',fixture+code+checks],check=True)

class PlayerDataTests(unittest.TestCase):
    def test_initial_objects_fetch_xhr_and_signed_media_are_preserved(self):
        start=YOUTUBE_ADBLOCK_SCRIPT.index("    // Remove ad instructions")
        end=YOUTUBE_ADBLOCK_SCRIPT.index("    // 4. Safe YouTube",start)
        fixture=r"""
const assert=require('assert');
const window=globalThis; const document={addEventListener(){}};
const location={href:'https://www.youtube.com/watch?v=fixture'};
const originalParse=JSON.parse;
const source={
  adPlacements:[{adPlacementRenderer:{}}],adSlots:[{adSlotRenderer:{}}],
  playerAds:[{playerLegacyDesktopWatchAdsRenderer:{playerAdParams:{autoplay:'1',showContentThumbnail:true,enabledEngageTypes:'fixture'}}}],
  adPlayback:{context:'fixture-playback'},adBreakHeartbeatParams:'fixture-heartbeat',
  videoDetails:{videoId:'fixture'},
  streamingData:{formats:[{url:'https://cdn.test/media?sig=abc&n=def&pot=fixture&x=1'}],serverAbrStreamingUrl:'https://cdn.test/videoplayback?sig=sabr&n=fixture'},
  serviceIntegrityDimensions:{poToken:'fixture-integrity-token'}
};
window.ytInitialPlayerResponse=structuredClone(source);
window.ytplayer={config:{args:{player_response:JSON.stringify(source)}}};
let reply='';window.fetch=()=>Promise.resolve(new Response(reply,{status:200,headers:{'content-type':'application/json'}}));
class XMLHttpRequest {open(){} get responseText(){return reply} get response(){return this.responseType==='json'?originalParse(reply):reply}}
window.XMLHttpRequest=XMLHttpRequest;
"""
        checks=r"""
const expected=structuredClone(source);delete expected.adPlacements;delete expected.adSlots;
function assertClean(data,label){assert.deepStrictEqual(data,expected,label)}
assertClean(window.ytInitialPlayerResponse,'existing initial object');
assertClean(nativeParse(window.ytplayer.config.args.player_response),'existing serialized config');
window.ytInitialPlayerResponse=structuredClone(source);
assertClean(window.ytInitialPlayerResponse,'new initial object');
window.ytplayer={config:{args:{player_response:nativeStringify(source)}}};
assertClean(nativeParse(window.ytplayer.config.args.player_response),'new serialized config');
window.ytplayer.config.args.player_response=nativeStringify(source);
assertClean(nativeParse(window.ytplayer.config.args.player_response),'updated serialized args');
assertClean(JSON.parse(nativeStringify(source)),'JSON.parse');
reply=nativeStringify({playerResponse:source});
const xhr=new XMLHttpRequest();xhr.open('GET','/youtubei/v1/player');xhr.readyState=4;
assertClean(nativeParse(xhr.responseText).playerResponse,'XHR responseText');
assertClean(nativeParse(xhr.response).playerResponse,'XHR text response');
const jsonXhr=new XMLHttpRequest();jsonXhr.open('GET','/youtubei/v1/player');jsonXhr.readyState=4;jsonXhr.responseType='json';
assertClean(jsonXhr.response.playerResponse,'XHR JSON response');
const ordinary=new XMLHttpRequest();ordinary.open('GET','/other');ordinary.readyState=4;
assert.strictEqual(ordinary.responseText,reply);
assert.strictEqual(isPlayerApi('https://youtube.com.evil.test/youtubei/v1/player'),false);
const unchanged = ' { "response": {"comments":[1,2,3]}, "value": 12345678901234567890 } ';
assert.strictEqual(cleanPlayerText(unchanged), unchanged);
assert.strictEqual(cleanPlayerText('{"description":"adPlacements"}'), '{"description":"adPlacements"}');
const configOnly=' { "playerAds": [], "adPlayback": {}, "adBreakHeartbeatParams": "fixture" } ';
assert.strictEqual(cleanPlayerText(configOnly),configOnly);
const nested=nativeStringify({player_response:nativeStringify(source)});
assertClean(nativeParse(nativeParse(cleanPlayerText(nested)).player_response),'nested serialized response');
assertClean(nativeParse(JSON.parse(nested).player_response),'JSON serialized response');
let revived=JSON.parse('{"x":1}',(key,value)=>key==='x'?2:value);
assert.strictEqual(revived.x,2);

(async()=>{const response=await fetch('/youtubei/v1/next');const data=await response.json();assertClean(data.playerResponse,'fetch JSON response');console.log('PASS: ad placements removed; playback, heartbeat, integrity and signed media preserved across initial objects, args, JSON, XHR and fetch');})().catch(e=>{console.error(e);process.exitCode=1});
"""
        subprocess.run(['node','-e',fixture+YOUTUBE_ADBLOCK_SCRIPT[start:end]+checks],check=True)

if __name__=='__main__':unittest.main()
