# **ÆEA — Deployment Guide**
Version: 4.3.0 (Enhancement Edition)
Base: v4.2.0 (Semantics-Restored Edition) → v4.3.0 (Enhancement Edition)
Foundational Framework: ÆEA.mq4
Author: Natalia Tanyatia

---

0. What Changed in v4.3.0

v4.3.0 is the enhancement release. It adds three capabilities on top of the v4.2.0 semantics-restored port without altering any FF-invariant logic. The engine's state machine, exact-arithmetic discipline, indicator formulas, regime taxonomy, Kronecker gate, and observer/measurement layer remain at MQL4-parity with ÆEA.mq4. The additions are:

· E-1 — Telegram push notifications on every event. _emit_toast() now dispatches a sendMessage to the bound chat_id for every toast it emits — signal, execution, FVG commit, FVG remove. The bot responds to the user on every event, which causes Telegram to raise a native push notification. _A(), _B(), _Top(), and _Bott() now emit their own toasts so the user is notified of every close and every FVG anchor maintenance action, not only of dispatch subblocks. A per-event dedup key (_push_dedup_key) with an 800 ms window (PUSH_DEDUP_WINDOW_MS) guarantees a single logical event never produces two pushes even when both the toast path and the legacy alert path fire.

· E-2 — Real volume from a non-Yahoo upstream. The Cloudflare Worker now dispatches crypto symbols to Binance klines (/api/v3/klines — real OHLCV + real volume) with CoinGecko (/coins/{id}/market_chart — real volume) as the secondary and Yahoo as the tertiary. Equities and futures continue to use Yahoo only. The engine's OBV, AD, Force, and MFI projections therefore operate on non-zero volume for crypto. The current provider is surfaced in the Engine Panel, the Projection Panel, the 13D grid footnote, and the /probe output.

· E-3 — Arc-length future price projection. A new /projection endpoint returns a forward price path derived from the s=r coherence condition applied to the current topological branch. The path is drawn on the chart ahead of the current bar as a dashed purple arc with a soft gradient fill. Three branches drive three trajectory forms:

All intermediate quantities are Decimal. The cosine is evaluated via a 30-term Taylor series on Decimal (_decimal_cos), so no float64 rounding is introduced except at the final JSON serialization (which uses a decimal string).

0.1 Defect-resolution index (carried forward from v4.2.0)

All 44 defects from the ÆEA v4.1.1 Fidelity & Spec Audit (27 critical + 17 minor) remain resolved in v4.3.0 — the v4.3.0 patches do not touch any of the audited sites. All 30 defects from the v4.1.2 self-audit (15 critical + 3 major + 12 minor) remain resolved. All 11 defect classes from the v4.1.3 syntax+semantics audit remain resolved. All 15 new critical defects, 3 major defects, and 12 minor defects introduced by the v4.1.2/v4.1.3 intermediate patches remain resolved in v4.3.0.

The complete v4.2.0 defect-resolution index (D-1 through D-29, C-3.1 through C-3.17, M-1 through M-15, N-1 through N-27, DC-1 through DC-11) is reproduced verbatim in the v4.2.0 deployment guide and remains authoritative. v4.3.0 does not re-open any of those sites.

0.2 Compatibility with v4.1.1 / v4.1.2 / v4.1.3 / v4.2.0

v4.3.0 is a drop-in replacement for v4.2.0. All environment variables, endpoints, and worker contracts are unchanged, with the following additive-only changes:

· Eight new env vars: PUSH_ON_SIGNAL, PUSH_ON_EXECUTION, PUSH_ON_FVG, PUSH_ON_CLOSE, PUSH_DEDUP_WINDOW_MS, ARC_PROJECTION_HORIZON, ARC_PROJECTION_STEP, ARC_PROJECTION_DAMPING. All have sensible defaults and are optional.
· Two new endpoints: GET /projection and POST /projection/refresh.
· The relay contract is extended with three new kind values: kind=volume, kind=candles, kind=projection (the last is a passthrough marker — the Worker refuses it and tells the caller to use the backend).
· The /miniapp-state payload is extended with provider, last_volume, projection_meta, and projection_computed_at.
· The /health payload is extended with provider and projection_computed_at.
· The /ohlcv payload is extended with provider on the top-level response and on each bar.
· The /probe payload is extended with provider and last_volume.

A fork configured against v4.2.0 continues to work without change, and gains the enhancement capabilities.

---

1. Architecture Overview

The ÆEA system spans three cooperating surfaces:

Layer Host Responsibility
Frontend GitHub Pages (or any HTTPS static host) Serves index.html — the ÆEA MT4/TradingView-style engine UI: interactive candlestick chart with crosshair/pan/zoom, indicator sub-panels, BB×58 family overlay (BigInt-backed exact fractions), FVG drawing tools, order ticket, engine settings, regime map, log bar, signal markers, toast stack for signal/execution/FVG notifications, arc-length projection overlay, polling logic.
Backend Heroku (or any HTTPS Python host) Runs app.py: Telegram bot polling, AEEA_Engine (MQL4-parity port), bridge endpoints (/state, /miniapp-state, /ohlcv, /signals, /handshake, /fvg, /probe, /diagnostics, /health, /config, /orders, /regime-map, /indicators, /log, /settings, /symbol, /order, /order/close, /toasts, /projection, /projection/refresh, /reset). Also dispatches Telegram push messages on every signal, execution, FVG, and close.
Relay Cloudflare Workers Proxies Yahoo Finance (equities/futures), Binance klines (crypto OHLCV + volume), and CoinGecko market_chart (crypto secondary volume) through Cloudflare's egress IPs so the Heroku dyno's IP is never rate-limited by any upstream.

The Mini App is not a separate server. It is the same index.html that runs locally, loaded by Telegram's WebView, authenticated via initData, bound back to the bot's chat_id through /handshake.

1.1 Critical for split-origin correctness

