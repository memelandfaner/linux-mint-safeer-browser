"""Native per-user browser registration for GTK desktops."""
import os
import tempfile
from pathlib import Path
from gi.repository import Gio, GLib

DESKTOP_ID = 'safeer-browser.desktop'
WEB_TYPES = ('x-scheme-handler/http', 'x-scheme-handler/https',
             'text/html', 'application/xhtml+xml')


_EXEC_RESERVED = set(' \t"\'\\><~|&;$*?#()`%')


def _exec_argument(value):
    """Quote an Exec argument only when the Desktop Entry spec requires it.

    xdg-utils (xdg-open, xdg-mime, xdg-settings) take the first word of Exec literally, quotes
    included, to find the program - a quoted "/usr/bin/safeer" is "not found" there and the
    entry is skipped in favour of the next browser. Plain paths therefore stay unquoted."""
    value = str(value)
    if not any(char in _EXEC_RESERVED for char in value):
        return value
    value = value.replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value + '"'


def launcher_command(app_dir):
    """The command that starts *this* install: the packaged launcher next to the payload
    (/usr/lib/safeer-browser -> /usr/bin/safeer) when it exists, else python3 with safeer_mint.py."""
    app_dir = Path(app_dir).resolve()
    launcher = app_dir.parent.parent / 'bin' / 'safeer'
    if launcher.is_file() and os.access(launcher, os.X_OK):
        return _exec_argument(launcher)
    return '/usr/bin/python3 ' + _exec_argument(app_dir / 'safeer_mint.py')


def _exec_program(exec_line):
    """Resolved path of the program an Exec line starts, or None when it cannot run.

    GLib refuses to load a desktop entry whose program does not exist (GDesktopAppInfo returns
    NULL), which is exactly what a leftover entry from an uninstalled checkout looks like."""
    try:
        _ok, argv = GLib.shell_parse_argv(exec_line or '')
    except GLib.Error:
        return None
    if not argv:
        return None
    program = argv[0]
    if os.path.isabs(program):
        return program if os.access(program, os.X_OK) else None
    return GLib.find_program_in_path(program)


def _starts_this_install(exec_line, app_dir):
    """True when the Exec line runs this install's launcher or its safeer_mint.py."""
    program = _exec_program(exec_line)
    if program is None:
        return False
    try:
        _ok, argv = GLib.shell_parse_argv(exec_line)
    except GLib.Error:
        return False
    app_dir = Path(app_dir).resolve()
    launcher = app_dir.parent.parent / 'bin' / 'safeer'
    try:
        if Path(program).resolve() == launcher.resolve():
            return True
    except OSError:
        pass
    words = [w for w in argv[1:] if not w.startswith('%')]
    return any(Path(w).resolve() == (app_dir / 'safeer_mint.py') for w in words if os.path.isabs(w))


