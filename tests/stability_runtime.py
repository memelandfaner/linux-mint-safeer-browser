"""Bounded tab/worker allocation regression in a separate, temporary browser profile."""
import gc,json,os,pathlib,resource,sys,tempfile,threading,time
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
profile=tempfile.TemporaryDirectory(prefix='safeer-stability-')
os.environ['XDG_CONFIG_HOME']=profile.name
sys.path.insert(0,sys.argv[1] if len(sys.argv)>1 else str(pathlib.Path(__file__).resolve().parents[1]))
import core.config as cfg
cfg.CONFIG_DIR=str(pathlib.Path(profile.name)/'safeer-mint')
cfg.CONFIG_FILE=str(pathlib.Path(cfg.CONFIG_DIR)/'settings.json')
pathlib.Path(cfg.CONFIG_DIR).mkdir()
pathlib.Path(cfg.CONFIG_FILE).write_text(json.dumps({'first_run_completed':True,'check_default_browser':False,'sidebar_enabled':False,'doh_enabled':False}))
from safeer_mint import SafeerMintBrowser,GLib,Gtk,WebKit2
app=SafeerMintBrowser(initial_url='about:blank')
app.show_all()
stop=threading.Event();collections=[]
def track(phase,info):
    if phase=='start':collections.append(threading.current_thread().name)
gc.callbacks.append(track)
gc.set_threshold(50,5,5)
def allocate():
    while not stop.is_set():
        items=[]
        for _ in range(100):
            obj=[]; obj.append(obj);items.append(obj)
        del items
        time.sleep(.005)
worker=threading.Thread(target=allocate,name='test-network-worker',daemon=True);worker.start()
state={'round':0,'ok':False}
def cycle():
    try:
        tid=app.new_tab('about:blank',switch=True)
        app.close_tab(tid)
        state['round']+=1
        if state['round']<30:return True
        # Restored background tabs must not start network loads until selected.
        deferred=app.new_tab('about:blank',switch=False,defer=True)
        item=next(t for t in app.tabs if t['id']==deferred)
        assert item['webview'].get_uri() is None
        app.switch_to_tab(deferred)
        assert not item.get('deferred')
        app.close_tab(deferred)
        # Terminate only this isolated test renderer; recovery must require a click.
        view=app.get_active_webview()
        view.terminate_web_process()
        app.switch_to_tab(app.active_tab_id)
        GLib.timeout_add(800,finish)
    except Exception as e:
        print('FAIL:',e,flush=True);Gtk.main_quit()
    return False
def finish():
    stop.set();worker.join(timeout=2)
    print('Rounds:',state['round'],'collector threads:',sorted(set(collections)),flush=True)
    assert collections and set(collections)=={'MainThread'},collections
    assert app.get_active_tab().get('crashed')
    assert app.get_active_tab().get('crash_notice') is not None
    notice=app.get_active_tab()['crash_notice']
    button=next(child for child in notice.get_children() if isinstance(child,Gtk.Button))
    button.clicked()
    GLib.timeout_add(1000,recovered)
    return False

def recovered():
    tab=app.get_active_tab()
    if not tab.get('crashed') and tab.get('crash_notice') is None and tab['webview'].get_uri()=='about:blank':
        state['ok']=True
    Gtk.main_quit()
    return False
GLib.timeout_add(100,cycle)
GLib.timeout_add_seconds(15,lambda:(Gtk.main_quit(),False)[1])
Gtk.main();stop.set();worker.join(timeout=2)
app.destroy();gc.callbacks.remove(track);profile.cleanup()
if not state['ok']:raise SystemExit(1)
print('PASS: tab churn, worker allocations and native crash notice; no automatic reload')
