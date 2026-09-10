"""Keep cyclic Python/GObject finalization on GTK's owning thread."""
import gc
import threading
from gi.repository import GLib

_gc_source = None
_gc_ticks = 0

def install_main_thread_gc():
    """Automatic GC may run in a DNS worker and finalize a WebKit wrapper there."""
    global _gc_source
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('GTK must be initialized on the main thread')
    if _gc_source is not None:
        return
    gc.disable()
    def collect():
        global _gc_ticks
        _gc_ticks += 1
        gc.collect(2 if _gc_ticks % 15 == 0 else 0)
        return GLib.SOURCE_CONTINUE
    _gc_source = GLib.timeout_add_seconds(2, collect)


def collect_closed_views():
    """Called through the GTK loop after a tab has been detached and destroyed."""
    gc.collect()
    return GLib.SOURCE_REMOVE
