# **ÆEA BOT — TELEGRAM MINI APP DEPLOYMENT GUIDE**
*Version:* 4.12 (Telegram Web App Enabled)
*Target:* `app.py` + `index.html` served as a Telegram Mini App
*Prereqs:* Working `TELEGRAM_BOT_TOKEN`, a public HTTPS endpoint, `python-telegram-bot >= 21.x`

## 1. What the Mini App Adds

The ÆEA bot exposes the same Codex Symbolica visualization that runs locally at
`http://127.0.0.1:8765/` as a **Telegram Web App** — reachable from inside any
Telegram client by tapping a button, without needing a browser, port forwarding,
or a PC.

When launched inside Telegram:

| Feature | Behavior |
|---|---|
| **Identity** | `initData` HMAC-SHA256 verified by `POST /handshake`; `user_id` binds to `engine.state.chat_id` |
| **Theme** | `themeParams` → CSS variables (`--tma-bg`, `--tma-text`, …) |
| **Viewport** | `expand()` + `viewportChanged` event hooks |
| **Swipes** | `disableVerticalSwipes()` so chart drag doesn't close the app |
| **Haptics** | `HapticFeedback.impactOccurred()` on FVG commit/delete |
| **Closing** | `enableClosingConfirmation()` guard, plus in-app ✕ CLOSE button |
| **Menu** | `MenuButtonWebApp` — persistent bottom-left entry point |
| **Auth** | Every `/state`, `/fvg`, `DELETE /fvg/{idx}` request carries `X-Telegram-Init-Data` |

Outside Telegram, the same page still runs as a plain web GUI — all TMA features
degrade gracefully.

## 2. HTTPS Is Mandatory

**Telegram will not load a Mini App over `http://`.** You have three options:

### Option A — Built-in Tunnel (recommended)

`app.py` already spawns a public HTTPS tunnel at startup using the first
available provider in this order:

1. **`cloudflared`** — no account, zero config, ephemeral `*.trycloudflare.com` URL
2. **`ngrok`** — requires free signup + authtoken
3. **`serveo.net`** — via SSH, no account

Install `cloudflared` (Termux / Linux):

```bash
# Termux (Android, aarch64)
pkg install cloudflared

# Debian/Ubuntu
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# macOS
brew install cloudflared
```

Then just run:

```bash
export TELEGRAM_BOT_TOKEN='123456:ABC…'
python3 app.py
```

Watch the logs:

```
🌐 ÆEA Mini App Bridge listening on http://127.0.0.1:8765
🌐 Spawning tunnel: cloudflared tunnel --url http://127.0.0.1:8765 …
🌐 Tunnel established via cloudflared: https://random-words-1234.trycloudflare.com
```

The public URL is auto-injected into the bot's /start keyboard as a
"⚡ Open ÆEA Mini App" button, and registered as a MenuButtonWebApp.

Option B — Explicit URL

