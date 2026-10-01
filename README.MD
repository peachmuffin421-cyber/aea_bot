# **ÆEA BOT — DEPLOYMENT GUIDE**
*Version:* 4.0.1 (MQL4-Parity + MT4/TradingView TWA Edition — Split-Origin Architecture + Cloudflare Worker Relay + CORS/Backend-URL Hardening)
*Target:* `index.html` (static frontend) + `app.py` (bot + bridge) + `worker.js` (relay)
*Prereqs:* `TELEGRAM_BOT_TOKEN`, a Cloudflare account, a GitHub account, a Heroku account, `git`, `wrangler`, `heroku` CLI, Python 3.11+

---

## 1. Architecture Overview

The ÆEA system is three cooperating surfaces:

| Layer | Host | Responsibility |
|---|---|---|
| **Frontend** | GitHub Pages (or any HTTPS static host) | Serves `index.html` — the ÆEA MT4/TradingView-style engine UI: interactive candlestick chart with crosshair/pan/zoom, indicator sub-panels, FVG drawing tools, order ticket, engine settings, regime map, log bar, signal markers, polling logic. |
| **Backend** | Heroku (or any HTTPS Python host) | Runs `app.py`: Telegram bot polling, `AEEA_Engine` (MQL4-parity port), bridge endpoints (`/state`, `/miniapp-state`, `/ohlcv`, `/signals`, `/handshake`, `/fvg`, `/probe`, `/diagnostics`, `/health`, `/config`, `/orders`, `/regime-map`, `/indicators`, `/log`, `/settings`, `/symbol`, `/order`, `/order/close`). |
| **Relay** | Cloudflare Workers | Proxies Yahoo Finance through Cloudflare's egress IPs so the Heroku dyno's IP is never rate-limited by Yahoo. |

The Mini App is not a separate server. It is the same `index.html` that runs locally, loaded by Telegram's WebView, authenticated via `initData`, bound back to the bot's `chat_id` through `/handshake`.

**Critical for split-origin correctness (v4.0.1):** Because the frontend is served from GitHub Pages (origin `https://<user>.github.io`) and the backend lives on Heroku (origin `https://<app>.herokuapp.com`), the frontend must be explicitly told the backend origin. This is done with the `?backend=` query parameter (see §5.1 and §6.1). Without it, the TWA will attempt to fetch `/miniapp-state`, `/ohlcv`, etc. from GitHub Pages and receive 404s.

---

## 2. Repository Layout

**Repo A — Frontend (GitHub Pages):**

```

aei-miniapp/
├── index.html
├── README.md
└── (optional assets)

```

**Repo B — Backend + Relay (Heroku):**

```

aei-backend/
├── app.py
├── index.html           # optional fallback served at GET /
├── requirements.txt
├── runtime.txt
├── Procfile
├── app.json
├── .env.example
├── .gitignore
├── worker.js            # Cloudflare Worker source (deployed separately)
├── wrangler.toml
├── package.json
└── README.md

```

---

## 3. Cloudflare Worker Deployment

### 3.1 Install Wrangler

```bash
npm install -g wrangler
wrangler login
```

3.2 Deploy the Worker

From the repo root (where wrangler.toml lives):

```bash
wrangler deploy
```

Wrangler prints the deployed URL, e.g.:

```
https://aei-relay.<your-subdomain>.workers.dev
```

3.3 (Optional) Enable the Shared-Secret Gate

```bash
wrangler secret put RELAY_KEY
# paste a random 32+ character string when prompted
```

If set, the Worker rejects any non-/health request missing the X-Relay-Key header. Pair with the same value in Heroku's RELAY_KEY config var.

3.4 Verify the Worker

```bash
curl "https://aei-relay.<your-subdomain>.workers.dev/health"
# → {"ok":true,"service":"aei-relay","gated":false}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTC-USD&kind=price"
# → {"symbol":"BTC-USD","close":95432.12,...}
```

---

4. Heroku Backend Deployment

4.1 Create the Heroku App

```bash
cd aei-backend
git init
heroku create your-app-name
```

4.2 Set Config Vars

```bash
heroku config:set TELEGRAM_BOT_TOKEN="123456:ABCdef…" -a your-app-name
heroku config:set RELAY_URL="https://aei-relay.<your-subdomain>.workers.dev" -a your-app-name
heroku config:set TELEGRAM_WEBAPP_URL="https://<your-username>.github.io/<repo-name>/" -a your-app-name
heroku config:set CORS_ORIGIN="https://<your-username>.github.io" -a your-app-name
heroku config:set REQUIRE_AUTH="1" -a your-app-name
```