def desktop_entry_text(existing, app_dir):
    """Repair the main group without changing existing launch actions or labels.

    Exec is rewritten whenever it would not start this install - a program that no longer
    exists, or another checkout of Safeer - since a broken Exec makes the whole entry
    unloadable and a foreign one would make the wrong Safeer the default."""
    key = GLib.KeyFile()
    if existing:
        key.load_from_data(existing, len(existing.encode('utf-8')),
                           GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    command = launcher_command(app_dir)
    defaults = {
        'Type': 'Application', 'Name': 'Safeer Browser',
        'Exec': command + ' %U',
        'Icon': 'safeer-browser', 'Terminal': 'false',
        'StartupWMClass': 'safeer-browser', 'Categories': 'Network;WebBrowser;',
    }
    for name, value in defaults.items():
        try:
            present = key.get_string('Desktop Entry', name)
        except GLib.Error:
            present = None
        # Exec is ours to own: anything but the canonical command (a removed or foreign launcher,
        # or a needlessly quoted path that xdg-utils cannot resolve) is replaced.
        if not present or (name == 'Exec' and present != value):
            key.set_string('Desktop Entry', name, value)
    try:
        types = list(key.get_string_list('Desktop Entry', 'MimeType'))
    except GLib.Error:
        types = []
    key.set_string_list('Desktop Entry', 'MimeType', list(dict.fromkeys(types + list(WEB_TYPES))))
    # xdg-settings' fix_local_desktop_file can append MimeType to the last action.
    for group in key.get_groups()[0]:
        if not group.startswith('Desktop Action '):
            continue
        if 'MimeType' in key.get_keys(group)[0]:
            key.remove_key(group, 'MimeType')
        try:
            action_exec = key.get_string(group, 'Exec')
        except GLib.Error:
            action_exec = None
        if action_exec and (_exec_program(action_exec) is None or action_exec.startswith('"')):
            key.set_string(group, 'Exec', command)  # uninstalled launcher, or quoting xdg-utils cannot read
    return key.to_data()[0]


def _packaged_entry_for(app_dir):
    """Path of a system-wide safeer-browser.desktop that starts this install, or None."""
    user_dir = Path(GLib.get_user_data_dir()) / 'applications'
    for data_dir in GLib.get_system_data_dirs():
        candidate = Path(data_dir) / 'applications' / DESKTOP_ID
        if not candidate.is_file() or candidate.parent == user_dir:
            continue
        try:
            key = GLib.KeyFile()
            key.load_from_file(str(candidate), GLib.KeyFileFlags.NONE)
            if _starts_this_install(key.get_string('Desktop Entry', 'Exec'), app_dir):
                return candidate
        except GLib.Error:
            continue
    return None


def _back_up(path):
    backup = path.with_suffix('.desktop.safeer-backup')
    if not backup.exists():
        backup.write_bytes(path.read_bytes())


def ensure_desktop_entry(app_dir):
    """Return the desktop entry that registers this install, repairing or retiring a per-user one.

    A packaged install has its entry in /usr/share/applications; a stale per-user copy (left by
    an earlier checkout) would shadow it in menus and cannot even be loaded once its launcher
    is gone, so it is backed up and removed. Without a packaged entry (a development checkout)
    the per-user entry is written, or repaired so that it starts this install."""
    directory = Path(GLib.get_user_data_dir()) / 'applications'
    path = directory / DESKTOP_ID
    packaged = _packaged_entry_for(app_dir)
    if packaged is not None:
        if path.exists():
            _back_up(path)
            path.unlink()
        return packaged
    existing_app = Gio.DesktopAppInfo.new(DESKTOP_ID)
    source = path if path.exists() else (
        Path(existing_app.get_filename()) if existing_app is not None else None)
    existing = source.read_text() if source is not None else ''
    updated = desktop_entry_text(existing, app_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != updated:
        if path.exists():
            _back_up(path)
        fd, temporary = tempfile.mkstemp(prefix='.safeer-', suffix='.desktop', dir=directory)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(updated)
            os.chmod(temporary, 0o644)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return path


def is_default_browser():
    for content_type in WEB_TYPES:
        app = Gio.AppInfo.get_default_for_type(content_type, False)
        if app is None or app.get_id() != DESKTOP_ID:
            return False
    return True


def set_default_browser(app_dir):
    if os.environ.get("FLATPAK_ID") or os.environ.get("APPIMAGE") or os.environ.get("SAFEER_PORTABLE"):
        return False, ["Izberite Safeer v sistemskih nastavitvah privzetih aplikacij. / Select Safeer in your desktop default-app settings."]
    errors = []
    try:
        path = ensure_desktop_entry(app_dir)
        try:
            app = Gio.DesktopAppInfo.new_from_filename(str(path))
        except TypeError:  # PyGObject raises this when GLib returns NULL (entry it will not load)
            app = None
        if app is None:
            raise RuntimeError(f'Zaganjalnika Safeer ni mogoče naložiti: {path}')
        for content_type in WEB_TYPES:
            try:
                if not app.set_as_default_for_type(content_type):
                    errors.append(content_type)
            except GLib.Error as error:
                errors.append(f'{content_type}: {error.message}')
        success = is_default_browser()
        if not success and not errors:
            errors.append('Sistem ni potrdil vseh povezav HTTP/HTTPS in spletnih datotek.')
        return success, errors
    except (OSError, GLib.Error, RuntimeError, TypeError, ValueError) as error:
        return False, [str(error)]
