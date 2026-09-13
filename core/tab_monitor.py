"""Per-tab resource accounting from /proc.

Every tab has its own web process. WebKitGTK does not tell the embedder which PID serves
which WebKitWebView, but the processes are our own descendants (UI process -> bwrap ->
WebKitWebProcess) and a tab gets its process the moment it first loads, so the monitor pairs
newly appeared processes with the tabs that started loading since the last sample (oldest
first). Reading a process's `stat` and `statm` costs microseconds, so a two-second sample of
all tabs is free; from it each tab gets a CPU share (of one core) and a resident size in MB.

The monitor does not act on its own. It hands the browser a verdict per tab:

* `hot`   - the tab has been over budget (CPU or memory) for a short while; show it.
* `hog`   - over budget for the patience period; a background tab may be put to sleep.
* `calm`  - within budget.

Media is exempt from being put to sleep (the browser passes `audio=True` for tabs that play
sound), and the active tab is never put to sleep - only shown.

No GTK here: the browser calls `sample()` from its main loop and reads plain data back.
"""
import contextlib
import os
import time
from dataclasses import dataclass, field

CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
PAGE_KB = (os.sysconf("SC_PAGE_SIZE") // 1024) if hasattr(os, "sysconf") else 4


@dataclass
class TabSample:
    tab_id: str
    pid: int = 0
    cpu: float = 0.0            # share of one core, 0.0-1.0 (can exceed 1.0 for multi-threaded pages)
    rss_mb: int = 0
    threads: int = 0
    active: bool = False
    audio: bool = False
    over_since: float = None    # monotonic time when the tab first went over budget (None = within budget)
    verdict: str = "calm"       # calm | hot | hog

    @property
    def over_for(self):
        return (time.monotonic() - self.over_since) if self.over_since is not None else 0.0


@dataclass
class _ProcessReading:
    ticks: int
    at: float


WEB_PROCESS_COMM = b"WebKitWebProces"  # /proc/<pid>/comm is cut at 15 characters


def web_processes_under(root_pid, proc="/proc"):
    """PIDs of the WebKitWebProcess descendants of root_pid (bwrap and xdg-dbus-proxy sit in between)."""
    found = []
    stack = [int(root_pid)]
    seen = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        try:
            with open(f"{proc}/{pid}/task/{pid}/children", "rb") as handle:
                kids = [int(x) for x in handle.read().split()]
        except (OSError, ValueError):
            continue
        for kid in kids:
            try:
                with open(f"{proc}/{kid}/comm", "rb") as handle:
                    comm = handle.read().strip()
            except OSError:
                continue
            if comm == WEB_PROCESS_COMM:
                found.append(kid)
            else:
                stack.append(kid)
    return found


@dataclass
class TabMonitor:
    cpu_budget: float = 0.5          # share of one core a tab may use for long
    memory_budget_mb: int = 1024     # resident size a tab may keep for long
    show_after: float = 10.0         # seconds over budget before the tab is marked hot
    patience: float = 60.0           # seconds over budget before a background tab is a hog
    proc: str = "/proc"
    root_pid: int = 0                # the UI process; 0 = this process
    _last: dict = field(default_factory=dict)      # pid -> _ProcessReading
    _state: dict = field(default_factory=dict)     # tab_id -> TabSample
    _pid_of: dict = field(default_factory=dict)    # tab_id -> pid (attributed)
    _ignored: set = field(default_factory=set)     # auxiliary web views (sidebar, keyboard): never paired with a tab

    def __post_init__(self):
        # Whatever already runs when the monitor starts belongs to auxiliary views, not to tabs.
        self._ignored = set(web_processes_under(self.root_pid or os.getpid(), self.proc))

    @contextlib.contextmanager
    def auxiliary(self):
        """Wrap the creation/first load of a helper WebView so its process is never paired with a tab."""
        root = self.root_pid or os.getpid()
        before = set(web_processes_under(root, self.proc))
        try:
            yield
        finally:
            self._ignored |= set(web_processes_under(root, self.proc)) - before

    # ---- reading /proc -------------------------------------------------
    def _read_stat(self, pid):
        """Return (utime+stime ticks, threads) or None if the process is gone."""
        try:
            with open(f"{self.proc}/{pid}/stat", "rb") as handle:
                raw = handle.read()
        except OSError:
            return None
        # The command name may contain spaces or parentheses; fields start after the last ')'.
        fields = raw.rsplit(b")", 1)[1].split()
        try:
            return int(fields[11]) + int(fields[12]), int(fields[17])
        except (IndexError, ValueError):
            return None

    def _read_rss_mb(self, pid):
        try:
            with open(f"{self.proc}/{pid}/statm", "rb") as handle:
                fields = handle.read().split()
            return int(fields[1]) * PAGE_KB // 1024
        except (OSError, IndexError, ValueError):
            return 0

    # ---- pairing tabs with processes ------------------------------------
    def pid_of(self, tab_id):
        return self._pid_of.get(tab_id, 0)

    def attribute(self, wanting, live_pids):
        """Pair tabs that want a process (list of (tab_id, since), oldest first) with processes
        that appeared since the last sample. Drops pairings whose process is gone."""
        live = set(live_pids)
        self._ignored &= live
        for tab_id, pid in list(self._pid_of.items()):
            if pid not in live:
                del self._pid_of[tab_id]
        known = set(self._pid_of.values()) | self._ignored
        fresh = sorted(pid for pid in live if pid not in known)
        matched = {}
        for (tab_id, _since), pid in zip(sorted(wanting, key=lambda item: item[1]), fresh):
            self._pid_of[tab_id] = pid
            matched[tab_id] = pid
        return matched

    # ---- sampling --------------------------------------------------------
    def sample(self, tabs, now=None):
        """`tabs`: iterable of (tab_id, wants_since, active, audio) where wants_since is the
        monotonic time the tab started loading without a known process (None = has one or
        needs none). Returns {tab_id: TabSample}."""
        now = time.monotonic() if now is None else now
        tabs = list(tabs)
        live = web_processes_under(self.root_pid or os.getpid(), self.proc)
        self.attribute([(tab_id, since) for tab_id, since, _a, _s in tabs if since is not None], live)
        seen_pids = set()
        result = {}
        for tab_id, _since, active, audio in tabs:
            previous = self._state.get(tab_id)
            pid = self._pid_of.get(tab_id, 0)
            sample = TabSample(tab_id=tab_id, pid=pid, active=bool(active), audio=bool(audio))
            if previous is not None:
                sample.over_since = previous.over_since
            if sample.pid > 0:
                stat = self._read_stat(sample.pid)
                if stat is not None:
                    ticks, sample.threads = stat
                    seen_pids.add(sample.pid)
                    last = self._last.get(sample.pid)
                    if last is not None and now > last.at:
                        sample.cpu = max(0.0, (ticks - last.ticks) / CLK_TCK / (now - last.at))
                    self._last[sample.pid] = _ProcessReading(ticks, now)
                    sample.rss_mb = self._read_rss_mb(sample.pid)
            over = sample.cpu >= self.cpu_budget or sample.rss_mb >= self.memory_budget_mb
            if over:
                if sample.over_since is None:
                    sample.over_since = now
            else:
                sample.over_since = None
            over_for = (now - sample.over_since) if sample.over_since is not None else 0.0
            if over_for >= self.patience:
                sample.verdict = "hog"
            elif over_for >= self.show_after:
                sample.verdict = "hot"
            else:
                sample.verdict = "calm"
            result[tab_id] = sample
        # Forget processes and tabs that are gone.
        self._last = {pid: reading for pid, reading in self._last.items() if pid in seen_pids}
        self._state = result
        return result

    def forget(self, tab_id):
        self._state.pop(tab_id, None)
        self._pid_of.pop(tab_id, None)

    def snapshot(self):
        return dict(self._state)


def describe(sample, lang="sl"):
    """Short human text for a tooltip: 'CPU 74 % · 1,2 GB'."""
    cpu = f"{int(round(sample.cpu * 100))} %"
    if sample.rss_mb >= 1024:
        mem = (f"{sample.rss_mb / 1024:.1f} GB").replace(".", "," if lang == "sl" else ".")
    else:
        mem = f"{sample.rss_mb} MB"
    return f"CPU {cpu} · {mem}"
