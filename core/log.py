"""A small rotating log file for the browser's own messages.

The desktop launcher gives the browser no terminal: stdout ends in /dev/null and only stderr
reaches ~/.xsession-errors, so the diagnostics the code prints (a tab's web process stopping,
a filter list failing to compile, a memory limit being hit) were lost. `install()` keeps the
original streams and additionally writes every line to <config dir>/safeer.log, rotated at
1 MB with three backups. Callers keep using print(); nothing else in the code changes.

Only the browser's own messages land here. Page URLs appear only where the code already
prints them; the log is not a browsing history.
"""
import logging
import logging.handlers
import os
import sys
import threading

LOG_NAME = "safeer.log"
_LOGGER_NAME = "safeer"
_installed = False


class _Tee:
    """A text stream that forwards to the original stream and to the logger, line by line."""

    def __init__(self, original, level):
        self._original = original
        self._level = level
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, text):
        try:
            if self._original is not None:
                self._original.write(text)
        except Exception:  # noqa: BLE001 - a closed terminal must not break logging
            pass
        with self._lock:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    logging.getLogger(_LOGGER_NAME).log(self._level, line.rstrip())
        return len(text)

    def flush(self):
        try:
            if self._original is not None:
                self._original.flush()
        except Exception:  # noqa: BLE001
            pass

    def isatty(self):
        try:
            return bool(self._original is not None and self._original.isatty())
        except Exception:  # noqa: BLE001
            return False

    def fileno(self):
        if self._original is None:
            raise OSError("no underlying stream")
        return self._original.fileno()

    @property
    def encoding(self):
        return getattr(self._original, "encoding", "utf-8")


def log_path(config_dir):
    return os.path.join(config_dir, LOG_NAME)


def install(config_dir, app_version=""):
    """Route print() output (stdout and stderr) into the rotating log file as well."""
    global _installed
    if _installed:
        return log_path(config_dir)
    try:
        os.makedirs(config_dir, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path(config_dir), maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname).1s %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(handler)
        sys.stdout = _Tee(sys.__stdout__, logging.INFO)
        sys.stderr = _Tee(sys.__stderr__, logging.WARNING)
        _installed = True
        logger.info("Safeer Browser %s started (pid %d)", app_version, os.getpid())
    except Exception as exc:  # noqa: BLE001 - logging is best effort
        try:
            sys.__stderr__.write(f"[Log] Dnevnika ni bilo mogoče odpreti: {exc}\n")
        except Exception:  # noqa: BLE001
            pass
    return log_path(config_dir)


def event(message, *args):
    """Log a line without going through print (for background threads)."""
    logging.getLogger(_LOGGER_NAME).info(message, *args)
