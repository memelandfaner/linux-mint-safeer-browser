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
let reply='';window.fetch=()=>Promise.resolve(new Response(reply,{status:200,headers:{'content-type':'application/json'}}));
class XMLHttpRequest {open(){} get responseText(){return reply} get response(){return reply}}
window.XMLHttpRequest=XMLHttpRequest;
"""
        checks=r"""
const source={adPlacements:[{}],playerAds:[{}],adSlots:[{}],adBreakHeartbeatParams:'ad',videoDetails:{videoId:'fixture'},streamingData:{formats:[{url:'https://cdn.test/media?sig=abc&x=1'}]}};
window.ytInitialPlayerResponse=structuredClone(source);
assert(!('adPlacements' in window.ytInitialPlayerResponse));
assert(!('adBreakHeartbeatParams' in window.ytInitialPlayerResponse));
assert.strictEqual(window.ytInitialPlayerResponse.streamingData.formats[0].url,source.streamingData.formats[0].url);
window.ytplayer={config:{args:{player_response:nativeStringify(source)}}};
assert(!nativeParse(window.ytplayer.config.args.player_response).playerAds);
window.ytplayer.config.args.player_response=nativeStringify(source);
assert(!nativeParse(window.ytplayer.config.args.player_response).adSlots);
reply=nativeStringify({playerResponse:source});
const xhr=new XMLHttpRequest();xhr.open('GET','/youtubei/v1/player');xhr.readyState=4;
assert(!nativeParse(xhr.responseText).playerResponse.adPlacements);
const ordinary=new XMLHttpRequest();ordinary.open('GET','/other');ordinary.readyState=4;
assert.strictEqual(ordinary.responseText,reply);
assert.strictEqual(isPlayerApi('https://youtube.com.evil.test/youtubei/v1/player'),false);
(async()=>{const response=await fetch('/youtubei/v1/next');const data=await response.json();assert(!data.playerResponse.adBreakHeartbeatParams);assert(data.playerResponse.streamingData);console.log('PASS: direct initial objects, late assignments, serialized config, fetch.json and XHR; media preserved');})().catch(e=>{console.error(e);process.exitCode=1});
"""
        subprocess.run(['node','-e',fixture+YOUTUBE_ADBLOCK_SCRIPT[start:end]+checks],check=True)

if __name__=='__main__':unittest.main()
