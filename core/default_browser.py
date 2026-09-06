"""Native per-user browser registration for GTK desktops."""
import os
import tempfile
from pathlib import Path
from gi.repository import Gio, GLib

DESKTOP_ID = 'safeer-browser.desktop'
WEB_TYPES = ('x-scheme-handler/http', 'x-scheme-handler/https',
             'text/html', 'application/xhtml+xml')


def _exec_argument(value):
    value = str(value).replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value + '"'


def desktop_entry_text(existing, app_dir):
    """Repair the main group without changing existing launch actions or labels."""
    key = GLib.KeyFile()
    if existing:
        key.load_from_data(existing, len(existing.encode('utf-8')),
                           GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    defaults = {
        'Type': 'Application', 'Name': 'Safeer Browser',
        'Exec': '/usr/bin/python3 ' + _exec_argument(Path(app_dir).resolve() / 'safeer_mint.py') + ' %U',
        'Icon': 'safeer-browser', 'Terminal': 'false',
        'StartupWMClass': 'safeer-browser', 'Categories': 'Network;WebBrowser;',
    }
    for name, value in defaults.items():
        try:
            present = key.get_string('Desktop Entry', name)
        except GLib.Error:
            present = None
        if not present:
            key.set_string('Desktop Entry', name, value)
    try:
        types = list(key.get_string_list('Desktop Entry', 'MimeType'))
    except GLib.Error:
        types = []
    key.set_string_list('Desktop Entry', 'MimeType', list(dict.fromkeys(types + list(WEB_TYPES))))
    # xdg-settings' fix_local_desktop_file can append MimeType to the last action.
    for group in key.get_groups()[0]:
        if group.startswith('Desktop Action ') and 'MimeType' in key.get_keys(group)[0]:
            key.remove_key(group, 'MimeType')
    return key.to_data()[0]


def ensure_desktop_entry(app_dir):
    directory = Path(GLib.get_user_data_dir()) / 'applications'
    path = directory / DESKTOP_ID
    existing_app = Gio.DesktopAppInfo.new(DESKTOP_ID)
    source = path if path.exists() else (
        Path(existing_app.get_filename()) if existing_app is not None else None)
    existing = source.read_text() if source is not None else ''
    updated = desktop_entry_text(existing, app_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != updated:
        if path.exists():
            backup = path.with_suffix('.desktop.safeer-backup')
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
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
    errors = []
    try:
        path = ensure_desktop_entry(app_dir)
        app = Gio.DesktopAppInfo.new_from_filename(str(path))
        if app is None:
            raise RuntimeError('Registracija zaganjalnika Safeer ni uspela.')
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
    except (OSError, GLib.Error, RuntimeError) as error:
        return False, [str(error)]
