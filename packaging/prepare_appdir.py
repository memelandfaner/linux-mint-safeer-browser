"""Seed dynamic GTK, GI, Python and WebKit resources before ELF dependency resolution."""
import pathlib, shutil, subprocess, sys, sysconfig
root = pathlib.Path(sys.argv[1])
license_packages = set()
triplet = subprocess.check_output(['dpkg-architecture','-qDEB_HOST_MULTIARCH'],text=True).strip()
lib = pathlib.Path('/usr/lib')/triplet

def copy(source, target):
    source=pathlib.Path(source); target=root/target
    if not source.exists():
        raise SystemExit(f'Required runtime resource missing: {source}')
    ownership=subprocess.run(['dpkg-query','-S',str(source)],capture_output=True,text=True)
    for line in ownership.stdout.splitlines():
        if ': ' in line:
            license_packages.update(p.split(':')[0] for p in line.split(': ',1)[0].split(', '))
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.is_dir():
        shutil.copytree(source,target,dirs_exist_ok=True,symlinks=False,
                        ignore=shutil.ignore_patterns('__pycache__','test','tests','config-*','_test*','_xxtest*'))
    else:
        shutil.copy2(source,target)

pyver=f'python{sys.version_info.major}.{sys.version_info.minor}'
copy(sys.executable,'usr/bin/python3')
copy(pathlib.Path('/usr/lib')/pyver,f'usr/lib/{pyver}')
for module in ('gi','cairo'):
    copy(pathlib.Path('/usr/lib/python3/dist-packages')/module,f'usr/lib/python3/dist-packages/{module}')
for sub in ('girepository-1.0','webkit2gtk-4.1','gstreamer-1.0','gstreamer1.0','gdk-pixbuf-2.0','gtk-3.0'):
    copy(lib/sub,f'usr/lib/{triplet}/{sub}')
# GIO TLS and proxy support are dynamically loaded.
for name in ('libgiognutls.so','libgiolibproxy.so'):
    copy(lib/'gio/modules'/name,f'usr/lib/{triplet}/gio/modules/{name}')
for name in ('libwebkit2gtk-4.1.so.0','libjavascriptcoregtk-4.1.so.0','libgtk-3.so.0','libgdk-3.so.0', 'libgirepository-1.0.so.1','libgstreamer-1.0.so.0'):
    copy(lib/name,f'usr/lib/{name}')
copy('/usr/share/glib-2.0/schemas','usr/share/glib-2.0/schemas')
# No glibc, loader, GPU drivers, credentials or host certificate stores are copied.
subprocess.run(['glib-compile-schemas',str(root/'usr/share/glib-2.0/schemas')],check=True)

for package in sorted(license_packages):
    notice=pathlib.Path('/usr/share/doc')/package/'copyright'
    if notice.exists():
        dest=root/'usr/share/doc'/package/'copyright'
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(notice,dest)

# Match the desktop ID and AppStream component ID for AppImage validators.
appid='io.github.memelandfaner.SafeerBrowser'
metadata=root/'usr/share/metainfo'
(metadata/f'{appid}.metainfo.xml').rename(metadata/f'{appid}.appdata.xml')
xml=metadata/f'{appid}.appdata.xml'
xml.write_text(xml.read_text().replace('safeer-browser.desktop',f'{appid}.desktop'))
desktop=root/'usr/share/applications/safeer-browser.desktop'
desktop.rename(desktop.with_name(f'{appid}.desktop'))
