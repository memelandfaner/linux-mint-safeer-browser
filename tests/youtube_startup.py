"""Five-song real Safeer/WebKit startup and uninterrupted-playback test.
Isolated profile, ordinary HTTPS + DoH + all shields, no account credentials.
Usage: PYTHONPATH=. /usr/bin/python3 tests/youtube_startup.py /tmp/result.json [IDs...]
One play request per song only; no retries, seeking, or forced quality changes.
"""
import json, os, sys, tempfile, time
from unittest.mock import patch
os.environ['GSETTINGS_BACKEND'] = 'memory'
import core.config as cfg
cfg.CONFIG_DIR = tempfile.mkdtemp(prefix='safeer-startup-')
cfg.CONFIG_FILE = os.path.join(cfg.CONFIG_DIR, 'settings.json')
with open(cfg.CONFIG_FILE, 'w') as f:
    json.dump({'first_run_completed':True,'sidebar_enabled':False,'integrations':{},'doh_enabled':True,'doh_provider':'quad9','window_width':1280,'window_height':820}, f)
from safeer_mint import SafeerMintBrowser, Gtk, GLib, WebKit2, Gdk
if os.environ.get('SAFEER_TEST_NATIVE_UA') == '1':
    import safeer_mint
    safeer_mint.USER_AGENT = None
if os.environ.get('SAFEER_TEST_UA'):
    import safeer_mint
    safeer_mint.USER_AGENT=os.environ['SAFEER_TEST_UA']
out = sys.argv[1]
ids = sys.argv[2:] or ['5NV6Rdv1a3I','4NRXx6U8ABQ','JGwWNGJdvx8','YQHsXMglC9A','VPRjCeoBqrI']
with patch.object(SafeerMintBrowser, 'setup_ipc_socket', lambda self: None):
    app = SafeerMintBrowser(initial_url='about:blank')
app.show_all(); app.sidebar_box.hide()
wv = app.get_active_webview()
if os.environ.get('SAFEER_TEST_SCRIPT'):
    with open(os.environ['SAFEER_TEST_SCRIPT']) as f: extra=f.read()
    wv.get_user_content_manager().add_script(WebKit2.UserScript.new(extra,WebKit2.UserContentInjectedFrames.ALL_FRAMES,WebKit2.UserScriptInjectionTime.START,None,None))
