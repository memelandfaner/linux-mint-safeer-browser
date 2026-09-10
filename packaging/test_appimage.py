"""Extract and exercise an AppImage with its own Python and library environment."""
import os, pathlib, subprocess, sys, tempfile
repo=pathlib.Path(__file__).resolve().parents[1]
artifact=pathlib.Path(sys.argv[1]).resolve()
subprocess.run([str(artifact),'--version'],check=True)
with tempfile.TemporaryDirectory(prefix='safeer-appimage-test-') as directory:
    subprocess.run([str(artifact),'--appimage-extract'],cwd=directory,stdout=subprocess.DEVNULL,check=True)
    appdir=pathlib.Path(directory)/'squashfs-root'
    runner=appdir/'.smoke-run'
    content=(appdir/'AppRun').read_text()
    entry='exec "$APPDIR/usr/bin/safeer" "$@"'
    if content.count(entry)!=1:
        raise SystemExit('Unrecognized AppRun entry point')
    runner.write_text(content.replace(entry,'exec "$PYTHON" "$@"'))
    runner.chmod(0o755)
    smoke=[str(repo/'packaging/smoke.py'),str(appdir/'usr/lib/safeer-browser')]
    if subprocess.run([str(runner),*smoke],timeout=45).returncode!=0:
        # Diagnostics only: find which AppRun variable breaks the bundled runtime. Never used for release.
        variants={'LD_LIBRARY_PATH':['LD_LIBRARY_PATH'],'GIO_MODULE_DIR':['GIO_MODULE_DIR'],
                  'GSETTINGS_SCHEMA_DIR':['GSETTINGS_SCHEMA_DIR'],'GST':['GST_PLUGIN_SYSTEM_PATH','GST_PLUGIN_SCANNER'],
                  'WEBKIT_EXEC_PATH':['WEBKIT_EXEC_PATH','WEBKIT_INJECTED_BUNDLE_PATH'],'GTK_USE_PORTAL':['GTK_USE_PORTAL'],
                  'XDG_DATA_DIRS':['XDG_DATA_DIRS'],
                  'ALL_RUNTIME_PATHS':['LD_LIBRARY_PATH','GIO_MODULE_DIR','GSETTINGS_SCHEMA_DIR','GST_PLUGIN_SYSTEM_PATH','GST_PLUGIN_SCANNER','WEBKIT_EXEC_PATH','WEBKIT_INJECTED_BUNDLE_PATH','GTK_USE_PORTAL','XDG_DATA_DIRS']}
        for label,names in variants.items():
            variant=appdir/f'.smoke-without-{label}'
            text=runner.read_text().replace('exec "$PYTHON" "$@"','unset '+' '.join(names)+'\nexec "$PYTHON" "$@"')
            variant.write_text(text);variant.chmod(0o755)
            try:
                code=subprocess.run([str(variant),*smoke],timeout=45,capture_output=True,text=True).returncode
            except subprocess.TimeoutExpired:
                code='timeout'
            print(f'DIAGNOSTIC without {label}: exit {code}',flush=True)
        raise SystemExit('AppImage smoke failed')
