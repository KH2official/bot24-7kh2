```markdown
# Single-Page Bot Host (Python + Flask)

What this is
- A single-page web host to run a bot (Python or Node.js) directly on one website.
- Upload a .zip, or a single .py/.js file, provide a bot token, and the server will:
  - Extract files if zipped
  - Detect the main file (index.js, main.py, bot.py, app.py or the first .py/.js)
  - Set BOT_TOKEN1..N environment variables for tokens you add
  - Install dependencies if package.json or requirements.txt present (best-effort)
  - Start the bot and stream its console to the single-page UI
- Controls: Start, Stop, Restart, Fix Bugs (reinstall deps). Everything on one page, no navigation.

How to run locally
1. Place files:
   - app.py
   - utils.py
   - static/index.html
   - requirements.txt
2. Create virtualenv (recommended) and install:
   ```
   python -m venv venv
   source venv/bin/activate   # Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
3. Start:
   ```
   python app.py
   ```
4. Open: http://localhost:8080

Notes and limitations
- This runs arbitrary uploaded code on the host machine: do NOT expose this publicly without proper sandboxing/authentication.
- Dependency installation requires network access and that npm/pip are available in the host environment.
- For true 24/7 hosting consider running this on a VPS or a platform that allows persistent processes. Replit/Glitch may require special configuration for always-on behavior.
- For production use add authentication and sandboxing (Docker, Firejail, or separate VMs).

Security disclaimer
- You are executing untrusted code on the host. Use in trusted environments or add strong isolation before exposing to others.

If you want:
- I can add simple password protection / token for the web UI.
- I can provide a Dockerfile or Procfile for Replit/Glitch.
- I can add an in-browser file editor to edit uploaded files.
```