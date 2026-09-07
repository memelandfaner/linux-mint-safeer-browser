"""Verify real WebKit script exclusions on the reported xAI redirect URLs."""
import json,os,tempfile
from unittest.mock import patch
os.environ['GSETTINGS_BACKEND']='memory'
import core.config as cfg
cfg.CONFIG_DIR=tempfile.mkdtemp(prefix='safeer-auth-compat-');cfg.CONFIG_FILE=os.path.join(cfg.CONFIG_DIR,'settings.json')
with open(cfg.CONFIG_FILE,'w') as f:json.dump({'first_run_completed':True,'doh_enabled':False,'force_dark_mode':False,'integrations':{}},f)
from safeer_mint import SafeerMintBrowser,Gtk,GLib,WebKit2
with patch.object(SafeerMintBrowser,'setup_ipc_socket',lambda self:None):app=SafeerMintBrowser(initial_url='about:blank')
wv=app.get_active_webview();app.show_all()
urls=['https://accounts.x.ai/check-login?redirect=grok-com&return_to=%2F%3Fq%3DreasoningMode%3Dnone%26voice%3Dfalse','https://grok.com/?reasoningMode=none&voice=false','https://grok.com.evil.example/check-login']
idx=-1;failures=[]
html='<html><body><div id="login" class="tp-modal"><form><input name="email"></form></div><div id="ad" data-component="ad-slot">fixture</div></body></html>'
def next_page():
 global idx
 idx+=1
 if idx==len(urls):app.destroy();Gtk.main_quit();return False
 wv.load_html(html,urls[idx]);return False
def checked(view,res,*_):
 try:
  d=json.loads(view.evaluate_javascript_finish(res).to_string());print('AUTH_COMPAT',idx,d,flush=True)
  assert d['uri']==urls[idx],d
  assert d['guard']==(idx==2) and d['throttler']==(idx==2),d
  assert d['login'],d
  assert d['ad']==(idx<2),d
 except Exception as e:failures.append(str(e))
 GLib.idle_add(next_page)
def inspect():
 wv.evaluate_javascript("JSON.stringify({uri:location.href,guard:!!window._adguard_safeer_active,throttler:!!window._safeer_tab_optimizer,login:!!document.getElementById('login'),ad:!!document.getElementById('ad')})",-1,None,None,None,checked,None);return False
wv.connect('load-changed',lambda w,e:GLib.timeout_add(3300,inspect) if idx>=0 and e==WebKit2.LoadEvent.FINISHED else None)
GLib.idle_add(next_page);GLib.timeout_add_seconds(20,lambda:(failures.append('timeout'),app.destroy(),Gtk.main_quit()) and False)
Gtk.main()
if failures:raise SystemExit(str(failures))
print('PASS xAI/Grok scripts and deceptive host isolation')
