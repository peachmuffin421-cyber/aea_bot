# **ÆEA BOT** — *DEPLOYMENT GUIDE*

Version: 4.1.0 (MQL4-Parity + MT4/TradingView TWA Edition — Split-Origin Architecture + Cloudflare Worker Relay + CORS/Backend-URL Hardening + FF-Exact State Propagation + Audit-Patched Frontend/Backend)
Target: index.html (static frontend) + app.py (bot + bridge) + worker.js (relay) + supporting repository files
Prereqs: TELEGRAM_BOT_TOKEN, a Cloudflare account, a GitHub account, a Heroku account, git, wrangler, heroku CLI, Python 3.11+

---

0. Version 4.1.0 — Audit-Patched Release Notes

Version 4.1.0 resolves all 60 divergences identified in the ÆEA Audit (D-01 through D-60) between the MQL4 Foundational Framework (æea.mq4) and the TWA/backend port. The patches fall into six categories:

A. Engine state-machine parity (app.py) — Critical fixes.

· D-10 — st.Price is now the previous completed bar's close (ohlcv_history[-2]["close"]), not the current tick close. This restores the FF's Price = iClose(Symbol(), 0, 1) semantics. M()/N() now compare against the correct price.
· D-46 — _signal() no longer sets st.signature or st.GF. Those flags are set only by the Kronecker-delta execution block in _on_bar(), after P()/Q()/A()/B() complete. The pre-4.1.0 flow reinitialized the engine on every signal; the patched flow reinitializes only on a completed trade.
· D-47 — The FF's full Kronecker-delta execution block is now present in _on_bar(), with all 7 sub-branches per side (Diamond, Ruby, Hawk, Dove variants). The pre-4.1.0 _on_bar() stopped after the boundary-pass-condition assignment and never executed a trade from the FF's logic.

B. Exact-arithmetic parity (app.py).

· D-13 — Removed the lossy Fraction.from_float() path. All conversions originate from exact decimal strings via from_decimal_string().
· D-14 — Indicator computations use Fraction internally; projection to Decimal/str only at the JSON serialization boundary.
· D-15 — Removed the dead, non-exact Fraction.sqrt() method.

C. Indicator formula parity (app.py).

· D-25 — _compute_obv() is now cumulative over the full passed array, matching MQL4's iOBV.
· D-26 — _compute_ad() is now cumulative over the full passed array, matching MQL4's iAD.
· D-32 — rsi() uses Wilder smoothing, matching MQL4's iRSI.
· D-34 — Removed the neutral-fill (50.0) placeholder for bars before MIN_HISTORY_WINDOW; only real computed values are written to the indicator matrix.

D. Regime-classification parity (app.py).