# Passive event recording starts before the page/player JavaScript.
recorder = """(()=>{window.__playbackTest={events:[],timers:[]};const timeout=window.setTimeout;window.setTimeout=function(callback,delay,...args){if(delay>=15000&&delay<=18000)window.__playbackTest.timers.push({delay,native:typeof callback==='function'&&Function.prototype.toString.call(callback).includes('[native code]'),at:performance.now()/1000,stack:new Error().stack.split('\\n').slice(0,5)});return timeout.call(this,callback,delay,...args)};for(const name of ['playing','waiting','stalled','pause','error','loadedmetadata'])document.addEventListener(name,e=>{if(e.target.tagName==='VIDEO')window.__playbackTest.events.push({event:name,at:performance.now()/1000,time:e.target.currentTime});},true)})()"""
wv.get_user_content_manager().add_script(WebKit2.UserScript.new(recorder,WebKit2.UserContentInjectedFrames.TOP_FRAME,WebKit2.UserScriptInjectionTime.START,None,None))
probe = """(()=>{const p=document.getElementById('movie_player'),v=p?.querySelector('video');const vis=e=>!!e&&e.getBoundingClientRect().height>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';let buffers=[];if(v)for(let i=0;i<v.buffered.length;i++)buffers.push([v.buffered.start(i),v.buffered.end(i)]);return JSON.stringify({title:document.title,ua:navigator.userAgent,playerConfigKeys:Object.keys(window.ytInitialPlayerResponse?.playerConfig||{}),videoId:p?.getVideoData?.().video_id,player:!!p?.playVideo,ad:!!p&&(p.classList.contains('ad-showing')||p.classList.contains('ad-interrupting')),adControls:[...document.querySelectorAll('.ytp-ad-text,.ytp-ad-player-overlay,.ytp-ad-skip-button,.ytp-skip-ad-button')].filter(vis).length,adSlots:[...document.querySelectorAll('ytd-ad-slot-renderer,#player-ads')].filter(vis).length,time:v?.currentTime,ready:v?.readyState,paused:v?.paused,error:v?.error?.code,state:p?.getPlayerState?.(),quality:p?.getPlaybackQuality?.(),debug:p?.getStatsForNerds?.()?.debug_info,buffers,stats:window._safeerAdStats||{},events:window.__playbackTest?.events||[],mse:window.__mseTest||[],network:window.__networkTest||[],timers:window.__playbackTest?.timers||[],warning:[...document.querySelectorAll('.ytp-generic-popup,.ytp-error,.ytp-error-content-wrap,.ytp-spinner-message')].filter(vis).map(e=>e.innerText.slice(0,160)),slowResources:performance.getEntriesByType('resource').filter(r=>r.duration>2000).map(r=>({host:new URL(r.name,location.href).hostname,path:new URL(r.name,location.href).pathname,seconds:Math.round(r.duration)/1000,start:Math.round(r.startTime)/1000})),consent:[...document.querySelectorAll('button')].some(b=>b.getBoundingClientRect().height>0&&['Reject all','Zavrni vse'].includes(b.innerText.trim()))})})()"""
trace=[]
if os.environ.get('SAFEER_TEST_TRACE') == '1':
    import urllib.parse
    from core.doh_proxy import DoHResolver
    original_resolve = DoHResolver.resolve
    def timed_resolve(self, hostname, *args, **kwargs):
        t=time.monotonic(); result=original_resolve(self,hostname,*args,**kwargs)
        elapsed=time.monotonic()-t
        if elapsed>.1 or not result:trace.append({'kind':'dns','host':hostname,'seconds':round(elapsed,3),'ok':bool(result)})
        return result
    DoHResolver.resolve=timed_resolve
    def resource_started(view, resource, request):
        epoch=started
        url=urllib.parse.urlsplit(request.get_uri());begin=time.monotonic();query=urllib.parse.parse_qs(url.query)
        if not (url.hostname or '').endswith(('googlevideo.com','youtube.com','googleapis.com')):return
        def done(resource):
            if epoch!=started:return
            response=resource.get_response();elapsed=time.monotonic()-begin
            if elapsed>1 or url.path=='/videoplayback' or (response and response.get_status_code()>=400):
                trace.append({'kind':'resource','host':url.hostname,'path':url.path,'seconds':round(elapsed,3),'status':response.get_status_code() if response else None,'client':query.get('c',[''])[0],'itag':query.get('itag',[''])[0],'pot_present':'pot' in query,'n_present':'n' in query,'start':round(begin-started,3)})
        def failed(resource,error):
            if epoch==started:trace.append({'kind':'resource-failed','host':url.hostname,'path':url.path,'domain':str(error.domain),'code':error.code,'start':round(begin-started,3)})
        resource.connect('failed',failed)
        resource.connect('finished',done)
    wv.connect('resource-load-started',resource_started)
results=[]; samples=[]; idx=-1; started=0; first=None; busy=False; requested=False; accepted=False

def js(code,cb=None):
    wv.evaluate_javascript(code,-1,None,None,None,cb,None)

def finish(reason):
    global busy
    busy=True
    elapsed=time.monotonic()-started
    last=samples[-1] if samples else {}
    stalls=[]
    for s in samples:
        if first is not None and s['elapsed']>first+1 and (s.get('ready',0)<3 or s.get('paused')):
            stalls.append(s['elapsed'])
    result={'id':ids[idx],'title':last.get('title'),'first_play_seconds':first,'observed_seconds':round(elapsed,2),'reason':reason,'post_start_stall_samples':stalls,'ad_samples':sum(bool(s.get('ad') or s.get('adControls') or s.get('adSlots')) for s in samples),'error_samples':sum(bool(s.get('error') or s.get('warning')) for s in samples),'last':last,'samples':samples,'trace':list(trace)}
    result['passed']=reason=='complete' and not result['ad_samples'] and not result['error_samples'] and not stalls and (last.get('time') or 0)>28
    results.append(result)
    with open(out,'w') as f: json.dump(results,f,indent=2)
    print('RESULT',json.dumps({k:v for k,v in result.items() if k not in ('samples','last','trace')}),flush=True)
    try:
        pix=Gdk.pixbuf_get_from_window(app.get_window(),0,0,app.get_allocated_width(),app.get_allocated_height());pix.savev(out+'-'+ids[idx]+'.png','png',[],[])
    except Exception:pass
    GLib.timeout_add(500,next_song)