Optional:

```bash
heroku config:set RELAY_KEY="<same value as wrangler secret>" -a your-app-name
heroku config:set UPDATE_INTERVAL="30" -a your-app-name
heroku config:set SYMBOL="BTC-USD" -a your-app-name
heroku config:set LOG_BUFFER_SIZE="200" -a your-app-name
```

TELEGRAM_WEBAPP_URL does two things:

· Tells the bot where the Mini App lives (used for MenuButtonWebApp).
· Prevents TunnelManager from spawning cloudflared (which is not installed on Heroku).

REQUIRE_AUTH defaults to 1. Set it to 0 only for local development without Telegram initData.

Critical for CORS (v4.0.1): CORS_ORIGIN should be set to your GitHub Pages origin (https://<your-username>.github.io), NOT *, so that the browser preflight for X-Telegram-Init-Data is honored correctly and the wildcard does not collide with credentialed requests. If you must use *, the frontend still works because it sends credentials: 'omit', but locking down is recommended.

4.3 Deploy

```bash
git add .
git commit -m "ÆEA backend v4.0.1 (MQL4-Parity + MT4/TradingView TWA — CORS hardening)"
git push heroku main
```

4.4 Verify the Backend

```bash
curl "https://your-app-name.herokuapp.com/health"
# → {"ok":true,"service":"aei-bridge","version":"4.0.1",...}

curl -H "X-Telegram-Init-Data: <valid>" "https://your-app-name.herokuapp.com/config"
# → {"public_url":"...","require_auth":true,...}
```

Key check on /probe: "empty": false and relay_url populated.

---

5. GitHub Pages Frontend Deployment

5.1 Configure the Backend URL

The patched index.html (v4.0.1) resolves the backend in this order:

1. window.__AEEA_BACKEND_URL__ (if the host page sets it before the script loads)
2. ?backend=https://... query-string override (persisted to localStorage)
3. localStorage['aeea_backend_url']
4. same-origin (relative paths)

No hard-coded Heroku fallback. A fork must be explicitly configured.

In the Telegram Mini App context, the Web App URL configured in BotFather must include the query string:

```
https://<your-username>.github.io/<repo-name>/?backend=https://your-app-name.herokuapp.com/
```

This is what makes the TWA able to reach the Heroku backend. Without it, the TWA loads, renders the empty chart, and displays a connection badge of no backend with an explicit error banner.

5.2 Push to GitHub

```bash
cd aei-miniapp
git init
git add index.html README.md
git commit -m "ÆEA Mini App v4.0.1 (MT4/TradingView-style)"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

5.3 Enable Pages

1. Repo → Settings → Pages
2. Source: Deploy from a branch
3. Branch: main / / (root)
4. Save

After ~60 seconds, the site is live at:

```
https://<your-username>.github.io/<repo-name>/
```

Open it with ?backend=https://your-app-name.herokuapp.com/ to point it at your backend.

---

6. BotFather Configuration

6.1 Create the Mini App

```
/newapp
→ pick your bot
→ Title:          ÆEA Engine
→ Description:    MQL4-Parity Trading Bot Visualization
→ Photo:          640x360 PNG (optional)
→ Short name:     aea-engine
→ Web App URL:    https://<your-username>.github.io/<repo-name>/?backend=https://your-app-name.herokuapp.com/
→ Short name in menu: ÆEA
```

Critical: the Web App URL must be the GitHub Pages URL with the ?backend= query string appended. Telegram loads the static frontend; the frontend then talks to Heroku because it has been told the backend origin explicitly.

Without the ?backend= parameter, the TWA shows no backend in the connection badge and refuses to poll. This is intentional: it eliminates the silent-failure mode where the TWA would otherwise poll GitHub Pages for /miniapp-state.

6.2 Set the Menu Button

```
/setmenubutton
→ pick your bot
→ URL: https://<your-username>.github.io/<repo-name>/?backend=https://your-app-name.herokuapp.com/
→ Button text: ÆEA Mini App
```

---

7. Environment Variables Reference

Heroku (Backend)

Variable Default Purpose
TELEGRAM_BOT_TOKEN (required) Bot token from BotFather. Also derives the initData HMAC key.
TELEGRAM_WEBAPP_URL (empty) GitHub Pages URL. Skips tunnel spawn.
RELAY_URL (empty) Cloudflare Worker URL. Required for live prices.
RELAY_KEY (empty) Optional shared secret matching wrangler secret put RELAY_KEY.
RELAY_TIMEOUT 10 Per-attempt HTTP timeout (seconds).
RELAY_MAX_RETRIES 3 Retries before symbol-chain rotation.
PORT Heroku-assigned Bridge bind port (Heroku prefers this over BRIDGE_PORT).
BRIDGE_HOST 0.0.0.0 Bind address. Heroku requires 0.0.0.0.
BRIDGE_USE_TLS 0 Heroku terminates TLS at its router → leave 0.
BRIDGE_TLS_CERT / BRIDGE_TLS_KEY (empty) Only when running your own TLS.
BRIDGE_TUNNEL cloudflared Ignored on Heroku (no cloudflared binary).
CORS_ORIGIN * Set to your GitHub Pages origin to lock down writes.
REQUIRE_AUTH 1 Enforce X-Telegram-Init-Data on all non-/health endpoints.
LOG_BUFFER_SIZE 200 Ring-buffer size for the /log endpoint.
SYMBOL BTC-USD Default trading symbol.
UPDATE_INTERVAL 30 Price-feed polling interval (seconds).

GitHub Pages (Frontend)

There are no environment variables on static hosting. All configuration lives in index.html and is resolved at boot (see §5.1). The canonical way to configure it is through the ?backend= query parameter in the BotFather Web App URL (§6.1).

---

8. Verification Checklist

After all three surfaces are deployed:

☐ curl https://aei-relay.<sub>.workers.dev/health returns {"ok":true,…}
☐ curl https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=price returns a real price
☐ curl https://your-app.herokuapp.com/health returns {"ok":true,…}
☐ curl -H "X-Telegram-Init-Data: <valid>" https://your-app.herokuapp.com/probe shows "empty": false
☐ https://<user>.github.io/<repo>/?backend=https://your-app.herokuapp.com/ loads the ÆEA UI in a browser
☐ Telegram → /start → tap ⚡ Open ÆEA Mini App
☐ Top toolbar renders symbol + timeframe + chart-type
☐ Connection badge shows connected (green)
☐ Chart renders candlesticks with crosshair
☐ Pan/zoom works (drag, wheel, pinch)
☐ Long-press opens the context menu
☐ · IND opens the indicator picker
☐ Added indicator sub-panels render live series
☐ REGIME view renders the per-bar map
☐ Engine Panel shows KC/prime/dime/mem/tag/invert/safety
☐ Kronecker Panel shows live m/n
☐ Order Ticket places simulated orders
☐ FVG list shows all anchors
☐ Log bar shows recent events
☐ heroku logs --tail -a your-app-name shows 🔗 Web App session registered: user_id=…

---

9. Security Notes

9.1 initData Verification

Every non-/health request carries the X-Telegram-Init-Data header (when REQUIRE_AUTH=1). The bridge verifies it using the standard scheme:

```
secret_key        = HMAC_SHA256(bot_token, "WebAppData")
data_check_string = sorted("key=value" lines, excluding "hash") joined by "\n"
expected_hash     = HMAC_SHA256(data_check_string, secret_key).hexdigest()
```

Freshness is enforced: auth_date must be within [-5 min, +24 h] of server time.

9.2 CORS (v4.0.1 Hardening)

The bridge now:

· Responds to OPTIONS preflight with 204 No Content.
· Advertises X-Telegram-Init-Data and Authorization in Access-Control-Allow-Headers.
· Advertises GET, POST, DELETE, OPTIONS in Access-Control-Allow-Methods.
· Caches preflight for 86400 seconds via Access-Control-Max-Age.
· Sends Vary: Origin when CORS_ORIGIN is not *.

The frontend always sends credentials: 'omit' and uses header-based auth (X-Telegram-Init-Data), so wildcard CORS_ORIGIN=* is technically compatible. Locking down CORS_ORIGIN to the GitHub Pages origin is recommended.

9.3 Relay Exposure

The Cloudflare Worker is public by default. If you enable RELAY_KEY, every non-/health request must present X-Relay-Key. app.py reads RELAY_KEY from env and injects the header automatically.

9.4 Tunnel Exposure (Local Mode Only)

When running locally without TELEGRAM_WEBAPP_URL, app.py spawns cloudflared/ngrok/serveo. The public tunnel URL is registered as a MenuButtonWebApp. Rotate the bot token in BotFather if a tunnel URL leaks during an active session.

---

10. Local-Only Mode

Useful for development without Telegram:

```bash
export TELEGRAM_BOT_TOKEN='123456:ABC…'
export RELAY_URL='https://aei-relay.<sub>.workers.dev'
export REQUIRE_AUTH='0'
python3 app.py
```

The bot starts, the bridge listens on http://127.0.0.1:8765, and the tunnel spawns automatically. Open http://localhost:8765/ in a browser on the same machine. With REQUIRE_AUTH=0, the auth gate is bypassed.

To point the local browser at the same bridge without a query string, same-origin resolution kicks in (step 4 in §5.1).

---

11. Troubleshooting Matrix

Symptom Diagnosis Fix
Worker /health 404s Deploy failed or wrong URL Re-run wrangler deploy; confirm the printed URL
Worker returns no_data for BTC-USD Yahoo renamed ticker for Cloudflare IP Try BTCUSD=X; SYMBOL_FALLBACKS rotates automatically
/probe on Heroku shows relay_url: "" RELAY_URL not set heroku config:set RELAY_URL=…
/probe shows "empty": true Worker unreachable from dyno curl $RELAY_URL/health from your terminal; check RELAY_KEY match
/status shows 0.00000 Feed was running before relay was set Send /stop_feed, then /start_feed
/health on Heroku shows "stale": true Feed loop not receiving data Check heroku logs --tail; send /stop_feed then /start_feed
Mini App HUD shows no backend in connection badge Web App URL lacks ?backend= Append ?backend=https://your-app.herokuapp.com/ to the BotFather Web App URL
Mini App shows Awaiting OHLCV data… forever Backend URL resolution failed OR CORS blocked Verify the ?backend= parameter; verify CORS_ORIGIN matches your GitHub Pages origin; check DevTools Network tab
Symbol change → Symbol change failed: unknown /symbol returned non-JSON or the relay returned no price Check heroku logs for change_symbol_exception; ensure RELAY_URL is set and the Worker is healthy for the target symbol
POST /handshake → 403 invalid_init_data Bot token mismatch Ensure Heroku's TELEGRAM_BOT_TOKEN matches the token used in BotFather
All non-/health endpoints return 401 REQUIRE_AUTH=1 and no initData Launch from inside Telegram, or set REQUIRE_AUTH=0 for local dev
Telegram button opens blank page Web App URL is http:// Recheck /newapp — must be HTTPS
FVG commits silently vanish Not authenticated Launch from Telegram; check heroku logs for 401 unauthorized
Chart drag closes Mini App disableVerticalSwipes not applied Confirm telegram-web-app.js loads before app JS
Indicator sub-panel shows Awaiting data… /indicators endpoint returned empty Ensure ohlcv_history has ≥ MIN_HISTORY_WINDOW bars
heroku logs shows bind: Address already in use Port conflict Ensure app.py reads $PORT (it does via BRIDGE_PORT fallback)
Connection badge stuck on retrying… Backend reachable but auth failing Check /health from terminal; check that /miniapp-state returns 200; verify REQUIRE_AUTH and header propagation

---

12. Update Workflow

Frontend changes:

```bash
cd aei-miniapp
# edit index.html
git add index.html
git commit -m "Update chart overlay"
git push origin main
# GitHub Pages redeploys in ~60 s
```

Backend changes:

```bash
cd aei-backend
# edit app.py
git add app.py
git commit -m "Fix FVG decoherence"
git push heroku main
# Heroku rebuilds and restarts in ~2 min
```

Relay changes:

```bash
# edit worker.js
wrangler deploy
# Cloudflare redeploys in ~5 s
```

No coordination needed — the three deploys are independent.

Config-var changes (CORS, backend URL, relay URL):

```bash
heroku config:set CORS_ORIGIN="https://<user>.github.io" -a your-app-name
heroku config:set TELEGRAM_WEBAPP_URL="https://<user>.github.io/<repo>/?backend=https://your-app-name.herokuapp.com/" -a your-app-name
```

After changing TELEGRAM_WEBAPP_URL, re-run /setmenubutton in BotFather so the menu button picks up the new URL.

---

13. Q.E.D.

The Mini App is now served from two cooperating origins, fed by a third:

· GitHub Pages — the presentation surface, loaded by Telegram's WebView.
· Heroku — the computational substrate, polled by the frontend.
· Cloudflare Worker — the market-data relay, polled by the dyno.

BACKEND_URL is the wire between frontend and backend. RELAY_URL is the wire between backend and relay. Set them once, push all three, and the Mini App is live inside Telegram.

v4.0.1 addendum: The wire between frontend and backend is now established explicitly via the ?backend= query parameter in the BotFather Web App URL, and CORS preflight is fully honored by the bridge. The failure mode of the earlier version — silent Awaiting OHLCV data… with no diagnostic — is now surfaced as no backend in the connection badge, with a corresponding error banner.