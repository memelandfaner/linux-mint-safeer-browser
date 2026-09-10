"""Full browser, renderer, HTTP download and profile smoke; isolated test data only."""
import json, os, pathlib, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
profile=tempfile.TemporaryDirectory(prefix='safeer-smoke-')
os.environ['XDG_CONFIG_HOME']=profile.name
config=pathlib.Path(profile.name)/'safeer-mint'
config.mkdir()
(config/'settings.json').write_text(json.dumps({'first_run_completed':True,'check_default_browser':False,'sidebar_enabled':False,'doh_enabled':False,'session_restore':False}))
sys.path.insert(0,sys.argv[1])
from safeer_mint import SafeerMintBrowser, Gtk, GLib, WebKit2, Gio, ConfigManager
class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        self.send_response(200)
        if self.path=='/download':
            self.send_header('Content-Type','application/octet-stream')
            self.send_header('Content-Disposition','attachment; filename="smoke.txt"')
            body=b'Safeer download fixture'
        else:
            self.send_header('Content-Type','text/html')
            body=b'<html><head><title>Safeer packaging smoke</title></head><body>Safeer</body></html>'
        self.end_headers(); self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
window=SafeerMintBrowser(initial_url=url)
# Exercise the real download handlers, but write only into temporary test storage.
window.get_default_downloads_dir=lambda: profile.name
view=window.get_active_webview()
result={'ok':False,'started':False}
def finish_download(download):
    target=pathlib.Path(profile.name)/'smoke.txt'
    if target.read_bytes()!=b'Safeer download fixture':
        print('FAIL: downloaded bytes differ',flush=True);Gtk.main_quit();return
    window.config.set('packaging_smoke_marker','persistent')
    if ConfigManager().get('packaging_smoke_marker')!='persistent':
        print('FAIL: settings were not persisted',flush=True);Gtk.main_quit();return
    result['ok']=bool(window.web_context.get_sandbox_enabled())
    print('PASS: full browser rendered HTTP, downloaded exact bytes and persisted settings',flush=True)
    print('WebKit sandbox enabled:',window.web_context.get_sandbox_enabled(),flush=True)
    Gtk.main_quit()
def finish_check(webview, event):
    if result['started'] or event!=WebKit2.LoadEvent.FINISHED or webview.get_title()!='Safeer packaging smoke':
        return
    result['started']=True
    download=window.web_context.download_uri(url+'/download')
    download.connect('finished',finish_download)
    download.connect('failed',lambda _d,error: (print('FAIL: download failed:',error.message,flush=True),Gtk.main_quit()))
view.connect('load-changed',finish_check)
view.connect('notify::title',lambda v,p: finish_check(v,WebKit2.LoadEvent.FINISHED))
view.connect('web-process-terminated',lambda _v,reason: (print('FAIL: web process terminated:',reason.value_nick,flush=True),Gtk.main_quit()))
view.connect('load-failed',lambda _v,_e,uri,error: print('load-failed:',uri,error.message,flush=True))
window.show_all()
def timed_out():
    print('FAIL: timeout; title=%r uri=%r download_started=%s' % (view.get_title(),view.get_uri(),result['started']),flush=True)
    import subprocess as _sp
    print(_sp.run(['ps','-eo','pid,ppid,stat,wchan:24,args'],capture_output=True,text=True).stdout.replace('\n','\n  ')[:6000] if True else '',flush=True)
    Gtk.main_quit();return False
print('WebKitGTK %d.%d.%d' % (WebKit2.get_major_version(),WebKit2.get_minor_version(),WebKit2.get_micro_version()),flush=True)
GLib.timeout_add_seconds(30,timed_out)
Gtk.main()
window.destroy()
server.shutdown();server.server_close();profile.cleanup()
raise SystemExit(0 if result['ok'] else 1)
