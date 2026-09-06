"""Live full-application playback/ad regression. Uses an isolated profile, no credentials.
Run from repo root: PYTHONPATH=. /usr/bin/python3 tests/youtube_live.py
Optional argv video IDs replace the default ten. Writes /tmp/safeer-youtube112-results.json.
"""
import os,tempfile,json,time,sys
from unittest.mock import patch
os.environ['GSETTINGS_BACKEND']='memory'
import core.config as cfg
cfg.CONFIG_DIR=tempfile.mkdtemp(prefix='safeer-youtube112-')
cfg.CONFIG_FILE=os.path.join(cfg.CONFIG_DIR,'settings.json')
with open(cfg.CONFIG_FILE,'w') as f:json.dump({'first_run_completed':True,'sidebar_enabled':False,'integrations':{},'doh_enabled':True,'doh_provider':'quad9','window_width':1280,'window_height':820,'force_dark_mode':False},f)
from safeer_mint import SafeerMintBrowser,Gtk,GLib,WebKit2,Gdk
with patch.object(SafeerMintBrowser,'setup_ipc_socket',lambda self:None):
 app=SafeerMintBrowser(initial_url='about:blank')
app.show_all();app.sidebar_box.hide();wv=app.get_active_webview()
ids=sys.argv[1:] or ['RQUgq9pqmII','5NV6Rdv1a3I','dQw4w9WgXcQ','4NRXx6U8ABQ','JGwWNGJdvx8','YQHsXMglC9A','9bZkp7q19f0','OPf0YbXqDm0','nfWlot6h_JM','VPRjCeoBqrI']
results=[]
if os.environ.get('SAFEER_TEST_RESUME') == '1':
 with open('/tmp/safeer-youtube112-results.json') as f: results=json.load(f)
 completed={r['video_id'] for r in results if r['passed']}
 ids=[v for v in ids if v not in completed]
expected_count=len(ids)+len(results)
idx=-1;started=0;busy=False;samples=[];seeked=False;seek_at=0;play_at=None
probe="""(()=>{let p=document.getElementById('movie_player'),v=document.querySelector('video');let vis=e=>!!e&&e.getBoundingClientRect().height>0&&getComputedStyle(e).display!=='none';return JSON.stringify({title:document.title,active:!!window._safeer_linux_yt_active,stats:window._safeerAdStats||{},ad:!!p&&(p.classList.contains('ad-showing')||p.classList.contains('ad-interrupting')),adControls:Array.from(document.querySelectorAll('.ytp-ad-text,.ytp-ad-preview-container,.ytp-ad-player-overlay,.ytp-ad-skip-button,.ytp-skip-ad-button')).filter(vis).map(e=>e.className),time:v&&v.currentTime,duration:v&&v.duration,ready:v&&v.readyState,paused:v&&v.paused,error:v&&v.error&&v.error.code,playerError:Array.from(document.querySelectorAll('.ytp-error-content-wrap,.ytp-error')).filter(vis).map(e=>e.innerText.slice(0,150)),adSlots:Array.from(document.querySelectorAll('ytd-ad-slot-renderer,#player-ads')).filter(vis).length,images:Array.from(document.images).filter(i=>i.naturalWidth>0).length})})()"""

def runjs(js,callback=None):wv.evaluate_javascript(js,-1,None,None,None,callback,None)
def finish_video(reason):
 global busy
 if idx<0:return
 active_samples=[s for s in samples if (s.get('time') or 0) and (s.get('ready') or 0)>=3 and not s.get('ad')]
 result={'video_id':ids[idx],'seconds':round(time.monotonic()-started,1),'reason':reason,'playback_samples':len(active_samples),'ad_samples':sum(bool(s.get('ad')) for s in samples),'seek_tested':seeked,'last':samples[-1] if samples else {},'samples':samples}
 result['passed']=reason=='complete' and len(active_samples)>=15 and not any(s.get('ad') or s.get('error') or s.get('playerError') for s in samples) and result['last'].get('adSlots')==0
 results.append(result)
 with open('/tmp/safeer-youtube112-results.json','w') as f:json.dump(results,f,indent=2)
 print('VIDEO_RESULT',json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
 try:
  pb=Gdk.pixbuf_get_from_window(app.get_window(),0,0,app.get_allocated_width(),app.get_allocated_height());pb.savev('/tmp/safeer-youtube112-'+ids[idx]+'.png','png',[],[])
 except Exception:pass
 busy=True
 GLib.timeout_add(300,next_video)

def next_video():
 global idx,started,busy,samples,seeked,seek_at,play_at
 idx+=1
 if idx>=len(ids):
  print('COMPLETE',sum(r['passed'] for r in results),'/',len(results),flush=True)
  app.destroy();Gtk.main_quit();return False
 started=time.monotonic();samples=[];seeked=False;seek_at=0;play_at=None;busy=False
 print('START',idx+1,ids[idx],flush=True)
 wv.load_uri('https://www.youtube.com/watch?v='+ids[idx]);return False

def sampled(view,res,*args):
 global busy,seeked,seek_at,play_at
 busy=False
 try:s=json.loads(view.evaluate_javascript_finish(res).to_string())
 except Exception as e:
  if time.monotonic()-started>90:finish_video('script unavailable')
  return
 elapsed=time.monotonic()-started;s['elapsed']=round(elapsed,1);samples.append(s)
 # Reject optional consent in this test profile only; start through the site's own player.
 if not s.get('time') or s.get('paused'):
  runjs("Array.from(document.querySelectorAll('button')).find(b=>['Reject all','Zavrni vse'].includes(b.innerText.trim()))?.click();document.getElementById('movie_player')?.playVideo();")
 if (s.get('time') or 0)>1 and (s.get('ready') or 0)>=3 and not s.get('ad'):
  if play_at is None:play_at=elapsed
  if not seeked and elapsed-play_at>=18 and (s.get('duration') or 0)>90:
   seeked=True;seek_at=elapsed
   runjs("var p=document.getElementById('movie_player'),v=document.querySelector('video');if(p&&v&&Number.isFinite(v.duration))p.seekTo(Math.min(v.duration*0.45,600),true);")
  if seeked and elapsed-seek_at>=20:finish_video('complete');return
 if elapsed>90:finish_video('timeout');return

def tick():
 global busy
 if idx<0 or busy:return True
 busy=True;runjs(probe,sampled);return True
wv.connect('web-process-terminated',lambda w,r:finish_video('web process terminated'))
GLib.timeout_add(300,next_video);GLib.timeout_add_seconds(1,tick)
Gtk.main()
if not all(r['passed'] for r in results) or len(results)!=expected_count:raise SystemExit(1)
