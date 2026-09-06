"""Isolated real-WebKit login flow regression, without accounts or credentials.
Run from repo root: PYTHONPATH=. /usr/bin/python3 tests/login_runtime.py
"""
import os,tempfile,json,threading,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from unittest.mock import patch
os.environ['GSETTINGS_BACKEND']='memory'
import core.config as cfg
cfg.CONFIG_DIR=tempfile.mkdtemp(prefix='safeer-login-test-')
cfg.CONFIG_FILE=os.path.join(cfg.CONFIG_DIR,'settings.json')
with open(cfg.CONFIG_FILE,'w') as f:json.dump({'first_run_completed':True,'doh_enabled':False,'force_dark_mode':False,'integrations':{'test':{'name':'Test','icon':'T','url':'https://example.org','enabled':True}}},f)
from safeer_mint import SafeerMintBrowser,Gtk,GLib,WebKit2
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):self.serve('GET','')
 def do_POST(self):self.serve('POST',self.rfile.read(int(self.headers.get('Content-Length',0))).decode())
 def serve(self,method,body):
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
  if self.path.startswith('/callback'):
   data={'method':method,'body':body,'query':self.path.split('?',1)[-1], 'cookie':'fixture=yes' in self.headers.get('Cookie','')}
   html='<script>if(window.opener){window.opener.postMessage('+json.dumps(data)+',"*");window.close();}</script>'
  else:
   html='''<html><body><div id="challenge" style="position:fixed;z-index:10000;inset:0"><iframe src="about:blank"></iframe></div><div class="tp-modal" id="login"><form><input name="email"></form></div><div data-component="ad-slot" id="advert">Ad</div><script>document.cookie='fixture=yes; path=/';window.results=[];addEventListener('message',e=>{if(e.origin===location.origin || e.origin===location.origin.replace('127.0.0.1','localhost'))results.push(e.data)});</script></body></html>'''
  self.wfile.write(html.encode())
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:'+str(server.server_port)
with patch.object(SafeerMintBrowser,'setup_ipc_socket',lambda self:None):
 app=SafeerMintBrowser(initial_url=base+'/')
app.show_all();wv=app.get_active_webview();started=False;failure=[]

def finish(message=None):
 if message:failure.append(message)
 app.destroy();Gtk.main_quit();return False

def result(view,res,*args):
 try:
  data=json.loads(view.evaluate_javascript_finish(res).to_string())
  print('LOGIN_RUNTIME',json.dumps(data),flush=True)
  assert len(data['results'])==4,data
  by={item['query'].split('case=')[-1]:item for item in data['results']}
  assert all(by[key]['cookie'] for key in ['direct','delayed','post']),data
  assert by['cross']['cookie'] is False,data
  assert by['post']['method']=='POST' and by['post']['body']=='proof=fixture%2Bbody',data
  assert data['popupsAllowed'] and data['challenge'] and data['login'] and not data['ad'],data
  assert data['blockedAutomatic'] is True,data
  assert len(app.tabs)==1,len(app.tabs)
  finish()
 except Exception as e:finish(str(e))

def inspect():
 wv.evaluate_javascript("JSON.stringify({results, popupsAllowed:!!window.popupOpened,blockedAutomatic:window.blockedAutomatic,challenge:!!document.getElementById('challenge'),login:!!document.getElementById('login'),ad:!!document.getElementById('advert')})",-1,None,None,None,result,None)
 return False

def start(view,event):
 global started
 if event!=WebKit2.LoadEvent.FINISHED or started:return
 started=True
 js="""window.popupOpened=!!window.open('/callback?case=direct','direct');
 window.open(location.origin.replace('127.0.0.1','localhost')+'/callback?case=cross','cross');
 var p=window.open('about:blank','delayed');setTimeout(()=>{if(p)p.location='/callback?case=delayed'},50);
 var f=document.createElement('form');f.method='POST';f.action='/callback?utm_source=fixture&case=post';f.target='post';
 var i=document.createElement('input');i.name='proof';i.value='fixture+body';f.appendChild(i);document.body.appendChild(f);f.submit();
 setTimeout(()=>{window.blockedAutomatic=(window.open('/callback?case=unwanted','unwanted')===null)},2500);
 """
 # WebKit's evaluation API supplies a user gesture, matching a clicked login button.
 view.evaluate_javascript(js,-1,None,None,None,None,None)
 GLib.timeout_add_seconds(7,inspect)
wv.connect('load-changed',start)
GLib.timeout_add_seconds(20,lambda:finish('Runtime timeout'))
Gtk.main();server.shutdown();server.server_close()
if failure:raise SystemExit('FAILED: '+repr(failure))
print('Login popup/opener, POST, cookie, close, challenge and ad-block checks passed')
