#!/usr/bin/env python3
"""
Helper utilities:
- allowed_file, unzip_and_fix (handles .zip or single file)
- detect_main_file (recursive search)
- fix_dependencies (pip/npm install best-effort)
"""
import os
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
        # Extract all; if files are nested in a single folder keep them.
        with zipfile.ZipFile(upload_path, "r") as z:
            z.extractall(extract_path)
    else:
        # Single file uploaded (.py or .js) -> move to extract_path
        dest = extract_path / upload_path.name
        shutil.move(str(upload_path), str(dest))
    # If no .py/.js found in root, try recursively find and move those files to root
    found = list(extract_path.rglob("*.py")) + list(extract_path.rglob("*.js"))
    if not found:
        raise Exception("No .py or .js files found in uploaded package.")
    # If files are nested in subfolder and root contains only one folder, flatten that folder
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
    # Check common filenames first
    candidates = ["index.js", "main.py", "bot.py", "app.py"]
    for c in candidates:
        p = folder / c
        if p.exists():
            return c
    # Otherwise pick first .py or .js in folder root
    for p in folder.iterdir():
        if p.is_file() and p.suffix in (".py", ".js"):
            return p.name
    # As fallback, search recursively and return the first match
    for p in folder.rglob("*.py"):
        return str(p.relative_to(folder))
    for p in folder.rglob("*.js"):
        return str(p.relative_to(folder))
    return None

def fix_dependencies(folder: Path):
    # Best-effort install. Non-fatal if commands missing.
    folder = Path(folder)
    pkg = folder / "package.json"
    req = folder / "requirements.txt"
    if pkg.exists():
        try:
            subprocess.run(["npm", "install"], cwd=str(folder), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            # try without check to continue
            subprocess.run(["npm", "install"], cwd=str(folder))
    if req.exists():
        try:
            subprocess.run([sys_executable(), "-m", "pip", "install", "-r", str(req)], cwd=str(folder), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            subprocess.run([sys_executable(), "-m", "pip", "install", "-r", str(req)], cwd=str(folder))

def sys_executable():
    # helper to prefer the same python interpreter
    return os.environ.get("PYTHON_INTERPRETER") or (os.sys.executable or "python3")