If you already have an HTTPS endpoint (reverse proxy, Heroku, Fly.io, VPS with
Let's Encrypt), skip the tunnel entirely:

```bash
export TELEGRAM_WEBAPP_URL='https://your-domain.example/aei'
export TELEGRAM_BOT_TOKEN='123456:ABC…'
python3 app.py
```

The tunnel manager will detect this env var and refuse to spawn its own.

Option C — TLS on the Local Bridge

Wrap the ThreadingHTTPServer in TLS (useful behind nginx/Caddy):

```bash
export BRIDGE_USE_TLS=1
export BRIDGE_TLS_CERT=/etc/ssl/certs/aei.crt
export BRIDGE_TLS_KEY=/etc/ssl/private/aei.key
python3 app.py
```

Note: Telegram itself still won't trust a self-signed cert. You need a
publicly-trusted CA (Let's Encrypt via certbot) or an upstream terminator.

3. BotFather Configuration

Open @BotFather in Telegram:

3.1 Create the Mini App

```
/newapp
→ pick your bot
→ Title:  ÆEA Codex
→ Description: Quantum-Financial Topology Visualization
→ Photo:  640x360 PNG (optional)
→ Short name: aea-codex
→ Web App URL: https://your-domain.example/
→ Short name in menu: ÆEA
```

3.2 Set the Menu Button (alternative to auto-registration)

If MenuButtonWebApp auto-registration fails (bot not admin, network), set it
manually:

```
/setmenubutton
→ pick your bot
→ URL: https://your-domain.example/
→ Button text: ÆEA Mini App
```

3.3 (Optional) Inline Mode Deep-Link

For sharing: https://t.me/YourBotUsername/aea-codex

4. Environment Variables Reference

Variable Default Purpose
TELEGRAM_BOT_TOKEN (required) Bot token from BotFather
TELEGRAM_WEBAPP_URL (empty) Explicit public HTTPS URL; skips tunnel
BRIDGE_HOST 127.0.0.1 Bind address of local bridge
BRIDGE_PORT 8765 Bind port of local bridge
BRIDGE_USE_TLS 0 Wrap bridge in TLS (1 to enable)
BRIDGE_TLS_CERT (empty) PEM cert path when TLS enabled
BRIDGE_TLS_KEY (empty) PEM key path when TLS enabled
BRIDGE_TUNNEL cloudflared Preferred tunnel: cloudflared, ngrok, serveo
BRIDGE_PUBLIC_TIMEOUT 45 Seconds to wait for tunnel URL discovery

5. Verification Checklist

After python3 app.py starts, confirm:

☐ Log shows 🌐 ÆEA Mini App Bridge listening on http://127.0.0.1:8765
☐ Log shows 🌐 Tunnel established via cloudflared: https://…trycloudflare.com
☐ curl http://127.0.0.1:8765/health → {"ok": true, "service": "aei-bridge", "version": "4.12"}
☐ curl http://127.0.0.1:8765/config → JSON with "public_url" populated
☐ Telegram /start → keyboard shows "⚡ Open ÆEA Mini App" button
☐ Tapping the button opens the Codex Symbolica UI inside Telegram
☐ Mini App top-left badge shows TMA and your @username
☐ Tapping ▲ + chart draws a blue FVG; TRACE panel logs TMA handshake OK and FVG POST OK
☐ Tapping ✖ deletes the FVG; backend logs 🔻 FVG removed: idx=…
☐ Haptic feedback fires on FVG commit (mobile only)
☐ Bot logs show 🌐 Web App session registered: user_id=…

6. Local-Only Mode (No Telegram)

You can still use the GUI without Telegram at all:

```bash
python3 app.py        # starts bot AND bridge
```

Then open http://localhost:8765/ in any browser on the same machine.

· The Mini App auto-connect block skips when window.Telegram.WebApp is undefined
· Click CONNECT to manually attach to the local bridge
· All chart tools work identically; no initData is required for /state reads
· /fvg POSTs are accepted with verified=false (no HMAC check, since there's no session)

7. Security Notes

7.1 initData Verification

POST /handshake and every authenticated /fvg request verify the Telegram
initData blob using the standard HMAC-SHA256 scheme:

```
secret_key       = HMAC_SHA256(bot_token, "WebAppData")
data_check_string = sorted(key=value lines) joined by "\n", excluding `hash`
expected_hash    = HMAC_SHA256(data_check_string, secret_key).hexdigest()
```

Enforced freshness: auth_date must be within [-5min, +24h] of server time.

7.2 Tunnel Exposure

Cloudflared/ngrok tunnels expose the bridge to the public internet.
Mitigations:

· initData HMAC gates all write endpoints (POST /fvg, DELETE /fvg/{idx})
· GET /state is read-only and reveals only symbolic state + price; no
  credentials, no PII, no Telegram token
· To lock down reads too, add a simple bearer check:

```python
# inside BridgeHandler.do_GET, before serving /state
if path == "/state" and not _extract_auth_headers(self)[2]:
    self._send_json(401, {"error": "unauthorized"})
    return
```

· Rotate the bot token in BotFather if a tunnel URL leaks with an active session

7.3 Rate Limits

The /fvg endpoint inherits the Arc-Length Gate: if |s² − r²| > 1.0 at
the moment of commit, the FVG is rejected with HTTP 422 regardless of HMAC
validity. This is a hard compiler spec, not a soft guard.

8. Troubleshooting Matrix

Symptom Diagnosis Fix
/webapp says "tunnel pending" forever cloudflared not on PATH pkg install cloudflared (Termux) or brew install cloudflared
Telegram button opens blank page TELEGRAM_WEBAPP_URL points to http:// Use HTTPS; Telegram blocks cleartext
POST /handshake → 403 invalid_init_data bot token mismatch Ensure TELEGRAM_BOT_TOKEN env matches the token used to create the Mini App
FVG commits silently vanish Arc-Length deviation at commit time Watch TRACE panel; wait for Δ → 0 then retry
hud-conn stuck on DISCONNECTED bridge not running Ensure python3 app.py is running; check /health
Mini App shows no @username badge launched outside Telegram Normal — badge only shows in TMA mode
Menu button missing /setmenubutton not called Run BotFather /setmenubutton OR ensure post_init succeeded
Chart drag closes Mini App disableVerticalSwipes not applied Confirm telegram-web-app.js loaded before app JS
pip install python-telegram-bot fails Python < 3.9 Upgrade Python; PTB v21 requires 3.9+
Tunnel URL changes every restart cloudflared ephemeral tunnels Use named tunnel (paid) or set TELEGRAM_WEBAPP_URL

9. File Layout

Place all three files side by side:

```
aei-seed/
├── app.py          # bot + HTTPS bridge + tunnel manager
├── index.html      # Codex Symbolica GUI (served by bridge)
└── README.md       # this file
```

app.py resolves index.html relative to its own directory, so the bridge
serves it automatically at GET /.

10. Minimal Quickstart

```bash
# 1. Install deps
pip install python-telegram-bot yfinance

# 2. Install tunnel (Termux)
pkg install cloudflared

# 3. Set token
export TELEGRAM_BOT_TOKEN='123456:ABCdef…'

# 4. Run
python3 app.py

# 5. In Telegram:
#    /start → tap "⚡ Open ÆEA Mini App"
#    Draw FVGs with ▲ / ▼ ; delete with ✖
```

That's it. The Mini App is live.

11. Architecture Recap

```
┌──────────────────┐       ┌─────────────────────────┐
│  Telegram Client │──┐    │  Telegram Servers       │
│  (Web App view)  │  │    │  (relay / auth / theme) │
└──────────────────┘  │    └─────────────────────────┘
                      │                │
                      │    HTTPS       │
                      ▼                ▼
         ┌────────────────────────────────────────┐
         │  cloudflared / ngrok / serveo tunnel   │
         │  (public *.trycloudflare.com URL)      │
         └──────────────┬─────────────────────────┘
                        │
                        ▼
         ┌────────────────────────────────────────┐
         │  BridgeServer (ThreadingHTTPServer)    │
         │  ├── GET  /            → index.html    │
         │  ├── GET  /state       → snapshot      │
         │  ├── GET  /config      → metadata      │
         │  ├── POST /handshake   → initData HMAC │
         │  ├── POST /fvg         → Arc-Length gate│
         │  └── DEL  /fvg/{idx}   → remove        │
         └──────────────┬─────────────────────────┘
                        │
                        ▼
         ┌────────────────────────────────────────┐
         │  AEEA_Engine  (tick loop)              │
         │  ├── YahooFinanceFeed                  │
         │  ├── state.k / state.l (imbalance)     │
         │  ├── Premium[] / Discount[] (anchors)  │
         │  └── _send_signal_alert → Telegram     │
         └────────────────────────────────────────┘
```

The Mini App is not a separate server — it's the same index.html that
runs locally, executed inside Telegram's WebView, authenticated via initData,
and bound back to the bot's chat_id via the handshake. One process, one
state, two presentation surfaces.

12. Q.E.D.

The Mini App is now a first-class surface of the ÆEA engine:

· Locally — open http://localhost:8765/ in a browser
· Remotely — tap the Telegram menu button
· Both — share the same AEEA_Engine.state, the same BridgeState._fvgs,
  the same Fraction-exact price math

LOGOS = Φ = Truth = Path = Origin

Codex_Symbolica ⊢ Codex_Symbolica

# **ÆEA Telegram Mini App — GitHub Pages + Heroku Deployment Guide**
*Version:* 5.0 (Split-Origin Architecture: Static Frontend + Dynamic Backend)
*Target:* index.html on GitHub Pages + app.py on Heroku
*Prereqs:* GitHub account, Heroku account, TELEGRAM_BOT_TOKEN, git, Heroku CLI

1. Why Split the Deployment?

Telegram Mini Apps are just web pages loaded inside Telegram's WebView. They can be served from any public HTTPS URL. By splitting the app:

Layer Host What It Does
Frontend GitHub Pages Serves index.html (Codex Symbolica visualization, FVG tools, polling logic). Free, fast, CDN-backed.
Backend Heroku Runs app.py: the Telegram bot, AEEA_Engine, Yahoo Finance feed, and the HTTP bridge (/state, /handshake, /fvg).

Benefits:

· GitHub Pages is free forever for public repos (no dyno sleeping)
· Heroku handles the dynamic work (bot polling, state, exact Decimal math)
· Frontend and backend can be updated independently
· Zero-downtime deploys on either side

2. Repository Layout

You need two separate locations:

Repo A — Frontend (GitHub Pages)

```
aei-miniapp/
├── index.html          # the Codex Symbolica GUI
├── README.md           # this file
└── (optional assets)
```

Push this to a GitHub repo, then enable Pages under Settings → Pages → Source: main branch / root.

Your live URL will be:

```
https://<your-username>.github.io/<repo-name>/
```

Repo B — Backend (Heroku)

```
aei-backend/
├── app.py              # bot + bridge
├── index.html          # (optional fallback — Heroku serves it if no tunnel)
├── requirements.txt    # python deps
├── Procfile            # Heroku process declaration
└── runtime.txt         # optional Python version pin
```

Push this to Heroku via the Heroku CLI.

3. Frontend Setup (GitHub Pages)

3.1 Configure the Backend URL

Open index.html and find the _detectEndpoint method inside the TelegramBridge class. Add a BACKEND_URL constant at the top of the <script> block:

```javascript
// ============================================================
// BACKEND CONFIGURATION — set this to your Heroku app URL
// ============================================================
const BACKEND_URL = 'https://your-app-name.herokuapp.com';
```

Then update _detectEndpoint:

```javascript
_detectEndpoint() {
    if (typeof BACKEND_URL !== 'undefined' && BACKEND_URL) return BACKEND_URL;
    if (TELEGRAM_WEBAPP_URL) return TELEGRAM_WEBAPP_URL;
    const origin = window.location.origin;
    if (origin && origin !== 'null' && origin.indexOf('http') === 0) return origin;
    return 'http://localhost:8765';
}
```

3.2 Push to GitHub

```bash
cd aei-miniapp
git init
git add index.html README.md
git commit -m "Initial ÆEA Mini App frontend"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

3.3 Enable GitHub Pages

1. Go to your repo on GitHub
2. Settings → Pages
3. Source: Deploy from a branch
4. Branch: main / / (root)
5. Click Save

Wait ~60 seconds. Your site will be live at:

```
https://<your-username>.github.io/<repo-name>/
```

Verify by opening that URL in a browser. You should see the Codex Symbolica UI (it will show "DISCONNECTED" since the backend isn't running yet).

4. Backend Setup (Heroku)

4.1 Modify app.py for Heroku Port Binding

Heroku assigns a dynamic port via the $PORT environment variable. Update the bridge port line in app.py:

```python
BRIDGE_PORT: int = int(os.getenv("PORT", os.getenv("BRIDGE_PORT", "8765")))
```

This makes Heroku's port take priority, with 8765 as the local fallback.

4.2 Create requirements.txt

```
python-telegram-bot>=21.0
yfinance
```

4.3 Create Procfile

```
web: python app.py
```

4.4 Create runtime.txt (Optional)

Pin Python to a version Heroku supports:

```
python-3.11.9
```

4.5 Deploy to Heroku

```bash
cd aei-backend
git init
git add .
git commit -m "Initial ÆEA backend"
heroku create your-app-name
heroku config:set TELEGRAM_BOT_TOKEN="123456:ABCdef..."
heroku config:set TELEGRAM_WEBAPP_URL="https://<your-username>.github.io/<repo-name>/"
git push heroku main
```

The TELEGRAM_WEBAPP_URL env var does two things:

· Tells the bot where the Mini App lives (used for MenuButtonWebApp)
· Prevents TunnelManager from trying to spawn cloudflared (which isn't installed on Heroku)

4.6 Verify the Backend

```bash
curl https://your-app-name.herokuapp.com/health
# → {"ok": true, "service": "aei-bridge", "version": "4.12"}

curl https://your-app-name.herokuapp.com/config
# → {"public_url": "https://<your-username>.github.io/<repo-name>/", ...}
```

5. BotFather Configuration

5.1 Create the Mini App

Open @BotFather in Telegram:

```
/newapp
→ pick your bot
→ Title:  ÆEA Codex
→ Description: Quantum-Financial Topology Visualization
→ Photo:  640x360 PNG (optional)
→ Short name: aea-codex
→ Web App URL: https://<your-username>.github.io/<repo-name>/
→ Short name in menu: ÆEA
```

Critical: The Web App URL must be the GitHub Pages URL, not the Heroku URL. Telegram loads the static frontend; the frontend then talks to Heroku.

5.2 Set the Menu Button (Alternative)

If MenuButtonWebApp auto-registration fails:

```
/setmenubutton
→ pick your bot
→ URL: https://<your-username>.github.io/<repo-name>/
→ Button text: ÆEA Mini App
```

5.3 Deep Link (Optional)

For sharing:

```
https://t.me/<YourBotUsername>/aea-codex
```

6. Environment Variables Reference

Heroku (Backend)

Variable Default Purpose
TELEGRAM_BOT_TOKEN (required) Bot token from BotFather
TELEGRAM_WEBAPP_URL (empty) GitHub Pages URL — skips tunnel spawn
PORT (Heroku-assigned) Bridge bind port
BRIDGE_HOST 0.0.0.0 Bind address (Heroku requires 0.0.0.0)
BRIDGE_USE_TLS 0 Heroku terminates TLS at its router; leave 0
BRIDGE_TLS_CERT / BRIDGE_TLS_KEY (empty) Only if running your own TLS
BRIDGE_TUNNEL cloudflared Ignored on Heroku (no cloudflared binary)

Set them via:

```bash
heroku config:set KEY=value
```

GitHub Pages (Frontend)

Constant Where Purpose
BACKEND_URL top of <script> in index.html Heroku app URL

There are no environment variables on GitHub Pages — it's static hosting. Everything must be hardcoded in the HTML/JS.

7. Verification Checklist

After both sides are deployed:

☐ https://<user>.github.io/<repo>/ loads the Codex Symbolica UI in a browser
☐ curl https://your-app.herokuapp.com/health returns {"ok": true}
☐ curl https://your-app.herokuapp.com/config shows public_url = your GitHub Pages URL
☐ Open Telegram → /start → tap "⚡ Open ÆEA Mini App"
☐ Mini App loads; top-left badge shows TMA and your @username
☐ hud-conn shows CONNECTED (green) within ~5 seconds
☐ Tapping ▲ on the chart draws a blue FVG line
☐ FVG appears in the bottom panel with s=r status
☐ Tapping ✖ removes it
☐ heroku logs --tail shows 🌐 Web App session registered: user_id=...
☐ Live price updates every ~2s in the HUD

8. Security Notes

8.1 Frontend Visibility

BACKEND_URL is visible in the page source. This is fine — the backend's /state endpoint is read-only and reveals only symbolic state (no credentials, no PII). Write endpoints (/fvg, /handshake) are protected by initData HMAC verification.

8.2 CORS

app.py sets Access-Control-Allow-Origin: * on all responses. This is required for cross-origin fetches from GitHub Pages to Heroku. If you want to lock it down to your GitHub Pages domain only, change the CORS header in BridgeHandler._set_cors:

```python
def _set_cors(self):
    self.send_header("Access-Control-Allow-Origin", "https://<user>.github.io")
    # ... rest unchanged
```

8.3 initData Verification

Every POST /handshake and POST /fvg request carries the X-Telegram-Init-Data header. app.py verifies it using HMAC-SHA256 with WebAppData as the secret key, and enforces auth_date freshness (≤ 24h, ≥ -5m skew). Requests that fail verification are rejected with HTTP 403.

8.4 Arc-Length Gate

FVG commits are rejected with HTTP 422 if |s² − r²| > 1.0 at commit time. This is a hard compiler spec, not a soft guard.

9. Troubleshooting

Symptom Diagnosis Fix
Mini App loads but hud-conn stays DISCONNECTED Frontend can't reach Heroku Check BACKEND_URL in index.html; run curl $BACKEND_URL/health
POST /handshake → 403 TELEGRAM_BOT_TOKEN mismatch Ensure Heroku's TELEGRAM_BOT_TOKEN matches the token used in BotFather for the Mini App
Telegram button opens a blank page Web App URL is http:// GitHub Pages is always HTTPS, so this means BotFather's URL is wrong — recheck /newapp
FVG commits silently vanish Arc-Length deviation at commit Open TRACE panel; wait for Δ → 0 then retry
hud-conn shows LOCAL-ONLY Frontend is not in TMA mode and not pointed at a backend Open via Telegram, or set BACKEND_URL and reload
Heroku dyno sleeps, first load is slow Free tier idles after 30 min Upgrade to a paid dyno, or use a pinger (e.g., UptimeRobot)
CORS error in browser console Heroku CORS header missing Verify _set_cors is called on the response; check Heroku logs
Menu button missing set_chat_menu_button failed Run BotFather /setmenubutton manually
heroku logs shows bind: Address already in use Port conflict Heroku sets $PORT dynamically — ensure app.py reads it
GitHub Pages shows 404 Pages not enabled Settings → Pages → Source: main / root

10. Architecture Diagram

```
┌──────────────────────────┐
│   Telegram Client        │
│   (WebView, user taps    │
│    Mini App button)      │
└────────────┬─────────────┘
             │ HTTPS GET (loads static HTML)
             ▼
┌──────────────────────────────────────┐
│   GitHub Pages                       │
│   https://<user>.github.io/<repo>/   │
│   ├── index.html                     │
│   └── BACKEND_URL = heroku-url       │
└────────────┬─────────────────────────┘
             │ fetch() → /state, /handshake, /fvg
             │ (with X-Telegram-Init-Data header)
             ▼
┌──────────────────────────────────────┐
│   Heroku (app.py)                    │
│   ├── Telegram bot polling           │
│   ├── AEEA_Engine (Decimal math)     │
│   ├── Yahoo Finance feed             │
│   └── Bridge endpoints:              │
│        GET  /state                   │
│        POST /handshake               │
│        POST /fvg                     │
│        DEL  /fvg/{idx}               │
│        GET  /health                  │
│        GET  /config                  │
└────────────┬─────────────────────────┘
             │
             ▼
      Yahoo Finance API
```

11. Update Workflow

Frontend changes

```bash
cd aei-miniapp
# edit index.html
git add index.html
git commit -m "Update chart overlay"
git push origin main
# GitHub Pages auto-deploys in ~60s
```

Backend changes

```bash
cd aei-backend
# edit app.py
git add app.py
git commit -m "Fix FVG decoherence"
git push heroku main
# Heroku rebuilds and restarts in ~2 min
```

No coordination needed — the two deploys are independent.

12. One-Command Deploy (Cheat Sheet)

```bash
# ─── Frontend (GitHub Pages) ───────────────────────
cd aei-miniapp
git add . && git commit -m "update" && git push origin main

# ─── Backend (Heroku) ──────────────────────────────
cd ../aei-backend
git add . && git commit -m "update" && git push heroku main

# ─── Verify ────────────────────────────────────────
curl https://your-app-name.herokuapp.com/health
```

13. Q.E.D.

The Mini App is now served from two origins that cooperate:

· GitHub Pages — the presentation surface, loaded by Telegram's WebView
· Heroku — the computational substrate, polled by the frontend

The BACKEND_URL constant is the single wire between them. Set it once, push both, and the Mini App is live inside Telegram.

LOGOS = Φ = Truth = Path = Origin

Codex_Symbolica ⊢ Codex_Symbolica

---

•📌 Here is the complete deployment guide. Everything you need, in order, with the full contents of every outstanding file.

---

ÆEA Deployment Guide — Cloudflare Worker Relay

Goal: Fix the "price stuck at 0.0" problem by routing Yahoo Finance through a Cloudflare Worker instead of calling it directly from Heroku.

Architecture after deployment:

```
Yahoo Finance ──► Cloudflare Worker (fresh IP) ──► Heroku app.py ──► Bridge ──► Mini App
```

---

Prerequisites

· A Cloudflare account (free tier is sufficient) — sign up at dash.cloudflare.com
· Your Heroku app name (referred to as your-app-name below)
· Your Heroku CLI logged in (heroku login)
· Your GitHub repo for the Mini App frontend
· Git installed locally

---

Step 1 — Deploy the Cloudflare Worker

1.1 Create the Worker

1. Go to https://dash.cloudflare.com
2. Click Workers & Pages in the left sidebar
3. Click Create Application → Create Worker
4. Name it aei-relay
5. Click Deploy (accept the default template for now)
6. Click Edit code to enter the editor

1.2 Replace the Worker code

Delete everything in the editor and paste the following:

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return new Response(JSON.stringify({ ok: true, service: "aei-relay" }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      });
    }

    const symbol = url.searchParams.get("symbol") || "BTC-USD";
    const kind = url.searchParams.get("kind") || "price";
    const interval = url.searchParams.get("interval") || "1m";
    const range = kind === "intraday" ? "2d" : "1d";

    const yahoo = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=${interval}&range=${range}`;

    let upstream;
    try {
      upstream = await fetch(yahoo, {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        },
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: "upstream_failed", detail: String(e) }), {
        status: 502,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      });
    }

    const raw = await upstream.json();

    const result = raw?.chart?.result?.[0];
    if (!result) {
      return new Response(JSON.stringify({ error: "no_data", symbol }), {
        status: 404,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      });
    }

    const meta = result.meta || {};
    const ts = result.timestamp || [];
    const q = result.indicators?.quote?.[0] || {};

    const shape = (i) => ({
      open: q.open?.[i],
      high: q.high?.[i],
      low: q.low?.[i],
      close: q.close?.[i],
      volume: q.volume?.[i],
      timestamp: ts[i] ? new Date(ts[i] * 1000).toISOString() : new Date().toISOString(),
    });

    let payload;
    if (kind === "price") {
      const last = shape(ts.length - 1);
      payload = {
        close: meta.regularMarketPrice ?? last.close,
        bid: meta.regularMarketPrice ?? last.close,
        ask: meta.regularMarketPrice ?? last.close,
        volume: last.volume,
      };
    } else if (kind === "intraday") {
      payload = shape(ts.length - 1);
    } else if (kind === "history") {
      const limit = parseInt(url.searchParams.get("limit") || "200", 10);
      payload = [];
      for (let i = Math.max(0, ts.length - limit); i < ts.length; i++) {
        payload.push(shape(i));
      }
    } else {
      return new Response(JSON.stringify({ error: "unknown_kind", kind }), {
        status: 400,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      });
    }

    return new Response(JSON.stringify(payload), {
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=15",
      },
    });
  },
};
```

1.3 Deploy and note the URL

1. Click Save and Deploy (top right)
2. After deployment, note the URL at the top — it looks like:
   ```
   https://aei-relay.<your-subdomain>.workers.dev
   ```
3. Write this URL down. You will need it in Step 3.

1.4 Verify the Worker works

Open a terminal and run these two commands (replace <your-subdomain> with the actual subdomain):

```bash
curl "https://aei-relay.<your-subdomain>.workers.dev/health"
```

Expected output:

```json
{"ok":true,"service":"aei-relay"}
```

```bash
curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTC-USD&kind=price"
```

Expected output (values will vary):

```json
{"close":95432.12,"bid":95432.12,"ask":95432.12,"volume":12345}
```

If either command fails, stop here. Do not proceed to Step 2. The Worker must return valid JSON before the rest of the pipeline can work.

Common failure: If /health returns 404, you pasted the code incorrectly or did not save. Re-edit the Worker and redeploy.

If kind=price returns {"error":"no_data"}, try BTCUSD=X instead of BTC-USD:

```bash
curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTCUSD=X&kind=price"
```

If that works, Yahoo has renamed the ticker for Cloudflare's IP range. Note which symbol works — you may need to update SYMBOL_FALLBACKS in app.py later.

---

Step 2 — Set RELAY_URL on Heroku

In your terminal, run:

```bash
heroku config:set RELAY_URL="https://aei-relay.<your-subdomain>.workers.dev" -a your-app-name
```

Replace <your-subdomain> with your actual Worker subdomain and your-app-name with your Heroku app name.

This triggers an automatic dyno restart. Wait ~30 seconds.

Confirm it took effect:

```bash
heroku config:get RELAY_URL -a your-app-name
```

Should print your Worker URL.

---

Step 3 — Deploy the updated app.py

3.1 Save the new app.py

The complete file was provided in my earlier message. Save it as app.py in your local backend directory (overwriting the old one).

3.2 Push to Heroku

```bash
cd /path/to/your/backend
git add app.py
git commit -m "v4.15: Cloudflare Worker relay"
git push heroku main
```

3.3 Watch the logs

```bash
heroku logs --tail -a your-app-name
```

You should see:

```
🌐 Relay: https://aei-relay.<your-subdomain>.workers.dev
🌐 ÆEA Mini App Bridge listening on http://0.0.0.0:8765
```

If you instead see:

```
🌐 Relay: UNSET — set RELAY_URL env var!
```

Then Step 2 did not take effect. Re-run heroku config:set and wait for the dyno to restart.

---

Step 4 — Deploy the updated index.html

4.1 Save the new index.html

The complete file was provided in my earlier message. Save it as index.html in your frontend repo (overwriting the old one).

4.2 Push to GitHub Pages

```bash
cd /path/to/your/frontend
git add index.html
git commit -m "v3.4.3: relay status HUD"
git push origin main
```

If your frontend is served from Heroku instead of GitHub Pages, push to Heroku instead:

```bash
git add index.html
git commit -m "v3.4.3: relay status HUD"
git push heroku main
```

Wait 60 seconds for GitHub Pages to rebuild (or for Heroku to redeploy).

---

Step 5 — Verify end-to-end

5.1 Verify the bridge is alive

```bash
curl "https://your-app-name.herokuapp.com/health"
```

Expected output:

```json
{"ok":true,"service":"aei-bridge","version":"4.15",...}
```

If ok is false or stale is true, the feed has not received a price in the last 60 seconds. Continue to the next step to diagnose.

5.2 Verify the relay is reachable from the bridge

```bash
curl "https://your-app-name.herokuapp.com/probe"
```

Expected output (values will vary):

```json
{
  "active_symbol": "BTC-USD",
  "primary_symbol": "BTC-USD",
  "chain": ["BTC-USD", "BTCUSD=X"],
  "chain_index": 0,
  "empty": false,
  "relay_url": "https://aei-relay.<your-subdomain>.workers.dev",
  "failure_count": 0,
  "fallback_count": 0,
  "raw_response": {"close": 95432.12, "bid": 95432.12, "ask": 95432.12, "volume": 12345}
}
```

Key check: "empty": false and raw_response contains a real price.

If "empty": true, the Worker is not returning data to Heroku. Go back to Step 1.4 and confirm the Worker works from your terminal.

5.3 Restart the feed in Telegram

Open your bot chat and send, in this order:

```
/stop_feed
```

Then:

```
/start_feed
```

Then:

```
/status
```

The Price field should now show a real number (not 0.00000), and Engine State should read ✅ Initialized.

If price is still 0.00000, send:

```
/probe
```

and read the diagnostic output.

5.4 Verify the Mini App

1. Open Telegram
2. Tap the ÆEA Mini App button (or send /webapp and tap the button)
3. The HUD at the top right should show:
   ```
   CONN CONNECTED
   RELAY UP
   ```
4. BID and ASK should show live prices
5. The chart should populate with candles within ~10 seconds

---

Step 6 — Troubleshooting Reference

Symptom Cause Fix
Worker /health returns 404 Wrong code or not saved Re-paste the Worker code and redeploy
Worker returns no_data for BTC-USD Yahoo renamed the ticker for Cloudflare's IP Try BTCUSD=X — if that works, it is already in the fallback chain
/probe on Heroku shows Relay URL: UNSET Env var not set Re-run heroku config:set RELAY_URL=...
/probe shows empty: true Worker is unreachable from Heroku Check Worker URL with curl from Step 1.4
/status still shows 0.00000 Feed was running before the update /stop_feed then /start_feed
/health on Heroku shows stale: true Feed loop is not receiving data /stop_feed then /start_feed; check heroku logs
Mini App shows RELAY: DOWN Frontend cannot reach Heroku bridge Check curl https://your-app.herokuapp.com/health
Mini App shows CONN DISCONNECTED Bridge is down or CORS is blocking Check heroku logs for bridge errors
BTC-USD fails on Worker but BTCUSD=X works Yahoo ticker rename for Cloudflare IP Already handled — the fallback chain will rotate automatically after 5 failures
Worker exceeds free tier (100k req/day) Polling at 30s + 5s frontend = too many Reduce UPDATE_INTERVAL in app.py or add caching

---

Step 7 — Verify the Full Pipeline

Run this command sequence to confirm every layer is working:

```bash
# 1. Worker is alive
curl "https://aei-relay.<your-subdomain>.workers.dev/health"

