"""Real WebKit recovery from one simulated TLS transport interruption on a search GET.
Isolated profile; certificate validation and real HTTPS stay enabled throughout.
PYTHONPATH=. /usr/bin/python3 tests/network_runtime.py
"""
import os,tempfile,json,time,sys
from unittest.mock import patch
os.environ['GSETTINGS_BACKEND']='memory'
import core.config as cfg
cfg.CONFIG_DIR=tempfile.mkdtemp(prefix='safeer-search112-');cfg.CONFIG_FILE=os.path.join(cfg.CONFIG_DIR,'settings.json')
with open(cfg.CONFIG_FILE,'w') as f:json.dump({'first_run_completed':True,'integrations':{},'doh_enabled':True,'doh_provider':'quad9','force_dark_mode':True},f)
from core.doh_proxy import LocalDoHProxy,DoHResolver
original_resolve=DoHResolver.resolve;original_pipe=LocalDoHProxy._pipe_sockets
permanent='--permanent' in sys.argv
ips=set();state={'interrupted':False,'errors':[],'passed':False,'native_failed':False};started=time.monotonic()
def resolve(self,host,*a,**kw):
 ip=original_resolve(self,host,*a,**kw)
 if host=='duckduckgo.com' and ip:ips.add(ip)
 return ip
def pipe(self,client,remote):
 if remote.getpeername()[0] in ips and (permanent or not state['native_failed']):
  state['interrupted']=True;print('Injected one transport interruption before TLS, no certificate bypass',flush=True);return
 return original_pipe(self,client,remote)
DoHResolver.resolve=resolve;LocalDoHProxy._pipe_sockets=pipe
from core.network_errors import NetworkErrorHandler
original_failed=NetworkErrorHandler.load_failed
def failed(self,view,event,uri,error):
 state['native_failed']=True
 state['errors'].append(error.code)
 print('TRANSPORT_FAILURE',error.domain,error.code,str(error),'method',self.requests.get(uri),flush=True)
 return original_failed(self,view,event,uri,error)
NetworkErrorHandler.load_failed=failed
from safeer_mint import SafeerMintBrowser,Gtk,GLib,WebKit2
with patch.object(SafeerMintBrowser,'setup_ipc_socket',lambda self:None):app=SafeerMintBrowser(initial_url='safeer://home')
app.show_all();wv=app.get_active_webview()
# Force a valid navigation through the same address-entry path users use.
app.config.set('search_engine','duckduckgo')
def start():
 wv.evaluate_javascript("setEngine('duckduckgo');document.getElementById('searchInput').value='test';handleSearch();",-1,None,None,None,None,None)
 return False

def inspect_result(view,res,*args):
 try:data=json.loads(view.evaluate_javascript_finish(res).to_string())
 except Exception:return
 if permanent and data['errorDocument']:
  state['passed']=len(state['errors'])==2 and view._safeer_load_failed and app.security_icon.get_text()=='⚠️'
  print('ERROR_PAGE',json.dumps(data),'bounded retry:',state['passed'],flush=True)
  from gi.repository import Gdk
  pb=Gdk.pixbuf_get_from_window(app.get_window(),0,0,app.get_allocated_width(),app.get_allocated_height());pb.savev('/tmp/safeer-network-error112.png','png',[],[])
  app.destroy();Gtk.main_quit();return
 if data['results']>3 and 'DuckDuckGo' in data['title']:
  state['passed']=state['interrupted'] and state['native_failed'] and not view._safeer_load_failed
  print('SEARCH_RESULT',json.dumps(data),'retry succeeded:',state['passed'],flush=True)
  app.destroy();Gtk.main_quit()

def inspect():
 wv.evaluate_javascript("JSON.stringify({title:document.title,results:document.querySelectorAll('[data-testid=result],.result').length,errorDocument:document.title.includes('mogoče')})",-1,None,None,None,inspect_result,None)
 return True
GLib.timeout_add_seconds(2,start);GLib.timeout_add_seconds(2,inspect)
GLib.timeout_add_seconds(55,lambda:(print('TIMEOUT',state,flush=True),app.destroy(),Gtk.main_quit(),False)[-1])
Gtk.main()
if not state['passed']:raise SystemExit(1)