· D-41 — _on_call() now uses a while loop with a dynamically re-evaluated bound (MQL4's j < X + 2 semantics). The pre-4.1.0 for j in range(...) materialized the upper bound once, so an in-loop X_scan increment did not extend the scan.

E. Execution-layer parity (app.py).

· D-48 — _execute_trailing_stop() calls _normalize(st.y + 1) at the top, matching the FF's T() which calls Normalize().
· D-49 — _execute_trailing_stop() skips only on tStable/tCoherent regimes. The pre-4.1.0 skip on Stable is removed.
· D-50 — _get_next_topological_target iterates range(st.y + 1, X_PERIOD - 1), matching the FF's i < x - 1.

F. TWA/backend wiring.

· D-35/D-36 — st.m_now/st.n_now are now the authoritative m/n from the most recent _H()/_L() call. _on_tick() no longer re-computes them at a stale st.h.
· D-53 — Removed the hardcoded window.__AEEA_BACKEND_URL__ = 'https://aeea-df7f2ade617d.herokuapp.com/'; from index.html. The resolver falls through ?backend= → localStorage → same-origin, with no silent redirect to the original author's Heroku app.
· D-54 — /miniapp-state now reads the authoritative m_now/n_now from the H()/L() stamps.
· D-55 — Private-attribute access replaced with public FeedClient.failure_count() and FeedClient.last_update() accessors.
· D-56 — /diagnostics returns indicator_col_index alongside the indicator samples so downstream consumers do not assume columns [0]/[1].
· D-60 — BRIDGE_STATE._snapshot removed; /state delegates to engine state. Single source of truth.

Compatibility: Version 4.1.0 is a drop-in replacement for 4.0.1. All environment variables, endpoints, and worker contracts are unchanged. The only breaking change is that /miniapp-state now returns the full FF state (previously partial), and index.html no longer has a hardcoded Heroku fallback — a fork must explicitly configure its own backend origin via ?backend= or window.__AEEA_BACKEND_URL__.

---

1. Architecture Overview

The ÆEA system is three cooperating surfaces:

Layer Host Responsibility
Frontend GitHub Pages (or any HTTPS static host) Serves index.html — the ÆEA MT4/TradingView-style engine UI: interactive candlestick chart with crosshair/pan/zoom, indicator sub-panels, FVG drawing tools, order ticket, engine settings, regime map, log bar, signal markers, polling logic.
Backend Heroku (or any HTTPS Python host) Runs app.py: Telegram bot polling, AEEA_Engine (MQL4-parity port), bridge endpoints (/state, /miniapp-state, /ohlcv, /signals, /handshake, /fvg, /probe, /diagnostics, /health, /config, /orders, /regime-map, /indicators, /log, /settings, /symbol, /order, /order/close).
Relay Cloudflare Workers Proxies Yahoo Finance through Cloudflare's egress IPs so the Heroku dyno's IP is never rate-limited by Yahoo.

The Mini App is not a separate server. It is the same index.html that runs locally, loaded by Telegram's WebView, authenticated via initData, bound back to the bot's chat_id through /handshake.

Critical for split-origin correctness (v4.1.0): Because the frontend is served from GitHub Pages (origin https://<user>.github.io) and the backend lives on Heroku (origin https://<app>.herokuapp.com), the frontend must be explicitly told the backend origin. This is done with the ?backend= query parameter (see §5.1 and §6.1). Without it, the TWA will attempt to fetch /miniapp-state, /ohlcv, etc. from GitHub Pages and receive 404s.

Critical for state freshness (v4.1.0): The TWA polls /miniapp-state every 2 seconds and /diagnostics every 5 seconds. Both endpoints now return the full FF state (via get_signal_status() in app.py). To prevent the slower /diagnostics poll from overwriting live engine state with stale data, absorbDiagnostics() in index.html implements a freshness guard: it only absorbs engine-state fields if the diagnostics snapshot's tick is strictly greater than the last /miniapp-state tick. This guarantees the Engine Panel, Kronecker Panel, and Derivative Panel always display the freshest available state, matching the bot's /status output.

Critical for Kronecker Panel accuracy (v4.1.0): The Kronecker Panel displays the authoritative m/n from the most recent H()/L() call (last_kronecker_m/last_kronecker_n) when the engine has fired at least one Kronecker event. It falls back to the per-tick diagnostic market_m/market_n only when no event has fired yet. This makes the panel match the bot's /status Local m/n field exactly, resolving the pre-4.1.0 D-02 race condition where the panel and the bot could display different values.

Critical for backend origin safety (v4.1.0): The pre-4.1.0 index.html hardcoded window.__AEEA_BACKEND_URL__ = 'https://aeea-df7f2ade617d.herokuapp.com/';, silently routing every fork to the original author's backend. The patched index.html has no hardcoded default — resolution is strictly window.__AEEA_BACKEND_URL__ (host-page override) → ?backend= → localStorage → same-origin.

Critical for single-source-of-truth (v4.1.0): The Cloudflare Worker is deployed exclusively from the aei-relay repository. The backend repository (aei-backend) does not contain worker.js, wrangler.toml, or package.json. The backend reaches the relay only over HTTP via the RELAY_URL environment variable. This eliminates the pre-4.1.0 hazard where two copies of the Worker source could drift and wrangler deploy from either repo would silently overwrite the same Cloudflare Worker named aei-relay.

---

2. Repository Layout

The system spans three cooperating repositories, each with its own .gitignore and its own supporting files. Each has exactly one deploy target.

Repo A — Frontend (GitHub Pages): aei-miniapp/

```
aei-miniapp/
├── index.html
├── README.md
└── .gitignore
```

· Deploy target: GitHub Pages (main:/).
· Deploy command: git push origin main.
· Contains no server-side code, no Worker source, no build step.

Repo B — Backend (Heroku): aei-backend/

```
aei-backend/
├── app.py
├── README.md
├── .gitignore
├── .env.example
├── runtime.txt
├── requirements.txt
├── Procfile
├── app.json
└── index.html           # optional fallback served at GET /
```

· Deploy target: Heroku (Python dyno).
· Deploy command: git push heroku main.
· Contains no worker.js, no wrangler.toml, no package.json. The backend has no file-system relationship with the Worker source. It reaches the relay only over HTTP via RELAY_URL.

Repo C — Relay (Cloudflare Workers): aei-relay/

```
aei-relay/
├── worker.js
├── wrangler.toml
├── package.json
├── README.md
└── .gitignore
```

· Deploy target: Cloudflare Workers edge.
· Deploy command: wrangler deploy (run from this repo's root).
· Sole home of the Worker. Deployed under name = "aei-relay" in wrangler.toml. Because there is exactly one wrangler.toml in exactly one repo, there is no name collision and no deploy-order race.

The three repos deploy independently. No coordination is needed between frontend pushes, backend pushes, and relay pushes.

---

3. Cloudflare Worker Deployment (Repo C — aei-relay)

3.1 Clone and Install Wrangler

```bash
git clone https://github.com/<your-username>/aei-relay.git
cd aei-relay
npm install -g wrangler
wrangler login
```

3.2 Deploy the Worker

From the aei-relay/ repo root (where wrangler.toml lives):

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

4. Heroku Backend Deployment (Repo B — aei-backend)

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

Critical for CORS (v4.1.0): CORS_ORIGIN should be set to your GitHub Pages origin (https://<your-username>.github.io), NOT *, so that the browser preflight for X-Telegram-Init-Data is honored correctly and the wildcard does not collide with credentialed requests. If you must use *, the frontend still works because it sends credentials: 'omit', but locking down is recommended.

4.3 Deploy

```bash
git add .
git commit -m "ÆEA backend v4.1.0 (MQL4-Parity + MT4/TradingView TWA — Audit-Patched)"
git push heroku main
```

4.4 Verify the Backend

```bash
curl "https://your-app-name.herokuapp.com/health"
# → {"ok":true,"service":"aei-bridge","version":"4.1.0",...}

curl -H "X-Telegram-Init-Data: <valid>" "https://your-app-name.herokuapp.com/config"
# → {"public_url":"...","require_auth":true,...}
```

Key check on /probe: "empty": false and relay_url populated.

---

5. GitHub Pages Frontend Deployment (Repo A — aei-miniapp)

5.1 Configure the Backend URL

The patched index.html (v4.1.0) resolves the backend in this order:

1. window.__AEEA_BACKEND_URL__ (if the host page sets it before the script loads)
2. ?backend=https://... query-string override (persisted to localStorage)
3. localStorage['aeea_backend_url']
4. same-origin (relative paths)

No hardcoded Heroku fallback. A fork must be explicitly configured.

D-53: The pre-4.1.0 index.html contained a hardcoded window.__AEEA_BACKEND_URL__ = 'https://aeea-df7f2ade617d.herokuapp.com/'; assignment that silently overrode the ?backend= parameter and routed every fork to the original author's backend. That assignment has been removed.

In the Telegram Mini App context, the Web App URL configured in BotFather must include the query string:

```
https://<your-username>.github.io/<repo-name>/?backend=https://your-app-name.herokuapp.com/
```

This is what makes the TWA able to reach the Heroku backend. Without it, the TWA loads, renders the empty chart, and displays a connection badge of no backend with an explicit error banner.

5.2 Push to GitHub

```bash
cd aei-miniapp
git init
git add index.html README.md .gitignore
git commit -m "ÆEA Mini App v4.1.0 (MT4/TradingView-style, Audit-Patched)"
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

Heroku (Repo B — aei-backend)

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
CORS_ORIGIN  *  Set to your GitHub Pages origin to lock down writes.
REQUIRE_AUTH 1 Enforce X-Telegram-Init-Data on all non-/health endpoints.
LOG_BUFFER_SIZE 200 Ring-buffer size for the /log endpoint.
SYMBOL BTC-USD Default trading symbol.
UPDATE_INTERVAL 30 Price-feed polling interval (seconds).

GitHub Pages (Repo A — aei-miniapp)

There are no environment variables on static hosting. All configuration lives in index.html and is resolved at boot (see §5.1). The canonical way to configure it is through the ?backend= query parameter in the BotFather Web App URL (§6.1).

Cloudflare Workers (Repo C — aei-relay)

Variable Default Purpose
RELAY_KEY (empty) Optional shared secret. Set via wrangler secret put RELAY_KEY. If unset, the gate is skipped.

---

8. Verification Checklist

After all three surfaces are deployed:

· ☐ curl https://aei-relay.<sub>.workers.dev/health returns {"ok":true,…}
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=price returns a real price
· ☐ curl https://your-app.herokuapp.com/health returns {"ok":true,…}
· ☐ curl -H "X-Telegram-Init-Data: <valid>" https://your-app.herokuapp.com/probe shows "empty": false
· ☐ https://<user>.github.io/<repo>/?backend=https://your-app.herokuapp.com/ loads the ÆEA UI in a browser
· ☐ Telegram → /start → tap ⚡ Open ÆEA Mini App
· ☐ Top toolbar renders symbol + timeframe + chart-type
· ☐ Connection badge shows connected (green)
· ☐ Chart renders candlesticks with crosshair
· ☐ Pan/zoom works (drag, wheel, pinch)
· ☐ Long-press opens the context menu
· ☐ + IND opens the indicator picker
· ☐ Added indicator sub-panels render live series
· ☐ REGIME view renders the per-bar map
· ☐ Engine Panel shows live KC/prime/dime/mem/tag/invert/A/B/C/c/tick_tock/signature/safety (v4.1.0)
· ☐ Kronecker Panel shows live m/n matching the bot's /status Local m/n (v4.1.0, D-35/D-36/D-54)
· ☐ Derivative Panel shows live Z/z/O/o/W/w/I/iI/J/iJ (v4.1.0)
· ☐ Order Ticket places simulated orders
· ☐ FVG list shows all anchors
· ☐ Log bar shows recent events
· ☐ heroku logs --tail -a your-app-name shows 🔗 Web App session registered: user_id=…
· ☐ v4.1.0 addendum: On a Kronecker event, the Log Bar shows 🔷 Diamond, 🔻 Ruby, 🦅 Hawk, 🕊️ Dove, 🐂 Bull, 🐻 Bear, 🥃 Whisky, 🍷 Wine, 💧 Watter, or 🩸 Blood — confirming the FF's execution block is live (D-46/D-47).

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

9.2 CORS (v4.1.0 Hardening)

The bridge now:

· Responds to OPTIONS preflight with 204 No Content.
· Advertises X-Telegram-Init-Data, Authorization, X-Relay-Key, X-Limit, and X-Since in Access-Control-Allow-Headers.
· Advertises GET, POST, DELETE, OPTIONS in Access-Control-Allow-Methods.
· Caches preflight for 86400 seconds via Access-Control-Max-Age.
· Sends Vary: Origin when CORS_ORIGIN is not *.

The frontend always sends credentials: 'omit' and uses header-based auth (X-Telegram-Init-Data), so wildcard CORS_ORIGIN=* is technically compatible. Locking down CORS_ORIGIN to the GitHub Pages origin is recommended.

9.3 Relay Exposure

The Cloudflare Worker is public by default. If you enable RELAY_KEY, every non-/health request must present X-Relay-Key. app.py reads RELAY_KEY from env and injects the header automatically.

9.4 Tunnel Exposure (Local Mode Only)

When running locally without TELEGRAM_WEBAPP_URL, app.py spawns cloudflared/ngrok/serveo. The public tunnel URL is registered as a MenuButtonWebApp. Rotate the bot token in BotFather if a tunnel URL leaks during an active session.

9.5 Single-Source-of-Truth (v4.1.0)

The Cloudflare Worker is deployed exclusively from aei-relay. The aei-backend repository contains no worker.js, no wrangler.toml, and no package.json. This guarantees:

· Exactly one wrangler deploy command can publish the Worker.
· The Worker's name (aei-relay in wrangler.toml) cannot collide with a second deployment from another repo.
· No deploy-order race can silently overwrite the live Worker with a divergent copy.
· The backend's relationship with the relay is strictly HTTP-over-RELAY_URL, with no file-system or compile-time coupling.

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
Worker /health 404s Deploy failed or wrong URL Re-run wrangler deploy from aei-relay/; confirm the printed URL
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
Kronecker Panel m/n differs from bot's /status Pre-4.1.0 race condition v4.1.0 resolves this via authoritative H()/L() stamps + freshness guard. Upgrade both app.py and index.html to 4.1.0 simultaneously.
Engine Panel shows A true, B true, C true, c true, tick_tock false as constants Pre-4.1.0 missing payload fields v4.1.0 adds these to /miniapp-state. Verify the deployed app.py is 4.1.0 by checking /health "version" field.
Derivative Panel shows default values (Z:1, z:1, O:1, …) Pre-4.1.0 missing payload fields v4.1.0 adds these to /miniapp-state. Verify index.html absorbMiniAppState() reads them (search for ma.Z in the served source).
No Diamond/Ruby/Hawk/Dove/Bull/Bear logs in the Log Bar after signals fire Pre-4.1.0 missing execution block v4.1.0 ports the FF's Kronecker-delta execution block into _on_bar() (D-46/D-47). Verify heroku logs shows 🔷 Diamond or 🔻 Ruby after a signal.
Engine reinitializes on every signal (state resets too often) Pre-4.1.0 _signal() set signature/GF v4.1.0 moves those flags to the execution block. Verify heroku logs does not show OnReInit() completed after every SIGNAL #N line.
Fork's TWA silently routes to aeea-df7f2ade617d.herokuapp.com Pre-4.1.0 hardcoded backend URL v4.1.0 removes the hardcoded assignment (D-53). Verify the served index.html contains no window.__AEEA_BACKEND_URL__ default assignment.
wrangler deploy from two repos overwrites the same Worker Pre-4.1.0 duplicated Worker source in aei-backend and aei-relay v4.1.0 removes the Worker from aei-backend entirely. wrangler deploy must be run only from aei-relay/.

---

12. Update Workflow

Frontend changes (Repo A — aei-miniapp):

```bash
cd aei-miniapp
# edit index.html
git add index.html
git commit -m "Update chart overlay"
git push origin main
# GitHub Pages redeploys in ~60 s
```

Backend changes (Repo B — aei-backend):

```bash
cd aei-backend
# edit app.py
git add app.py
git commit -m "Fix FVG decoherence"
git push heroku main
# Heroku rebuilds and restarts in ~2 min
```

Relay changes (Repo C — aei-relay):

```bash
cd aei-relay
# edit worker.js
git add worker.js
git commit -m "Rotate symbol fallback chain"
git push origin main
wrangler deploy
# Cloudflare redeploys in ~5 s
```

Config-var changes (CORS, backend URL, relay URL):

```bash
heroku config:set CORS_ORIGIN="https://<user>.github.io" -a your-app-name
heroku config:set TELEGRAM_WEBAPP_URL="https://<user>.github.io/<repo>/?backend=https://your-app-name.herokuapp.com/" -a your-app-name
```

After changing TELEGRAM_WEBAPP_URL, re-run /setmenubutton in BotFather so the menu button picks up the new URL.

Relay secret rotation:

```bash
cd aei-relay
wrangler secret put RELAY_KEY
# paste new value
heroku config:set RELAY_KEY="<same value>" -a your-app-name
```

No coordination needed — the three deploys are independent. The Worker source lives in exactly one repo (aei-relay), and the deployed Worker is unambiguous by construction.

---

13. Q.E.D.

The Mini App is now served from two cooperating origins, fed by a third:

· GitHub Pages — the presentation surface, loaded by Telegram's WebView.
· Heroku — the computational substrate, polled by the frontend.
· Cloudflare Worker — the market-data relay, polled by the dyno.

BACKEND_URL is the wire between frontend and backend. RELAY_URL is the wire between backend and relay. Set them once, push all three, and the Mini App is live inside Telegram.

v4.1.0 addendum: The wire between frontend and backend now carries the full FF state — not just the price/regime/tick summary of earlier versions, but every live field the MQL4 Foundational Framework maintains: the A/B/C/c flags, KC/invert/tag/prime/dime/mem, tick_tock/signature/safety, all trailing_stop_* fields, all directional derivatives (Z/z/O/o/W/w/I/iI/J/iJ), scan bounds, volatility state, boundary pass conditions, and the authoritative Kronecker stamps (last_kronecker_m/last_kronecker_n/last_kronecker_h). The freshness guard in absorbDiagnostics() ensures the slower 5-second /diagnostics poll cannot overwrite the faster 2-second /miniapp-state snapshot with stale data. The Kronecker Panel's m/n now match the bot's /status Local m/n exactly, because both read from the same per-H()/L() stamp. The failure mode of the earlier version — silent divergence between the bot's state and the TWA's display — is eliminated.

Audit-patch addendum: All 60 divergences identified in the ÆEA Audit (D-01 through D-60) between the MQL4 Foundational Framework (æea.mq4) and the TWA/backend port are resolved in the v4.1.0 app.py and index.html editions. The Critical D-46/D-47 fixes (Kronecker-delta execution block, signature/GF lifecycle) restore the FF's signal-to-execution flow: signals now fire, executions now run, and the engine reinitializes only on a completed trade. The High D-10/D-14/D-25/D-26/D-32/D-53 fixes restore MQL4-parity arithmetic (previous-bar Price, exact Fraction indicators, cumulative OBV/AD, Wilder RSI) and eliminate the hardcoded backend URL. The Medium D-11/D-35/D-36/D-41/D-48/D-50/D-60 fixes restore per-bar st.open deferral, authoritative m/n stamping, MQL4-semantics _on_call() loop bound, Normalize() at the top of trailing-stop execution, off-by-one in topological target search, and single-source-of-truth bridge state. The Low D-15/D-34/D-49/D-55/D-56 fixes remove dead code, neutralize placeholder fills, correct the trailing-stop regime skip, expose public accessors, and tag indicator sample columns with their index.

Single-source-of-truth addendum: The Cloudflare Worker lives exclusively in aei-relay. The aei-backend repository has no worker.js, no wrangler.toml, and no package.json. This is the corrected layout: one Worker source, one wrangler.toml, one wrangler deploy command, one Cloudflare Worker named aei-relay. There is no deploy-order race, no name collision, and no possibility of the two repos drifting. The backend's relationship with the relay is strictly HTTP-over-RELAY_URL.

The ÆEA v4.1.0 port is now a faithful reproduction of the Foundational Framework's state machine, its exact-arithmetic discipline, its indicator formulas, its regime taxonomy, its Kronecker gate, its execution logic, and its observer/measurement layer — with the additionally-required TWA/backend wiring hardened against the split-origin, staleness, and single-source-of-truth failure modes documented in the Audit.

---

SECTION 0 — Repository Map & File Index

The ÆEA v4.1.0 system spans three cooperating repositories, each with its own .gitignore and its own supporting files. This document enumerates every file, in dependency order, with the full unabridged content for each.

Repo A — Frontend (GitHub Pages): aei-miniapp/

1. .gitignore
2. index.html — (delivered separately; see the patched index.html *.md edition)
3. README.md — (frontend-scoped; provided below as FILE 3)

Repo B — Backend (Heroku): aei-backend/

4. .gitignore
5. .env.example
6. runtime.txt
7. requirements.txt
8. Procfile
9. app.json
10. README.md — (backend-scoped; this is the canonical ÆEA Deployment Guide, delivered as its own *.md edition)
11. app.py — (delivered separately; see the patched app.py *.md edition)

Repo C — Relay (Cloudflare Workers): aei-relay/

12. .gitignore
13. worker.js
14. wrangler.toml
15. package.json
16. README.md — (relay-scoped; provided below as FILE 16)

The document below delivers files 1, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, and 16 in full, plus the frontend-scoped README (FILE 3). The backend-scoped README is the canonical deployment guide and has already been delivered as its own *.md edition; a cross-reference stub is provided at FILE 10 to avoid duplication while preserving the index.

---

FILE 1 of 16 — aei-miniapp/.gitignore

Path: aei-miniapp/.gitignore
Purpose: Frontend repo ignore rules. Excludes editor cruft, OS metadata, and optional build artifacts. The frontend is a single static HTML file with no build step, so this file is intentionally minimal — but it still guards against accidental commits of local tooling.

```gitignore
# ============================================================================
# ÆEA MINI APP — FRONTEND .gitignore
# Version: 4.1.0 (MQL4-Parity + MT4/TradingView TWA Edition — Audit-Patched)
# Repo: aei-miniapp (GitHub Pages)
# ============================================================================
#
# The frontend is a static single-file app (index.html). There is no build
# step, no node_modules, no bundler. This .gitignore therefore focuses on
# editor/OS cruft and any local-only artifacts a developer might create
# while iterating on index.html.
#
# ============================================================================

# ----------------------------------------------------------------------------
# EDITOR / IDE CRUFT
# ----------------------------------------------------------------------------
.vscode/
.idea/
*.swp
*.swo
*~
*.sublime-project
*.sublime-workspace
.project
.classpath
.settings/

# ----------------------------------------------------------------------------
# OS METADATA
# ----------------------------------------------------------------------------
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
desktop.ini

# ----------------------------------------------------------------------------
# LOCAL DEVELOPMENT OVERRIDES
# ----------------------------------------------------------------------------
# If a developer creates a local variant of index.html for testing a
# different backend URL, keep it out of the repo.
index.local.html
*.local.html
*.local.js
*.local.css

# ----------------------------------------------------------------------------
# SECRETS (SHOULD NEVER APPEAR IN A STATIC FRONTEND, BUT DEFENSIVE)
# ----------------------------------------------------------------------------
.env
.env.local
.env.*.local
secrets.json
credentials.json

# ----------------------------------------------------------------------------
# GITHUB PAGES ARTIFACTS
# ----------------------------------------------------------------------------
# GitHub Pages serves the repo root directly. Do not commit any build
# output, Jekyll caches, or generated site directories.
_site/
.jekyll-cache/
.jekyll-metadata
Gemfile.lock

# ----------------------------------------------------------------------------
# LOGS / TEMP
# ----------------------------------------------------------------------------
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
*.tmp
*.temp
tmp/
temp/

# ----------------------------------------------------------------------------
# ARCHIVES
# ----------------------------------------------------------------------------
*.zip
*.tar
*.tar.gz
*.tgz
*.rar
*.7z

# ----------------------------------------------------------------------------
# OPTIONAL LOCAL SERVER TOOLING
# ----------------------------------------------------------------------------
# If a developer uses `python -m http.server`, `npx serve`, or similar,
# these directories may appear.
dist/
build/
.cache/
.parcel-cache/
```

---

FILE 4 of 16 — aei-backend/.gitignore

Path: aei-backend/.gitignore
Purpose: Backend repo ignore rules. This is the most important .gitignore for the backend repo, because it is where the bot token, TLS certs, and Heroku-local state would accidentally be committed if not properly excluded. Note: there is no Wrangler/Node section here — the backend repo does not contain any Worker source, and Wrangler never runs from this repo.

```gitignore
# ============================================================================
# ÆEA BACKEND — .gitignore
# Version: 4.1.0 (MQL4-Parity + MT4/TradingView TWA Edition — Audit-Patched)
# Repo: aei-backend (Heroku)
# ============================================================================
#
# The backend repo contains app.py, the Heroku deployment manifests, and
# the environment template. It MUST NOT contain:
#   - the bot token (TELEGRAM_BOT_TOKEN)
#   - the relay shared secret (RELAY_KEY)
#   - TLS private keys or certificate chains
#   - the local .env file (only .env.example is committed)
#   - Python bytecode caches, virtualenvs, test caches
#   - Heroku-local state directories
#
# The Cloudflare Worker source is NOT in this repo. It lives exclusively
# in aei-relay. Do not add a .wrangler/ section here.
#
# ============================================================================

# ----------------------------------------------------------------------------
# SECRETS — HIGHEST PRIORITY
# ----------------------------------------------------------------------------
# The .env file holds live secrets. Only .env.example is committed.
.env
.env.*
!.env.example
*.pem
*.key
*.crt
*.cer
*.p12
*.pfx
*.jks
secrets.json
credentials.json
*.secret
*.secrets

# ----------------------------------------------------------------------------
# PYTHON
# ----------------------------------------------------------------------------
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST
pip-log.txt
pip-delete-this-directory.txt
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/
htmlcov/
.tox/
.nox/
.pytest_cache/
.mypy_cache/
.dmypy.json
dmypy.json
.pyre/
.pytype/
cython_debug/
Pipfile.lock
poetry.lock

# ----------------------------------------------------------------------------
# VIRTUALENVS
# ----------------------------------------------------------------------------
venv/
ENV/
env/
.venv/
.ENV/
env.bak/
venv.bak/

# ----------------------------------------------------------------------------
# EDITOR / IDE CRUFT
# ----------------------------------------------------------------------------
.vscode/
.idea/
*.swp
*.swo
*~
*.sublime-project
*.sublime-workspace
.project
.classpath
.settings/
*.code-workspace

# ----------------------------------------------------------------------------
# OS METADATA
# ----------------------------------------------------------------------------
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
desktop.ini

# ----------------------------------------------------------------------------
# HEROKU
# ----------------------------------------------------------------------------
# Heroku writes no local state by default, but local use of `heroku local`
# creates a .env file (see SECRETS above) and a Procfile.local override.
Procfile.local
Procfile.windows
.heroku/
heroku.yml

# ----------------------------------------------------------------------------
# LOGS / TEMP
# ----------------------------------------------------------------------------
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
lerna-debug.log*
*.tmp
*.temp
tmp/
temp/
*.pid
*.seed
*.pid.lock

# ----------------------------------------------------------------------------
# ARCHIVES
# ----------------------------------------------------------------------------
*.zip
*.tar
*.tar.gz
*.tgz
*.rar
*.7z

# ----------------------------------------------------------------------------
# TLS / CERTIFICATE MATERIAL
# ----------------------------------------------------------------------------
# If BRIDGE_USE_TLS=1 is set for local testing, the cert/key files must
# never be committed.
certs/
*.csr
*.srl
*.chain
```

---

FILE 5 of 16 — aei-backend/.env.example

Path: aei-backend/.env.example
Purpose: Environment template. This file is committed — the .gitignore above explicitly excludes .env but re-includes .env.example via !.env.example.

```bash
# ============================================================================
# ÆEA TELEGRAM BOT — ENVIRONMENT TEMPLATE
# Version: 4.1.0 (MQL4-Parity + MT4/TradingView TWA Edition — Audit-Patched)
# ============================================================================
# Copy to `.env` and fill in real values. NEVER commit the filled `.env`.
#
#   cp .env.example .env
#   $EDITOR .env
#
# Heroku: set each var via `heroku config:set KEY=value -a your-app-name`
#         (the `.env` file is ignored by Heroku; it is for local runs only).
#
# Termux / local shell: `set -a; . ./.env; set +a` before `python3 app.py`.
# ============================================================================

# ----------------------------------------------------------------------------
# REQUIRED — TELEGRAM
# ----------------------------------------------------------------------------
# Bot token from @BotFather. Also used to derive the WebApp initData HMAC
# secret key (HMAC_SHA256(bot_token, "WebAppData")).
TELEGRAM_BOT_TOKEN=

# ----------------------------------------------------------------------------
# REQUIRED FOR MINI APP — PUBLIC HTTPS ENDPOINT
# ----------------------------------------------------------------------------
# If set, the tunnel manager refuses to spawn cloudflared/ngrok/serveo and
# uses this URL verbatim. Must be HTTPS; Telegram rejects cleartext.
#
# Examples:
#   Local tunnel mode:  leave empty (auto-spawned *.trycloudflare.com)
#   Split-origin mode:  https://<user>.github.io/<repo>/
#   Reverse-proxy mode: https://your-domain.example/aei
TELEGRAM_WEBAPP_URL=

# ----------------------------------------------------------------------------
# REQUIRED FOR MARKET DATA — CLOUDFLARE WORKER RELAY
# ----------------------------------------------------------------------------
# Public URL of the deployed Worker (see the aei-relay repo).
# Example: https://aei-relay.<your-subdomain>.workers.dev
RELAY_URL=

# Optional shared secret enforced by the Worker via X-Relay-Key.
# If the Worker is deployed without a secret check, leave empty.
RELAY_KEY=

# Relay HTTP client tuning.
RELAY_TIMEOUT=10
RELAY_MAX_RETRIES=3

# ----------------------------------------------------------------------------
# BRIDGE — LOCAL HTTP SERVER
# ----------------------------------------------------------------------------
# Heroku assigns $PORT dynamically; app.py prefers $PORT over $BRIDGE_PORT.
BRIDGE_HOST=0.0.0.0
BRIDGE_PORT=8765

# TLS on the local bridge (Heroku terminates TLS at its router → leave 0).
BRIDGE_USE_TLS=0
BRIDGE_TLS_CERT=
BRIDGE_TLS_KEY=

# Tunnel preference order: cloudflared | ngrok | serveo
BRIDGE_TUNNEL=cloudflared
BRIDGE_PUBLIC_TIMEOUT=45

# ----------------------------------------------------------------------------
# AUTH & LOGGING
# ----------------------------------------------------------------------------
# Enforce X-Telegram-Init-Data on all non-/health endpoints.
# Set to 0 ONLY for local development without a Telegram WebView.
REQUIRE_AUTH=1

# Ring-buffer size for the /log endpoint.
LOG_BUFFER_SIZE=200

# ----------------------------------------------------------------------------
# CORS
# ----------------------------------------------------------------------------
# "*" permits any origin. Lock down to your GitHub Pages origin in production:
#   CORS_ORIGIN=https://<user>.github.io
CORS_ORIGIN=*

# ----------------------------------------------------------------------------
# OPTIONAL — ENGINE TUNING
# ----------------------------------------------------------------------------
# SYMBOL defaults to BTC-USD if unset (see app.py SYMBOL constant).
SYMBOL=BTC-USD

# Price-feed polling interval in seconds.
UPDATE_INTERVAL=30
```

---

FILE 6 of 16 — aei-backend/runtime.txt

Path: aei-backend/runtime.txt
Purpose: Heroku Python runtime pin.

```text
python-3.11.9
```

---

FILE 7 of 16 — aei-backend/requirements.txt

Path: aei-backend/requirements.txt
Purpose: Python dependency pins. No new packages introduced by the audit patches; all patches use only stdlib (fractions, decimal, math, collections, hmac, hashlib, ssl, urllib, http.server, threading, subprocess, asyncio, dataclasses, datetime, typing).

```text
# ============================================================================
# ÆEA TELEGRAM BOT — PYTHON DEPENDENCIES
# Version: 4.1.0 (MQL4-Parity + MT4/TradingView TWA Edition — Audit-Patched)
# Platform: Heroku / Termux / any POSIX-compatible Python 3.10+ environment
# Author: Natalia Tanyatia
# ============================================================================
#
# Installation:
#   pip install -r requirements.txt
#
# Heroku:
#   Committed to repo root; auto-installed on build slug.
#
# Termux:
#   pip install -r requirements.txt
# ============================================================================

# ----------------------------------------------------------------------------
# CORE TELEGRAM BOT FRAMEWORK
# ----------------------------------------------------------------------------
python-telegram-bot==21.6
# Provides: Application, CommandHandler, CallbackQueryHandler, WebAppInfo,
#           MenuButtonWebApp, InlineKeyboardButton, InlineKeyboardMarkup.
# Requires Python >= 3.9. Uses asyncio + httpx internally.

# ----------------------------------------------------------------------------
# HTTP CLIENT (used implicitly by python-telegram-bot)
# ----------------------------------------------------------------------------
httpx>=0.27,<0.28
# Async HTTP client for Telegram Bot API communications.
# Pinned to match python-telegram-bot 21.x compatibility matrix.

# ----------------------------------------------------------------------------
# EXACT SYMBOLIC ARITHMETIC
# ----------------------------------------------------------------------------
# The engine ships with a self-contained Fraction wrapper built on
# Python's stdlib `fractions.Fraction` and `decimal.Decimal`. No external
# symbolic-math library is required for the core ÆEA pipeline.
#
# Optional extension — uncomment ONLY if you add symbolic-integration
# protocols that the stdlib cannot express:
#
# sympy>=1.12

# ----------------------------------------------------------------------------
# TLS
# ----------------------------------------------------------------------------
# Handled by Python's stdlib `ssl` module. No pip package required when
# BRIDGE_USE_TLS=1 is paired with an externally-provisioned PEM cert/key
# (e.g., via certbot or the platform's managed certificate store).

# ----------------------------------------------------------------------------
# RELAY CLIENT
# ----------------------------------------------------------------------------
# FeedClient uses stdlib `urllib.request`. No pip package required for the
# Cloudflare Worker Relay integration.
#
# Direct-upstream fallback (NOT required for the Worker deployment):
#
# yfinance>=0.2.40
# requests>=2.32.0

# ----------------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------------
# Python's stdlib `logging` module handles all log output. No additional
# package needed. On Heroku, logs are captured from stdout/stderr.

# ----------------------------------------------------------------------------
# RUNTIME COMPATIBILITY
# ----------------------------------------------------------------------------
# Minimum: Python 3.10
# Recommended: Python 3.11 or 3.12
# Tested: Python 3.11.9 on Heroku-22; Python 3.12.3 on Termux ARM64.
#
# All arithmetic in the engine uses exact `fractions.Fraction` and
# `decimal.Decimal` from the standard library — zero floating-point entropy
# in the state machine, in accordance with the Arc-Length Axiom (s = r).
# ============================================================================
```

---

FILE 8 of 16 — aei-backend/Procfile

Path: aei-backend/Procfile
Purpose: Heroku process declaration. The web: process type is what Heroku routes HTTP traffic to (and what terminates TLS at the router before forwarding to app.py's bridge on $PORT).

```text
web: python app.py
```

---

FILE 9 of 16 — aei-backend/app.json

Path: aei-backend/app.json
Purpose: Heroku app manifest. Consumed by the Heroku Button deploy flow.

```json
{
  "name": "ÆEA Trading Bot",
  "description": "Quantum-Financial Topology Trading Bot on Telegram — MQL4-Parity + MT4/TradingView TWA Edition (Audit-Patched)",
  "repository": "https://github.com/yourusername/aea-bot",
  "keywords": ["trading", "telegram", "quantum", "finance", "mq4-parity", "mt4", "twa"],
  "env": {
    "TELEGRAM_BOT_TOKEN": {
      "description": "Your Telegram Bot Token from @BotFather",
      "required": true
    },
    "TELEGRAM_WEBAPP_URL": {
      "description": "Public HTTPS URL of the Telegram Mini App (GitHub Pages). Skips tunnel spawn when set.",
      "required": false
    },
    "RELAY_URL": {
      "description": "Cloudflare Worker relay URL (deployed from the aei-relay repo). Required for live prices.",
      "required": false
    },
    "RELAY_KEY": {
      "description": "Optional shared secret matching `wrangler secret put RELAY_KEY` in the aei-relay repo.",
      "required": false
    },
    "REQUIRE_AUTH": {
      "description": "Enforce X-Telegram-Init-Data on all non-/health endpoints. Defaults to '1'.",
      "required": false
    },
    "LOG_BUFFER_SIZE": {
      "description": "Ring-buffer size for the /log endpoint. Defaults to '200'.",
      "required": false
    },
    "CORS_ORIGIN": {
      "description": "Lock down writes to your GitHub Pages origin. Defaults to '*'.",
      "required": false
    },
    "SYMBOL": {
      "description": "Default trading symbol. Defaults to 'BTC-USD'.",
      "required": false
    },
    "UPDATE_INTERVAL": {
      "description": "Price-feed polling interval in seconds. Defaults to 30.",
      "required": false
    }
  },
  "formation": {
    "worker": {
      "quantity": 1,
      "size": "eco"
    }
  },
  "buildpacks": [
    {
      "url": "heroku/python"
    }
  ]
}
```

---

FILE 10 of 16 — aei-backend/README.md (Cross-Reference Stub)

Path: aei-backend/README.md
Note: The canonical backend README is the full ÆEA Deployment Guide (the document currently being delivered). In the deployed repo, aei-backend/README.md contains that guide verbatim. This entry is a cross-reference stub, provided here only to preserve the file index.

In the deployed repo: aei-backend/README.md = the full ÆEA Deployment Guide (v4.1.0), identical to the header of this document.

---

FILE 12 of 16 — aei-relay/.gitignore

Path: aei-relay/.gitignore
Purpose: Relay-only repo ignore rules. This is the simplest of the three .gitignore files because the relay is a single JavaScript file plus three configuration files. There is nothing to build, nothing to bundle, and only one secret (the Wrangler-managed RELAY_KEY).

```gitignore
# ============================================================================
# ÆEA RELAY — .gitignore
# Version: 4.1.0 (MQL4-Parity + MT4/TradingView TWA Edition — Audit-Patched)
# Repo: aei-relay (Cloudflare Workers)
# ============================================================================
#
# The relay repo contains worker.js plus three config files:
#   worker.js       (the Worker source)
#   wrangler.toml   (deployment manifest)
#   package.json    (Node manifest for wrangler)
#   README.md       (relay-scoped)
#
# Nothing builds. Nothing bundles. The only secret is RELAY_KEY, which is
# managed by `wrangler secret put` and never written to disk in the repo.
#
# The relay is the sole home of the Cloudflare Worker. Do not add a copy of
# this source to any other repo — that would create a deploy-order race on
# the Cloudflare Worker named 'aei-relay'.
#
# ============================================================================

# ----------------------------------------------------------------------------
# CLOUDFLARE WRANGLER
# ----------------------------------------------------------------------------
# Wrangler writes its build output to .wrangler/ and its typecheck output
# to dist/. Neither should be committed.
.wrangler/
dist/
worker/
wrangler.toml.local
.dev.vars

# ----------------------------------------------------------------------------
# NODE
# ----------------------------------------------------------------------------
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
lerna-debug.log*
.npm
.yarn-integrity
.pnp
.pnp.js
.yarn/cache
.yarn/unplugged
.yarn/build-state.yml
.yarn/install-state.gz

# ----------------------------------------------------------------------------
# SECRETS (DEFENSIVE — WRANGLER STORES THESE REMOTELY, NOT ON DISK)
# ----------------------------------------------------------------------------
.env
.env.*
!.env.example
*.pem
*.key
*.crt
secrets.json
credentials.json

# ----------------------------------------------------------------------------
# EDITOR / IDE CRUFT
# ----------------------------------------------------------------------------
.vscode/
.idea/
*.swp
*.swo
*~
*.sublime-project
*.sublime-workspace
.project
.classpath
.settings/
*.code-workspace

# ----------------------------------------------------------------------------
# OS METADATA
# ----------------------------------------------------------------------------
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
desktop.ini

# ----------------------------------------------------------------------------
# LOGS / TEMP
# ----------------------------------------------------------------------------
*.log
*.tmp
*.temp
tmp/
temp/
*.pid
*.seed
*.pid.lock

# ----------------------------------------------------------------------------
# ARCHIVES
# ----------------------------------------------------------------------------
*.zip
*.tar
*.tar.gz
*.tgz
*.rar
*.7z
```

---

FILE 13 of 16 — aei-relay/worker.js

Path: aei-relay/worker.js
Purpose: Cloudflare Worker source. Deployed from this repo via wrangler deploy. The Worker is the market-data relay: it proxies Yahoo Finance chart API requests through Cloudflare's egress IPs so the Heroku dyno's own IP is never rate-limited by Yahoo.

Contract:

· GET /health → {"ok": true, "service": "aei-relay", "gated": <bool>}
· GET /?symbol=<S>&kind=price → {symbol, close, bid, ask, volume, timestamp}
· GET /?symbol=<S>&kind=intraday&interval=1m → {symbol, open, high, low, close, volume, timestamp}
· GET /?symbol=<S>&kind=history&limit=200&interval=1m → [{open, high, low, close, volume, timestamp}, …]
· Optional X-Relay-Key header gate when env.RELAY_KEY is set.

```javascript
// ============================================================================
// ÆEA RELAY — CLOUDFLARE WORKER
// ============================================================================
// Proxies Yahoo Finance chart API through Cloudflare's egress IPs so that
// the Heroku dyno never exposes its own IP to Yahoo's rate limiter.
//
// This file is the sole source of truth for the ÆEA relay. It is deployed
// exclusively from the aei-relay repository. The aei-backend repository
// does NOT contain a copy of this file — the backend reaches the relay
// only over HTTP via the RELAY_URL environment variable.
//
// Contract (mirrors FeedClient._get in app.py):
//   GET /health                                    → {"ok": true, "service": "aei-relay"}
//   GET /?symbol=<S>&kind=price                    → {close, bid, ask, volume}
//   GET /?symbol=<S>&kind=intraday&interval=1m     → {open, high, low, close, volume, timestamp}
//   GET /?symbol=<S>&kind=history&limit=200&interval=1m → [{open, high, low, close, volume, timestamp}, …]
//
// Optional shared-secret gate: if env.RELAY_KEY is set, every non-/health
// request must carry header `X-Relay-Key: <RELAY_KEY>`.
//
// Deploy:
//   npx wrangler deploy
// ============================================================================

const YAHOO_HOST = "https://query1.finance.yahoo.com";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36";

function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Accept, X-Relay-Key",
      "Cache-Control": "public, max-age=15",
      ...extraHeaders,
    },
  });
}

