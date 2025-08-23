#!/usr/bin/env python3
"""
Helper utilities:
- allowed_file, unzip_and_fix (handles .zip or single file)
- detect_main_file (recursive search)
- fix_dependencies (pip/npm install best-effort)
"""
import os
import sys
import zipfile
import shutil
import subprocess
from pathlib import Path

ALLOWED_EXTENSIONS = {"zip", "py", "js"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def unzip_and_fix(upload_path: Path, extract_path: Path):
    upload_path = Path(upload_path)
    extract_path = Path(extract_path)
    if upload_path.suffix.lower() == ".zip" and zipfile.is_zipfile(upload_path):
        with zipfile.ZipFile(upload_path, "r") as z:
            z.extractall(extract_path)
        try:
            upload_path.unlink()
        except Exception:
            pass
    else:
        dest = extract_path / upload_path.name
        shutil.move(str(upload_path), str(dest))
    found = list(extract_path.rglob("*.py")) + list(extract_path.rglob("*.js"))
    if not found:
        raise Exception("No .py or .js files found in uploaded package.")
    entries = list(extract_path.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        for item in inner.iterdir():
            target = extract_path / item.name
            try:
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                shutil.move(str(item), str(target))
            except Exception:
                pass
        try:
            shutil.rmtree(inner)
        except Exception:
            pass

def detect_main_file(folder: Path):
    candidates = ["index.js", "main.py", "bot.py", "app.py"]
    for c in candidates:
        p = folder / c
        if p.exists():
            return c
    for p in folder.iterdir():
        if p.is_file() and p.suffix in (".py", ".js"):
            return p.name
    for p in folder.rglob("*.py"):
        return str(p.relative_to(folder))
    for p in folder.rglob("*.js"):
        return str(p.relative_to(folder))
    return None

def sys_executable():
    return os.environ.get("PYTHON_INTERPRETER") or (sys.executable or "python3")

def fix_dependencies(folder: Path):
    folder = Path(folder)
    pkg = folder / "package.json"
    req = folder / "requirements.txt"
    if pkg.exists():
        try:
            subprocess.run(["npm", "install"], cwd=str(folder), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            try:
                subprocess.run(["npm", "install"], cwd=str(folder))
            except Exception:
                pass
    if req.exists():
        try:
            subprocess.run([sys_executable(), "-m", "pip", "install", "-r", str(req)], cwd=str(folder), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            try:
                subprocess.run([sys_executable(), "-m", "pip", "install", "-r", str(req)], cwd=str(folder))
            except Exception:
                pass