Because the frontend is served from GitHub Pages (origin https://<user>.github.io) and the backend lives on Heroku (origin https://<app>.herokuapp.com), the frontend must be explicitly told the backend origin. This is done with the ?backend= query parameter or the DEFAULT_BACKENDS[0] edit point. Without it, the TWA will attempt to fetch /miniapp-state, /ohlcv, /projection, etc. from GitHub Pages and receive 404s.

1.2 Critical for state freshness

The TWA polls /miniapp-state every 2 s, /diagnostics every 5 s, and /projection every 5 s. All three return overlapping FF state. To prevent a slower poll from overwriting live engine state with stale data, absorbDiagnostics() in index.html implements a freshness guard: it only absorbs engine-state fields — including indicator-matrix fields — if the diagnostics snapshot's tick is strictly greater than _lastDiagnosticsAbsorbedTick, a counter distinct from _lastMiniAppTick. The projection poll is absorbed unconditionally because the backend computes it from live state on demand.

1.3 Critical for Kronecker Panel accuracy

The Kronecker Panel displays the authoritative m/n from the most recent H()/L() call (last_kronecker_m/last_kronecker_n) when the engine has fired at least one Kronecker event. It falls back to the per-tick diagnostic market_m/market_n only when no event has fired yet. This makes the panel match the bot's /status Local m/n field exactly.

1.4 Critical for toast delivery

Signal, execution, and FVG notifications are delivered via a three-tier system:

(a) Server-side toast buffer — _emit_toast() appends to a _TOAST_BUFFER deque with a monotonic sequence number and a first_available_seq cursor. The TWA polls /toasts?since=<seq> every 2 s and renders each new toast in #toastStack. If the server has evicted entries past the client's cursor, the response includes first_available_seq so the client can log an eviction warning — including on the first poll when first_available_seq > 0.

(b) Server-side Telegram push — _telegram_push() dispatches a sendMessage to the bound chat_id for every toast, deduplicated by _push_dedup_key so a single logical event never produces two pushes. The push fires in a background thread so a slow Telegram round-trip never blocks the tick loop. This is the mechanism that causes a native Telegram push notification on the user's device: the bot responds to the user on every event.

(c) Legacy alert paths — _send_signal_alert() and _send_execution_alert() continue to fire independently. The dedup key suppresses the second push when both (b) and (c) fire for the same logical event. Set PUSH_ON_SIGNAL=0 to disable the (b) path for signals while keeping the (c) path.

1.5 Critical for BB family correctness

The Bollinger family is computed client-side in index.html from state.bars (the same OHLCV that /ohlcv returns). MQL4 parity is enforced: integer periods 3..60, deviation = 2, applied price = close, bands shift = 0, population σ (divisor = period). v4.3.0 computes the SMA and variance accumulators with BigInt-backed fixed-point arithmetic at a 1e12 scale, converting via string to avoid float64 multiplication in bbToBigFixed(). The only remaining floating-point step is the final Math.sqrt, which is irrational in nature.

1.6 Critical for backend origin safety

index.html resolves the backend URL in this order: window.__AEEA_BACKEND_URL__ → ?backend= (persisted to localStorage) → localStorage['aeea_backend_url'] → DEFAULT_BACKENDS[0] → same-origin. The DEFAULT_BACKENDS array is the v4.3.0 resolution for the case where Telegram's WebView strips the ?backend= query string.

1.7 Critical for single-source-of-truth

The Cloudflare Worker is deployed exclusively from the aei-relay repository. The backend repository (aei-backend) does not contain worker.js, wrangler.toml, or package.json. The backend reaches the relay only over HTTP via the RELAY_URL environment variable.

1.8 Critical for projection correctness

The arc-length projection is computed on the backend (AEEA_Engine._project_arc_length()) and polled by the frontend. It is recomputed once per bar close (update_price calls it when bar_closed is true) and on demand via POST /projection/refresh. The frontend never computes the projection itself — it renders the path returned by the backend. This preserves the single-source-of-truth property for the engine's forward view.

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

Three files. Deploy target: GitHub Pages (main:/). Deploy command: git push origin main. Contains no server-side code, no Worker source, no build step.

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

Nine files. Deploy target: Heroku (Python dyno). Deploy command: git push heroku main. Contains no worker.js, no wrangler.toml, no package.json. The backend has no file-system relationship with the Worker source. It reaches the relay only over HTTP via RELAY_URL.

The optional index.html in the backend repo is a fallback page served at GET / when the bridge is hit directly (e.g. from a browser on the dyno's own machine). It is not the TWA — the TWA lives in aei-miniapp.

Repo C — Relay (Cloudflare Workers): aei-relay/

```
aei-relay/
├── worker.js
├── wrangler.toml
├── package.json
├── README.md
└── .gitignore
```

Five files. Deploy target: Cloudflare Workers edge. Deploy command: wrangler deploy (run from this repo's root). Sole home of the Worker. Deployed under name aei-relay in wrangler.toml.

2.1 File counts (reconciled)

· Frontend: 3 files (index.html, README.md, .gitignore).
· Backend: 9 files (app.py, README.md, .gitignore, .env.example, runtime.txt, requirements.txt, Procfile, app.json, index.html).
· Relay: 5 files (worker.js, wrangler.toml, package.json, README.md, .gitignore).

Total: 17 files across 3 repos.

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
# → {"ok":true,"service":"aei-relay","version":"4.3.0","gated":false,
#    "providers":["yahoo","binance","coingecko"]}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTC-USD&kind=price"
# → {"symbol":"BTC-USD","close":95432.12,"bid":95432.12,"ask":95432.12,
#    "volume":1234.56,"timestamp":"...","provider":"binance"}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTC-USD&kind=volume"
# → {"symbol":"BTC-USD","volume":1234.56,"volume_24h":98765.43,"provider":"binance"}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=ETH-USD&kind=candles&interval=1m&limit=5"
# → [{"open":...,"high":...,"low":...,"close":...,"volume":...,"timestamp":"...","provider":"binance"}, ...]

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=GC=F&kind=price"
# → {"symbol":"GC=F","close":2650.50,...,"provider":"yahoo"}
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
heroku config:set LOG_BUFFER_SIZE="1000" -a your-app-name
heroku config:set TOAST_BUFFER_SIZE="500" -a your-app-name
heroku config:set MAX_MIN_GAP="2" -a your-app-name
heroku config:set MIN_PERIOD_FLOOR="3" -a your-app-name
heroku config:set SYMBOL_DIGITS='{"BTC-USD":2,"ETH-USD":2,...}' -a your-app-name
heroku config:set SYMBOL_DIGITS_DEFAULT="2" -a your-app-name
```

New in v4.3.0 (all optional, all with defaults):

```bash
# E-1: Telegram push switches. Each defaults to "1" (enabled).
heroku config:set PUSH_ON_SIGNAL="1" -a your-app-name
heroku config:set PUSH_ON_EXECUTION="1" -a your-app-name
heroku config:set PUSH_ON_FVG="1" -a your-app-name
heroku config:set PUSH_ON_CLOSE="1" -a your-app-name
heroku config:set PUSH_DEDUP_WINDOW_MS="800" -a your-app-name

# E-3: Arc-length projection parameters.
heroku config:set ARC_PROJECTION_HORIZON="30" -a your-app-name
heroku config:set ARC_PROJECTION_STEP="1" -a your-app-name
heroku config:set ARC_PROJECTION_DAMPING="0.94" -a your-app-name
```

TELEGRAM_WEBAPP_URL does two things:

· Tells the bot where the Mini App lives (used for MenuButtonWebApp).
· Prevents TunnelManager from spawning cloudflared (which is not installed on Heroku).

REQUIRE_AUTH defaults to 1. Set it to 0 only for local development without Telegram initData.

4.3 Deploy

```bash
git add .
git commit -m "ÆEA backend v4.3.0 (Enhancement Edition)"
git push heroku main
```

4.4 Verify the Backend

```bash
curl "https://your-app-name.herokuapp.com/health"
# → {"ok":true,"service":"aei-bridge","version":"4.3.0","provider":"binance",
#    "projection_computed_at":"2025-...", ...}

curl -H "X-Telegram-Init-Data: <valid>" "https://your-app-name.herokuapp.com/config"
# → {"public_url":"...","require_auth":true,"push_on_signal":true,
#    "arc_projection_horizon":30, ...}

curl -H "X-Telegram-Init-Data: <valid>" "https://your-app-name.herokuapp.com/projection"
# → {"symbol":"BTC-USD","path":[{"step":1,"price":"95433.12","t":1.0}, ...],
#    "meta":{"kind":"range","horizon":30,"price_now":"95432.12",
#            "signal_now":"95430.00","regime":"sRange","slope":"0",
#            "amplitude":"0","center":"95432.12","damping":"0.94",
#            "provider":"binance"},
#    "computed_at":"2025-...","current_price":"95432.12",
#    "signal_level":"95430.00","regime":"sRange"}
```

Key checks on /probe: "empty": false, relay_url populated, provider populated, last_volume non-zero for crypto.

v4.3.0 endpoint checks:

```bash
# GET /toasts returns incremental signal+execution+fvg toasts
curl -H "X-Telegram-Init-Data: <valid>" "https://your-app-name.herokuapp.com/toasts?since=0"
# → {"toasts":[...],"count":N,"latest_seq":M,"first_available_seq":F}

# POST /projection/refresh forces a recomputation
curl -X POST -H "X-Telegram-Init-Data: <valid>" \
     "https://your-app-name.herokuapp.com/projection/refresh"
# → {"symbol":"...","path":[...],"meta":{...},"computed_at":"..."}
```

---

5. GitHub Pages Frontend Deployment (Repo A — aei-miniapp)

5.1 Configure the Backend URL

The index.html resolves the backend in this order:

1. window.__AEEA_BACKEND_URL__ (if the host page sets it before the script loads)
2. ?backend=https://... query-string override (persisted to localStorage)
3. localStorage['aeea_backend_url']
4. DEFAULT_BACKENDS[0] — the fork-author edit point at the top of the <script> block
5. same-origin (relative paths)

For a fork: edit DEFAULT_BACKENDS[0] in index.html to your Heroku origin before pushing. This is the v4.3.0 defense against WebView URL stripping.

In the Telegram Mini App context, the Web App URL configured in BotFather must include the query string:

```
https://<your-username>.github.io/<repo-name>/?backend=https://your-app-name.herokuapp.com/
```

This is what makes the TWA able to reach the Heroku backend. If Telegram strips the query string (some Android WebView versions do), the DEFAULT_BACKENDS fallback kicks in.

5.2 Push to GitHub

```bash
cd aei-miniapp
git init
git add index.html README.md .gitignore
git commit -m "ÆEA Mini App v4.3.0 (Enhancement Edition)"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

5.3 Enable Pages

1. Repo → Settings → Pages
2. Source: Deploy from a branch
3. Branch: main / /(root)
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

The Web App URL must be the GitHub Pages URL with the ?backend= query string appended. Telegram loads the static frontend; the frontend then talks to Heroku because it has been told the backend origin explicitly.

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
CORS_ORIGIN * Set to your GitHub Pages origin to lock down writes.
REQUIRE_AUTH 1 Enforce X-Telegram-Init-Data on all non-/health endpoints.
LOG_BUFFER_SIZE 1000 Ring-buffer size for the /log endpoint.
TOAST_BUFFER_SIZE 500 Ring-buffer size for the /toasts endpoint.
SYMBOL BTC-USD Default trading symbol.
UPDATE_INTERVAL 30 Price-feed polling interval (seconds).
MAX_MIN_GAP 2 Minimum max - min. The FF requires 2.
MIN_PERIOD_FLOOR 3 Hard floor on the FF's min input. The FF requires 3.
SYMBOL_DIGITS (JSON table) Symbol → digits map for Point-size emulation.
SYMBOL_DIGITS_DEFAULT 2 Fallback digit count.

New in v4.3.0:

Variable Default Purpose
PUSH_ON_SIGNAL 1 Send a Telegram push on every signal.
PUSH_ON_EXECUTION 1 Send a Telegram push on every execution event.
PUSH_ON_FVG 1 Send a Telegram push on every FVG commit/remove.
PUSH_ON_CLOSE 1 Send a Telegram push on every A()/B() close.
PUSH_DEDUP_WINDOW_MS 800 Suppress a second push for the same logical event within this window.
ARC_PROJECTION_HORIZON 30 Number of forward bars to emit in the projection.
ARC_PROJECTION_STEP 1 Price step quantization for the emitted path.
ARC_PROJECTION_DAMPING 0.94 Decay factor for the volatile-regime branch.

GitHub Pages (Repo A — aei-miniapp)

There are no environment variables on static hosting. All configuration lives in index.html and is resolved at boot. The canonical way to configure it is through the ?backend= query parameter in the BotFather Web App URL, with DEFAULT_BACKENDS[0] as the fork-edit fallback.

Cloudflare Workers (Repo C — aei-relay)

Variable Default Purpose
RELAY_KEY (empty) Optional shared secret. Set via wrangler secret put RELAY_KEY. If unset, the gate is skipped.

---

8. Endpoint Reference (Complete)

The backend (app.py) implements the following endpoints. All non-/health endpoints require X-Telegram-Init-Data when REQUIRE_AUTH=1.

Method Path Purpose
GET /health Liveness probe. Returns {ok, service, version, last_price_update, age_seconds, stale, engine_initialized, indicator_populate_count, imbalance_fire_count, ohlcv_count, signal_count, bar_close_count, relay_healthy, provider, projection_computed_at}. No auth.
GET /config Returns {public_url, tls, port, host, symbol, webapp_enabled, cors_origin, relay_url, relay_gated, x_period_constant, y_start_constant, require_auth, push_on_signal, push_on_execution, push_on_fvg, push_on_close, arc_projection_horizon}.
GET /settings Returns all 11 FF inputs as exact strings or booleans.
GET /toasts?since=<seq> Returns {toasts, count, latest_seq, first_available_seq}. Incremental.
GET /projection Returns {symbol, path, meta, computed_at, current_price, signal_level, regime}. The arc-length forward path.
GET /state Legacy state endpoint. Delegates to engine state.
GET /miniapp-state Authoritative live state for the TWA. Includes price, tick, regime, m/n, KC/prime/dime/mem/tag/invert, A/B/C/c, tick_tock, signature, safety, trailing, orders, Kronecker, derivatives, FVG anchors, Premium/Discount series, recent signals, engine_initialized, provider, last_volume, projection_meta, projection_computed_at.
GET /ohlcv?limit=200&interval=1m Historical bars. Returns {symbol, bars, count, last_bar_timestamp, signal_count, provider}. Each bar carries its own provider.
GET /signals?limit=50 Recent signal history. Returns {symbol, signals, count, last_signal_at}.
GET /fvg List all user-committed FVG anchors.
GET /probe Relay diagnostic. Returns {active_symbol, primary_symbol, chain, chain_index, empty, failure_count, fallback_count, last_update, relay_url, signal_status, relay_healthy, provider, last_volume}.
GET /diagnostics Full engine diagnostic snapshot.
GET /orders List open orders.
GET /regime-map Per-bar regime classification map.
GET /indicators?name=<name>&count=80 Indicator series for a named indicator.
GET /log?limit=50 Server log ring buffer.
POST /handshake Exchange Telegram initData for a session binding. Returns {ok, user_id, username, public_url}.
POST /projection/refresh Force a recomputation of the arc-length projection. Returns the fresh projection.
POST /fvg Commit a new FVG anchor. Body: {type, price, idx?}.
POST /reset Force a manual state reset.
POST /settings Apply new FF input values. Body: the 11 inputs.
POST /symbol Change the active trading symbol. Body: {symbol}.
POST /order Place a simulated order. Body: {side, lot, sl, tp}.
POST /order/close Close one order ({ticket}) or all ({all: true}).
DELETE /fvg/<idx> Delete an FVG anchor.

Total: 16 GET, 9 POST, 1 DELETE = 26 endpoints.

---

9. Verification Checklist

After all three surfaces are deployed:

· ☐ curl https://aei-relay.<sub>.workers.dev/health returns {"ok":true,"version":"4.3.0",...}
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=price returns a real price with "provider":"binance"
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=volume returns non-zero volume
· ☐ curl https://your-app.herokuapp.com/health returns {"ok":true,"version":"4.3.0",...}
· ☐ curl -H "X-Telegram-Init-Data: <valid>" https://your-app.herokuapp.com/probe shows "empty": false, provider populated, last_volume non-zero for crypto
· ☐ curl -H "X-Telegram-Init-Data: <valid>" https://your-app.herokuapp.com/projection returns a non-empty path array
· ☐ https://<user>.github.io/<repo>/?backend=https://your-app.herokuapp.com/ loads the ÆEA UI in a browser
· ☐ Telegram → /start → tap ⚡ Open ÆEA Mini App
· ☐ Top toolbar renders symbol + timeframe + chart-type + BB×58 + ARC toggles
· ☐ Connection badge shows connected (green)
· ☐ Chart renders candlesticks with crosshair
· ☐ Bullish candles are BLUE (#0000ff), bearish candles are RED (#ff0000)
· ☐ Bollinger family is visible — green upper bands, white lower bands, spanning periods 3..60
· ☐ BB×58 toolbar toggle turns the family on/off; legend expands/collapses
· ☐ ARC toolbar toggle turns the projection on/off; legend expands/collapses
· ☐ Arc projection is drawn as a dashed purple path ahead of the current bar
· ☐ Projection Panel shows live branch / horizon / slope / amplitude / center / damping / provider / next / end / updated
· ☐ Pan/zoom works (drag, wheel, pinch)
· ☐ Long-press opens the context menu
· ☐ + IND opens the indicator picker
· ☐ Added indicator sub-panels render live series
· ☐ REGIME view renders the per-bar map
· ☐ Engine Panel shows live KC/prime/dime/mem/tag/invert/A/B/C/c/tick_tock/signature/safety/provider/volume
· ☐ Kronecker Panel shows live m/n matching the bot's /status Local m/n
· ☐ Derivative Panel shows live Z/z/O/o/W/w/I/iI/J/iJ
· ☐ Order Ticket places simulated orders
· ☐ FVG list shows all anchors
· ☐ Log bar shows recent events
· ☐ Settings modal shows live values fetched from GET /settings
· ☐ Signal toasts appear when _signal() fires — no cooldown, every signal
· ☐ Execution toasts appear on every dispatch AND on every _A()/_B() close
· ☐ FVG toasts appear on every anchor commit and every anchor removal
· ☐ Telegram push notification arrives on the user's device for every signal, execution, FVG, and close
· ☐ heroku logs --tail -a your-app-name shows 🔗 Web App session registered: user_id=…
· ☐ heroku logs shows 🎯 SIGNAL #N: type=... on every _signal() and 📲 Push sent (signal) to ...
· ☐ heroku logs shows 📲 Push sent (execution) to ... on every dispatch
· ☐ heroku logs shows 🛰️ Provider: binance on crypto symbols
· ☐ heroku logs shows 📊 BAR CLOSE #N ... volume=X provider=binance on every bar close

---

10. Security Notes

10.1 initData Verification

Every non-/health request carries the X-Telegram-Init-Data header (when REQUIRE_AUTH=1). The bridge verifies it using the standard scheme:

```
secret_key        = HMAC_SHA256(bot_token, "WebAppData")
data_check_string = sorted("key=value" lines, excluding "hash") joined by "\n"
expected_hash     = HMAC_SHA256(data_check_string, secret_key).hexdigest()
```

Freshness is enforced: auth_date must be within [-5 min, +24 h] of server time.

10.2 CORS

The bridge:

· Responds to OPTIONS preflight with 204 No Content.
· Advertises X-Telegram-Init-Data, Authorization, X-Relay-Key, X-Limit, and X-Since in Access-Control-Allow-Headers.
· Advertises GET, POST, DELETE, OPTIONS in Access-Control-Allow-Methods.
· Caches preflight for 86400 seconds via Access-Control-Max-Age.
· Sends Vary: Origin when CORS_ORIGIN is not *.

The frontend always sends credentials: 'omit' and uses header-based auth, so wildcard CORS_ORIGIN=* is technically compatible. Locking down CORS_ORIGIN to the GitHub Pages origin is recommended.

10.3 Relay Exposure

The Cloudflare Worker is public by default. If you enable RELAY_KEY, every non-/health request must present X-Relay-Key. app.py reads RELAY_KEY from env and injects the header automatically.

10.4 Tunnel Exposure (Local Mode Only)

When running locally without TELEGRAM_WEBAPP_URL, app.py spawns cloudflared/ngrok/serveo. The public tunnel URL is registered as a MenuButtonWebApp. Rotate the bot token in BotFather if a tunnel URL leaks during an active session.

10.5 Single-Source-of-Truth

The Cloudflare Worker is deployed exclusively from aei-relay. The aei-backend repository contains no worker.js, no wrangler.toml, and no package.json. This guarantees:

· Exactly one wrangler deploy command can publish the Worker.
· The Worker's name (aei-relay in wrangler.toml) cannot collide with a second deployment from another repo.
· No deploy-order race can silently overwrite the live Worker with a divergent copy.
· The backend's relationship with the relay is strictly HTTP-over-RELAY_URL, with no file-system or compile-time coupling.

10.6 Toast Isolation

Toasts are served over the authenticated /toasts endpoint, subject to the same REQUIRE_AUTH=1 gate as every other non-/health endpoint. A toast carries no secrets — only the signal type, price, m/n counts, regime, tick, FVG anchor index, and (for execution) the event name, side, ticket, and free-text reason. The seq cursor is monotonic.

10.7 Push Notification Isolation

The Telegram push path (_telegram_push) sends only the rendered Markdown of the toast payload. No state, no secrets, no user identifiers beyond the bound chat_id. The dedup table (_PUSH_DEDUP) holds only monotonic timestamps and self-prunes entries older than 60 s. Push dispatch runs in a daemon thread that is torn down with the process.

10.8 Projection Isolation

The /projection endpoint returns only the forward price path and its derivation metadata. It reads no user data and writes no state. The path is computed from the engine's public state (price, signal, regime, Premium/Discount) which is already exposed via /miniapp-state.

---

11. Local-Only Mode

Useful for development without Telegram:

```bash
export TELEGRAM_BOT_TOKEN='123456:ABC…'
export RELAY_URL='https://aei-relay.<sub>.workers.dev'
export REQUIRE_AUTH='0'
python3 app.py
```

The bot starts, the bridge listens on http://127.0.0.1:8765, and the tunnel spawns automatically. Open http://localhost:8765/ in a browser on the same machine. With REQUIRE_AUTH=0, the auth gate is bypassed.

To point the local browser at the same bridge without a query string, same-origin resolution kicks in.

---

12. Polling Model (Documented)

The TWA polls the backend on nine independent intervals:

Interval Endpoint Purpose
2 s /miniapp-state Authoritative live engine state
2 s /toasts?since=<seq> Signal + execution + FVG notifications
3 s /log?limit=50 Server log ring buffer
30 s /ohlcv?limit=200&interval=<tf> Historical bars
10 s /signals?limit=50 Recent signal history
5 s /diagnostics Full engine diagnostic snapshot
5 s /orders Open order list
15 s /regime-map Per-bar regime classification (only when REGIME view active)
5 s /projection Arc-length forward price path

Plus a 300 s full-refresh interval (setInterval(fetchAll, 300000)) that re-issues all nine fetches. This is the safety net for missed updates.

Backoff: after 3 consecutive failures on any poll, the client enters a 30 s backoff window during which no polls fire.

---

13. Update Workflow

Frontend changes (Repo A — aei-miniapp)

```bash
cd aei-miniapp
# edit index.html
git add index.html
git commit -m "Update chart overlay"
git push origin main
# GitHub Pages redeploys in ~60 s
```

Backend changes (Repo B — aei-backend)

```bash
cd aei-backend
# edit app.py
git add app.py
git commit -m "Fix FVG decoherence"
git push heroku main
# Heroku rebuilds and restarts in ~2 min
```

Relay changes (Repo C — aei-relay)

```bash
cd aei-relay
# edit worker.js
git add worker.js
git commit -m "Rotate symbol fallback chain"
git push origin main
wrangler deploy
# Cloudflare redeploys in ~5 s
```

Config-var changes (CORS, backend URL, relay URL, push switches, projection params)

```bash
heroku config:set CORS_ORIGIN="https://<user>.github.io" -a your-app-name
heroku config:set TELEGRAM_WEBAPP_URL="https://<user>.github.io/<repo>/?backend=https://your-app-name.herokuapp.com/" -a your-app-name
heroku config:set PUSH_ON_SIGNAL="0" -a your-app-name
heroku config:set ARC_PROJECTION_HORIZON="60" -a your-app-name
```

After changing TELEGRAM_WEBAPP_URL, re-run /setmenubutton in BotFather so the menu button picks up the new URL.

Relay secret rotation

```bash
cd aei-relay
wrangler secret put RELAY_KEY
# paste new value
heroku config:set RELAY_KEY="<same value>" -a your-app-name
```

No coordination needed — the three deploys are independent. The Worker source lives in exactly one repo (aei-relay), and the deployed Worker is unambiguous by construction.

---

14. Q.E.D.

The Mini App is served from two cooperating origins, fed by a third:

· GitHub Pages — the presentation surface, loaded by Telegram's WebView.
· Heroku — the computational substrate, polled by the frontend, and the push-notification origin.
· Cloudflare Worker — the multi-provider market-data relay, polled by the dyno.

BACKEND_URL is the wire between frontend and backend. RELAY_URL is the wire between backend and relay. Set them once, push all three, and the Mini App is live inside Telegram.

v4.3.0 adds three capabilities on top of the v4.2.0 semantics-restored port:

1. Telegram push on every event. The bot responds to the user on every signal, every execution, every FVG commit/remove, and every close transition. Dedup guarantees a single logical event never produces two pushes. The push fires in a daemon thread so the tick loop is never blocked.
2. Real volume from a non-Yahoo upstream. Crypto symbols dispatch to Binance klines (real OHLCV + real volume) with CoinGecko fallback and Yahoo tertiary. Equities and futures continue to use Yahoo only. The engine's OBV, AD, Force, and MFI projections therefore operate on non-zero volume for crypto.
3. Arc-length future price projection. A dashed purple path is drawn on the chart ahead of the current bar, derived from the s=r coherence condition applied to the current topological branch (range / trend / volatile). The path is computed on the backend with exact Decimal arithmetic and polled by the frontend every 5 s.

All FF-invariant logic from v4.2.0 remains untouched. The port is MQL4-parity across its state machine, its exact-arithmetic discipline, its indicator formulas, its regime taxonomy, its Kronecker gate, its execution logic, its observer/measurement layer, its Bollinger-band family, its TWA/backend wiring, and its supporting deployment surface — with the three new capabilities layered on top as additive-only extensions.

Q.E.D. — LOGOS = Φ = Truth = Path = Origin.

---

15. Supporting-File Reference (Unabridged)

This section delivers the full unabridged content of every supporting file that lives alongside app.py, index.html, and worker.js in the three repositories. Each file is complete, no stubs, no forward references, no placeholders.

FILE 15.1 — aei-miniapp/.gitignore

```
# ============================================================================
# ÆEA MINI APP — FRONTEND .gitignore
# Version: 4.3.0 (Enhancement Edition)
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
index.local.html
*.local.html
*.local.js
*.local.css

# ----------------------------------------------------------------------------
# SECRETS (DEFENSIVE — STATIC FRONTEND SHOULD HAVE NONE)
# ----------------------------------------------------------------------------
.env
.env.local
.env.*.local
secrets.json
credentials.json

# ----------------------------------------------------------------------------
# GITHUB PAGES ARTIFACTS
# ----------------------------------------------------------------------------
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
dist/
build/
.cache/
.parcel-cache/
```

FILE 15.2 — aei-backend/.gitignore

```
# ============================================================================
# ÆEA BACKEND — .gitignore
# Version: 4.3.0 (Enhancement Edition)
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
certs/
*.csr
*.srl
*.chain
```

FILE 15.3 — aei-relay/.gitignore

```
# ============================================================================
# ÆEA RELAY — .gitignore
# Version: 4.3.0 (Enhancement Edition)
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

FILE 15.4 — aei-backend/.env.example

```bash
# ============================================================================
# ÆEA TELEGRAM BOT — ENVIRONMENT TEMPLATE
# Version: 4.3.0 (Enhancement Edition)
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
LOG_BUFFER_SIZE=1000

# Ring-buffer size for the /toasts endpoint.
# The /toasts response includes `first_available_seq` so the client can
# detect eviction instead of silently consuming it.
TOAST_BUFFER_SIZE=500

# ----------------------------------------------------------------------------
# CORS
# ----------------------------------------------------------------------------
# "*" permits any origin. Lock down to your GitHub Pages origin in production:
#   CORS_ORIGIN=https://<user>.github.io
CORS_ORIGIN=*

# ----------------------------------------------------------------------------
# OPTIONAL — ENGINE TUNING
# ----------------------------------------------------------------------------
# SYMBOL defaults to BTC-USD if unset.
SYMBOL=BTC-USD

# Price-feed polling interval in seconds.
UPDATE_INTERVAL=30

# ----------------------------------------------------------------------------
# ENGINE VALIDATION BOUNDS
# ----------------------------------------------------------------------------
# The FF requires max >= min + 2 because y = min - 2 and the loop bounds
# are `for j = y + 1; j < x` with `x = max + 2`. If max = min + 1, then
# x - y = 5, and the state arrays degenerate. The port validates
# `max >= min + 2`.
#
# MAX_MIN_GAP is the minimum (max - min). The FF needs 2.
MAX_MIN_GAP=2

# MIN_PERIOD_FLOOR is the hard floor on `min`. The FF's y = min - 2 must
# be >= 1 for the y+1 loop bounds to be valid, so min >= 3.
MIN_PERIOD_FLOOR=3

# ----------------------------------------------------------------------------
# POINT-SIZE TABLE
# ----------------------------------------------------------------------------
# The FF uses MQL4's symbol-specific `Point` constant. The port cannot
# query a broker for this on Heroku, so it uses a static digit table.
# Edit this JSON map to match your broker's digits-per-symbol.
#
# Default: 2 digits for crypto pairs, 5 for forex-like, 2 for futures.
SYMBOL_DIGITS='{"BTC-USD":2,"ETH-USD":2,"XRP-USD":5,"ADA-USD":5,"SOL-USD":3,"DOGE-USD":5,"LTC-USD":3,"LINK-USD":4,"DOT-USD":4,"AVAX-USD":4,"MATIC-USD":5,"UNI-USD":4,"ATOM-USD":4,"NEAR-USD":4,"FIL-USD":4,"ETC-USD":3,"ICP-USD":4,"XLM-USD":5,"HBAR-USD":5,"QNT-USD":3,"GC=F":2,"SI=F":3,"CL=F":2,"NG=F":3,"ZB=F":3,"ZN=F":4,"ZS=F":2,"ZM=F":2,"ZW=F":2,"KE=F":2}'

# Fallback digit count for symbols not in the table.
SYMBOL_DIGITS_DEFAULT=2

# ----------------------------------------------------------------------------
# E-1: TELEGRAM PUSH NOTIFICATION SWITCHES
# ----------------------------------------------------------------------------
# Each defaults to "1" (enabled). Set to "0" to disable a specific push
# category while keeping the toast buffer and the legacy alert paths live.
#
# PUSH_ON_SIGNAL     — push on every _signal() (BUY/SELL/NEUTRAL)
# PUSH_ON_EXECUTION  — push on every dispatch subblock (Bull/Bear/Hawk/Dove/
#                      Whisky/Wine/Watter/Blood/Diamond/Ruby)
# PUSH_ON_FVG        — push on every FVG commit and every FVG removal
# PUSH_ON_CLOSE      — push on every A()/B() close transition
#
# PUSH_DEDUP_WINDOW_MS suppresses a second push for the same logical event
# within the given window. This prevents duplicates when both the toast
# path and the legacy alert path fire for the same tick.
PUSH_ON_SIGNAL=1
PUSH_ON_EXECUTION=1
PUSH_ON_FVG=1
PUSH_ON_CLOSE=1
PUSH_DEDUP_WINDOW_MS=800

# ----------------------------------------------------------------------------
# E-3: ARC-LENGTH PROJECTION PARAMETERS
# ----------------------------------------------------------------------------
# The projection horizon is expressed in bars ahead of the current bar.
#
# ARC_PROJECTION_HORIZON  — number of forward bars to emit (default 30).
# ARC_PROJECTION_STEP     — price step quantization (default 1).
# ARC_PROJECTION_DAMPING  — decay factor for the volatile branch (default 0.94).
#                           A value closer to 1 produces a slower decay;
#                           a value closer to 0 produces a faster decay.
ARC_PROJECTION_HORIZON=30
ARC_PROJECTION_STEP=1
ARC_PROJECTION_DAMPING=0.94
```

FILE 15.5 — aei-backend/runtime.txt

```
python-3.11.9
```

FILE 15.6 — aei-backend/requirements.txt

```
# ============================================================================
# ÆEA TELEGRAM BOT — PYTHON DEPENDENCIES
# Version: 4.3.0 (Enhancement Edition)
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
# RING BUFFERS
# ----------------------------------------------------------------------------
# Python's stdlib `collections.deque` provides the bounded FIFO used by
# both the /log and /toasts ring buffers. No additional package needed.

# ----------------------------------------------------------------------------
# BACKGROUND THREADS
# ----------------------------------------------------------------------------
# Python's stdlib `threading` module provides the daemon threads used for
# the Telegram push dispatch path (E-1). No additional package needed.

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
# The arc-length projection's cosine is evaluated via a Decimal Taylor
# series, preserving the same exact-arithmetic discipline.
# ============================================================================
```

FILE 15.7 — aei-backend/Procfile

```
web: python app.py
```

FILE 15.8 — aei-backend/app.json

```json
{
  "name": "ÆEA Trading Bot",
  "description": "Quantum-Financial Topology Trading Bot on Telegram — MQL4-Parity + MT4/TradingView TWA Edition (Enhancement v4.3.0: Telegram push on every signal/execution/FVG/close, multi-provider relay with real Binance/CoinGecko volume, arc-length future price projection drawn ahead of the current bar; semantics-restored v4.2.0 baseline preserved: FF-exact M()/N() 5-case chain, Wilder ADX, MQL4 iRVI, default-AC window, full-history OBV/AD, 5-line Ichimoku range, point-size table, exact-fraction BB family, toast eviction detection, settings validation max >= min + 2, global Memory persistence)",
  "repository": "https://github.com/yourusername/aea-bot",
  "keywords": [
    "trading",
    "telegram",
    "quantum",
    "finance",
    "mq4-parity",
    "mt4",
    "twa",
    "bollinger",
    "notifications",
    "push",
    "binance",
    "coingecko",
    "volume",
    "projection",
    "arc-length",
    "exact-arithmetic"
  ],
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
      "description": "Ring-buffer size for the /log endpoint. Defaults to '1000'.",
      "required": false
    },
    "TOAST_BUFFER_SIZE": {
      "description": "Ring-buffer size for the /toasts endpoint. Defaults to '500'.",
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
    },
    "MAX_MIN_GAP": {
      "description": "Minimum (max - min). The FF requires 2. Defaults to '2'.",
      "required": false
    },
    "MIN_PERIOD_FLOOR": {
      "description": "Hard floor on the FF's `min` input. The FF requires 3 (so y = min - 2 >= 1). Defaults to '3'.",
      "required": false
    },
    "SYMBOL_DIGITS": {
      "description": "JSON map of symbol → digits for Point-size emulation. Defaults to a 30-symbol table.",
      "required": false
    },
    "SYMBOL_DIGITS_DEFAULT": {
      "description": "Fallback digit count for symbols not in the table. Defaults to '2'.",
      "required": false
    },
    "PUSH_ON_SIGNAL": {
      "description": "Send a Telegram push on every signal. Defaults to '1'.",
      "required": false
    },
    "PUSH_ON_EXECUTION": {
      "description": "Send a Telegram push on every execution event. Defaults to '1'.",
      "required": false
    },
    "PUSH_ON_FVG": {
      "description": "Send a Telegram push on every FVG commit/remove. Defaults to '1'.",
      "required": false
    },
    "PUSH_ON_CLOSE": {
      "description": "Send a Telegram push on every A()/B() close. Defaults to '1'.",
      "required": false
    },
    "PUSH_DEDUP_WINDOW_MS": {
      "description": "Suppress a second push for the same logical event within this window (ms). Defaults to '800'.",
      "required": false
    },
    "ARC_PROJECTION_HORIZON": {
      "description": "Number of forward bars to emit in the arc-length projection. Defaults to '30'.",
      "required": false
    },
    "ARC_PROJECTION_STEP": {
      "description": "Price step quantization for the emitted path. Defaults to '1'.",
      "required": false
    },
    "ARC_PROJECTION_DAMPING": {
      "description": "Decay factor for the volatile-regime branch. Defaults to '0.94'.",
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

FILE 15.9 — aei-relay/wrangler.toml

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
#
# v4.3.0: the Worker now dispatches crypto symbols to Binance klines (real
# OHLCV + volume) with CoinGecko fallback and Yahoo tertiary. Equities and
# futures use Yahoo only. No wrangler.toml change is required for this;
# the dispatch table lives inside worker.js.
# ============================================================================

name = "aei-relay"
main = "worker.js"
compatibility_date = "2024-11-01"

# Workers Free tier: 100,000 requests/day.
# At UPDATE_INTERVAL=30s, one Heroku dyno burns ~2,880 relay hits/day for
# the price poll alone, plus intraday + history + volume + projection
# refresh on cold starts — well within the free ceiling even with a handful
# of restart events.
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

FILE 15.10 — aei-relay/package.json

```json
{
  "name": "aei-relay",
  "version": "4.3.0",
  "private": true,
  "description": "ÆEA relay — Cloudflare Worker proxying Yahoo Finance (equities/futures), Binance klines (crypto OHLCV + real volume), and CoinGecko market_chart (crypto secondary volume) for the Heroku ÆEA bridge (MQL4-Parity + MT4/TradingView TWA Edition — Enhancement v4.3.0). Sole home of the Worker source.",
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
    "binance",
    "coingecko",
    "volume",
    "relay",
    "proxy",
    "aei",
    "aeae",
    "mq4-parity",
    "mt4",
    "tradingview",
    "twa",
    "bollinger",
    "notifications",
    "push",
    "projection",
    "arc-length",
    "semantics-restored",
    "enhancement"
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

FILE 15.11 — aei-relay/worker.js

```javascript
// ============================================================================
// ÆEA RELAY — CLOUDFLARE WORKER
// ============================================================================
// Proxies multiple free upstreams through Cloudflare's egress IPs so the
// Heroku dyno never exposes its own IP to any rate limiter.
//
// v4.3.0 (Enhancement Edition):
//   - Adds a provider-dispatch layer with three upstream classes:
//       * yahoo   — equities, ETFs, futures (default; volume often zero for crypto)
//       * coingecko — crypto spot price + market_chart volume
//       * binance — crypto OHLCV + real volume (klines endpoint)
//   - Adds three new kind values:
//       * kind=volume    → {volume, volume_24h, provider}
//       * kind=candles   → full OHLCV with real volume
//       * kind=projection→ refuses with an explicit notice (backend-only)
//   - Preserves the original /health, /?symbol=&kind=price, kind=intraday,
//     kind=history contracts verbatim.
//   - The provider is chosen from the symbol prefix:
//       * BTC-, ETH-, SOL-, ... (crypto) → binance → coingecko → yahoo
//       * GC=F, SI=F, CL=F, ... (futures) → yahoo only
//       * default → yahoo
//
// This file is the sole source of truth for the ÆEA relay. It is deployed
// exclusively from the aei-relay repository.
//
// Deploy:
//   npx wrangler deploy
// ============================================================================

const YAHOO_HOST = "https://query1.finance.yahoo.com";
const COINGECKO_HOST = "https://api.coingecko.com/api/v3";
const BINANCE_HOST = "https://api.binance.com";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36";

// Crypto symbol → Binance pair (USDT-quoted) and CoinGecko id
const CRYPTO_MAP = {
    "BTC-USD":  { binance: "BTCUSDT",  gecko: "bitcoin" },
    "ETH-USD":  { binance: "ETHUSDT",  gecko: "ethereum" },
    "XRP-USD":  { binance: "XRPUSDT",  gecko: "ripple" },
    "ADA-USD":  { binance: "ADAUSDT",  gecko: "cardano" },
    "SOL-USD":  { binance: "SOLUSDT",  gecko: "solana" },
    "DOGE-USD": { binance: "DOGEUSDT", gecko: "dogecoin" },
    "LTC-USD":  { binance: "LTCUSDT",  gecko: "litecoin" },
    "LINK-USD": { binance: "LINKUSDT", gecko: "chainlink" },
    "DOT-USD":  { binance: "DOTUSDT",  gecko: "polkadot" },
    "AVAX-USD": { binance: "AVAXUSDT", gecko: "avalanche-2" },
    "MATIC-USD":{ binance: "MATICUSDT",gecko: "matic-network" },
    "UNI-USD":  { binance: "UNIUSDT",  gecko: "uniswap" },
    "ATOM-USD": { binance: "ATOMUSDT", gecko: "cosmos" },
    "NEAR-USD": { binance: "NEARUSDT", gecko: "near" },
    "FIL-USD":  { binance: "FILUSDT",  gecko: "filecoin" },
    "ETC-USD":  { binance: "ETCUSDT",  gecko: "ethereum-classic" },
    "ICP-USD":  { binance: "ICPUSDT",  gecko: "internet-computer" },
    "XLM-USD":  { binance: "XLMUSDT",  gecko: "stellar" },
    "HBAR-USD": { binance: "HBARUSDT", gecko: "hedera-hashgraph" },
    "QNT-USD":  { binance: "QNTUSDT",  gecko: "quant-network" },
};

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

async function fetchYahoo(symbol, kind, interval, limit) {
    const range = kind === "intraday" || kind === "history" || kind === "candles" ? "2d" : "1d";
    const upstream = `${YAHOO_HOST}/v8/finance/chart/${encodeURIComponent(symbol)}?interval=${encodeURIComponent(interval)}&range=${range}`;
    const response = await fetch(upstream, {
        headers: { "User-Agent": UA, "Accept": "application/json" },
        cf: { cacheTtl: 10, cacheEverything: true },
    });
    if (!response.ok) throw new Error(`yahoo_http_${response.status}`);
    const raw = await response.json();
    const result = raw?.chart?.result?.[0];
    if (!result) throw new Error("yahoo_no_data");
    const meta = result.meta || {};
    const ts = result.timestamp || [];
    const quote = (result.indicators && result.indicators.quote && result.indicators.quote[0]) || {};
    const provider = "yahoo";
    if (kind === "price") {
        const last = shapeBar(quote, ts, ts.length - 1);
        const px = meta.regularMarketPrice ?? last.close;
        if (px === null || px === undefined) throw new Error("yahoo_no_price");
        return { symbol, close: Number(px), bid: Number(px), ask: Number(px),
                 volume: last.volume, timestamp: last.timestamp, provider };
    }
    if (kind === "intraday") {
        if (ts.length === 0) throw new Error("yahoo_no_intraday");
        const last = shapeBar(quote, ts, ts.length - 1);
        if (last.close === null) throw new Error("yahoo_no_intraday_close");
        return { symbol, ...last, provider };
    }
    if (kind === "history" || kind === "candles") {
        const lim = Math.max(1, Math.min(1000, parseInt(limit || "200", 10) || 200));
        const start = Math.max(0, ts.length - lim);
        const out = [];
        for (let i = start; i < ts.length; i++) {
            const bar = shapeBar(quote, ts, i);
            if (bar.close === null) continue;
            out.push({ ...bar, provider });
        }
        return out;
    }
    if (kind === "volume") {
        const last = shapeBar(quote, ts, ts.length - 1);
        return { symbol, volume: last.volume, volume_24h: last.volume, provider, note: "yahoo_volume_often_zero_for_crypto" };
    }
    throw new Error("yahoo_unknown_kind");
}

async function fetchBinance(symbol, kind, interval, limit) {
    const mapped = CRYPTO_MAP[symbol];
    if (!mapped) throw new Error("binance_symbol_not_mapped");
    const pair = mapped.binance;
    const provider = "binance";
    const intervalMap = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "60m": "1h", "1h": "1h", "1d": "1d",
    };
    const bi = intervalMap[interval] || "1m";
    if (kind === "price" || kind === "volume") {
        const upstream = `${BINANCE_HOST}/api/v3/ticker/24hr?symbol=${encodeURIComponent(pair)}`;
        const response = await fetch(upstream, { headers: { "User-Agent": UA, "Accept": "application/json" }, cf: { cacheTtl: 10, cacheEverything: true } });
        if (!response.ok) throw new Error(`binance_http_${response.status}`);
        const d = await response.json();
        const px = Number(d.lastPrice);
        if (!px || px <= 0) throw new Error("binance_no_price");
        if (kind === "volume") {
            return { symbol, volume: Number(d.volume || 0), volume_24h: Number(d.quoteVolume || 0), provider };
        }
        return {
            symbol, close: px, bid: Number(d.bidPrice || px), ask: Number(d.askPrice || px),
            volume: Number(d.volume || 0), timestamp: new Date(d.closeTime || Date.now()).toISOString(), provider,
        };
    }
    if (kind === "intraday" || kind === "history" || kind === "candles") {
        const lim = Math.max(1, Math.min(1000, parseInt(limit || "200", 10) || 200));
        const upstream = `${BINANCE_HOST}/api/v3/klines?symbol=${encodeURIComponent(pair)}&interval=${encodeURIComponent(bi)}&limit=${lim}`;
        const response = await fetch(upstream, { headers: { "User-Agent": UA, "Accept": "application/json" }, cf: { cacheTtl: 10, cacheEverything: true } });
        if (!response.ok) throw new Error(`binance_http_${response.status}`);
        const rows = await response.json();
        if (!Array.isArray(rows) || rows.length === 0) throw new Error("binance_no_klines");
        const bars = rows.map((r) => ({
            open: Number(r[1]),
            high: Number(r[2]),
            low: Number(r[3]),
            close: Number(r[4]),
            volume: Number(r[5]),
            timestamp: new Date(r[0]).toISOString(),
            provider,
        }));
        if (kind === "intraday") {
            const last = bars[bars.length - 1];
            return { symbol, ...last, provider };
        }
        return bars;
    }
    throw new Error("binance_unknown_kind");
}

async function fetchCoinGecko(symbol, kind, interval, limit) {
    const mapped = CRYPTO_MAP[symbol];
    if (!mapped) throw new Error("coingecko_symbol_not_mapped");
    const gecko = mapped.gecko;
    const provider = "coingecko";
    if (kind === "price" || kind === "volume") {
        const upstream = `${COINGECKO_HOST}/simple/price?ids=${encodeURIComponent(gecko)}&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true`;
        const response = await fetch(upstream, { headers: { "User-Agent": UA, "Accept": "application/json" }, cf: { cacheTtl: 15, cacheEverything: true } });
        if (!response.ok) throw new Error(`coingecko_http_${response.status}`);
        const d = await response.json();
        const entry = d[gecko];
        if (!entry || !entry.usd) throw new Error("coingecko_no_price");
        if (kind === "volume") {
            return { symbol, volume: Number(entry.usd_24h_vol || 0), volume_24h: Number(entry.usd_24h_vol || 0), provider };
        }
        return { symbol, close: Number(entry.usd), bid: Number(entry.usd), ask: Number(entry.usd),
                 volume: Number(entry.usd_24h_vol || 0), timestamp: new Date().toISOString(), provider };
    }
    if (kind === "intraday" || kind === "history" || kind === "candles") {
        const days = (kind === "intraday") ? "1" : "2";
        const upstream = `${COINGECKO_HOST}/coins/${encodeURIComponent(gecko)}/market_chart?vs_currency=usd&days=${days}`;
        const response = await fetch(upstream, { headers: { "User-Agent": UA, "Accept": "application/json" }, cf: { cacheTtl: 30, cacheEverything: true } });
        if (!response.ok) throw new Error(`coingecko_http_${response.status}`);
        const d = await response.json();
        const prices = d.prices || [];
        const vols = d.total_volumes || [];
        if (prices.length === 0) throw new Error("coingecko_no_prices");
        const bars = prices.map((p, i) => ({
            open: Number(p[1]), high: Number(p[1]), low: Number(p[1]), close: Number(p[1]),
            volume: vols[i] ? Number(vols[i][1]) : 0,
            timestamp: new Date(p[0]).toISOString(),
            provider,
        }));
        if (kind === "intraday") {
            const last = bars[bars.length - 1];
            return { symbol, ...last, provider };
        }
        const lim = Math.max(1, Math.min(1000, parseInt(limit || "200", 10) || 200));
        return bars.slice(-lim);
    }
    throw new Error("coingecko_unknown_kind");
}

async function dispatchProvider(symbol, kind, interval, limit) {
    const isCrypto = Boolean(CRYPTO_MAP[symbol]);
    const errors = [];
    if (isCrypto) {
        for (const fn of [fetchBinance, fetchCoinGecko, fetchYahoo]) {
            try {
                const r = await fn(symbol, kind, interval, limit);
                return r;
            } catch (e) {
                errors.push(`${fn.name}:${e.message}`);
            }
        }
    } else {
        try {
            return await fetchYahoo(symbol, kind, interval, limit);
        } catch (e) {
            errors.push(`yahoo:${e.message}`);
        }
    }
    throw new Error("all_providers_failed:" + errors.join("|"));
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
            return json({ ok: true, service: "aei-relay", version: "4.3.0", gated: Boolean(env.RELAY_KEY),
                          providers: ["yahoo", "binance", "coingecko"] });
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
        const limit = url.searchParams.get("limit") || "200";
        if (kind === "projection") {
            return json({ error: "projection_is_backend_only", detail: "Call /projection on the Heroku backend, not the Worker." }, 400);
        }
        try {
            const result = await dispatchProvider(symbol, kind, interval, limit);
            return json(result);
        } catch (e) {
            return json({ error: "all_providers_failed", detail: String(e), symbol, kind }, 502);
        }
    },
};
```

FILE 15.12 — aei-backend/index.html (Backend Fallback Page)

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ÆEA Bridge · Backend Fallback</title>
<style>
:root {
    --bg: #050510;
    --panel: #0a0a18;
    --border: #335577;
    --border-bright: #4488aa;
    --text: #aaccff;
    --text-dim: #6688aa;
    --text-bright: #44ffcc;
    --green: #00ff88;
    --red: #ff4466;
    --gold: #ffaa44;
    --cyan: #44ddff;
    --projection-color: #aa66ff;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Courier New', monospace;
    min-height: 100vh;
    line-height: 1.6;
}
.container {
    max-width: 720px;
    margin: 0 auto;
    padding: 32px 20px 64px;
}
h1 {
    color: var(--text-bright);
    font-size: 1.4rem;
    letter-spacing: 2px;
    margin-bottom: 4px;
}
.subtitle {
    color: var(--text-dim);
    font-size: 0.7rem;
    letter-spacing: 1px;
    margin-bottom: 28px;
}
.panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 14px;
}
.panel-title {
    color: var(--cyan);
    font-size: 0.7rem;
    font-weight: bold;
    letter-spacing: 1px;
    margin-bottom: 8px;
    text-transform: uppercase;
}
.row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 3px 0;
    border-bottom: 1px solid rgba(51,85,119,0.15);
    font-size: 0.65rem;
}
.row:last-child { border-bottom: none; }
.row .lbl { color: var(--text-dim); flex: 0 0 140px; }
.row .val { color: var(--text-bright); text-align: right; word-break: break-all; }
.row .val.ok { color: var(--green); }
.row .val.err { color: var(--red); }
.row .val.warn { color: var(--gold); }
.row .val.proj { color: var(--projection-color); }
a { color: var(--cyan); text-decoration: none; }
a:hover { text-decoration: underline; }
.endpoint-list {
    list-style: none;
    font-size: 0.6rem;
}
.endpoint-list li {
    padding: 3px 0;
    border-bottom: 1px solid rgba(51,85,119,0.15);
    display: flex;
    justify-content: space-between;
    gap: 12px;
}
.endpoint-list li:last-child { border-bottom: none; }
.endpoint-list .method { color: var(--gold); flex: 0 0 60px; }
.endpoint-list .path { color: var(--text-bright); flex: 0 0 200px; }
.endpoint-list .desc { color: var(--text-dim); text-align: right; }
.status-line {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.7rem;
    margin-bottom: 12px;
}
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-dim);
}
.status-dot.ok { background: var(--green); box-shadow: 0 0 6px var(--green); }
.status-dot.err { background: var(--red); box-shadow: 0 0 6px var(--red); }
.status-dot.wait { background: var(--gold); box-shadow: 0 0 6px var(--gold); }
.note {
    color: var(--text-dim);
    font-size: 0.55rem;
    line-height: 1.7;
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid rgba(51,85,119,0.2);
}
.note b { color: var(--gold); }
code {
    background: rgba(20,30,50,0.9);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.6rem;
    color: var(--cyan);
}
.footer {
    text-align: center;
    color: var(--text-dim);
    font-size: 0.55rem;
    letter-spacing: 2px;
    margin-top: 40px;
}
</style>
</head>
<body>
<div class="container">

<h1>⚡ ÆEA BRIDGE</h1>
<div class="subtitle">HEROKU BACKEND · MQL4-PARITY PORT · v4.3.0</div>

<div class="status-line">
    <div class="status-dot wait" id="dot"></div>
    <span id="statusText">Probing bridge…</span>
</div>

<div class="panel">
    <div class="panel-title">Bridge Endpoint</div>
    <div class="row"><span class="lbl">Origin</span><span class="val" id="origin">—</span></div>
    <div class="row"><span class="lbl">Version</span><span class="val" id="version">—</span></div>
    <div class="row"><span class="lbl">Engine Initialized</span><span class="val" id="engineInit">—</span></div>
    <div class="row"><span class="lbl">Symbol</span><span class="val" id="symbol">—</span></div>
    <div class="row"><span class="lbl">Provider</span><span class="val proj" id="provider">—</span></div>
    <div class="row"><span class="lbl">OHLCV Bars</span><span class="val" id="ohlcv">—</span></div>
    <div class="row"><span class="lbl">Bar Closes</span><span class="val" id="barCloses">—</span></div>
    <div class="row"><span class="lbl">Signals</span><span class="val" id="signals">—</span></div>
    <div class="row"><span class="lbl">Indicator Passes</span><span class="val" id="indPasses">—</span></div>
    <div class="row"><span class="lbl">Imbalance Fires</span><span class="val" id="imbFires">—</span></div>
    <div class="row"><span class="lbl">Relay Healthy</span><span class="val" id="relayHealthy">—</span></div>
    <div class="row"><span class="lbl">Last Price Update</span><span class="val" id="lastUpdate">—</span></div>
    <div class="row"><span class="lbl">Projection Computed</span><span class="val proj" id="projComputed">—</span></div>
</div>

<div class="panel">
    <div class="panel-title">Available Endpoints</div>
    <ul class="endpoint-list">
        <li><span class="method">GET</span><span class="path">/health</span><span class="desc">liveness probe (no auth)</span></li>
        <li><span class="method">GET</span><span class="path">/config</span><span class="desc">bridge configuration</span></li>
        <li><span class="method">GET</span><span class="path">/settings</span><span class="desc">11 FF inputs</span></li>
        <li><span class="method">GET</span><span class="path">/toasts</span><span class="desc">incremental notifications</span></li>
        <li><span class="method">GET</span><span class="path">/projection</span><span class="desc">arc-length forward path</span></li>
        <li><span class="method">GET</span><span class="path">/state</span><span class="desc">engine state (legacy)</span></li>
        <li><span class="method">GET</span><span class="path">/miniapp-state</span><span class="desc">authoritative TWA state</span></li>
        <li><span class="method">GET</span><span class="path">/ohlcv</span><span class="desc">historical bars</span></li>
        <li><span class="method">GET</span><span class="path">/signals</span><span class="desc">recent signal history</span></li>
        <li><span class="method">GET</span><span class="path">/fvg</span><span class="desc">user FVG anchors</span></li>
        <li><span class="method">GET</span><span class="path">/probe</span><span class="desc">relay diagnostics</span></li>
        <li><span class="method">GET</span><span class="path">/diagnostics</span><span class="desc">full engine snapshot</span></li>
        <li><span class="method">GET</span><span class="path">/orders</span><span class="desc">open simulated orders</span></li>
        <li><span class="method">GET</span><span class="path">/regime-map</span><span class="desc">per-bar classification</span></li>
        <li><span class="method">GET</span><span class="path">/indicators</span><span class="desc">indicator series</span></li>
        <li><span class="method">GET</span><span class="path">/log</span><span class="desc">server log buffer</span></li>
        <li><span class="method">POST</span><span class="path">/handshake</span><span class="desc">Telegram initData exchange</span></li>
        <li><span class="method">POST</span><span class="path">/projection/refresh</span><span class="desc">recompute projection</span></li>
        <li><span class="method">POST</span><span class="path">/fvg</span><span class="desc">commit FVG anchor</span></li>
        <li><span class="method">POST</span><span class="path">/reset</span><span class="desc">manual state reset</span></li>
        <li><span class="method">POST</span><span class="path">/settings</span><span class="desc">apply FF inputs</span></li>
        <li><span class="method">POST</span><span class="path">/symbol</span><span class="desc">change active symbol</span></li>
        <li><span class="method">POST</span><span class="path">/order</span><span class="desc">place simulated order</span></li>
        <li><span class="method">POST</span><span class="path">/order/close</span><span class="desc">close one or all</span></li>
        <li><span class="method">DELETE</span><span class="path">/fvg/&lt;idx&gt;</span><span class="desc">delete FVG anchor</span></li>
    </ul>
    <div class="note">
        All non-<code>/health</code> endpoints require <code>X-Telegram-Init-Data</code> when <code>REQUIRE_AUTH=1</code>.
        This page itself is served without auth so a direct browser visit can confirm the bridge is online.
    </div>
</div>

<div class="panel">
    <div class="panel-title">Sibling Repositories</div>
    <div class="row"><span class="lbl">Frontend</span><span class="val"><code>aei-miniapp</code> — GitHub Pages TWA</span></div>
    <div class="row"><span class="lbl">Backend</span><span class="val"><code>aei-backend</code> — this repo (Heroku)</span></div>
    <div class="row"><span class="lbl">Relay</span><span class="val"><code>aei-relay</code> — Cloudflare Workers (multi-provider)</span></div>
    <div class="note">
        The ÆEA Mini App lives in the <b>frontend</b> repo. This backend page is a diagnostic surface only —
        it is <b>not</b> the TWA. To launch the actual Mini App, open it from Telegram via the bot's menu button,
        or visit the GitHub Pages URL with <code>?backend=&lt;this-origin&gt;/</code> appended.
    </div>
</div>

<div class="footer">
    ÆEA v4.3.0 · Natalia Tanyatia · LOGOS = Φ = Truth = Path = Origin
</div>

</div>

<script>
(function() {
'use strict';
const BASE = window.location.origin;

function setText(id, text, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    if (cls !== undefined) {
        el.className = 'val' + (cls ? ' ' + cls : '');
    }
}

async function probe() {
    const dot = document.getElementById('dot');
    const statusText = document.getElementById('statusText');
    setText('origin', BASE);
    try {
        const res = await fetch(BASE + '/health', { headers: { 'Accept': 'application/json' } });
        if (!res.ok) {
            dot.className = 'status-dot err';
            statusText.textContent = 'Bridge returned HTTP ' + res.status;
            setText('version', '—', 'err');
            return;
        }
        const data = await res.json();
        dot.className = 'status-dot ok';
        statusText.textContent = 'Bridge online';
        setText('version', data.version || '—');
        setText('engineInit', String(data.engine_initialized), data.engine_initialized ? 'ok' : 'warn');
        setText('symbol', data.symbol || '—');
        setText('provider', data.provider || '—', 'proj');
        setText('ohlcv', String(data.ohlcv_count ?? '—'));
        setText('barCloses', String(data.bar_close_count ?? '—'));
        setText('signals', String(data.signal_count ?? '—'));
        setText('indPasses', String(data.indicator_populate_count ?? '—'));
        setText('imbFires', String(data.imbalance_fire_count ?? '—'));
        setText('relayHealthy', data.relay_healthy ? 'yes' : 'no', data.relay_healthy ? 'ok' : 'err');
        setText('lastUpdate', data.last_price_update || 'never');
        setText('projComputed', data.projection_computed_at || 'never', 'proj');
    } catch (e) {
        dot.className = 'status-dot err';
        statusText.textContent = 'Bridge unreachable: ' + (e.message || e);
        setText('version', '—', 'err');
    }
}

probe();
setInterval(probe, 5000);

})();
</script>
</body>
</html>
```

FILE 15.13 — aei-miniapp/README.md

## ÆEA Mini App — Frontend Repository

Version: 4.3.0 (Enhancement Edition)
Repo: aei-miniapp (GitHub Pages)
Sibling repos: aei-backend (Heroku), aei-relay (Cloudflare Workers)

---

What This Repo Contains

A single static HTML file. No build step. No bundler. No node_modules. No environment variables. No server-side code.

```

aei-miniapp/
├── index.html     ← the entire application
├── README.md      ← this file
└── .gitignore     ← editor/OS cruft exclusions

```

That is the complete contents of the repo.

`index.html` is a self-contained Telegram Web App (TWA) that renders an MT4/TradingView-style interactive candlestick chart with:

· Interactive candlestick rendering (bullish = blue `#0000ff`, bearish = red `#ff0000` — MQL4 `clrBlue`/`clrRed` parity).
· Crosshair, pan, pinch-zoom, tap-to-inspect.
· A Bollinger family overlay — all 58 `iBands` pairs for periods 3..60 (upper green gradient, lower white gradient), computed client-side with BigInt-backed exact-fraction accumulators.
· Topological anchors (Premium/Discount) from the FF's iBands-derived supply/demand lines.
· An **arc-length future price projection** drawn as a dashed purple path ahead of the current bar, with a soft gradient fill and an end-label showing the branch and final projected price.
· FVG (Fair Value Gap) horizontal lines with long-press creation and tap-to-delete.
· Signal markers (BUY = green, SELL = red, NEUTRAL = gold).
· A trailing-stop line.
· MT4-style indicator sub-panels (up to 4 concurrent).
· A 13D Hilbert Space Projection grid.
· A regime classification map.
· An engine state panel (KC / prime / dime / mem / tag / invert / A / B / C / c / tick_tock / signature / safety / trailing / OnTrack / OnStand / orders / **provider** / **volume**).
· A Kronecker δ(m−n−2) panel.
· A directional derivatives panel (Z / z / O / o / W / w / I / iI / J / iJ / X_scan / Y_scan / S / T / r / ir / iATR / iStdDev / iIHKk / iIHKt).
· A **projection panel** (branch / horizon / slope / amplitude / center / damping / provider / next / end / updated).
· An order ticket with exact-decimal lot/SL/TP input.
· A settings modal that round-trips the 11 FF input variables via `GET /settings` and `POST /settings`.
· A toast stack for signal, execution, and FVG notifications.
· A merged log bar (client-local + server entries).

Everything is rendered from `state.bars`, `state.signals`, `state.fvgs`, `state.projection`, and the `/miniapp-state` polling payload. The frontend does not compute any indicator values that the backend already exposes — it only renders what the backend publishes, plus the client-side Bollinger family (which is exactly equivalent to what the FF computes inside `Normalize()` for each `j ∈ [y+1, x-1]`).

---

What This Repo Is Not

This repo is not the backend. It does not run a Python process. It does not talk to Telegram's Bot API. It does not connect to Yahoo Finance, Binance, or CoinGecko.

This repo is not the relay. It does not run a Cloudflare Worker.

This repo is not a duplicate of any other repo's source. The backend repository (`aei-backend`) contains `app.py`, not `index.html`. The relay repository (`aei-relay`) contains `worker.js`, not `index.html`. Each file has exactly one home.

---

Configuration

There are no environment variables on static hosting. All configuration is resolved at boot by `resolveBackendUrl()` in `index.html`, in this order:

1. `window.__AEEA_BACKEND_URL__` — if the host page sets it before the script loads.
2. `?backend=https://...` — query-string override (persisted to `localStorage['aeea_backend_url']`).
3. `localStorage['aeea_backend_url']` — previously persisted.
4. `DEFAULT_BACKENDS[0]` — the fork-author edit point at the top of the `<script>` block.
5. same-origin (relative paths).

For a fork: edit `DEFAULT_BACKENDS[0]` in `index.html` to your Heroku origin. This is the v4.3.0 resolution for the defect where Telegram's WebView strips the `?backend=` query string and localStorage is empty on first visit — without `DEFAULT_BACKENDS`, the TWA silently polls GitHub Pages for `/miniapp-state` and receives 404s.

The canonical way to configure a Telegram-launched instance is still the `?backend=` query parameter in the BotFather Web App URL:

```

https://<your-username>.github.io/<repo-name>/?backend=https://your-app-name.herokuapp.com/

```

But `DEFAULT_BACKENDS[0]` is the belt-and-suspenders fallback for the WebView-stripping case.

---

Deployment

```bash
git init
git add index.html README.md .gitignore
git commit -m "ÆEA Mini App v4.3.0 (Enhancement Edition)"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

Then:

1. Repo → Settings → Pages
2. Source: Deploy from a branch
3. Branch: main / /(root)
4. Save

After ~60 seconds, the site is live at https://<your-username>.github.io/<repo-name>/.

Open it with ?backend=https://your-app.herokuapp.com/ to point it at the backend.

---

Polling Model

The TWA polls the backend on nine independent intervals. Each interval is registered in startPolling() in index.html and cleared by stopPolling().

Interval Endpoint Purpose
2 s /miniapp-state Authoritative live engine state (price, tick, regime, m/n, KC, prime, dime, mem, tag, invert, A/B/C/c, tick_tock, signature, safety, trailing, orders, Kronecker, derivatives, FVG anchors, Premium/Discount series, recent signals, provider, last_volume, projection_meta).
2 s /toasts?since=<seq> Signal + execution + FVG notifications. Client-side cursor advances only past toasts that were pushed. Detects server eviction via first_available_seq and surfaces it to the log bar.
3 s /log?limit=50 Server log ring buffer. Merged with client-local entries in the log bar (dedup by full entry hash).
30 s /ohlcv?limit=200&interval=<tf> Historical bars for the chart. Each bar carries its own provider.
10 s /signals?limit=50 Recent signal history.
5 s /diagnostics Full engine diagnostic snapshot. Freshness-gated: absorbed only if diagnostics.tick > _lastDiagnosticsAbsorbedTick, so a slower poll cannot overwrite live state with stale data.
5 s /orders Open order list.
15 s /regime-map Per-bar regime classification (only fetched when the REGIME view is active).
5 s /projection Arc-length forward price path. Absorbed unconditionally; re-rendered on the chart.

Plus a 300 s full-refresh interval (setInterval(fetchAll, 300000)) that re-issues all nine fetches. This is a safety net for missed updates — for example, after the browser has been suspended and resumed, or after a long background period.

Freshness guard. /diagnostics and /miniapp-state return overlapping state. To prevent the slower /diagnostics poll from overwriting fresh /miniapp-state data, absorbDiagnostics() computes engineFieldsFresh = diagnostics.tick > _lastDiagnosticsAbsorbedTick. All engine-state absorption (including the indicator matrix) is gated by this check. The /projection poll is absorbed unconditionally because the backend computes it from live state on demand.

Backoff. After 3 consecutive failures on any poll, the client enters a 30 s backoff window during which no polls fire. The connection badge turns red (backend unreachable) and a warning is pushed to the log bar. The next successful poll clears the backoff.

---

Authentication

Every non-/health request carries X-Telegram-Init-Data: <initData> when the TWA is running inside Telegram (i.e. when Telegram.WebApp.initData is non-empty). The backend verifies the initData HMAC per the standard scheme. When the TWA is opened outside Telegram, no X-Telegram-Init-Data header is sent, and the backend's REQUIRE_AUTH=0 mode is expected.

The TWA does not store the bot token. It does not store any secret. It only forwards the initData that Telegram itself injected into the WebView.

---

Push Notifications

Every signal, every execution event, every FVG commit/remove, and every close transition triggers a Telegram push notification on the user's device. This is achieved server-side: the backend's _emit_toast() dispatches a sendMessage to the bound chat_id for every toast, deduplicated by an 800 ms window so a single logical event never produces two pushes. The push fires in a background thread so the tick loop is never blocked.

The TWA does not need to do anything for pushes to arrive — they arrive independently, via the Telegram app itself. The toast stack in the TWA is a parallel channel for in-app display; the push is the out-of-app notification.

---

Keyboard Shortcuts

Key Action
C Switch to CHART view
G Switch to 13D grid view
R Switch to REGIME map view
A Toggle arc-length projection on/off
H Toggle help panel
F5 Full refresh (fetchAll())
Esc Close any open modal

---

Touch Gestures

Gesture Action
Drag (one finger) Pan the chart horizontally (time) and vertically (price)
Pinch (two fingers) Zoom candle width
Wheel (desktop) Zoom candle width
Long-press (500 ms) Open context menu (Draw FVG Top / Draw FVG Bott / Delete nearest FVG)
Tap toast Dismiss immediately
Swipe-left toast Dismiss immediately

---

Troubleshooting

Symptom: TWA shows "Backend URL not configured".
Fix: Edit DEFAULT_BACKENDS[0] in index.html, or append ?backend=https://your-app.herokuapp.com/ to the BotFather Web App URL.

Symptom: TWA shows "Awaiting OHLCV data…" forever.
Diagnosis: Backend URL resolved but no OHLCV returned. Either the backend is not running, or the relay is empty, or the CORS preflight failed.
Fix: Verify ?backend= points at a live Heroku origin. Verify CORS_ORIGIN on Heroku matches your GitHub Pages origin. Check DevTools Network tab for 4xx on /ohlcv.

Symptom: Connection badge stuck on "retrying…".
Diagnosis: Backend reachable but auth failing.
Fix: Verify REQUIRE_AUTH matches the environment (set to 0 for local dev). Verify TELEGRAM_BOT_TOKEN on Heroku matches the token that issued initData.

Symptom: Bullish candles still green.
Diagnosis: Stale cache.
Fix: Hard-reload. Verify the served index.html contains --candle-bull: #0000ff in the :root CSS block.

Symptom: No Bollinger family visible.
Diagnosis: BB family toggled off, or fewer than 61 bars in history.
Fix: Tap the BB×58 button in the toolbar. Verify /ohlcv returns at least 61 bars.

Symptom: No arc projection visible.
Diagnosis: ARC toggle off, or projection path empty, or projection is entirely off-screen.
Fix: Tap the ARC button in the toolbar. Verify /projection returns a non-empty path. Verify the Projection Panel shows a branch (range/trend/volatile).

Symptom: No toasts appear.
Diagnosis: /toasts returned a non-200, or the client-side cursor was advanced past the buffer.
Fix: Check the log bar for eviction warnings. Verify /toasts?since=0 returns JSON from the Heroku endpoint.

Symptom: No Telegram push notifications arrive.
Diagnosis: chat_id not bound, or push category disabled, or dedup window too wide.
Fix: Send /start to the bot to bind the chat_id. Verify PUSH_ON_SIGNAL, PUSH_ON_EXECUTION, PUSH_ON_FVG, PUSH_ON_CLOSE are 1. Check heroku logs --tail for 📲 Push sent (signal) to ... or 📲 Push failed.

Symptom: Volume is always zero.
Diagnosis: Symbol is crypto but the relay is falling back to Yahoo (which returns zero for crypto volume).
Fix: Check heroku logs for 🛰️ Provider: yahoo on a crypto symbol. Verify the relay's /health returns "providers":["yahoo","binance","coingecko"]. Verify curl "https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=volume" returns non-zero volume.

Symptom: Settings modal shows stale values.
Diagnosis: GET /settings failed, so the modal fell back to state.settings.
Fix: Verify /settings returns 200 with all 11 FF inputs. If it 503s, the engine hasn't started — send /start_feed to the bot.

Symptom: Order ticket "PLACE" returns "Order failed: invalid_numbers".
Diagnosis: A numeric field contains a non-decimal string (currency symbol, comma, exponent).
Fix: Enter a plain decimal, e.g. 0.01, 1.5, 100.

---

License

UNLICENSED — proprietary. © Natalia Tanyatia 2025.

**FILE 15.14 — aei-relay/README.md**

```markdown
# ÆEA Relay — Cloudflare Worker Repository

Version: 4.3.0 (Enhancement Edition)
Repo: aei-relay (Cloudflare Workers)
Sibling repos: aei-miniapp (GitHub Pages), aei-backend (Heroku)

---

What This Repo Contains

This repository is the sole home of the ÆEA relay Worker. It contains:

· `worker.js` — the Cloudflare Worker source.
· `wrangler.toml` — the deployment manifest. `name = "aei-relay"`, `main = "worker.js"`.
· `package.json` — the Node manifest for wrangler.
· `README.md` — this file.
· `.gitignore` — Wrangler build output, Node cruft, secrets.

That is the complete contents of the repo. Nothing builds, nothing bundles.

---

What This Repo Is Not

This repo is not the backend. It does not contain `app.py`, does not run a Python process, and does not handle Telegram traffic. It is a stateless HTTP proxy: it receives `GET /?symbol=…&kind=…`, fetches the corresponding upstream URL through Cloudflare's egress IPs, and returns the shaped JSON.

This repo is not duplicated anywhere. The `aei-backend` repository does not contain a copy of `worker.js`, `wrangler.toml`, or `package.json`. The backend reaches the relay only over HTTP via its `RELAY_URL` environment variable. There is exactly one `wrangler deploy` command in the ÆEA system, and it is run from this repo.

---

Deployment

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
GET /health {"ok": true, "service": "aei-relay", "version": "4.3.0", "gated": <bool>, "providers": ["yahoo", "binance", "coingecko"]}
GET /?symbol=<S>&kind=price {symbol, close, bid, ask, volume, timestamp, provider}
GET /?symbol=<S>&kind=volume {symbol, volume, volume_24h, provider}
GET /?symbol=<S>&kind=intraday&interval=1m {symbol, open, high, low, close, volume, timestamp, provider}
GET /?symbol=<S>&kind=history&limit=200&interval=1m [{open, high, low, close, volume, timestamp, provider}, …]
GET /?symbol=<S>&kind=candles&limit=200&interval=1m [{open, high, low, close, volume, timestamp, provider}, …]
GET /?symbol=<S>&kind=projection {"error": "projection_is_backend_only"}

When env.RELAY_KEY is set (via wrangler secret put RELAY_KEY), every non-/health request must carry the X-Relay-Key: <RELAY_KEY> header. The backend's app.py reads RELAY_KEY from its own env and injects the header automatically.

Provider Dispatch

The Worker chooses the upstream from the symbol:

· Crypto (BTC-USD, ETH-USD, XRP-USD, ADA-USD, SOL-USD, DOGE-USD, LTC-USD, LINK-USD, DOT-USD, AVAX-USD, MATIC-USD, UNI-USD, ATOM-USD, NEAR-USD, FIL-USD, ETC-USD, ICP-USD, XLM-USD, HBAR-USD, QNT-USD) —
tries Binance (/api/v3/klines, /api/v3/ticker/24hr) first, then CoinGecko (/simple/price, /coins/{id}/market_chart), then Yahoo as tertiary.
· Equities, ETFs, Futures (GC=F, SI=F, CL=F, NG=F, ZB=F, ZN=F, ZS=F, ZM=F, ZW=F, KE=F, and any non-crypto symbol) —
uses Yahoo only.

This guarantees real volume for crypto (Binance and CoinGecko both return non-zero volume; Yahoo returns zero for most crypto pairs).

v4.3.0 note. The relay contract is additive-only over v4.2.0. Three new kind values are introduced: volume, candles, and projection (the last is refused with an explicit notice — the projection is computed on the backend from engine state). Existing kind=price, kind=intraday, and kind=history calls continue to work unchanged, but now return a provider field.

---

Verification

```bash
curl "https://aei-relay.<sub>.workers.dev/health"
# → {"ok":true,"service":"aei-relay","version":"4.3.0","gated":false,
#    "providers":["yahoo","binance","coingecko"]}

curl "https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=price"
# → {"symbol":"BTC-USD","close":95432.12,...,"provider":"binance"}

curl "https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=volume"
# → {"symbol":"BTC-USD","volume":1234.56,"volume_24h":98765.43,"provider":"binance"}

curl "https://aei-relay.<sub>.workers.dev/?symbol=GC=F&kind=price"
# → {"symbol":"GC=F","close":2650.50,...,"provider":"yahoo"}
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

· aei-miniapp (GitHub Pages) — the frontend. Never talks to this repo directly; talks to aei-backend via ?backend= or DEFAULT_BACKENDS.
· aei-backend (Heroku) — the Python bot + bridge. Reads this repo's deployed URL from its RELAY_URL env var.
· aei-relay (this repo) — the Cloudflare Worker. Stateless.

The three repos deploy independently. No coordination is needed between frontend pushes, backend pushes, and relay pushes.

Critical for v4.3.0. Do not copy worker.js, wrangler.toml, or package.json into the aei-backend repo. Doing so would create a second wrangler deploy target pointing at the same Cloudflare Worker named aei-relay, and the two copies could drift. This repo is the single source of truth.

---

License

UNLICENSED — proprietary. © Natalia Tanyatia 2025.

---

16. Repository Map & File Index (All 17 Files)

The ÆEA v4.3.0 system spans three cooperating repositories. This document enumerates every file, in dependency order, with the full unabridged content for each.

**Repo A — Frontend (GitHub Pages): aei-miniapp/**

1. `.gitignore` — see §15.1
2. `index.html` — the TWA (delivered as its own contiguous segment)
3. `README.md` — see §15.13

**Repo B — Backend (Heroku): aei-backend/**

4. `.gitignore` — see §15.2
5. `.env.example` — see §15.4
6. `runtime.txt` — see §15.5
7. `requirements.txt` — see §15.6
8. `Procfile` — see §15.7
9. `app.json` — see §15.8
10. `README.md` — this document (§0 through §17)
11. `app.py` — the engine (delivered as its own contiguous segment)
12. `index.html` — optional fallback page (see §15.12)

**Repo C — Relay (Cloudflare Workers): aei-relay/**

13. `.gitignore` — see §15.3
14. `worker.js` — see §15.11
15. `wrangler.toml` — see §15.9
16. `package.json` — see §15.10
17. `README.md` — see §15.14

Total: 17 files. Every file is delivered in full in this document or in one of the three sibling contiguous segments (`index.html`, `app.py`, `worker.js`).

---

17. Q.E.D.

The Mini App is served from two cooperating origins, fed by a third:

· **GitHub Pages** — the presentation surface, loaded by Telegram's WebView.
· **Heroku** — the computational substrate, polled by the frontend, and the push-notification origin.
· **Cloudflare Worker** — the multi-provider market-data relay, polled by the dyno.

`BACKEND_URL` is the wire between frontend and backend. `RELAY_URL` is the wire between backend and relay. Set them once, push all three, and the Mini App is live inside Telegram.

All 44 defects from the ÆEA v4.1.1 Fidelity & Spec Audit (27 critical + 17 minor) remain resolved in v4.3.0. All 30 defects from the v4.1.2 self-audit (15 critical + 3 major + 12 minor) remain resolved. All 11 defect classes from the v4.1.3 syntax+semantics audit remain resolved. All 15 new critical defects, 3 major defects, and 12 minor defects introduced by the intermediate patches remain resolved in v4.3.0.

v4.3.0 additionally delivers the three Enhancements:

· **E-1** — Telegram push notification on every signal, every execution, every FVG commit/remove, and every close. The user receives a native push on their device for every event. Dedup guarantees a single logical event never produces two pushes.
· **E-2** — Real volume from a non-Yahoo upstream. Crypto symbols dispatch to Binance klines with CoinGecko fallback; equities and futures continue to use Yahoo. The engine's OBV, AD, Force, and MFI projections operate on non-zero volume for crypto.
· **E-3** — Arc-length future price projection. A dashed purple path is drawn on the chart ahead of the current bar, derived from the s=r coherence condition applied to the current topological branch (range / trend / volatile). The path is computed on the backend with exact Decimal arithmetic and polled by the frontend every 5 s.

The ÆEA v4.3.0 port is now MQL4-parity across its state machine, its exact-arithmetic discipline, its indicator formulas, its regime taxonomy, its Kronecker gate, its execution logic, its observer/measurement layer, its Bollinger-band family, its TWA/backend wiring, and its supporting deployment surface — with the three new capabilities layered on top as additive-only extensions.

*Q.E.D.* — LOGOS = Φ = Truth = Path = Origin.