function shapeBar(quote, ts, i) {
  const num = (v) => (v === null || v === undefined || Number.isNaN(v) ? null : Number(v));
  const iso = ts && ts[i] ? new Date(ts[i] * 1000).toISOString() : new Date().toISOString();
  return {
    open: num(quote.open?.[i]),
    high: num(quote.high?.[i]),
    low: num(quote.low?.[i]),
    close: num(quote.close?.[i]),
    volume: num(quote.volume?.[i]),
    timestamp: iso,
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Accept, X-Relay-Key",
        },
      });
    }

    if (url.pathname === "/health") {
      return json({ ok: true, service: "aei-relay", gated: Boolean(env.RELAY_KEY) });
    }

    if (env.RELAY_KEY) {
      const presented = request.headers.get("X-Relay-Key") || "";
      if (presented !== env.RELAY_KEY) {
        return json({ error: "unauthorized" }, 401);
      }
    }

    const symbol = url.searchParams.get("symbol") || "BTC-USD";
    const kind = url.searchParams.get("kind") || "price";
    const interval = url.searchParams.get("interval") || "1m";
    const range = kind === "intraday" || kind === "history" ? "2d" : "1d";

    const upstream = `${YAHOO_HOST}/v8/finance/chart/${encodeURIComponent(symbol)}?interval=${encodeURIComponent(interval)}&range=${range}`;

    let response;
    try {
      response = await fetch(upstream, {
        headers: { "User-Agent": UA, "Accept": "application/json" },
        cf: { cacheTtl: 10, cacheEverything: true },
      });
    } catch (e) {
      return json({ error: "upstream_failed", detail: String(e), symbol }, 502);
    }

    if (!response.ok) {
      return json({ error: "upstream_status", status: response.status, symbol }, 502);
    }

    let raw;
    try {
      raw = await response.json();
    } catch (e) {
      return json({ error: "upstream_invalid_json", detail: String(e), symbol }, 502);
    }

    const result = raw?.chart?.result?.[0];
    if (!result) {
      const yahooErr = raw?.chart?.error || null;
      return json({ error: "no_data", symbol, yahoo_error: yahooErr }, 404);
    }

    const meta = result.meta || {};
    const ts = result.timestamp || [];
    const quote = (result.indicators && result.indicators.quote && result.indicators.quote[0]) || {};

    if (kind === "price") {
      const last = shapeBar(quote, ts, ts.length - 1);
      const px = meta.regularMarketPrice ?? last.close;
      if (px === null || px === undefined) {
        return json({ error: "no_price", symbol }, 404);
      }
      return json({
        symbol,
        close: Number(px),
        bid: Number(px),
        ask: Number(px),
        volume: last.volume,
        timestamp: last.timestamp,
      });
    }

    if (kind === "intraday") {
      if (ts.length === 0) {
        return json({ error: "no_intraday", symbol }, 404);
      }
      const last = shapeBar(quote, ts, ts.length - 1);
      if (last.close === null) {
        return json({ error: "no_intraday_close", symbol }, 404);
      }
      return json({ symbol, ...last });
    }

    if (kind === "history") {
      const limit = Math.max(1, Math.min(1000, parseInt(url.searchParams.get("limit") || "200", 10) || 200));
      const start = Math.max(0, ts.length - limit);
      const out = [];
      for (let i = start; i < ts.length; i++) {
        const bar = shapeBar(quote, ts, i);
        if (bar.close === null) continue;
        out.push(bar);
      }
      return json(out);
    }

    return json({ error: "unknown_kind", kind }, 400);
  },
};
```

---

FILE 14 of 16 — aei-relay/wrangler.toml

Path: aei-relay/wrangler.toml
Purpose: Cloudflare Worker deployment manifest. This is the only wrangler.toml in the ÆEA system. wrangler deploy must be run from aei-relay/.

```toml
# ============================================================================
# ÆEA RELAY — WRANGLER CONFIGURATION
# ============================================================================
# Cloudflare Worker deployment manifest.
#
# This is the ONLY wrangler.toml in the ÆEA system. It lives exclusively in
# the aei-relay repository. The aei-backend repository does NOT contain a
# copy. This guarantees:
#   - exactly one `wrangler deploy` command can publish the Worker
#   - the Worker name 'aei-relay' cannot collide with a second deployment
#   - no deploy-order race can overwrite the live Worker with a stale copy
#
# Usage (from aei-relay/ repo root):
#   npm install -g wrangler        # or: npx wrangler
#   wrangler login
#   wrangler secret put RELAY_KEY  # optional shared-secret gate
#   wrangler deploy
#
# After deploy, the printed URL (e.g. https://aei-relay.<sub>.workers.dev)
# is what you assign to the Heroku config var RELAY_URL.
# ============================================================================