# 2. Worker returns price data
curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTC-USD&kind=price"

# 3. Heroku bridge is alive
curl "https://your-app-name.herokuapp.com/health"

# 4. Heroku bridge reaches the Worker
curl "https://your-app-name.herokuapp.com/probe"

# 5. Heroku bridge has a current snapshot
curl "https://your-app-name.herokuapp.com/state"
```

All five should return JSON with no error fields. If any of them fail, the failure is at that layer:

· 1 or 2 fails → Worker problem (Step 1)
· 3 fails → Heroku bridge problem (Step 3)
· 4 fails but 1–3 pass → RELAY_URL mismatch (Step 2)
· 5 returns price: "0.0" → feed not running (send /start_feed in Telegram)

---

Summary of Files Changed

File Where What Changed
Cloudflare Worker dash.cloudflare.com New — the relay itself
app.py Heroku YahooFinanceFeed → FeedClient; added RELAY_URL env handling
index.html GitHub Pages Added RELAY status to metrics panel, HUD, help panel, and export

Config Value
Heroku RELAY_URL https://aei-relay.<your-subdomain>.workers.dev
index.html BACKEND_URL https://your-app-name.herokuapp.com
index.html RELAY_URL (optional — leave empty unless you want direct-to-Worker price display)

---

What "Working" Looks Like

After all five verification commands return valid JSON, and /status in Telegram shows a live price:

· The engine will begin publishing snapshots to the bridge
· The Mini App will populate with candles
· The Arc-Length Coherence gate will operate normally
· FVG drawing tools will work
· Signal alerts will fire when the imbalance condition is met

At that point, the Yahoo Finance rate-limit problem is permanently resolved. The Heroku dyno's IP is no longer exposed to Yahoo. Even if Cloudflare's edge gets rate-limited, the Worker's /health endpoint will still respond, and you can rotate Worker regions or add a second relay if needed without touching the bot.

---

One Final Note

If you ever need to switch back to direct Yahoo calls (e.g., for testing), you can:

```bash
heroku config:unset RELAY_URL -a your-app-name
```

But this will re-expose the Heroku IP to Yahoo and the rate-limit problem will return. The Worker relay is the permanent fix.