def next_song():
    global idx,started,first,busy,requested,accepted,samples
    idx+=1
    if idx>=len(ids):
        print('COMPLETE',sum(r['passed'] for r in results),'/',len(results),flush=True)
        app.destroy();Gtk.main_quit();return False
    started=time.monotonic();first=None;requested=False;accepted=False;samples=[];busy=False;trace.clear()
    print('START',ids[idx],flush=True)
    wv.load_uri('https://www.youtube.com/watch?v='+ids[idx]);return False

def sampled(view,res,*args):
    global busy,first,requested,accepted
    busy=False
    elapsed=time.monotonic()-started
    try:s=json.loads(view.evaluate_javascript_finish(res).to_string())
    except Exception:
        if elapsed>90:finish('script timeout')
        return
    s['elapsed']=round(elapsed,2);samples.append(s)
    if os.environ.get('SAFEER_TEST_TRACE') == '1' and len(samples)%10==0:
        with open(out+'.live.json','w') as f:json.dump({'last':s,'trace':trace},f)
    if s.get('consent') and not accepted:
        accepted=True;js("[...document.querySelectorAll('button')].find(b=>b.getBoundingClientRect().height>0&&['Reject all','Zavrni vse'].includes(b.innerText.trim()))?.click()")
    if s.get('player') and s.get('videoId')==ids[idx] and not requested:
        requested=True;js("document.getElementById('movie_player').playVideo()")
    if s.get('videoId')==ids[idx] and (s.get('time') or 0)>.2 and (s.get('ready') or 0)>=3 and not s.get('paused') and not s.get('ad'):
        if first is None:
            first=round(elapsed,2);print('PLAYING',ids[idx],first,flush=True)
    if first is not None and elapsed-first>=32:finish('complete')
    elif elapsed>90:finish('timeout')

def tick():
    global busy
    if idx>=0 and idx<len(ids) and not busy:
        busy=True;js(probe,sampled)
    return True
wv.connect('web-process-terminated',lambda w,r:finish('web process terminated'))
if os.environ.get('SAFEER_TEST_WARMUP') == '1':
    warm_started=time.monotonic();warm_clicked=False;warm_ready=None
    def warmed(view,res,*args):
        global warm_clicked,warm_ready
        try:d=json.loads(view.evaluate_javascript_finish(res).to_string())
        except Exception:d={}
        if d.get('consent') and not warm_clicked:
            warm_clicked=True;warm_ready=None
            js("[...document.querySelectorAll('button')].find(b=>b.getBoundingClientRect().height>0&&['Reject all','Zavrni vse'].includes(b.innerText.trim()))?.click()")
        elif d.get('ready') and not d.get('consent'):
            if warm_ready is None:warm_ready=time.monotonic()
            elif time.monotonic()-warm_ready>3:
                print('WARMUP_COMPLETE',flush=True);next_song();return
        else:warm_ready=None
        if time.monotonic()-warm_started>90:
            print('WARMUP_FAILED',d,flush=True);app.destroy();Gtk.main_quit();return
        GLib.timeout_add(500,warm_tick)
    def warm_tick():
        js("JSON.stringify({host:location.hostname,phase:document.readyState,consent:[...document.querySelectorAll('button')].some(b=>b.getBoundingClientRect().height>0&&['Reject all','Zavrni vse'].includes(b.innerText.trim())),ready:location.hostname==='www.youtube.com'&&document.readyState==='complete'})",warmed)
        return False
    wv.load_uri('https://www.youtube.com/');GLib.timeout_add(500,warm_tick)
else:GLib.timeout_add(500,next_song)
GLib.timeout_add(500,tick);Gtk.main()
if len(results)!=len(ids) or not all(r['passed'] for r in results):raise SystemExit(1)