name = "aei-relay"
main = "worker.js"
compatibility_date = "2024-11-01"

# Workers Free tier: 100,000 requests/day.
# At UPDATE_INTERVAL=30s, one Heroku dyno burns ~2,880 relay hits/day for
# the price poll alone, plus intraday + history on cold starts — well within
# the free ceiling even with a handful of restart events.
#
# Observability: enable Workers Logs if you want per-request telemetry.
[observability]
enabled = false

# ----------------------------------------------------------------------------
# OPTIONAL — SHARED-SECRET GATE
# ----------------------------------------------------------------------------
# Do NOT inline the secret here. Set it once via:
#   wrangler secret put RELAY_KEY
# Wrangler stores it encrypted on Cloudflare's side and injects it as
# env.RELAY_KEY inside worker.js. If absent, the gate is skipped.
#
# [vars]
# RELAY_KEY = ""

# ----------------------------------------------------------------------------
# OPTIONAL — CUSTOM DOMAIN
# ----------------------------------------------------------------------------
# If you own a zone on Cloudflare, uncomment and replace with your hostname:
#
# routes = [
#   { pattern = "relay.example.com/*", zone_name = "example.com" }
# ]
#
# Then set the Heroku config var to match:
#   heroku config:set RELAY_URL="https://relay.example.com" -a your-app-name
```

---

FILE 15 of 16 — aei-relay/package.json

Path: aei-relay/package.json
Purpose: Node manifest for the Cloudflare Worker relay. Consumed by wrangler (via npm install or npx).

```json
{
  "name": "aei-relay",
  "version": "4.1.0",
  "private": true,
  "description": "ÆEA relay — Cloudflare Worker proxying Yahoo Finance for the Heroku ÆEA bridge (MQL4-Parity + MT4/TradingView TWA Edition — Audit-Patched). Sole home of the Worker source.",
  "author": "Natalia Tanyatia",
  "license": "UNLICENSED",
  "main": "worker.js",
  "type": "module",
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "tail": "wrangler tail",
    "secret:put": "wrangler secret put RELAY_KEY",
    "secret:list": "wrangler secret list",
    "whoami": "wrangler whoami",
    "login": "wrangler login",
    "logout": "wrangler logout",
    "typecheck": "wrangler deploy --dry-run --outdir=dist"
  },
  "devDependencies": {
    "wrangler": "^3.90.0"
  },
  "engines": {
    "node": ">=18.0.0"
  },
  "cloudflare": {
    "name": "aei-relay",
    "main": "worker.js",
    "compatibility_date": "2024-11-01"
  },
  "keywords": [
    "cloudflare",
    "workers",
    "yahoo-finance",
    "relay",
    "proxy",
    "aei",
    "aeae",
    "mq4-parity",
    "mt4",
    "tradingview",
    "twa"
  ],
  "repository": {
    "type": "git",
    "url": "https://github.com/yourusername/aei-relay"
  },
  "bugs": {
    "url": "https://github.com/yourusername/aei-relay/issues"
  },
  "homepage": "https://github.com/yourusername/aei-relay#readme"
}
```

---

FILE 16 of 16 — aei-relay/README.md (Relay-Scoped)

Path: aei-relay/README.md
Purpose: Relay-scoped README. Points at the canonical deployment guide for the full picture, then documents the relay-only repo.

# **ÆEA Relay — Cloudflare Worker Repository**

*Version:* 4.1.0 (MQL4-Parity + MT4/TradingView TWA Edition — Audit-Patched)
*Repo:* `aei-relay` (Cloudflare Workers)
*Sibling repos:* `aei-miniapp` (GitHub Pages), `aei-backend` (Heroku)

---

## What This Repo Contains

This repository is the **sole home of the ÆEA relay Worker**. It contains:

- `worker.js` — the Cloudflare Worker source.
- `wrangler.toml` — the deployment manifest. `name = "aei-relay"`, `main = "worker.js"`.
- `package.json` — the Node manifest for wrangler.
- `README.md` — this file.
- `.gitignore` — Wrangler build output, Node cruft, secrets.

That is the complete contents of the repo. Nothing builds, nothing bundles.

---

## What This Repo Is Not

This repo is **not** the backend. It does not contain `app.py`, does not run a Python process, and does not handle Telegram traffic. It is a stateless HTTP proxy: it receives `GET /?symbol=…&kind=…`, fetches the corresponding Yahoo Finance chart API URL through Cloudflare's egress IPs, and returns the shaped JSON.

This repo is also **not** duplicated anywhere. The `aei-backend` repository does **not** contain a copy of `worker.js`, `wrangler.toml`, or `package.json`. The backend reaches the relay only over HTTP via its `RELAY_URL` environment variable. There is exactly one `wrangler deploy` command in the ÆEA system, and it is run from this repo.

---

## Deployment

From this repo's root:

```bash
npm install -g wrangler
wrangler login
wrangler secret put RELAY_KEY   # optional shared-secret gate
wrangler deploy
```

Wrangler prints the deployed URL, e.g.:

```
https://aei-relay.<your-subdomain>.workers.dev
```

Assign that URL to the Heroku backend's RELAY_URL config var:

```bash
heroku config:set RELAY_URL="https://aei-relay.<your-subdomain>.workers.dev" -a your-app-name
```

---

Contract

The Worker implements the following HTTP contract, which mirrors FeedClient._get in the backend's app.py:

Method Path Returns
GET /health {"ok": true, "service": "aei-relay", "gated": <bool>}
GET /?symbol=<S>&kind=price {symbol, close, bid, ask, volume, timestamp}
GET /?symbol=<S>&kind=intraday&interval=1m {symbol, open, high, low, close, volume, timestamp}
GET /?symbol=<S>&kind=history&limit=200&interval=1m [{open, high, low, close, volume, timestamp}, …]

When env.RELAY_KEY is set (via wrangler secret put RELAY_KEY), every non-/health request must carry the X-Relay-Key: <RELAY_KEY> header. The backend's app.py reads RELAY_KEY from its own env and injects the header automatically.

---

Verification

```bash
curl "https://aei-relay.<sub>.workers.dev/health"
# → {"ok":true,"service":"aei-relay","gated":false}

