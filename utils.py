import os
import sys
import zipfile
import shutil
import subprocess

ALLOWED_EXTENSIONS = {'zip', 'py', 'js'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def unzip_and_fix(upload_path, extract_path):
    if upload_path.endswith('.zip') and zipfile.is_zipfile(upload_path):
        with zipfile.ZipFile(upload_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
    else:
        shutil.copy(upload_path, extract_path)
    # Ensure at least one .py or .js file exists
    files = os.listdir(extract_path)
    if not any(f.endswith(('.py', '.js')) for f in files):
        raise Exception("No .py or .js file found in uploaded code.")

def detect_main_file(folder):
    # Check for most common bot entry files
    main_names = ['index.js', 'main.py', 'bot.py', 'app.py']
    for fname in main_names:
        if os.path.exists(os.path.join(folder, fname)):
            return fname
    for fname in os.listdir(folder):
        if fname.endswith('.js') or fname.endswith('.py'):
            return fname
    return None

def run_bot(folder, mainfile, tokens):
    env = os.environ.copy()
    for i, token in enumerate(tokens):
        env[f'BOT_TOKEN{i+1}'] = token
    # Find requirements.txt or package.json and install if present
    fix_dependencies(folder)
    # Start bot
    log_file = open("console.log", "w")
    if mainfile.endswith('.js'):
        cmd = ["node", mainfile]
    elif mainfile.endswith('.py'):
        cmd = [sys.executable, mainfile]
    else:
        raise Exception("Unknown bot file type.")
    return subprocess.Popen(cmd, cwd=folder, stdout=log_file, stderr=subprocess.STDOUT, env=env)

def kill_bot():
    global bot_process
    try:
        import main
        if main.bot_process and main.bot_process.poll() is None:
            main.bot_process.terminate()
            main.bot_process.wait(timeout=5)
    except Exception:
        pass
    main.bot_process = None

def get_log():
    if os.path.exists("console.log"):
        with open("console.log") as f:
            return f.read()[-4000:]
    return ""

def fix_dependencies(folder):
    # Install dependencies for Python and Node.js
    if os.path.exists(os.path.join(folder, 'package.json')):
        subprocess.run(['npm', 'install'], cwd=folder)
    if os.path.exists(os.path.join(folder, 'requirements.txt')):
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], cwd=folder)