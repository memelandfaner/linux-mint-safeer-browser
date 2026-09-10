#!/usr/bin/env python3
"""Build and verify Safeer Browser for Windows.

Commands (run from any directory):
  icon            create build/windows/safeer.ico from assets/icon.png
  smoke-source    run the end-to-end smoke test from the Python sources
  pyinstaller     build build/windows/dist/SafeerBrowser/SafeerBrowser.exe
  smoke-frozen    run the smoke test against the built executable
  package         portable ZIP + Inno Setup installer + SHA256SUMS in build/windows/out
  install-test    silent install, registry check, launch smoke, silent uninstall
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WINDOWS = os.path.join(ROOT, "windows")
BUILD = os.path.join(ROOT, "build", "windows")
DIST = os.path.join(BUILD, "dist")
APP_DIR = os.path.join(DIST, "SafeerBrowser")
EXE = os.path.join(APP_DIR, "SafeerBrowser.exe")
OUT = os.path.join(BUILD, "out")
ICON = os.path.join(BUILD, "safeer.ico")

SHARED_DATA = [
    ("core/adblock.py", "shared/core"),
    ("core/config.py", "shared/core"),
    ("core/bookmarks_importer.py", "shared/core"),
    ("core/reader.py", "shared/core"),
    ("ui/home.html", "shared/ui"),
    ("ui/home.css", "shared/ui"),
    ("ui/home.js", "shared/ui"),
    ("assets/safeer-mark.svg", "shared/assets"),
    ("assets/icon.png", "shared/assets"),
    ("windows/VERSION", "shared/windows"),
]


def version() -> str:
    with open(os.path.join(WINDOWS, "VERSION"), encoding="utf-8") as handle:
        return handle.read().strip()


def run(command, **kwargs) -> None:
    print("+", " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def make_icon() -> str:
    from PIL import Image

    os.makedirs(BUILD, exist_ok=True)
    image = Image.open(os.path.join(ROOT, "assets", "icon.png")).convert("RGBA")
    image.save(ICON, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon:", ICON)
    return ICON


def pyinstaller() -> None:
    make_icon()
    shutil.rmtree(DIST, ignore_errors=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "SafeerBrowser", "--icon", ICON,
        "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"), "--specpath", BUILD,
        "--paths", WINDOWS,
        "--hidden-import", "safeer_windows.smoke",
        "--exclude-module", "tkinter",
        "--exclude-module", "PIL",  # only used by the build and CI screenshots
    ]
    for source, target in SHARED_DATA:
        command += ["--add-data", os.path.join(ROOT, *source.split("/")) + os.pathsep + target]
    command.append(os.path.join(WINDOWS, "launcher.py"))
    run(command)
    if not os.path.exists(EXE):
        raise SystemExit(f"missing {EXE}")
    webengine = [name for name in os.listdir(os.path.join(APP_DIR, "_internal", "PySide6"))] \
        if os.path.isdir(os.path.join(APP_DIR, "_internal", "PySide6")) else []
    print("bundled PySide6 entries:", len(webengine))
    helper = [os.path.join(dirpath, name) for dirpath, _dirs, files in os.walk(APP_DIR) for name in files
              if name.lower() == "qtwebengineprocess.exe"]
    if not helper:
        raise SystemExit("QtWebEngineProcess.exe was not bundled")
    print(f"built {EXE} ({dir_size(APP_DIR) / 1048576:.0f} MB); helper: {helper[0]}")
    prune_bundle()


def dir_size(path: str) -> int:
    return sum(os.path.getsize(os.path.join(d, f)) for d, _s, files in os.walk(path) for f in files)


# Qt plugin folders a Qt WebEngine widgets browser never loads.
UNUSED_PLUGIN_DIRS = {
    "assetimporters", "canbus", "designer", "geometryloaders", "help", "multimedia", "platforminputcontexts",
    "qmllint", "qmltooling", "renderers", "renderplugins", "sceneparsers", "scxmldatamodel", "sensors",
    "sqldrivers", "texttospeech", "virtualkeyboard", "webview", "3dinputdevices", "generic",
}


def pe_imports(path: str) -> set:
    import pefile  # shipped with PyInstaller on Windows

    pe = pefile.PE(path, fast_load=True)
    try:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                                               pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
        names = set()
        for attribute in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
            for entry in getattr(pe, attribute, None) or []:
                names.add(entry.dll.decode("ascii", "ignore").lower())
        return names
    finally:
        pe.close()


def prune_bundle() -> None:
    """Removes Qt modules (Qt 3D, Quick Controls, QML plugins ...) that nothing in the browser loads.

    Roots are every executable, every collected PySide6 extension module (they import each other at
    runtime), every kept Qt plugin and every non-Qt library; a Qt6*.dll stays when a root reaches it
    through PE import tables, so the removals cannot break loading.
    """
    pyside = os.path.join(APP_DIR, "_internal", "PySide6")
    if not os.path.isdir(pyside):
        print("prune: PySide6 folder not found, skipped")
        return
    before = dir_size(APP_DIR)
    shutil.rmtree(os.path.join(pyside, "qml"), ignore_errors=True)
    resources = os.path.join(pyside, "resources")
    if os.path.isdir(resources):
        for name in os.listdir(resources):
            if name.lower().endswith(".debug.pak"):  # developer-build DevTools resources, never loaded
                os.remove(os.path.join(resources, name))
    plugins = os.path.join(pyside, "plugins")
    if os.path.isdir(plugins):
        for name in os.listdir(plugins):
            if name.lower() in UNUSED_PLUGIN_DIRS:
                shutil.rmtree(os.path.join(plugins, name), ignore_errors=True)
    binaries = {}
    for dirpath, _dirs, files in os.walk(APP_DIR):
        for name in files:
            if name.lower().endswith((".dll", ".pyd", ".exe")):
                binaries.setdefault(name.lower(), os.path.join(dirpath, name))
    roots = []
    for name, path in binaries.items():
        inside_pyside = os.path.abspath(path).lower().startswith(os.path.abspath(pyside).lower() + os.sep)
        if not inside_pyside:
            roots.append(path)
        elif name.endswith(".exe") or os.sep + "plugins" + os.sep in path.lower():
            roots.append(path)
        elif not (name.startswith("qt6") and name.endswith(".dll")):
            roots.append(path)
    needed = set()
    queue = list(roots)
    while queue:
        path = queue.pop()
        key = os.path.basename(path).lower()
        if key in needed:
            continue
        needed.add(key)
        try:
            imports = pe_imports(path)
        except Exception as error:  # keep going; an unreadable binary is simply kept
            print(f"prune: cannot read imports of {path}: {error}")
            continue
        queue.extend(binaries[name] for name in imports if name in binaries and name not in needed)
    removed = []
    for name, path in binaries.items():
        inside_pyside = os.path.abspath(path).lower().startswith(os.path.abspath(pyside).lower() + os.sep)
        if inside_pyside and name not in needed and name.startswith("qt6") and name.endswith(".dll"):
            os.remove(path)
            removed.append(name)
    after = dir_size(APP_DIR)
    print(f"prune: removed {len(removed)} binaries and unused QML/plugins, {before / 1048576:.0f} MB -> {after / 1048576:.0f} MB")
    print("prune: removed", ", ".join(sorted(removed)))
    largest = sorted(((os.path.getsize(os.path.join(d, f)), os.path.relpath(os.path.join(d, f), APP_DIR))
                      for d, _s, files in os.walk(APP_DIR) for f in files), reverse=True)[:15]
    for size, name in largest:
        print(f"  {size / 1048576:6.1f} MB  {name}")


def print_report(path: str) -> bool:
    if not os.path.exists(path):
        print(f"smoke report missing: {path}")
        return False
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2, ensure_ascii=False))
    for result in report.get("results", []):
        mark = "PASS" if result["ok"] else ("FAIL" if result["required"] else "WARN")
        detail = result.get("detail")
        detail_text = json.dumps(detail, ensure_ascii=False, default=str) if not isinstance(detail, str) else detail
        print(f"{mark:4} {result['name']}: {detail_text[:600]}")
    return bool(report.get("ok"))


def smoke(command, report: str, online: bool, screenshot: str | None, env=None, timeout: int = 600) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
    if os.path.exists(report):
        os.remove(report)
    data_dir = tempfile.mkdtemp(prefix="safeer-smoke-")
    full = list(command) + ["--smoke-test", "--report", os.path.abspath(report), "--data-dir", data_dir]
    if online:
        full.append("--online")
    if screenshot:
        os.makedirs(os.path.dirname(os.path.abspath(screenshot)), exist_ok=True)
        full += ["--screenshot", os.path.abspath(screenshot)]
    print("+", " ".join(full), flush=True)
    started = time.monotonic()
    completed = subprocess.run(full, env=env, timeout=timeout)
    print(f"exit code {completed.returncode} after {time.monotonic() - started:.0f}s")
    ok = print_report(report)
    shutil.rmtree(data_dir, ignore_errors=True)
    if screenshot:
        print_screenshots(screenshot)
    if completed.returncode != 0 or not ok:
        raise SystemExit("smoke test failed")


def print_screenshots(screenshot: str) -> None:
    """Prints small JPEG previews into the CI log so the Windows UI can be reviewed without downloads."""
    try:
        import base64
        import io
        from PIL import Image
    except ImportError:
        return
    stem, ext = os.path.splitext(os.path.abspath(screenshot))
    for path in (stem + ext, stem + "-settings" + ext):
        if not os.path.exists(path):
            continue
        image = Image.open(path).convert("RGB")
        image.thumbnail((960, 960))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=62, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        print(f"SAFEER_SCREENSHOT_BEGIN {os.path.basename(path)} {image.size[0]}x{image.size[1]} {len(encoded)}")
        for start in range(0, len(encoded), 2000):
            print(encoded[start:start + 2000])
        print("SAFEER_SCREENSHOT_END")


def smoke_source(args) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = WINDOWS + os.pathsep + env.get("PYTHONPATH", "")
    smoke([sys.executable, "-m", "safeer_windows"], args.report, args.online, args.screenshot, env=env)


def smoke_frozen(args) -> None:
    exe = args.exe or EXE
    version_file = os.path.join(BUILD, "version.txt")
    run([exe, "--version", "--report", version_file], timeout=120)
    with open(version_file, encoding="utf-8") as handle:
        reported = handle.read().strip()
    expected = f"Safeer Browser {version()}"
    if reported != expected:
        raise SystemExit(f"--version reported {reported!r}, expected {expected!r}")
    print(reported)
    smoke([exe], args.report, args.online, args.screenshot)


def find_iscc() -> str:
    candidates = [shutil.which("iscc"), shutil.which("ISCC"),
                  os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Inno Setup 6", "ISCC.exe"),
                  os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Inno Setup 6", "ISCC.exe"),
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe")]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    raise SystemExit("Inno Setup 6 (ISCC.exe) was not found")


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def package() -> None:
    if not os.path.exists(EXE):
        raise SystemExit("run pyinstaller first")
    make_icon()
    os.makedirs(OUT, exist_ok=True)
    current = version()
    portable = os.path.join(OUT, f"SafeerBrowser-{current}-windows-x64-portable.zip")
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for dirpath, _dirs, files in os.walk(APP_DIR):
            for name in files:
                path = os.path.join(dirpath, name)
                archive.write(path, os.path.join("Safeer Browser", os.path.relpath(path, APP_DIR)))
    run([find_iscc(), f"/DAppVersion={current}", f"/DAppSourceDir={APP_DIR}", f"/DAppOutputDir={OUT}",
         f"/DAppIconFile={ICON}", os.path.join(WINDOWS, "installer.iss")])
    installer = os.path.join(OUT, f"SafeerBrowser-{current}-windows-x64-setup.exe")
    if not os.path.exists(installer):
        raise SystemExit(f"missing {installer}")
    names = [os.path.basename(portable), os.path.basename(installer)]
    with open(os.path.join(OUT, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as handle:
        for name in names:
            handle.write(f"{sha256(os.path.join(OUT, name))}  {name}\n")
    for name in names + ["SHA256SUMS"]:
        print(f"{name}: {os.path.getsize(os.path.join(OUT, name)) / 1048576:.1f} MB")


def registry_value(path: str, name: str = ""):
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def install_test(args) -> None:
    current = version()
    installer = os.path.join(OUT, f"SafeerBrowser-{current}-windows-x64-setup.exe")
    target = os.path.join(tempfile.gettempdir(), "SafeerBrowserInstallTest")
    shutil.rmtree(target, ignore_errors=True)
    log = os.path.join(OUT, "install.log")
    run([installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", f"/DIR={target}", f"/LOG={log}"], timeout=600)
    exe = os.path.join(target, "SafeerBrowser.exe")
    if not os.path.exists(exe):
        raise SystemExit("installer did not create SafeerBrowser.exe")
    checks = {
        "RegisteredApplications": registry_value(r"Software\RegisteredApplications", "Safeer Browser"),
        "StartMenuInternet": registry_value(r"Software\Clients\StartMenuInternet\SafeerBrowser\Capabilities", "ApplicationName"),
        "https association": registry_value(r"Software\Clients\StartMenuInternet\SafeerBrowser\Capabilities\URLAssociations", "https"),
        "URL command": registry_value(r"Software\Classes\SafeerBrowserURL\shell\open\command"),
        "HTML command": registry_value(r"Software\Classes\SafeerBrowserHTML\shell\open\command"),
    }
    print(json.dumps(checks, indent=2))
    if not all(checks.values()) or exe.lower() not in str(checks["URL command"]).lower():
        raise SystemExit("browser registration is incomplete")
    smoke_args = argparse.Namespace(exe=exe, report=os.path.join(OUT, "smoke-installed.json"), online=False, screenshot=None)
    smoke_frozen(smoke_args)
    uninstaller = os.path.join(target, "unins000.exe")
    run([uninstaller, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=300)
    deadline = time.monotonic() + 120
    while os.path.exists(exe) and time.monotonic() < deadline:
        time.sleep(1)
    if os.path.exists(exe):
        raise SystemExit("uninstaller left SafeerBrowser.exe behind")
    if registry_value(r"Software\RegisteredApplications", "Safeer Browser") is not None:
        raise SystemExit("uninstaller left the browser registration behind")
    print("install, launch and uninstall: OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("icon")
    sub.add_parser("pyinstaller")
    sub.add_parser("package")
    for name in ("smoke-source", "smoke-frozen"):
        smoke_parser = sub.add_parser(name)
        smoke_parser.add_argument("--report", default=os.path.join(OUT, f"{name}.json"))
        smoke_parser.add_argument("--online", action="store_true")
        smoke_parser.add_argument("--screenshot")
        smoke_parser.add_argument("--exe")
    sub.add_parser("install-test")
    args = parser.parse_args()
    if args.command == "icon":
        make_icon()
    elif args.command == "pyinstaller":
        pyinstaller()
    elif args.command == "package":
        package()
    elif args.command == "smoke-source":
        smoke_source(args)
    elif args.command == "smoke-frozen":
        smoke_frozen(args)
    elif args.command == "install-test":
        install_test(args)


if __name__ == "__main__":
    main()
