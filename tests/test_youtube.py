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

if __name__=='__main__':unittest.main()
