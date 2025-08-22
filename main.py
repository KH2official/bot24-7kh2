import os
import shutil
import subprocess
import sys
import threading
import time
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify, flash
from werkzeug.utils import secure_filename
from utils import (
    allowed_file,
    unzip_and_fix,
    detect_main_file,
    run_bot,
    kill_bot,
    get_log,
    fix_dependencies
)

UPLOAD_FOLDER = 'userbot'
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'super_secret_key'

# State
bot_process = None
tokens = []
last_error = ""

@app.route('/')
def index():
    return render_template("index.html", last_error=last_error, console_log=get_log(), tokens=tokens)

@app.route('/upload', methods=['POST'])
def upload():
    global bot_process, tokens, last_error
    kill_bot()
    tokens.clear()
    last_error = ""
    token = request.form.get('token')
    if token:
        tokens.append(token)
    file = request.files.get('file')
    if file and allowed_file(file.filename):
        shutil.rmtree(UPLOAD_FOLDER, ignore_errors=True)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
        file.save(filepath)
        try:
            unzip_and_fix(filepath, UPLOAD_FOLDER)
            mainfile = detect_main_file(UPLOAD_FOLDER)
            if not mainfile:
                raise Exception("Main bot file not found (.js or .py).")
            bot_process = run_bot(UPLOAD_FOLDER, mainfile, tokens)
        except Exception as e:
            last_error = str(e)
    else:
        last_error = "Invalid file type"
    return redirect(url_for('index'))

@app.route('/add_token', methods=['POST'])
def add_token():
    global tokens
    token = request.form.get('token')
    if token:
        tokens.append(token)
    return redirect(url_for('index'))

@app.route('/start')
def start():
    global bot_process, last_error
    kill_bot()
    last_error = ""
    try:
        mainfile = detect_main_file(UPLOAD_FOLDER)
        if not mainfile:
            raise Exception("Main bot file not found (.js or .py).")
        bot_process = run_bot(UPLOAD_FOLDER, mainfile, tokens)
    except Exception as e:
        last_error = str(e)
    return redirect(url_for('index'))

@app.route('/stop')
def stop():
    kill_bot()
    return redirect(url_for('index'))

@app.route('/restart')
def restart():
    kill_bot()
    time.sleep(1)
    return redirect(url_for('start'))

@app.route('/fixbugs')
def fixbugs():
    global last_error
    folder = UPLOAD_FOLDER
    try:
        fix_dependencies(folder)
        last_error = "Tried to fix bugs (dependencies reinstalled). Check console log."
    except Exception as e:
        last_error = f"Fix bugs failed: {e}"
    return redirect(url_for('index'))

@app.route('/console')
def console():
    return get_log()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)