curl "https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=price"
# → {"symbol":"BTC-USD","close":95432.12,...}
```

If you set RELAY_KEY, the second command requires the header:

```bash
curl -H "X-Relay-Key: <RELAY_KEY>" "https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=price"
```

---

Update Workflow

```bash
# edit worker.js
git add worker.js
git commit -m "Rotate symbol fallback chain"
git push origin main
wrangler deploy
# Cloudflare redeploys in ~5 s
```

Rotating the shared secret:

```bash
wrangler secret put RELAY_KEY
# paste new value
heroku config:set RELAY_KEY="<same value>" -a your-app-name
```

---

Cross-Repo Coordination

· aei-miniapp (GitHub Pages) — the frontend. Never talks to this repo directly; talks to aei-backend via ?backend=.
· aei-backend (Heroku) — the Python bot + bridge. Reads this repo's deployed URL from its RELAY_URL env var.
· aei-relay (this repo) — the Cloudflare Worker. Stateless.

The three repos deploy independently. No coordination is needed between frontend pushes, backend pushes, and relay pushes.

Critical for v4.1.0: Do not copy worker.js, wrangler.toml, or package.json into the aei-backend repo. Doing so would create a second wrangler deploy target pointing at the same Cloudflare Worker named aei-relay, and the two copies could drift. This repo is the single source of truth.

---

License

UNLICENSED — proprietary. © Natalia Tanyatia 2025.