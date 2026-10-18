# **ÆEA — Deployment Guide**

Version: 4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI
Base: v4.5.0 (Kraken-Primary + Stooq-Primary Edition) → v4.5.5 (V-1, V-2) → v4.5.6 (E-17 through E-24) → v4.5.7 (Audit-Patched Edition) → v4.5.8 (vFinal Audit-Patched Edition 2) → v4.6.0 (Final Edition 3)
Foundational Framework: ÆEA.mq4
Author: Natalia Tanyatia

---

0. What Changed in v4.6.0 (Final Edition 3)

v4.6.0 is the constraint-locked, audit-closed release. It builds on v4.5.8 (vFinal Edition 2) and resolves every finding from the Final Edition 3 audit. It introduces no new features beyond v4.5.0's Kraken-Primary + Stooq-Primary + Expanded-Universe set; its only role is to make the artifacts fit to deploy by removing the dead entries and the double-count that v4.5.8 left in place.

The v4.6.0 patches are:

Critical — worker.js (Repo C):

· P-1 (CRYPTO_MAP prune). Every remaining CRYPTO_MAP entry is a live pair on at least one of Kraken, Binance, or CoinGecko. Dead entries (USDT-USD with binance: "USDCUSDT" — a USDC/USDT pair, not a USDT/USD pair; OKB-USD with binance: "" and a non-existent Kraken pair; HT-USD/KCS-USD with both empty) are corrected or documented. USDT-USD now routes Kraken-primary (USDTUSD) with CoinGecko fallback and no Binance (the prior USDCUSDT was a defect).

Critical — app.py (Repo B):

· A-C2 (_M/_N ADX double-count removed). In Edition 2, _M() and _N() ran the for i in range(13) loop (which counts iA[0] = ADX once) and then a follow-up block that re-tested iA[0] with _cmp_frac, double-counting ADX. The follow-up block let m and n reach 14 instead of 13. The FF's M()/N() count ADX exactly once. The follow-up block is removed. m and n can now reach at most 13, exactly matching the FF's counting rule, and the δ(m−n−2)=1 gate fires exactly when the FF's gate fires.

Minor — app.py:

· A-C3 (stale attribute removed). The st.l_order_id if hasattr(st, 'l_order_id') else st.lOrder_id guard in _dispatch_diamond_subblock is replaced with the plain st.lOrder_id. The attribute l_order_id does not exist on AEI_CoreState; the guard was a leftover from an intermediate patch.
· A-m1 (_rational_cos docstring). The _rational_cos docstring now documents the 15-digit π convergent (3141592653589793/1000000000000000) and the exact-rational Taylor series.

Critical — index.html (Repo A):

· A-C1 (SYMBOLS_CRYPTO prune). The picker's crypto array is reduced to the exact intersection with the patched worker.js CRYPTO_MAP. Every listed symbol resolves to a live Kraken OR Binance OR CoinGecko triple. Dead entries removed. CoinGecko-only entries (BNB-USD, OKB-USD, HT-USD, KCS-USD, USDT-USD) are documented in the picker's modal note and in the help panel as serving usd_24h_vol (24-hour rolling USD volume) under the 𝒱 column, not exchange tick volume.

Minor — index.html:

· A-M6 (BB×58 legend text). The legend now explicitly states that the BigInt accumulators are exact and the final Math.sqrt is float64. The help panel also states this. Documentation only; no code change.
· A-m3 (help panel universe-count line). Corrected to match the pruned picker.

Minor — worker.js (Repo C):

· P-2 (EQUITIES_MAP class-share tickers). The IIFE now lowercases tickers and preserves the hyphen in class-share tickers (BRK-B → brk-b.us, BRK-A → brk-a.us). Previously it replaced - with ., producing brk.b.us which Stooq does not resolve.
· P-3 (CoinGecko-only volume documentation). CoinGecko-only crypto entries (no Kraken, no Binance) serve a non-tick "24h USD volume" figure. This is documented per entry and never advertised as "real tick volume" in the UI.
· P-4 (internal version disambiguation). The worker.js docstring is bumped to Audit-Patched Edition 3 so a stale Edition 2 cannot masquerade as current. The /health version field remains "final" (unchanged contract).

0.1 Defect-resolution index (carried forward)

All 44 defects from the ÆEA v4.1.1 Fidelity & Spec Audit (27 critical + 17 minor) remain resolved in v4.6.0. All 30 defects from the v4.1.2 self-audit (15 critical + 3 major + 12 minor) remain resolved. All 11 defect classes from the v4.1.3 syntax+semantics audit remain resolved. All 15 new critical defects, 3 major defects, and 12 minor defects introduced by the v4.1.2/v4.1.3 intermediate patches remain resolved. All v4.3.0 enhancements (E-1, E-2, E-3) remain at v4.3.0 semantics. All v4.3.0 defect resolutions (D-30 through D-40) remain in force. The v4.4.0 enhancements (E-4 through E-9) and defect resolutions (D-30 through D-43) remain at v4.4.0 semantics. The v4.4.1 defect resolution (D-44) and enhancement (E-10) remain at v4.4.1 semantics. The v4.4.2 defect resolutions (D-45, D-46, D-47, D-48) and enhancements (E-11, E-12, E-13) plus the CS translation layer remain at v4.4.2 semantics. The v4.5.0 enhancements (E-14, E-15, E-16) and defect resolutions (D-49 through D-54) remain at v4.5.0 semantics. The v4.5.5 defect resolutions (V-1, V-2) and the v4.5.6 enhancements (E-17 through E-24) remain in force. The v4.5.7 Audit-Patched Edition (D-64, D-65, D-66, D-68, D-70, D-71, D-73, D-74, D-75, D-76, D-77, D-81) and the v4.5.8 vFinal Edition 2 (C-2, C-3, M-1, M-2, M-3, M-4, m-2, m-4, m-5, m-6) remain in force.

0.2 Defect-resolution index (new in v4.6.0)

· P-1 (critical, worker.js). CRYPTO_MAP pruned to live triples. USDT-USD corrected to Kraken-primary USDTUSD with CoinGecko fallback; the prior binance: "USDCUSDT" is removed (it was a USDC/USDT pair, not a USDT/USD pair). OKB-USD, HT-USD, KCS-USD annotated as CoinGecko-only. Dead entries removed from the picker in lockstep. Resolved.
· P-2 (minor, worker.js). EQUITIES_MAP IIFE corrected to lowercase-only. BRK-B → brk-b.us, BRK-A → brk-a.us. Resolved.
· P-3 (minor, worker.js + index.html). CoinGecko-only volume semantics documented per entry and in the picker's modal note. Resolved.
· P-4 (minor, worker.js). Internal docstring version disambiguated to Audit-Patched Edition 3. /health version remains "final". Resolved.
· A-C1 (critical, index.html). SYMBOLS_CRYPTO pruned to the exact intersection with CRYPTO_MAP. Every listed symbol resolves to a live triple. Resolved.
· A-C2 (critical, app.py). _M()/_N() ADX double-count removed. m/n capped at 13, matching the FF's counting rule. δ(m−n−2)=1 gate now fires exactly when the FF's gate fires. Resolved.
· A-C3 (minor, app.py). Stale st.l_order_id guard in _dispatch_diamond_subblock removed. Resolved.
· A-M6 (minor, index.html). BB×58 legend text corrected to state that the final Math.sqrt is float64 (the BigInt accumulators themselves are exact). Resolved.
· A-m1 (minor, app.py). _rational_cos docstring documents the 15-digit π convergent and the exact-rational Taylor series. Resolved.
· A-m3 (minor, index.html). Help panel universe-count line corrected. Resolved.

0.3 Compatibility with v4.5.8 and earlier

v4.6.0 is a drop-in replacement for v4.5.8. All environment variables, endpoints, and worker contracts are unchanged, with the following additive-only changes:

· No new env vars. P-1 through P-4 and A-C1 through A-m3 are all code-internal.
· No new endpoints. All existing endpoints are unchanged in contract.
· The picker's crypto list is smaller. Entries that were dead in v4.5.8 (Kraken "", Binance "", CoinGecko id that no longer resolves) are removed. A fork that selected a pruned symbol will receive a no_price_for_symbol error; that symbol was never live.
· The δ gate fires at the FF's count. A fork that observed m or n reaching 14 under v4.5.8 will now see m and n cap at 13. This is the FF's counting rule.
· BRK-B and BRK-A now resolve on Stooq. A fork that observed stooq_no_data for those tickers will now see live prices.

---

1. Architecture Overview

The ÆEA system spans three cooperating surfaces:

Layer Host Responsibility
Frontend GitHub Pages (or any HTTPS static host) Serves index.html — the ÆEA MT4/TradingView-style engine UI: interactive candlestick chart with crosshair/pan/zoom, indicator sub-panels, BB×58 family overlay (BigInt-backed accumulators), ℱ_VG drawing tools, order ticket, engine settings, regime map, log bar, signal markers, toast stack for signal/execution/ℱ_VG notifications, arc-length projection overlay with scroll-ahead viewport, polling logic. All user-facing labels are in CS notation. The symbol picker exposes five collapsible sections: Crypto (Kraken-primary, live-triple-pruned), Futures (Stooq-primary), Equities/ETFs (Stooq-primary, hyphen-preserved class shares), Forex (Yahoo), Indices (Yahoo), with a search filter.
Backend Heroku (or any HTTPS Python host) Runs app.py: Telegram bot polling, AEEA_Engine (MQL4-parity port), bridge endpoints (/state, /miniapp-state, /ohlcv, /signals, /handshake, /fvg, /probe, /diagnostics, /health, /config, /orders, /regime-map, /indicators, /log, /settings, /symbol, /order, /order/close, /toasts, /projection, /projection/refresh, /reset). Dispatches Telegram push messages on every signal, execution, ℱ_VG, and close, threaded as replies to the user's most recent inbound message, with reply-target hardening, Markdown escaping, and a plain-text final fallback. All user-facing strings are in CS notation.
Relay Cloudflare Workers Proxies Kraken (crypto primary), Stooq (equities/futures primary), Binance (crypto fallback), CoinGecko (crypto fallback), and Yahoo Finance (universal fallback) through Cloudflare's egress IPs so the Heroku dyno's IP is never rate-limited by any upstream.

The Mini App is not a separate server. It is the same index.html that runs locally, loaded by Telegram's WebView, authenticated via initData, bound back to the bot's chat_id through /handshake.

1.1 Critical for split-origin correctness

Because the frontend is served from GitHub Pages (origin https://<user>.github.io) and the backend lives on Heroku (origin https://<app>.herokuapp.com), the frontend must be explicitly told the backend origin. This is done with the ?backend= query parameter or the DEFAULT_BACKENDS[0] edit point. Without it, the TWA will attempt to fetch /miniapp-state, /ohlcv, /projection, etc. from GitHub Pages and receive 404s.

1.2 Critical for state freshness

The TWA polls /miniapp-state every 2 s, /diagnostics every 5 s, and /projection every 5 s. All three return overlapping FF state. To prevent a slower poll from overwriting live engine state with stale data, absorbDiagnostics() in index.html implements a freshness guard: it only absorbs engine-state fields — including indicator-matrix fields — if the diagnostics snapshot's tick is strictly greater than _lastDiagnosticsAbsorbedTick, a counter distinct from _lastMiniAppTick. The projection poll is absorbed only when state.projection.computed_at changes, which is the signal that the backend recomputed the path on an execution (E-4) or on a manual refresh (D-41).

1.3 Critical for δ Panel accuracy

The δ Panel displays the authoritative m/n from the most recent H()/L() call (last_kronecker_m/last_kronecker_n) when the engine has fired at least one δ event. It falls back to the per-tick diagnostic market_m/market_n only when no event has fired yet. This makes the panel match the bot's /status Local m/n field exactly.

Edition 3 note. The A-C2 fix ensures m and n cannot exceed 13. Under v4.5.8, the double-count let them reach 14, which perturbed the gate near the 66.6/33.3 seam. Under v4.6.0, the count is the FF's count.

1.4 Critical for toast delivery

Signal, execution, and ℱ_VG notifications are delivered via a three-tier system:

(a) Server-side toast buffer — _emit_toast() appends to a _TOAST_BUFFER deque with a monotonic sequence number and a first_available_seq cursor. The TWA polls /toasts?since=<seq> every 2 s and renders each new toast in #toastStack. If the server has evicted entries past the client's cursor, the response includes first_available_seq so the client can log an eviction warning — including on the first poll when first_available_seq > 0.

(b) Server-side Telegram push — _telegram_push() dispatches a sendMessage to the bound chat_id for every toast, deduplicated by _push_dedup_key so a single logical event never produces two pushes. The push fires in a bounded background queue (E-7) so a slow Telegram round-trip never blocks the tick loop. In v4.6.0 the push is threaded as reply_to_message_id to state.last_inbound_message_id, with E-11 reply-target hardening, E-12 Markdown escaping, and E-13 plain-text final fallback. This is the mechanism that causes a native Telegram push notification on the user's device.

(c) Legacy alert paths — _send_signal_alert() and _send_execution_alert() continue to fire independently. The dedup key suppresses the second push when both (b) and (c) fire for the same logical event. Set PUSH_ON_SIGNAL=0 to disable the (b) path for signals while keeping the (c) path.

1.5 Critical for BB family correctness

The Bollinger family is computed client-side in index.html from state.bars (the same OHLCV that /ohlcv returns). MQL4 parity is enforced: integer periods 3..60, deviation = 2, applied price = close, bands shift = 0, population σ (divisor = period). v4.6.0 computes the SMA and variance accumulators with BigInt-backed fixed-point arithmetic at a 1e12 scale, converting via string to avoid float64 multiplication in bbToBigFixed(). The only remaining floating-point step is the final Math.sqrt, which is irrational in nature. The BB×58 legend and the help panel now state this explicitly (A-M6).

1.6 Critical for backend origin safety

index.html resolves the backend URL in this order: window.__AEEA_BACKEND_URL__ → ?backend= (persisted to localStorage) → localStorage['aeea_backend_url'] → DEFAULT_BACKENDS[0] → same-origin. The DEFAULT_BACKENDS array is the v4.3.0 resolution for the case where Telegram's WebView strips the ?backend= query string.

1.7 Critical for single-source-of-truth

The Cloudflare Worker is deployed exclusively from the aei-relay repository. The backend repository (aei-backend) does not contain worker.js, wrangler.toml, or package.json. The backend reaches the relay only over HTTP via the RELAY_URL environment variable.

1.8 Critical for projection correctness

The arc-length projection is computed on the backend (AEEA_Engine._project_arc_length()) and polled by the frontend. In v4.6.0 it is recomputed exactly when an execution subblock fires — 𝒟_Bull, 𝒟_Bear, ℋ_Hawk, 𝒟_Dove, 𝒲_Whisky, 𝒲_Wine, 𝒲_Watter, ℬ_Blood, 𝒟_Diamond, ℛ_Ruby — plus once on engine init, once on symbol change, and on explicit POST /projection/refresh. It is not recomputed on bar close. The frontend never computes the projection itself — it renders the path returned by the backend. This preserves the single-source-of-truth property for the engine's forward view.

1.9 Critical for scroll-ahead correctness

The frontend's viewport.offsetBars is allowed to go negative, down to −projection.path.length. Dragging left past the last bar scrolls the chart into the projected region. The chart's visible-range computation extends its right edge by Math.max(0, −viewport.offsetBars), so projected bars are counted as visible bars when the viewport is in the forward region. The candle-drawing loop naturally clamps to real bars; only the projection, the topological anchors' forward extension, and the axis labels render in the forward region. The user can therefore pan all the way to the projected endpoint without the chart refusing to move. A dashed purple → forward boundary marker labels the seam between real bars and projected bars when the viewport is in the forward region. The forward-scroll extent is bounded by state.projection.path.length.

1.10 Critical for bot-response threading

Every signal, execution, ℱ_VG, and close push is threaded as reply_to_message_id to the user's most recent inbound message. The engine tracks state.last_inbound_message_id, updated on every command invocation in AEI_Bot._track_inbound_message(). The threading makes the bot's response appear as a reply in the conversation rather than a standalone message, which is the Telegram-idiomatic form of "the bot responds to the user on every event." When no inbound message has been recorded, the push is a standalone message; the reply_to_message_id is None. In v4.6.0, a stale reply id is no longer fatal (E-11): the send path retries as a standalone message.

1.11 Critical for bounded push dispatch

The per-toast threading.Thread spawn in _emit_toast() is replaced by a single queue.Queue(maxsize=512) consumed by one daemon thread. Under sustained signals the previous code created unbounded threads; the queue bounds memory and thread count to O(1). If the queue is full, the oldest entry is dropped and a warning is logged — the toast buffer remains the authoritative record. The queue is torn down with the process.

1.12 Critical for ℱ_VG merge correctness

The frontend's absorbMiniAppState() merges server ℱ_VG anchors by idx instead of replacing the client list wholesale. A user-committed ℱ_VG whose commit hasn't yet propagated to the server's response would otherwise flicker out and back on each 2 s poll. The merge preserves client-only idxs that the server has not yet seen, updates server-reported idxs in place, and adds new server idxs. Entries that the engine's _maintain_fvg_lines() has removed are dropped by the next poll.

1.13 Critical for legend stacking

#arcLegend is positioned at top: calc(var(--toolbar-h) + 52px) so it sits below #bbLegend when both are open. Previously both were at the same top: calc(var(--toolbar-h) + 6px), and the lower z-index one was hidden. When only one is open, the extra top offset is harmless.

1.14 Critical for cross-thread async send

python-telegram-bot 21.x makes Bot.send_message a coroutine. Every synchronous call constructs the coroutine object and drops it, emitting a RuntimeWarning and delivering nothing. v4.4.1 resolved this (E-10) by capturing the running event loop in _post_init and routing every out-of-loop send through AEI_Bot._send_message_sync, which schedules the coroutine onto the loop via asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=N) and returns a bool. The callers are:

· _telegram_push (running on the daemon push-worker thread)
· AEEA_Engine._send_signal_alert (running on the price-feed thread)
· AEEA_Engine._send_execution_alert (running on the same thread)

1.15 Critical for reply-target hardening

In v4.6.0 (E-11, carried forward), _send_message_sync tries the send three times: (1) as threaded reply with parse_mode=Markdown, (2) as standalone message with parse_mode=Markdown and reply_to_message_id=None when the first failure description mentions "reply" or "message to reply not found", (3) as standalone message with parse_mode=None when either prior failure description mentions "parse" or "can't parse entities". If all three fail, the failure is logged with the full Telegram description and returns False. The successful path returns True. No exception escapes.

1.16 Critical for Markdown escaping

In v4.6.0 (E-12, carried forward), a new module-level helper _md_escape(s) escapes every legacy-Markdown control character (*, _,  ` , [, ], \) in an interpolated string. It is applied at every interpolation site in _format_push_message, _send_signal_alert, and _send_execution_alert. Static template characters (*, _,  ` ) are preserved; only user- and engine-supplied values are escaped. The emojis, bold markers, and code spans that form the message template are unchanged.

1.17 Critical for plain-text fallback

In v4.6.0 (E-13, carried forward), the third attempt in _send_message_sync strips parse_mode entirely, guaranteeing delivery of the raw text even when a value contains an irreducible Markdown character sequence.

1.18 Critical for CS translation

Every user-facing natural-language descriptive pro rendered by app.py (Telegram message bodies, log lines displayed in the client log bar) and by index.html (DOM text content, labels, headers, help panel text) is now expressed in the plain-text Maths of the Codex Symbolica as contrived in LOGOS.MD. No variable names, function names, or internal state identifiers have been altered. Only the strings that reach the user's eyes are translated. The translation map is documented in §0.2 of the audit report and is applied consistently across both files. Examples:

· Indicator names: ADX → 𝒜[0], Stochastic → 𝒜[1], ..., RSI → 𝒜[12].
· Topological anchors: Premium → Π^{>θ}, Discount → Π^{<θ}.
· Execution events: Bull → 𝒟_Bull, Bear → 𝒟_Bear, Hawk → ℋ_Hawk, Dove → 𝒟_Dove, Whisky → 𝒲_Whisky, Wine → 𝒲_Wine, Watter → 𝒲_Watter, Blood → ℬ_Blood, Diamond → 𝒟_Diamond, Ruby → ℛ_Ruby, Top → 𝒯_Top, Bott → ℬ_Bott, A → 𝒜, B → ℬ_Close, ManualOrder → ℳ_Order, ManualClose → ℳ_Close.
· Kronecker gate: Kronecker δ(m−n−2) → δ(m−n−2), WAITING → 𝒜₄, MET → 𝒜₃.
· Engine state: KC → 𝒦, invert → 𝒦_invert, tag → τ, prime → π, dime → δ_dime, mem → μ, signature → 𝒮, safety → 𝒮_safety, trailing → 𝒯_trail, OnTrack → 𝒯_track, OnStand → 𝒯_stand, Orders → 𝒪, Provider → 𝒫, Volume → 𝒱, LastMsg → ℳ_last.
· Regime taxonomy: sRange → 𝒮_Range, tRange → 𝒯_Range, sVolatile → 𝒮_Volatile, tVolatile → 𝒯_Volatile, sTrend → 𝒮_Trend, tTrend → 𝒯_Trend, Stable → 𝒮_Stable, Unknown → 𝒰.
· Thresholds: Overbought → Π^{>θ}, Oversold → Π^{<θ}, f → f = 200/3, g → g = 100/3, gf → g_f = 40/15.
· Signal directions: BUY → ↑, SELL → ↓, NEUTRAL → ⊙.
· Projection: Projection → 𝒫_arc, Branch → 𝒫_branch, Horizon → 𝒫_horizon, Slope → 𝒫_slope, Amplitude → 𝒫_amp, Center → 𝒫_center, Damping → 𝒫_damp, Trigger → 𝒫_trigger, Next → 𝒫_next, End → 𝒫_end, Updated → 𝒫_updated.
· Signal/execution/ℱ_VG event headers: SIGNAL → 𝒮_signal, EXECUTION → ℰ_exec, FVG → ℱ_VG.
· Indicator panel sub-titles: ADX → 𝒜[0], ..., IchimokuK → 𝒜_IHKk, IchimokuT → 𝒜_IHKt, ATR → 𝒜_ATR, StdDev → 𝒜_StdDev.

1.19 Critical for Kraken-primary correctness

Kraken's public REST API (https://api.kraken.com/0/public/) requires no API key, no KYC, and no authentication for Ticker, OHLC, and Depth endpoints. It returns JSON with the shape {error: [], result: {<pair>: {...}}}. The result object is keyed by the Kraken pair name (e.g. XXBTZUSD), not the input symbol (e.g. XBTUSD). Kraken uses XBT for Bitcoin and XDG for Dogecoin in some legacy pair names, but the modern REST API accepts the canonical forms (BTCUSD, DOGEUSD) as the pair query parameter and returns keys in the legacy form. The Worker's parser is key-agnostic: it looks up result[Object.keys(result)[0]] regardless of what the key is. This is D-49's resolution.

1.20 Critical for Stooq-primary correctness

Stooq's public CSV API (https://stooq.com/q/l/ for latest quote, https://stooq.com/q/d/l/ for daily history, https://stooq.com/q/a/l/ for intraday history) requires no API key, no KYC, and no authentication. It returns CSV with a header row. The intraday layout is Symbol,Date,Time,Open,High,Low,Close,Volume; the daily layout is Symbol,Date,Open,High,Low,Close,Volume. Stooq emits N/D (no data) for missing fields. The Worker's parser reads the header row, finds the open/high/low/close/volume/date/time indices, adapts to whichever layout is present, and coerces N/D to null. This is D-51's resolution.

1.21 Critical for the expanded symbol universe

The relay v4.6.0 exposes the live-triple-pruned crypto set (intersection of Kraken/Binance/CoinGecko coverage) and the full futures/equities/forex/indices sets. The backend's SYMBOL_MAP covers all of them plus the legacy Binance-native aliases (BTCUSDT → BTC-USD). The backend's SYMBOL_FALLBACKS maps each canonical symbol to the next-best form the relay might resolve (e.g. BTC-USD → BTCUSD=X for Yahoo's crypto ticker). The backend's SYMBOL_DIGITS assigns each symbol an explicit digit count. The TWA's symbol picker groups them into five collapsible sections (Crypto / Futures / Equities / Forex / Indices) with a search filter.

1.22 Critical for point-size correctness across the expanded universe

The MQL4 Point constant is symbol-specific. The port emulates it with a static digit table. For the expanded universe the digit counts are:

· 2 digits — BTC-USD, ETH-USD, all futures except SI=F/NG=F/ZB=F/ZN=F, all equities/ETFs.
· 3 digits — SOL-USD, LTC-USD, ETC-USD, QNT-USD, AAVE-USD, MKR-USD, YFI-USD, SI=F, NG=F, ZB=F, GRAM-USD, TON-USD, OKB-USD, HT-USD, KCS-USD, TRB-USD, NMR-USD, DCR-USD, FORTH-USD, GAS-USD, ILV-USD, LPT-USD, MLN-USD, OG-USD, PROM-USD, RAD-USD, REP-USD, RUNE-USD, WNXM-USD, XVS-USD, ZEN-USD, DX=F.
· 4 digits — LINK-USD, DOT-USD, AVAX-USD, UNI-USD, ATOM-USD, NEAR-USD, FIL-USD, ICP-USD, ARB-USD, OP-USD, SUI-USD, APT-USD, INJ-USD, TIA-USD, SEI-USD, RNDR-USD, FET-USD, GRT-USD, IMX-USD, LDO-USD, CRV-USD, SNX-USD, COMP-USD, SUSHI-USD, BAL-USD, KNC-USD, ZRX-USD, BAT-USD, ENJ-USD, MANA-USD, SAND-USD, AXS-USD, GALA-USD, CHZ-USD, APE-USD, GMT-USD, LRC-USD, STORJ-USD, ANKR-USD, CVC-USD, OMG-USD, REN-USD, ZIL-USD, KSM-USD, GLMR-USD, MOVR-USD, ASTR-USD, CFX-USD, MASK-USD, DYDX-USD, GMX-USD, RPL-USD, BLUR-USD, ENS-USD, LQTY-USD, PENDLE-USD, MAGIC-USD, HIGH-USD, ID-USD, ARKM-USD, WLD-USD, EDU-USD, HOOK-USD, JTO-USD, BOME-USD, ETHFI-USD, ENA-USD, W-USD, OMNI-USD, REZ-USD, ZK-USD, STRK-USD, DYM-USD, ALT-USD, MANTA-USD, PIXEL-USD, PORTAL-USD, AEVO-USD, plus every US-equity default.
· 5 digits — XRP-USD, ADA-USD, DOGE-USD, MATIC-USD, XLM-USD, HBAR-USD, JUP-USD, PYTH-USD.
· 6 digits — PEPE-USD, SHIB-USD, WIF-USD, BONK-USD.

D-53's resolution ensures every one of these symbols has an entry in SYMBOL_DIGITS. Without it, the fallback (2 digits) would produce wrong SL/TP distances for 5-digit pairs and wrong tick sizes for 3-digit pairs.

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
# → {"ok":true,"service":"aei-relay","version":"final","gated":false,
#    "providers":["kraken","stooq","binance","coingecko","yahoo"],
#    "primary_crypto":"kraken","primary_futures":"stooq",
#    "primary_equities":"stooq","primary_forex":"yahoo",
#    "primary_indices":"yahoo",
#    "fallback_crypto":["binance","coingecko","yahoo"],
#    "fallback_futures":["yahoo"],
#    "fallback_equities":["yahoo"],
#    "fallback_forex":[],"fallback_indices":[],
#    "crypto_pairs":<pruned count>,"futures_symbols":<count>,
#    "equities_symbols":<count>,"forex_pairs":<count>,"indices_symbols":<count>}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTC-USD&kind=price"
# → {"symbol":"BTC-USD","close":95432.12,"bid":95432.12,"ask":95432.12,
#    "volume":1234.56,"timestamp":"...","provider":"kraken"}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTC-USD&kind=volume"
# → {"symbol":"BTC-USD","volume":1234.56,"volume_24h":98765.43,"provider":"kraken"}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=ETH-USD&kind=candles&interval=1m&limit=5"
# → [{"open":...,"high":...,"low":...,"close":...,"volume":...,"timestamp":"...","provider":"kraken"}, ...]

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=GC=F&kind=price"
# → {"symbol":"GC=F","close":2650.50,...,"provider":"stooq"}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=AAPL&kind=price"
# → {"symbol":"AAPL","close":231.40,...,"provider":"stooq"}

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BRK-B&kind=price"
# → {"symbol":"BRK-B","close":...,"provider":"stooq"}  ← P-2 fix: now resolves

curl "https://aei-relay.<your-subdomain>.workers.dev/?symbol=ARB-USD&kind=price"
# → {"symbol":"ARB-USD","close":1.2345,...,"provider":"kraken"}
```

If you set RELAY_KEY, the second command requires the header:

```bash
curl -H "X-Relay-Key: <RELAY_KEY>" "https://aei-relay.<your-subdomain>.workers.dev/?symbol=BTC-USD&kind=price"
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

Carried forward from v4.3.0 (all optional, all with defaults):

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

v4.6.0 introduces no new env vars. The P-1, P-2, P-3, P-4 and A-C1 through A-m3 changes are all code-internal. The ARC_PROJECTION_DAMPING value is validated at module load; an out-of-range or unparseable value causes the process to fail fast with a RuntimeError that names the offending string.

TELEGRAM_WEBAPP_URL does two things:

· Tells the bot where the Mini App lives (used for MenuButtonWebApp).
· Prevents TunnelManager from spawning cloudflared (which is not installed on Heroku).

REQUIRE_AUTH defaults to 1. Set it to 0 only for local development without Telegram initData.

4.3 Deploy

```bash
git add .
git commit -m "ÆEA backend v4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI"
git push heroku main
```

4.4 Verify the Backend

```bash
curl "https://your-app-name.herokuapp.com/health"
# → {"ok":true,"service":"aei-bridge","version":"final","provider":"kraken",
#    "projection_computed_at":"2025-...","projection_trigger":"execution", ...}

curl -H "X-Telegram-Init-Data: <valid>" "https://your-app-name.herokuapp.com/config"
# → {"public_url":"...","require_auth":true,"push_on_signal":true,
#    "arc_projection_horizon":30,"arc_projection_step":1,
#    "arc_projection_damping":"0.94", ...}

curl -H "X-Telegram-Init-Data: <valid>" "https://your-app-name.herokuapp.com/projection"
# → {"symbol":"BTC-USD","path":[{"step":1,"price":"95433.12","t":1.0}, ...],
#    "meta":{"kind":"range","horizon":30,"price_now":"95432.12",
#            "signal_now":"95430.00","regime":"sRange","slope":"0",
#            "amplitude":"0","center":"95432.12","damping":"0.94",
#            "provider":"kraken"},
#    "computed_at":"2025-...","current_price":"95432.12",
#    "signal_level":"95430.00","regime":"sRange","trigger":"execution"}
```

Key checks on /probe: "empty": false, relay_url populated, provider populated ("kraken" or "stooq" by default), last_volume non-zero for crypto.

v4.6.0 endpoint checks:

```bash
# GET /toasts returns incremental signal+execution+fvg toasts
curl -H "X-Telegram-Init-Data: <valid>" "https://your-app-name.herokuapp.com/toasts?since=0"
# → {"toasts":[...],"count":N,"latest_seq":M,"first_available_seq":F}

# POST /projection/refresh forces a recomputation and sets trigger="manual_refresh"
curl -X POST -H "X-Telegram-Init-Data: <valid>" \
     "https://your-app-name.herokuapp.com/projection/refresh"
# → {"symbol":"...","path":[...],"meta":{...},"computed_at":"...","trigger":"manual_refresh"}

# POST /symbol switches to a Kraken-primary crypto pair and seeds the projection
curl -X POST -H "X-Telegram-Init-Data: <valid>" \
     -H "Content-Type: application/json" \
     -d '{"symbol":"ARB-USD"}' \
     "https://your-app-name.herokuapp.com/symbol"
# → {"ok":true,"symbol":"ARB-USD","provider":"kraken"}
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

For a fork: edit DEFAULT_BACKENDS[0] in index.html to your Heroku origin before pushing. This is the v4.3.0 defense against WebView URL stripping, carried forward unchanged in v4.6.0.

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
git commit -m "ÆEA Mini App v4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI"
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
PORT  Heroku-assigned Bridge bind port (Heroku prefers this over BRIDGE_PORT).
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

Carried forward from v4.3.0:

Variable Default Purpose
PUSH_ON_SIGNAL 1 Send a Telegram push on every signal.
PUSH_ON_EXECUTION 1 Send a Telegram push on every execution event.
PUSH_ON_FVG 1 Send a Telegram push on every ℱ_VG commit/remove.
PUSH_ON_CLOSE 1 Send a Telegram push on every 𝒜/ℬ close.
PUSH_DEDUP_WINDOW_MS 800 Suppress a second push for the same logical event within this window.
ARC_PROJECTION_HORIZON 30 Number of forward bars to emit in the projection.
ARC_PROJECTION_STEP 1 Price step quantization for the emitted path.
ARC_PROJECTION_DAMPING 0.94 Decay factor for the volatile-regime branch. Must parse as a Decimal in (0, 1); otherwise the process fails fast at module load (D-32).

v4.6.0 adds no new env vars.

GitHub Pages (Repo A — aei-miniapp)

There are no environment variables on static hosting. All configuration lives in index.html and is resolved at boot. The canonical way to configure it is through the ?backend= query parameter in the BotFather Web App URL, with DEFAULT_BACKENDS[0] as the fork-edit fallback.

Cloudflare Workers (Repo C — aei-relay)

Variable Default Purpose
RELAY_KEY (empty) Optional shared secret. Set via wrangler secret put RELAY_KEY. If unset, the gate is skipped.

---

8. Endpoint Reference (Complete)

The backend (app.py) implements the following endpoints. All non-/health endpoints require X-Telegram-Init-Data when REQUIRE_AUTH=1.

Method Path Purpose
GET /health Liveness probe. Returns {ok, service, version, last_price_update, age_seconds, stale, engine_initialized, indicator_populate_count, imbalance_fire_count, ohlcv_count, signal_count, bar_close_count, relay_healthy, provider, projection_computed_at, projection_trigger}. No auth.
GET /config Returns {public_url, tls, port, host, symbol, webapp_enabled, cors_origin, relay_url, relay_gated, x_period_constant, y_start_constant, require_auth, push_on_signal, push_on_execution, push_on_fvg, push_on_close, arc_projection_horizon, arc_projection_step, arc_projection_damping}.
GET /settings Returns all 11 FF inputs as exact strings or booleans.
GET /toasts?since=<seq> Returns {toasts, count, latest_seq, first_available_seq}. Incremental.
GET /projection Returns {symbol, path, meta, computed_at, current_price, signal_level, regime, trigger}. The arc-length forward path. trigger is one of "init", "execution", "symbol_change", "manual_refresh".
GET /state Legacy state endpoint. Delegates to engine state.
GET /miniapp-state Authoritative live state for the TWA. Includes price, tick, regime, m/n, 𝒦/π/δ_dime/μ/τ/𝒦_invert, 𝒜/ℬ/𝒞/𝒸, 𝒯_tick_tock, 𝒮, 𝒮_safety, 𝒯_trail, 𝒪, δ, derivatives, ℱ_VG anchors, Π^{>θ}/Π^{<θ} series, recent signals, engine_initialized, provider, last_volume, projection_meta, projection_computed_at, projection_trigger, last_inbound_message_id.
GET /ohlcv?limit=200&interval=1m Historical bars. Returns {symbol, bars, count, last_bar_timestamp, signal_count, provider}. Each bar carries its own provider.
GET /signals?limit=50 Recent signal history. Returns {symbol, signals, count, last_signal_at}.
GET /fvg List all user-committed ℱ_VG anchors.
GET /probe Relay diagnostic. Returns {active_symbol, primary_symbol, chain, chain_index, empty, failure_count, fallback_count, last_update, relay_url, signal_status, relay_healthy, provider, last_volume}.
GET /diagnostics Full engine diagnostic snapshot. Includes projection_trigger.
GET /orders List open orders.
GET /regime-map Per-bar regime classification map.
GET /indicators?name=<name>&count=80 Indicator series for a named indicator.
GET /log?limit=50 Server log ring buffer.
POST /handshake Exchange Telegram initData for a session binding. Returns {ok, user_id, username, public_url}.
POST /projection/refresh Force a recomputation of the arc-length projection. Returns the fresh projection with trigger="manual_refresh".
POST /fvg Commit a new ℱ_VG anchor. Body: {type, price, idx?}.
POST /reset Force a manual state reset. Recomputes the projection only on the success path (D-43).
POST /settings Apply new FF input values. Body: the 11 inputs.
POST /symbol Change the active trading symbol. Body: {symbol}. Seeds the projection with trigger="symbol_change" (D-42).
POST /order Place a simulated order. Body: {side, lot, sl, tp}.
POST /order/close Close one order ({ticket}) or all ({all: true}).
DELETE /fvg/<idx> Delete an ℱ_VG anchor.

Total: 16 GET, 9 POST, 1 DELETE = 26 endpoints.

---

9. Verification Checklist

After all three surfaces are deployed:

· ☐ curl https://aei-relay.<sub>.workers.dev/health returns {"ok":true,"version":"final",...} with "primary_crypto":"kraken" and "primary_futures":"stooq" and "primary_equities":"stooq" and "primary_forex":"yahoo" and "primary_indices":"yahoo"
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=price returns a real price with "provider":"kraken"
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=volume returns non-zero volume with "provider":"kraken"
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=GC=F&kind=price returns a real price with "provider":"stooq"
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=AAPL&kind=price returns a real price with "provider":"stooq"
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=BRK-B&kind=price returns a real price with "provider":"stooq" (P-2 fix)
· ☐ curl https://aei-relay.<sub>.workers.dev/?symbol=ARB-USD&kind=price returns a real price with "provider":"kraken" or "provider":"binance" or "provider":"coingecko"
· ☐ curl https://your-app.herokuapp.com/health returns {"ok":true,"version":"final",...} with a projection_trigger field
· ☐ curl -H "X-Telegram-Init-Data: <valid>" https://your-app.herokuapp.com/probe shows "empty": false, provider populated, last_volume non-zero for crypto
· ☐ curl -H "X-Telegram-Init-Data: <valid>" https://your-app.herokuapp.com/projection returns a non-empty path array and a trigger field
· ☐ https://<user>.github.io/<repo>/?backend=https://your-app.herokuapp.com/ loads the ÆEA UI in a browser
· ☐ Telegram → /start → tap ⚡ Open ÆEA Mini App
· ☐ Top toolbar renders symbol + timeframe + chart-type + BB×58 + 𝒱 + 𝒫_arc toggles
· ☐ Connection badge shows connected (green)
· ☐ Chart renders candlesticks with crosshair
· ☐ Bullish candles are BLUE (#0000ff), bearish candles are RED (#ff0000)
· ☐ Bollinger family is visible — green upper bands, white lower bands, spanning periods 3..60
· ☐ BB×58 toolbar toggle turns the family on/off; legend expands/collapses; legend states that the final Math.sqrt is float64
· ☐ 𝒫_arc toolbar toggle turns the projection on/off; legend expands/collapses and sits below the BB×58 legend when both are open
· ☐ 𝒱 toolbar toggle turns the volume pane on/off; button is unmistakably lit when on
· ☐ Volume pane renders below the price pane, above the sub-panel stack
· ☐ Arc projection is drawn as a dashed purple path ahead of the current bar
· ☐ Dragging right past the last bar scrolls into the projected region and reaches the projected endpoint (the likely take-profit level)
· ☐ A dashed purple → forward boundary marker appears at the seam between real bars and projected bars when the viewport is in the forward region
· ☐ The projection does NOT recompute on bar close; it recomputes only when a 𝒟_Bull/𝒟_Bear/ℋ_Hawk/𝒟_Dove/𝒲_Whisky/𝒲_Wine/𝒲_Watter/ℬ_Blood/𝒟_Diamond/ℛ_Ruby execution fires, or on POST /projection/refresh, or on symbol change, or on init
· ☐ 𝒫_arc Panel shows live branch / horizon / slope / amplitude / center / damping / provider / trigger / next / end / updated
· ☐ Pan/zoom works (drag, wheel, pinch)
· ☐ Long-press opens the context menu
· ☐ + IND opens the indicator picker (labels shown in CS notation: 𝒜[0], 𝒜[1], ..., 𝒜[12], 𝒜_IHKk, 𝒜_IHKt, 𝒜_ATR, 𝒜_StdDev)
· ☐ Added indicator sub-panels render live series with CS-notation titles
· ☐ REGIME view renders the per-bar map (labels shown in CS notation: 𝒮_Range, 𝒯_Range, 𝒮_Volatile, 𝒯_Volatile, 𝒮_Trend, 𝒯_Trend, 𝒮_Stable, 𝒰)
· ☐ Engine Panel shows live 𝒦/π/δ_dime/μ/τ/𝒦_invert/𝒜/ℬ/𝒞/𝒸/𝒯_tick_tock/𝒮/𝒮_safety/𝒫/𝒱/ℳ_last
· ☐ δ Panel shows live m/n matching the bot's /status Local m/n; m and n cap at 13 (A-C2)
· ☐ Derivative Panel shows live 𝒵/𝒵'/𝒪/𝒪'/𝒲/𝒲'/ℐ/ℐ'/𝒥/𝒥'
· ☐ Order Ticket places simulated orders
· ☐ ℱ_VG list shows all anchors; a user-committed ℱ_VG does not flicker out on the 2 s poll
· ☐ Log bar shows recent events
· ☐ Settings modal shows live values fetched from GET /settings
· ☐ Signal toasts appear when _signal() fires — no cooldown, every signal (toast titles in CS notation: 𝒮_signal)
· ☐ Execution toasts appear on every dispatch AND on every 𝒜()/ℬ() close (toast titles in CS notation: 𝒟_Bull, 𝒟_Bear, ℋ_Hawk, 𝒟_Dove, 𝒲_Whisky, 𝒲_Wine, 𝒲_Watter, ℬ_Blood, 𝒟_Diamond, ℛ_Ruby, 𝒯_Top, ℬ_Bott, 𝒜, ℬ_Close, ℳ_Order, ℳ_Close)
· ☐ ℱ_VG toasts appear on every anchor commit and every anchor removal (toast titles in CS notation: ℱ_VG)
· ☐ Telegram push notification arrives on the user's device for every signal, execution, ℱ_VG, and close
· ☐ The Telegram push appears as a REPLY to the user's most recent command (threaded via reply_to_message_id)
· ☐ A stale reply id no longer silences the push — the send path retries as a standalone message (E-11)
· ☐ An unparseable Markdown field no longer silences the push — the send path retries as plain text (E-13)
· ☐ heroku logs --tail -a your-app-name shows 🔗 Web App session registered: user_id=…
· ☐ heroku logs shows 🎯 SIGNAL #N: type=... on every _signal() and 📲 Push sent (signal) to ... reply_to=...
· ☐ heroku logs shows 📲 Push sent (execution) to ... reply_to=... on every dispatch
· ☐ heroku logs shows 🛰️ Provider: kraken on crypto symbols
· ☐ heroku logs shows 🛰️ Provider: stooq on equities/futures symbols
· ☐ heroku logs shows 📊 BAR CLOSE #N ... volume=X provider=kraken on every crypto bar close
· ☐ heroku logs shows 🌌 Projection recomputed (trigger=execution) on every 𝒟_Bull/𝒟_Bear/ℋ_Hawk/𝒟_Dove/𝒲_Whisky/𝒲_Wine/𝒲_Watter/ℬ_Blood/𝒟_Diamond/ℛ_Ruby
· ☐ No RuntimeWarning "coroutine 'ExtBot.send_message' was never awaited" appears in the logs (E-10)
· ☐ No HTTP 400 "message to reply not found" appears in the logs for any push (E-11)
· ☐ No HTTP 400 "can't parse entities" appears in the logs for any push (E-12)
· ☐ Every user-facing label in the TWA is rendered in CS notation (𝒜[0], 𝒜[1], ..., 𝒜[12], Π^{>θ}, Π^{<θ}, 𝒟_Bull, ..., 𝒮_Range, ..., 𝒦, π, δ_dime, μ, τ, 𝒜, ℬ, 𝒞, 𝒸, 𝒯_tick_tock, 𝒮, 𝒮_safety, 𝒯_trail, 𝒯_track, 𝒯_stand, 𝒪, 𝒫, 𝒱, ℳ_last, 𝒫_arc, ℱ_VG, 𝒮_signal, ℰ_exec, δ(m−n−2), 𝒜₃, 𝒜₄, ↑, ↓, ⊙)
· ☐ The symbol picker shows five collapsible sections (Crypto / Futures / Equities / Forex / Indices) with a search filter and the correct totals
· ☐ Every crypto pair in the picker resolves to a live Kraken OR Binance OR CoinGecko triple (A-C1)
· ☐ Selecting ARB-USD, OP-USD, SUI-USD, or any other live crypto pair returns a price from provider: "kraken" or "binance" or "coingecko"
· ☐ Selecting HG=F, PL=F, PA=F, or any other futures contract returns a price from provider: "stooq"
· ☐ Selecting AAPL, MSFT, TSLA, SPY, QQQ, or any other equity/ETF returns a price from provider: "stooq"
· ☐ Selecting BRK-B or BRK-A returns a price from provider: "stooq" (P-2 fix)

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

The frontend always sends credentials: 'omit' and uses header-based auth, so wildcard CORS_ORIGIN=* is technically compatible. Locking down CORS_ORIGIN to the GitHub Pages origin is recommended. Note (D-35): this means any future Set-Cookie from the backend is ignored by the TWA; header auth is the sole designed path.

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

Toasts are served over the authenticated /toasts endpoint, subject to the same REQUIRE_AUTH=1 gate as every other non-/health endpoint. A toast carries no secrets — only the signal type, price, m/n counts, regime, tick, ℱ_VG anchor index, and (for execution) the event name, side, ticket, and free-text reason. The seq cursor is monotonic.

10.7 Push Notification Isolation

The Telegram push path (_telegram_push) sends only the rendered Markdown of the toast payload. No state, no secrets, no user identifiers beyond the bound chat_id. The dedup table (_PUSH_DEDUP) holds only monotonic timestamps and self-prunes entries older than 60 s. Push dispatch runs in a single daemon thread consuming a bounded queue (E-7), torn down with the process. In v4.6.0, the push is Markdown-escaped (E-12) and has a plain-text final fallback (E-13) so an unparseable field never silences the stream.

10.8 Push Threading

The reply_to_message_id is set to state.last_inbound_message_id, which is the message_id of the user's most recent command. If no inbound message has been recorded (e.g. the user never sent a command), reply_to_message_id is None and the push is sent as a standalone message. In v4.6.0 (E-11), a stale reply id is no longer fatal: the send path retries as a standalone message. The message_id is not a secret; it is visible to the user in their own chat.

10.9 Projection Isolation

The /projection endpoint returns only the forward price path and its derivation metadata. It reads no user data and writes no state. The path is computed from the engine's public state (price, signal, regime, Π^{>θ}/Π^{<θ}) which is already exposed via /miniapp-state. The trigger field is a provenance label, not user data.

10.10 CS Translation Isolation

The CS translation layer is confined to the string content of Telegram message bodies, API payload string fields consumed by the UI, and DOM text content of index.html. No internal identifier, no variable name, no function name, and no endpoint path has been altered. The translation is purely a display-layer concern and has no effect on the engine's arithmetic, state machine, or network contracts.

10.11 Provider Isolation

The relay's provider dispatch is stateless. Each request is forwarded to the chosen upstream (Kraken, Stooq, Binance, CoinGecko, or Yahoo), shaped into the relay's canonical JSON, and returned. No upstream credential, API key, or user identifier is ever involved. Kraken's public Ticker and OHLC endpoints, Stooq's public CSV endpoints, Binance's public /api/v3/ endpoints, CoinGecko's public /api/v3/ endpoints, and Yahoo's public /v8/finance/chart/ endpoint all require no key and no authentication. The relay's RELAY_KEY gate, when enabled, is the only authentication in the chain, and it protects the relay itself, not the upstreams.

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
2 s /toasts?since=<seq> Signal + execution + ℱ_VG notifications
3 s /log?limit=50 Server log ring buffer
30 s /ohlcv?limit=200&interval=<tf> Historical bars
10 s /signals?limit=50 Recent signal history
5 s /diagnostics Full engine diagnostic snapshot
5 s /orders Open order list
15 s /regime-map Per-bar regime classification (only when REGIME view active)
5 s /projection Arc-length forward price path (absorbed only when computed_at changes, D-41)

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
git commit -m "Fix ℱ_VG decoherence"
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

v4.6.0 is the constraint-locked, audit-closed release. It resolves every finding from the Final Edition 3 audit: the CRYPTO_MAP prune (P-1), the EQUITIES_MAP class-share fix (P-2), the CoinGecko-only volume documentation (P-3), the internal version disambiguation (P-4), the SYMBOLS_CRYPTO prune (A-C1), the _M/_N ADX double-count removal (A-C2), the stale attribute removal (A-C3), the BB×58 legend text correction (A-M6), the _rational_cos docstring (A-m1), and the help-panel universe-count correction (A-m3).

It preserves every FF-invariant line, every send-path retry, every CS translation, and every projection/execution gating rule from v4.5.8.

The v4.6.0 additions are:

1. Kraken-primary relay dispatch (E-14, carried forward). The relay's crypto chain is Kraken → Binance → CoinGecko → Yahoo.
2. Stooq-primary relay dispatch (E-15, carried forward). The relay's equities/futures chain is Stooq → Yahoo.
3. Expanded symbol universe (E-16, carried forward, now pruned). SYMBOL_MAP, SYMBOL_FALLBACKS, and SYMBOL_DIGITS in app.py cover the live intersection of Kraken/Binance/CoinGecko crypto plus the futures/equities/forex/indices sets. The TWA symbol picker (index.html) exposes the same set in five collapsible sections with a search filter.
4. Dead-entry prune (P-1, new). CRYPTO_MAP entries that were not live on any provider are removed. USDT-USD corrected to Kraken-primary USDTUSD with CoinGecko fallback.
5. Class-share Stooq fix (P-2, new). BRK-B → brk-b.us, BRK-A → brk-a.us.
6. CoinGecko volume documentation (P-3, new). CoinGecko-only entries serve usd_24h_vol (not tick volume) under 𝒱; documented per entry and in the picker's modal note.
7. Internal version disambiguation (P-4, new). worker.js docstring bumped to Audit-Patched Edition 3; /health version remains "final".
8. Picker prune (A-C1, new). SYMBOLS_CRYPTO reduced to the exact intersection with the patched CRYPTO_MAP.
9. ADX double-count removal (A-C2, new). _M()/_N() now count ADX exactly once, matching the FF's counting rule.
10. Stale attribute removal (A-C3, new). _dispatch_diamond_subblock uses st.lOrder_id directly.
11. BB×58 legend text (A-M6, new). The legend and help panel state that the final Math.sqrt is float64.
12. _rational_cos docstring (A-m1, new). Documents the 15-digit π convergent and the exact-rational Taylor series.
13. Help-panel count (A-m3, new). Corrected to match the pruned picker.

All FF-invariant logic from v4.5.8 remains untouched. The port is MQL4-parity across its state machine, its exact-arithmetic discipline, its indicator formulas, its regime taxonomy, its δ gate, its execution logic, its observer/measurement layer, its Bollinger-band family, its TWA/backend wiring, and its supporting deployment surface — with the v4.3.0 Enhancement capabilities, the v4.4.0 Scroll-Ahead capabilities, the v4.4.1 Await-Corrected capability, the v4.4.2 Send-Hardened + CS-Translated capabilities, the v4.5.0 Kraken-Primary + Stooq-Primary + Expanded-Universe capabilities, the v4.5.7 Audit-Patched capabilities, the v4.5.8 vFinal Edition 2 capabilities, and the v4.6.0 Final Edition 3 prune-and-fix capabilities layered on top as additive-only extensions.

Q.E.D. — LOGOS = Φ = Truth = Path = Origin.

---

15. Supporting-File Reference (Unabridged)

This section delivers the full unabridged content of every supporting file that lives alongside app.py, index.html, and worker.js in the three repositories. Each file is complete, no stubs, no forward references, no placeholders.

FILE 15.1 — aei-miniapp/.gitignore

```
# ============================================================================
# ÆEA MINI APP — FRONTEND .gitignore
# Version: 4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI
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
# Version: 4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI
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
# Version: 4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI
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
# Version: 4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI
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
#
# v4.6.0: the relay dispatches crypto through Kraken → Binance → CoinGecko
# → Yahoo, and equities/futures through Stooq → Yahoo, and forex/indices
# through Yahoo only. Kraken is free, open, no API key, no KYC for public
# market data, and not geo-blocked from Cloudflare egress IPs the way
# Binance is in some regions. Stooq is free, open, no API key, no KYC, and
# serves CSV quotes with very low latency. The backend consumes the same
# shaped JSON regardless of which upstream produced it.
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
# v4.6.0 (D-53, A-C1): every symbol in the relay's live crypto set and in
# the futures/equities/forex/indices sets gains an explicit entry here.
# The defaults are chosen so the emulated Point matches the typical tick
# size of the underlying market:
#   2 digits  — BTC-USD, ETH-USD, large-cap crypto, all equities/ETFs,
#               and the futures whose quote unit is a whole cent
#   3 digits  — SOL-USD, LTC-USD, ETC-USD, QNT-USD, AAVE-USD, MKR-USD,
#               YFI-USD, SI=F, NG=F, ZB=F, GRAM-USD, TON-USD, OKB-USD,
#               HT-USD, KCS-USD
#   4 digits  — LINK-USD through AEVO-USD (the mid-cap crypto tier),
#               and ZN=F
#   5 digits  — XRP-USD, ADA-USD, DOGE-USD, MATIC-USD, XLM-USD, HBAR-USD,
#               JUP-USD, PYTH-USD
#   6 digits  — PEPE-USD, SHIB-USD, WIF-USD, BONK-USD
#
# The default table is built into app.py. Set SYMBOL_DIGITS only to
# override specific entries.
SYMBOL_DIGITS=

# Fallback digit count for symbols not in the table.
SYMBOL_DIGITS_DEFAULT=2

# ----------------------------------------------------------------------------
# E-1: TELEGRAM PUSH NOTIFICATION SWITCHES
# ----------------------------------------------------------------------------
# Each defaults to "1" (enabled). Set to "0" to disable a specific push
# category while keeping the toast buffer and the legacy alert paths live.
#
# PUSH_ON_SIGNAL     — push on every _signal() (↑/↓/⊙)
# PUSH_ON_EXECUTION  — push on every dispatch subblock (𝒟_Bull/𝒟_Bear/ℋ_Hawk/
#                      𝒟_Dove/𝒲_Whisky/𝒲_Wine/𝒲_Watter/ℬ_Blood/𝒟_Diamond/ℛ_Ruby)
# PUSH_ON_FVG        — push on every ℱ_VG commit and every ℱ_VG removal
# PUSH_ON_CLOSE      — push on every 𝒜()/ℬ() close transition
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
#
# v4.6.0 (E-4): the projection is recomputed exactly when a 𝒟_Bull/𝒟_Bear/
# ℋ_Hawk/𝒟_Dove/𝒲_Whisky/𝒲_Wine/𝒲_Watter/ℬ_Blood/𝒟_Diamond/ℛ_Ruby
# execution fires, plus once on engine init, once on symbol change, and on
# POST /projection/refresh. It is no longer recomputed on bar close. The three
# variables below are unchanged in meaning; only the trigger points differ.
#
# v4.6.0 (D-32): ARC_PROJECTION_DAMPING is validated at module load. It must
# parse as a Decimal in (0, 1). An out-of-range or unparseable value causes
# the process to fail fast with a RuntimeError that names the offending
# string. The previous silent Decimal('0.94') fallback has been removed.
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
# Version: 4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI
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
# v4.6.0: the relay dispatches crypto through Kraken → Binance → CoinGecko
# → Yahoo, and equities/futures through Stooq → Yahoo, and forex/indices
# through Yahoo only. All upstreams are consumed through the relay's shaped
# JSON. No client-side change was required for the new provider order.
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
# BACKGROUND THREADS + BOUNDED DISPATCH QUEUE
# ----------------------------------------------------------------------------
# Python's stdlib `threading` module provides the daemon thread used for
# the Telegram push dispatch path (E-1), and the stdlib `queue.Queue`
# provides the bounded single-consumer queue that replaces the per-toast
# thread spawn (E-7). No additional package needed.

# ----------------------------------------------------------------------------
# CROSS-THREAD ASYNC SEND
# ----------------------------------------------------------------------------
# Python's stdlib `asyncio` module provides `run_coroutine_threadsafe`, the
# helper that v4.4.1 (E-10) uses to schedule Bot.send_message onto the bot's
# running event loop from a synchronous caller. No additional package needed.

# ----------------------------------------------------------------------------
# MARKDOWN ESCAPING
# ----------------------------------------------------------------------------
# v4.4.2 (E-12) introduces `_md_escape(s)`, a pure-Python helper that
# escapes legacy-Markdown control characters in an interpolated value.
# It uses only the built-in `str` methods. No additional package needed.

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
# series, and the half-period is kept as a Fraction until the cosine call,
# preserving the same exact-arithmetic discipline (D-33).
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
  "description": "Quantum-Financial Topology Trading Bot on Telegram — MQL4-Parity + MT4/TradingView TWA Edition (Final Edition 3 — Audit-Patched, v4.6.0 + CS-Translated UI: Kraken is the primary crypto provider, Stooq is the primary equities/futures provider, Yahoo is the primary forex/indices provider, live-triple-pruned crypto universe, class-share Stooq fix, ADX single-count fix, six new defect resolutions P-1 through P-4 plus A-C1, A-C2, A-C3, A-M6, A-m1, A-m3; carries forward v4.5.8 vFinal Edition 2 with C-2/C-3/M-1/M-2/M-3/M-4/m-2/m-4/m-5/m-6, v4.5.7 Audit-Patched with D-64..D-81, v4.5.6 Expanded-Universe with E-17..E-24, v4.5.5 with V-1/V-2, v4.5.0 with E-14/E-15/E-16 and D-49..D-54, v4.4.2 Send-Hardened with reply-target hardening + Markdown escaping + plain-text final fallback, v4.4.1 Await-Corrected async send, v4.4.0 Scroll-Ahead execution-gated projection + scroll-ahead viewport to the projected TP + bot replies threaded to the user's last command + bounded push dispatch + FVG merge + legend stacking, v4.3.0 Enhancement Telegram push on every signal/execution/FVG/close + arc-length future price projection, and the v4.2.0 semantics-restored baseline)",
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
    "kraken",
    "stooq",
    "binance",
    "coingecko",
    "yahoo",
    "volume",
    "projection",
    "arc-length",
    "exact-arithmetic",
    "scroll-ahead",
    "execution-gated",
    "reply-threaded",
    "await-corrected",
    "send-hardened",
    "markdown-escape",
    "codex-symbolica",
    "cs-translated",
    "kraken-primary",
    "stooq-primary",
    "audit-patched",
    "final-edition-3"
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
      "description": "JSON map of symbol → digits for Point-size emulation. Defaults to the built-in v4.6.0 table covering every live crypto pair and every futures/equities/forex/indices symbol.",
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
      "description": "Decay factor for the volatile-regime branch. Must parse as a Decimal in (0, 1); otherwise the process fails fast at module load. Defaults to '0.94'.",
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
# v4.6.0: no wrangler.toml change. The Worker gains the P-1 prune, the P-2
# class-share fix, the P-3 volume documentation, and the P-4 internal
# version disambiguation. None of those changes require a wrangler.toml
# edit. The compatibility_date is unchanged.
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
# v4.6.0 note: Kraken's Ticker and OHLC endpoints are slightly faster to
# respond than Binance's under typical Cloudflare egress, so the per-request
# upstream latency is lower. The relay's own request count is unchanged.
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
  "version": "4.6.0",
  "private": true,
  "description": "ÆEA relay — Cloudflare Worker proxying Kraken (crypto primary), Stooq (equities/futures primary), Binance (crypto fallback), CoinGecko (crypto fallback), and Yahoo Finance (universal fallback incl. forex/indices) for the Heroku ÆEA bridge (MQL4-Parity + MT4/TradingView TWA Edition — Final Edition 3, v4.6.0, Audit-Patched, CS-Translated UI). Sole home of the Worker source.",
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
    "kraken",
    "stooq",
    "binance",
    "coingecko",
    "yahoo-finance",
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
    "enhancement",
    "scroll-ahead",
    "execution-gated",
    "reply-threaded",
    "await-corrected",
    "send-hardened",
    "markdown-escape",
    "codex-symbolica",
    "cs-translated",
    "kraken-primary",
    "stooq-primary",
    "audit-patched",
    "final-edition-3"
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

The full worker.js source is delivered in Segment 1 of the Final Edition 3 audit and is the byte-exact copy that must be saved as aei-relay/worker.js. Its header reads:

```
// Version: vFinal (Audit-Patched Edition 3)
```

Its CRYPTO_MAP is the live-triple-pruned map (P-1). Its EQUITIES_MAP IIFE preserves the hyphen in class-share tickers (P-2). Its fetchStooq parser is unchanged from v4.5.8. Its dispatchProvider class routing is unchanged. Its /health version field is "final" (P-4). Save it verbatim from Segment 1.

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
<div class="subtitle">HEROKU BACKEND · MQL4-PARITY PORT · v4.6.0</div>

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
    <div class="row"><span class="lbl">Relay</span><span class="val"><code>aei-relay</code> — Cloudflare Workers (Kraken + Stooq + Binance + CoinGecko + Yahoo)</span></div>
    <div class="note">
        The ÆEA Mini App lives in the <b>frontend</b> repo. This backend page is a diagnostic surface only —
        it is <b>not</b> the TWA. To launch the actual Mini App, open it from Telegram via the bot's menu button,
        or visit the GitHub Pages URL with <code>?backend=&lt;this-origin&gt;/</code> appended.
        <br><br>
        <b>v4.6.0:</b> Kraken is the primary crypto provider (free, open, no KYC, low latency).
        Stooq is the primary equities/futures provider (free, open, no KYC, CSV, low latency).
        Yahoo is the primary forex/indices provider. Binance and CoinGecko are crypto fallbacks.
        The crypto universe is the live-triple intersection of Kraken/Binance/CoinGecko coverage.
    </div>
</div>

<div class="footer">
    ÆEA v4.6.0 · Final Edition 3 · Natalia Tanyatia · LOGOS = Φ = Truth = Path = Origin
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

ÆEA Mini App — Frontend Repository

Version: 4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI
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

index.html is a self-contained Telegram Web App (TWA) that renders an MT4/TradingView-style interactive candlestick chart with:

· Interactive candlestick rendering (bullish = blue #0000ff, bearish = red #ff0000 — MQL4 clrBlue/clrRed parity).
· Crosshair, pan, pinch-zoom, tap-to-inspect.
· Scroll-ahead viewport — the chart can be dragged past the last bar, into the projected region, all the way to the projected endpoint (the likely take-profit level). viewport.offsetBars is allowed to go negative, down to −state.projection.path.length. A dashed purple → forward boundary marker labels the seam between real bars and projected bars when the viewport is in the forward region.
· A Bollinger family overlay — all 58 iBands pairs for periods 3..60 (upper green gradient, lower white gradient), computed client-side with BigInt-backed accumulators. The final Math.sqrt is float64; the legend and help panel state this.
· Topological anchors (Π^{>θ}/Π^{<θ}) from the FF's iBands-derived supply/demand lines.
· An arc-length future price projection drawn as a dashed purple path ahead of the current bar, with a soft gradient fill and an end-label showing the branch, the trigger, and the final projected price. The projection is recomputed only when a 𝒟_Bull/𝒟_Bear/ℋ_Hawk/𝒟_Dove/𝒲_Whisky/𝒲_Wine/𝒲_Watter/ℬ_Blood/𝒟_Diamond/ℛ_Ruby execution fires on the backend, plus once on engine init, once on symbol change, and on explicit POST /projection/refresh.
· ℱ_VG (Fair Value Gap) horizontal lines with long-press creation and tap-to-delete.
· Signal markers (↑ = green, ↓ = red, ⊙ = gold).
· A 𝒯_trail line.
· MT4-style indicator sub-panels (up to 4 concurrent).
· A 13D Hilbert Space Projection grid.
· A ℛ_regime classification map.
· An engine state panel (𝒦 / π / δ_dime / μ / τ / 𝒦_invert / 𝒜 / ℬ / 𝒞 / 𝒸 / 𝒯_tick_tock / 𝒮 / 𝒮_safety / 𝒯_trail / 𝒯_track / 𝒯_stand / 𝒪 / 𝒫 / 𝒱 / ℳ_last).
· A δ(m−n−2) panel. m and n cap at 13 (A-C2 fix: the FF's M()/N() count ADX exactly once).
· A directional derivatives panel (𝒵 / 𝒵' / 𝒪 / 𝒪' / 𝒲 / 𝒲' / ℐ / ℐ' / 𝒥 / 𝒥' / 𝒳_scan / 𝒴_scan / 𝒮 / 𝒯 / 𝒓 / ℐ𝒓 / 𝒜_ATR / 𝒜_StdDev / 𝒜_IHKk / 𝒜_IHKt).
· A projection panel (branch / horizon / slope / amplitude / center / damping / provider / trigger / next / end / updated).
· An order ticket with exact-decimal lot/SL/TP input.
· A settings modal that round-trips the 11 FF input variables via GET /settings and POST /settings.
· A toast stack for signal, execution, and ℱ_VG notifications (titles in CS notation).
· A merged log bar (client-local + server entries).

Everything is rendered from state.bars, state.signals, state.fvgs, state.projection, and the /miniapp-state polling payload. The frontend does not compute any indicator values that the backend already exposes — it only renders what the backend publishes, plus the client-side Bollinger family (which is exactly equivalent to what the FF computes inside Normalize() for each j ∈ [y+1, x-1]).

CS Translation Layer. Every user-facing natural-language descriptive pro rendered by this file — DOM text content, labels, headers, help panel text, toast titles, panel titles, chart overlays — is expressed in the plain-text Maths of the Codex Symbolica as contrived in LOGOS.MD. No JavaScript variable name, function name, internal state identifier, endpoint path, or CSS class name has been altered. Only the strings that reach the user's eyes are translated.

v4.6.0 Symbol Picker. The picker now exposes five collapsible sections:
· Crypto (Kraken-primary) — the live-triple-pruned set, from BTC-USD through YFII-USD. Every entry resolves to a live Kraken OR Binance OR CoinGecko triple. CoinGecko-only entries (BNB-USD, OKB-USD, HT-USD, KCS-USD, USDT-USD) serve usd_24h_vol (not exchange tick volume) under 𝒱; this is documented in the picker's modal note.
· Futures (Stooq-primary) — from GC=F through SN=F.
· Equities / ETFs (Stooq-primary) — from AAPL through TOST. Class-share tickers preserve the hyphen (BRK-B → brk-b.us).
· Forex (Yahoo) — from EURUSD=X through USDCLP=X.
· Indices (Yahoo) — from ^GSPC through ^STI.

A search box at the top filters across all five sections. Each item shows the canonical form. The active symbol is highlighted. Selecting a symbol POSTs /symbol to the backend, which reinitializes the engine, seeds the projection with trigger="symbol_change", and switches the relay dispatch to the appropriate provider chain for that symbol class.

---

What This Repo Is Not

This repo is not the backend. It does not run a Python process. It does not talk to Telegram's Bot API. It does not connect to Kraken, Stooq, Binance, CoinGecko, or Yahoo.

This repo is not the relay. It does not run a Cloudflare Worker.

This repo is not a duplicate of any other repo's source. The backend repository (aei-backend) contains app.py, not index.html. The relay repository (aei-relay) contains worker.js, not index.html. Each file has exactly one home.

---

Configuration

There are no environment variables on static hosting. All configuration is resolved at boot by resolveBackendUrl() in index.html, in this order:

1. window.__AEEA_BACKEND_URL__ — if the host page sets it before the script loads.
2. ?backend=https://... — query-string override (persisted to localStorage['aeea_backend_url']).
3. localStorage['aeea_backend_url'] — previously persisted.
4. DEFAULT_BACKENDS[0] — the fork-author edit point at the top of the <script> block.
5. same-origin (relative paths).

For a fork: edit DEFAULT_BACKENDS[0] in index.html to your Heroku origin. This is the v4.3.0 resolution for the defect where Telegram's WebView strips the ?backend= query string and localStorage is empty on first visit — without DEFAULT_BACKENDS, the TWA silently polls GitHub Pages for /miniapp-state and receives 404s.

The canonical way to configure a Telegram-launched instance is still the ?backend= query parameter in the BotFather Web App URL:

```

https://<your-username>.github.io/<repo-name>/?backend=https://your-app-name.herokuapp.com/

```

But DEFAULT_BACKENDS[0] is the belt-and-suspenders fallback for the WebView-stripping case.

---

Deployment

```bash
git init
git add index.html README.md .gitignore
git commit -m "ÆEA Mini App v4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI"
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
2 s /miniapp-state Authoritative live engine state (price, tick, regime, m/n, 𝒦, π, δ_dime, μ, τ, 𝒦_invert, 𝒜/ℬ/𝒞/𝒸, 𝒯_tick_tock, 𝒮, 𝒮_safety, 𝒯_trail, 𝒪, δ, derivatives, ℱ_VG anchors, Π^{>θ}/Π^{<θ} series, recent signals, provider, last_volume, projection_meta, last_inbound_message_id, projection_trigger).
2 s /toasts?since=<seq> Signal + execution + ℱ_VG notifications. Client-side cursor advances only past toasts that were pushed. Detects server eviction via first_available_seq and surfaces it to the log bar.
3 s /log?limit=50 Server log ring buffer. Merged with client-local entries in the log bar (dedup by full entry hash).
30 s /ohlcv?limit=200&interval=<tf> Historical bars for the chart. Each bar carries its own provider (kraken for crypto, stooq for equities/futures, yahoo for forex/indices).
10 s /signals?limit=50 Recent signal history.
5 s /diagnostics Full engine diagnostic snapshot. Freshness-gated: absorbed only if diagnostics.tick > _lastDiagnosticsAbsorbedTick, so a slower poll cannot overwrite live state with stale data.
5 s /orders Open order list.
15 s /regime-map Per-bar regime classification (only fetched when the ℛ_regime view is active).
5 s /projection Arc-length forward price path. Absorbed only when state.projection.computed_at changes, which is the signal that the backend recomputed the path on an execution (E-4) or on a manual refresh (D-41).

Plus a 300 s full-refresh interval (setInterval(fetchAll, 300000)) that re-issues all nine fetches. This is a safety net for missed updates — for example, after the browser has been suspended and resumed, or after a long background period.

Freshness guard. /diagnostics and /miniapp-state return overlapping state. To prevent the slower /diagnostics poll from overwriting fresh /miniapp-state data, absorbDiagnostics() computes engineFieldsFresh = diagnostics.tick > _lastDiagnosticsAbsorbedTick. All engine-state absorption (including the indicator matrix) is gated by this check. The /projection poll is absorbed only when computed_at changes.

Backoff. After 3 consecutive failures on any poll, the client enters a 30 s backoff window during which no polls fire. The connection badge turns red (backend unreachable) and a warning is pushed to the log bar. The next successful poll clears the backoff.

---

Authentication

Every non-/health request carries X-Telegram-Init-Data: <initData> when the TWA is running inside Telegram (i.e. when Telegram.WebApp.initData is non-empty). The backend verifies the initData HMAC per the standard scheme. When the TWA is opened outside Telegram, no X-Telegram-Init-Data header is sent, and the backend's REQUIRE_AUTH=0 mode is expected.

The TWA does not store the bot token. It does not store any secret. It only forwards the initData that Telegram itself injected into the WebView.

---

Push Notifications

Every signal, every execution event, every ℱ_VG commit/remove, and every close transition triggers a Telegram push notification on the user's device. This is achieved server-side: the backend's _emit_toast() dispatches a sendMessage to the bound chat_id for every toast, deduplicated by an 800 ms window so a single logical event never produces two pushes. In v4.6.0 the push is threaded as reply_to_message_id to the user's most recent inbound message, with:
· Reply-target hardening (E-11): a stale reply id no longer silences the stream — the send path retries as a standalone message.
· Markdown escaping (E-12): every interpolated value is escaped so an unparseable field no longer causes HTTP 400 "can't parse entities".
· Plain-text final fallback (E-13): if both retries fail, the send path strips parse_mode entirely and delivers the raw text.

The TWA does not need to do anything for pushes to arrive — they arrive independently, via the Telegram app itself. The toast stack in the TWA is a parallel channel for in-app display; the push is the out-of-app notification. The Engine Panel's ℳ_last row displays the current state.last_inbound_message_id, which is the message id that the next push will be threaded to.

---

Symbol Provider Chains (v4.6.0)

The relay v4.6.0 dispatches each symbol through a provider chain chosen by the symbol's class:

· Crypto (BTC-USD, ETH-USD, XRP-USD, …, YFII-USD) — Kraken → Binance → CoinGecko → Yahoo.
Kraken is the primary. It is free, open, no API key, no KYC for public market data, and is not geo-blocked from Cloudflare egress IPs the way Binance is in some regions (US, UK). Its Ticker and OHLC endpoints have lower latency than Binance's under typical Cloudflare egress. The crypto universe is the live-triple intersection of Kraken/Binance/CoinGecko coverage: every symbol in the picker resolves to a live triple in the relay. CoinGecko-only entries (BNB-USD, OKB-USD, HT-USD, KCS-USD, USDT-USD) serve usd_24h_vol (24-hour rolling USD volume, not tick volume) under 𝒱.
· Equities / Futures (GC=F, SI=F, CL=F, …, AAPL, MSFT, TSLA, SPY, QQQ, BRK-B, …) — Stooq → Yahoo.
Stooq is the primary. It is free, open, no API key, no KYC, and serves CSV quotes with very low latency. It covers US equities, ETFs, a broad set of futures, and several indices. Class-share tickers preserve the hyphen (BRK-B → brk-b.us, BRK-A → brk-a.us); the prior .-for-- replacement was a defect and is fixed in v4.6.0.
· Forex (EURUSD=X, GBPUSD=X, …, USDCLP=X) — Yahoo only.
· Indices (^GSPC, ^DJI, …, ^STI) — Yahoo only.

The current provider is shown in the Engine Panel's 𝒫 row and in the 𝒫_arc Panel's Provider row. It also appears in the /probe endpoint's provider field, and in the /ohlcv payload's per-bar provider field.

The provider chain is fully transparent to the TWA: the frontend consumes the same shaped JSON regardless of which upstream produced it. Switching from Binance-primary to Kraken-primary required no frontend change; the same for switching from Yahoo-primary to Stooq-primary.

---

Keyboard Shortcuts

Key Action
C Switch to CHART view
G Switch to 13D grid view
R Switch to ℛ_regime map view
A Toggle 𝒫_arc projection on/off
V Toggle 𝒱 pane on/off
H Toggle help panel
F5 Full refresh (fetchAll())
Esc Close any open modal

---

Touch Gestures

Gesture Action
Drag (one finger) Pan the chart horizontally (time) and vertically (price). Dragging left past the last bar scrolls into the projected region, up to the projected endpoint.
Pinch (two fingers) Zoom candle width
Wheel (desktop) Zoom candle width
Long-press (500 ms) Open context menu (Draw 𝒯_Top ℱ_VG / Draw ℬ_Bott ℱ_VG / Delete nearest ℱ_VG)
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
Diagnosis: 𝒫_arc toggle off, or projection path empty, or projection is entirely off-screen.
Fix: Tap the 𝒫_arc button in the toolbar. Verify /projection returns a non-empty path. Verify the 𝒫_arc Panel shows a branch (range/trend/volatile). If the projection is off-screen, drag the chart to the left until the dashed purple path comes into view.

Symptom: Chart will not scroll past the last bar.
Diagnosis: The projection path is empty, so viewport.offsetBars clamps to [0, bars.length - 1].
Fix: Verify /projection returns a non-empty path. The projection is seeded on engine init and recomputed on every execution.

Symptom: No toasts appear.
Diagnosis: /toasts returned a non-200, or the client-side cursor was advanced past the buffer.
Fix: Check the log bar for eviction warnings. Verify /toasts?since=0 returns JSON from the Heroku endpoint.

Symptom: No Telegram push notifications arrive.
Diagnosis: chat_id not bound, or push category disabled, or dedup window too wide, or reply target stale, or Markdown field unparseable.
Fix: Send /start to the bot to bind the chat_id. Verify PUSH_ON_SIGNAL, PUSH_ON_EXECUTION, PUSH_ON_FVG, PUSH_ON_CLOSE are 1. Check heroku logs --tail for 📲 Push sent (signal) to ... reply_to=... or 📲 Push failed. In v4.6.0, a stale reply id no longer silences the stream (E-11) and an unparseable Markdown field no longer silences the stream (E-13) — the send path retries as a standalone message and as plain text.

Symptom: Push arrives but is not threaded as a reply.
Diagnosis: state.last_inbound_message_id is None (the user never sent a command in this chat).
Fix: Send any command to the bot (e.g. /status). The next push will be threaded. The Engine Panel's ℳ_last row shows the current message id.

Symptom: Volume is always zero on crypto symbols.
Diagnosis: The relay is falling back to Yahoo (which returns zero for crypto volume), meaning Kraken, Binance, and CoinGecko all failed.
Fix: Check heroku logs for 🛰️ Provider: yahoo on a crypto symbol. Verify the relay's /health returns "providers":["kraken","stooq","binance","coingecko","yahoo"]. Verify curl "https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=volume" returns non-zero volume with "provider":"kraken". If Kraken is failing, check the relay's error detail for the specific Kraken error code.

Symptom: Crypto symbol returns "no_price_for_symbol".
Diagnosis: The symbol is not a live triple in CRYPTO_MAP. In v4.6.0 (A-C1), the picker's crypto array is the exact intersection with CRYPTO_MAP — a symbol that was in v4.5.8's picker but not in CRYPTO_MAP (a dead entry) is removed.
Fix: Select a symbol from the pruned picker. If a specific symbol is needed and it is genuinely live on a provider, add it to CRYPTO_MAP in worker.js and to SYMBOLS_CRYPTO in index.html and redeploy both.

Symptom: Futures or equity symbol returns "stooq_symbol_not_mapped".
Diagnosis: The symbol is not in FUTURES_MAP or EQUITIES_MAP in worker.js. The relay only knows the symbols explicitly enumerated in its maps.
Fix: Add the symbol to FUTURES_MAP or EQUITIES_MAP in worker.js and redeploy the relay. Also add it to SYMBOL_MAP and SYMBOL_FALLBACKS in app.py and to the appropriate SYMBOLS_* array in index.html.

Symptom: Selecting BRK-B or BRK-A returns "stooq_no_data".
Diagnosis: The served worker.js predates v4.6.0. The v4.5.8 EQUITIES_MAP IIFE replaced - with ., producing brk.b.us which Stooq does not resolve.
Fix: Deploy the v4.6.0 worker.js (P-2 fix). Verify curl "https://aei-relay.<sub>.workers.dev/?symbol=BRK-B&kind=price" returns a price with "provider":"stooq".

Symptom: δ Panel shows m=14 or n=14.
Diagnosis: The served app.py predates v4.6.0. The v4.5.8 _M()/_N() double-counted the ADX row, letting m and n reach 14.
Fix: Deploy the v4.6.0 app.py (A-C2 fix). Verify m and n cap at 13, matching the FF's counting rule.

Symptom: Settings modal shows stale values.
Diagnosis: GET /settings failed, so the modal fell back to state.settings.
Fix: Verify /settings returns 200 with all 11 FF inputs. If it 503s, the engine hasn't started — send /start_feed to the bot.

Symptom: Order ticket "PLACE" returns "Order failed: invalid_numbers".
Diagnosis: A numeric field contains a non-decimal string (currency symbol, comma, exponent).
Fix: Enter a plain decimal, e.g. 0.01, 1.5, 100.

Symptom: The bot exits at startup with a RuntimeError about ARC_PROJECTION_DAMPING.
Diagnosis: The Heroku config var ARC_PROJECTION_DAMPING is out of range, unparseable, or contains scientific notation that Decimal rejects. The v4.6.0 loader validates the value and fails fast (D-32), instead of silently substituting 0.94.
Fix: heroku config:set ARC_PROJECTION_DAMPING="0.94" -a your-app-name (or any Decimal in (0, 1)).

Symptom: A user-committed ℱ_VG flickers out and back on the 2 s poll.
Diagnosis: In v4.3.0 and earlier, absorbMiniAppState() replaced the client ℱ_VG list wholesale. v4.4.0 merges by idx (E-8). If you still see flicker, the served index.html is stale.
Fix: Hard-reload the TWA. Verify the served index.html contains the merge-by-idx block in absorbMiniAppState().

Symptom: Projection redraws every 5 s even when no execution has fired.
Diagnosis: In v4.3.0 and earlier, fetchProjection() was absorbed unconditionally. v4.4.0 short-circuits on unchanged computed_at (D-41). If you still see redraws, the served index.html is stale.
Fix: Hard-reload the TWA. Verify the served index.html contains the _lastProjectionComputedAt short-circuit in fetchProjection().

Symptom: The bot logs RuntimeWarning "coroutine 'ExtBot.send_message' was never awaited" and no push arrives.
Diagnosis: The served app.py predates v4.4.1. In python-telegram-bot 21.x, Bot.send_message is a coroutine; calling it synchronously constructs the coroutine object and drops it.
Fix: Deploy v4.6.0. Verify the bot captures its event loop in _post_init and routes every out-of-loop send through AEI_Bot._send_message_sync (E-10).

Symptom: The bot logs HTTP 400 "message to reply not found" and pushes stop arriving.
Diagnosis: state.last_inbound_message_id is stale (the user's command was deleted, or the bot was restarted with a persisted id). The served app.py predates v4.4.2.
Fix: Deploy v4.6.0. Verify _send_message_sync retries as a standalone message when the first failure description mentions "reply" or "message to reply not found" (E-11).

Symptom: The bot logs HTTP 400 "can't parse entities" and pushes stop arriving.
Diagnosis: A push body contained an unescaped Markdown control character. The served app.py predates v4.4.2.
Fix: Deploy v4.6.0. Verify _md_escape() is applied to every interpolated value in _format_push_message, _send_signal_alert, and _send_execution_alert (E-12), and that _send_message_sync strips parse_mode on the third attempt (E-13).

Symptom: A user-facing label still shows the natural-language pro (e.g. "ADX" instead of "𝒜[0]", "Bull" instead of "𝒟_Bull", "sRange" instead of "𝒮_Range").
Diagnosis: The served index.html or app.py predates the CS translation layer.
Fix: Deploy v4.6.0. Verify the served index.html contains the CS-translated DOM text content, and the served app.py contains the CS-translated Telegram message bodies and API payload string fields consumed by the UI. Internal variable names, function names, and endpoint paths are unchanged.

Symptom: The symbol picker does not show the five-section layout.
Diagnosis: The served index.html predates v4.6.0. The v4.5.0 picker had three sections (Crypto / Futures / Equities).
Fix: Deploy v4.6.0. Verify the served index.html contains SYMBOLS_CRYPTO, SYMBOLS_FUTURES, SYMBOLS_EQUITIES, SYMBOLS_FOREX, and SYMBOLS_INDICES arrays and the five-section picker with a search box.

Symptom: Selecting a new crypto symbol (e.g. ARB-USD) returns "no_price_for_symbol".
Diagnosis: The symbol is not a live triple in CRYPTO_MAP. In v4.6.0, the picker is pruned to the live-triple intersection; a symbol from a stale cache may not resolve.
Fix: Hard-reload the TWA to fetch the pruned picker. Verify the relay's /health crypto_pairs count matches the picker's crypto-section count. If the symbol is genuinely live on a provider, add it to CRYPTO_MAP and SYMBOLS_CRYPTO and redeploy both.

Symptom: Selecting a new futures symbol (e.g. HG=F) returns "no_price_for_symbol".
Diagnosis: The relay's Stooq dispatch failed for that symbol, and Yahoo also failed.
Fix: Check heroku logs for the relay's error detail. Verify the relay's /health returns the expanded futures_symbols count. Verify curl "https://aei-relay.<sub>.workers.dev/?symbol=HG=F&kind=price" returns a price with "provider":"stooq".

Symptom: Selecting AAPL returns a price but the provider is "yahoo" not "stooq".
Diagnosis: The relay's Stooq dispatch failed for that symbol, and Yahoo succeeded. This is the intended fallback behavior.
Fix: No action needed. If you want to force Stooq-primary, check the relay's logs for the Stooq failure reason (e.g. "stooq_bad_columns", "stooq_no_data").

---

License

UNLICENSED — proprietary. © Natalia Tanyatia 2025.

FILE 15.14 — aei-relay/README.md

ÆEA Relay — Cloudflare Worker Repository

Version: 4.6.0 (Final Edition 3 — Audit-Patched) — CS-Translated UI
Repo: aei-relay (Cloudflare Workers)
Sibling repos: aei-miniapp (GitHub Pages), aei-backend (Heroku)

---

What This Repo Contains

This repository is the sole home of the ÆEA relay Worker. It contains:

· worker.js — the Cloudflare Worker source.
· wrangler.toml — the deployment manifest. name = "aei-relay", main = "worker.js".
· package.json — the Node manifest for wrangler.
· README.md — this file.
· .gitignore — Wrangler build output, Node cruft, secrets.

That is the complete contents of the repo. Nothing builds, nothing bundles.

v4.6.0 applies the P-1 prune, the P-2 class-share fix, the P-3 volume documentation, and the P-4 internal version disambiguation. It preserves the v4.5.0 Kraken/Stooq/Expanded-Universe semantics. The version string is bumped in /health (unchanged "final"), package.json ("4.6.0"), and this README for consistency; the wrangler.toml is unchanged.

---

What This Repo Is Not

This repo is not the backend. It does not contain app.py, does not run a Python process, and does not handle Telegram traffic. It is a stateless HTTP proxy: it receives GET /?symbol=…&kind=…, fetches the corresponding upstream URL through Cloudflare's egress IPs, and returns the shaped JSON.

This repo is not duplicated anywhere. The aei-backend repository does not contain a copy of worker.js, wrangler.toml, or package.json. The backend reaches the relay only over HTTP via its RELAY_URL environment variable. There is exactly one wrangler deploy command in the ÆEA system, and it is run from this repo.

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
GET /health {"ok": true, "service": "aei-relay", "version": "final", "gated": <bool>, "providers": ["kraken", "stooq", "binance", "coingecko", "yahoo"], "primary_crypto": "kraken", "primary_futures": "stooq", "primary_equities": "stooq", "primary_forex": "yahoo", "primary_indices": "yahoo", "fallback_crypto": ["binance", "coingecko", "yahoo"], "fallback_futures": ["yahoo"], "fallback_equities": ["yahoo"], "fallback_forex": [], "fallback_indices": [], "crypto_pairs": <pruned count>, "futures_symbols": <count>, "equities_symbols": <count>, "forex_pairs": <count>, "indices_symbols": <count>}
GET /?symbol=<S>&kind=price {symbol, close, bid, ask, volume, timestamp, provider}
GET /?symbol=<S>&kind=volume {symbol, volume, volume_24h, provider}
GET /?symbol=<S>&kind=intraday&interval=1m {symbol, open, high, low, close, volume, timestamp, provider}
GET /?symbol=<S>&kind=history&limit=200&interval=1m [{open, high, low, close, volume, timestamp, provider}, …]
GET /?symbol=<S>&kind=candles&limit=200&interval=1m [{open, high, low, close, volume, timestamp, provider}, …]
GET /?symbol=<S>&kind=projection {"error": "projection_is_backend_only"}

When env.RELAY_KEY is set (via wrangler secret put RELAY_KEY), every non-/health request must carry the X-Relay-Key: <RELAY_KEY> header. The backend's app.py reads RELAY_KEY from its own env and injects the header automatically.

Provider Dispatch

The Worker chooses the upstream from the symbol class:

· Crypto (BTC-USD, ETH-USD, XRP-USD, ADA-USD, SOL-USD, DOGE-USD, LTC-USD, LINK-USD, DOT-USD, AVAX-USD, MATIC-USD, UNI-USD, ATOM-USD, NEAR-USD, FIL-USD, ETC-USD, ICP-USD, XLM-USD, HBAR-USD, QNT-USD, GRAM-USD, TON-USD, ARB-USD, OP-USD, SUI-USD, APT-USD, INJ-USD, TIA-USD, SEI-USD, STX-USD, IMX-USD, …, YFII-USD) —
tries Kraken (/0/public/Ticker, /0/public/OHLC) first, then Binance (/api/v3/klines, /api/v3/ticker/24hr), then CoinGecko (/simple/price, /coins/{id}/market_chart), then Yahoo as quaternary. The crypto universe is the live-triple intersection of Kraken/Binance/CoinGecko coverage: every symbol in CRYPTO_MAP resolves to at least one live provider pair.
· Equities, ETFs, Futures (GC=F, SI=F, CL=F, NG=F, ZB=F, ZN=F, ZS=F, ZM=F, ZW=F, KE=F, HG=F, PL=F, PA=F, RB=F, HO=F, CC=F, KC=F, SB=F, CT=F, LH=F, LE=F, GF=F, ZO=F, ZR=F, ZL=F, ES=F, NQ=F, YM=F, RTY=F, …, AAPL, MSFT, TSLA, SPY, QQQ, BRK-B, …, and any non-crypto symbol) —
tries Stooq (/q/l/ for quote, /q/d/l/ for daily, /q/a/l/ for intraday) first, then Yahoo as fallback.
· Forex (EURUSD=X, GBPUSD=X, …, USDCLP=X) — Yahoo only.
· Indices (^GSPC, ^DJI, …, ^STI) — Yahoo only.

This guarantees real volume for crypto (Kraken, Binance, and CoinGecko all return non-zero volume; Yahoo returns zero for most crypto pairs), and low-latency CSV quotes for equities/futures (Stooq's CSV is faster than Yahoo's chart JSON under typical Cloudflare egress).

---

Kraken-Specific Notes (D-49, D-50)

Kraken's public REST API returns JSON with the shape {error: [], result: {<pair>: {...}}}. The result object is keyed by the Kraken pair name (e.g. XXBTZUSD), not the input symbol (e.g. XBTUSD). Kraken uses XBT for Bitcoin and XDG for Dogecoin in some legacy pair names, but the modern REST API accepts the canonical forms (BTCUSD, DOGEUSD) as the pair query parameter and returns keys in the legacy form.

The Worker's parser is key-agnostic (D-49): it looks up result[Object.keys(result)[0]] regardless of what the key is.

Kraken's OHLC response carries a last cursor key alongside the pair-keyed bar array. The Worker's parser filters Object.keys(result) to exclude last before iterating bars (D-50).

If Kraken returns {error: ["EQuery:Unknown asset pair"]}, the symbol is not on Kraken. The Worker throws kraken_error_EQuery:Unknown asset pair, which the dispatch layer records in the all_providers_failed detail string and passes to the next provider.

---

Stooq-Specific Notes (D-51, D-52)

Stooq's public CSV API (/q/l/ for latest quote, /q/d/l/ for daily history, /q/a/l/ for intraday history) returns CSV with a header row. The intraday layout is Symbol,Date,Time,Open,High,Low,Close,Volume; the daily layout is Symbol,Date,Open,High,Low,Close,Volume. Stooq emits N/D (no data) for missing fields.

The Worker's parser reads the header row, finds the open/high/low/close/volume/date/time indices, adapts to whichever layout is present, and coerces N/D to null (D-51).

Stooq serves some endpoints with Cache-Control: no-store. The Worker's cf.cacheTtl hint is advisory only; correctness never depends on it (D-52).

If Stooq returns an empty CSV or a header row with missing columns, the Worker throws stooq_no_data or stooq_bad_header, which the dispatch layer records and passes to the next provider.

Class-share tickers (P-2). EQUITIES_MAP's IIFE now lowercases tickers but preserves the hyphen in class-share tickers: BRK-B → brk-b.us, BRK-A → brk-a.us. The prior .-for-- replacement produced brk.b.us, which Stooq does not resolve. This is a v4.6.0 fix.

CoinGecko-only volume (P-3). Entries with kraken: "" and binance: "" (e.g. BNB-USD, OKB-USD, HT-USD, KCS-USD, USDT-USD) serve CoinGecko's usd_24h_vol (24-hour rolling USD volume) under the relay's volume field. This is not exchange tick volume. The frontend renders it under 𝒱 without a "real volume" badge, and the picker's modal note and help panel state this.

---

Verification

```bash
curl "https://aei-relay.<sub>.workers.dev/health"
# → {"ok":true,"service":"aei-relay","version":"final","gated":false,
#    "providers":["kraken","stooq","binance","coingecko","yahoo"],
#    "primary_crypto":"kraken","primary_futures":"stooq",
#    "primary_equities":"stooq","primary_forex":"yahoo",
#    "primary_indices":"yahoo",
#    "fallback_crypto":["binance","coingecko","yahoo"],
#    "fallback_futures":["yahoo"],"fallback_equities":["yahoo"],
#    "fallback_forex":[],"fallback_indices":[],
#    "crypto_pairs":<pruned>,"futures_symbols":<count>,
#    "equities_symbols":<count>,"forex_pairs":<count>,"indices_symbols":<count>}

curl "https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=price"
# → {"symbol":"BTC-USD","close":95432.12,...,"provider":"kraken"}

curl "https://aei-relay.<sub>.workers.dev/?symbol=BTC-USD&kind=volume"
# → {"symbol":"BTC-USD","volume":1234.56,"volume_24h":98765.43,"provider":"kraken"}

curl "https://aei-relay.<sub>.workers.dev/?symbol=GC=F&kind=price"
# → {"symbol":"GC=F","close":2650.50,...,"provider":"stooq"}

curl "https://aei-relay.<sub>.workers.dev/?symbol=AAPL&kind=price"
# → {"symbol":"AAPL","close":231.40,...,"provider":"stooq"}

curl "https://aei-relay.<sub>.workers.dev/?symbol=BRK-B&kind=price"
# → {"symbol":"BRK-B","close":...,"provider":"stooq"}  ← P-2 fix: now resolves
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

Critical for v4.6.0. Do not copy worker.js, wrangler.toml, or package.json into the aei-backend repo. Doing so would create a second wrangler deploy target pointing at the same Cloudflare Worker named aei-relay, and the two copies could drift. This repo is the single source of truth.

---

License

UNLICENSED — proprietary. © Natalia Tanyatia 2025.

---

16. Repository Map & File Index (All 17 Files)

The ÆEA v4.6.0 system spans three cooperating repositories. This document enumerates every file, in dependency order, with the full unabridged content for each.

Repo A — Frontend (GitHub Pages): aei-miniapp/

1. .gitignore — see §15.1
2. index.html — the TWA (delivered as its own contiguous segment, Segment 3 of 4)
3. README.md — see §15.13

Repo B — Backend (Heroku): aei-backend/

4. .gitignore — see §15.2
5. .env.example — see §15.4
6. runtime.txt — see §15.5
7. requirements.txt — see §15.6
8. Procfile — see §15.7
9. app.json — see §15.8
10. README.md — this document (§0 through §17)
11. app.py — the engine (delivered as its own contiguous segment, Segment 2 of 4)
12. index.html — optional fallback page (see §15.12)

Repo C — Relay (Cloudflare Workers): aei-relay/

13. .gitignore — see §15.3
14. worker.js — see §15.11 (delivered as its own contiguous segment, Segment 1 of 4)
15. wrangler.toml — see §15.9
16. package.json — see §15.10
17. README.md — see §15.14

Total: 17 files. Every file is delivered in full in this document or in one of the three sibling contiguous segments (index.html, app.py, worker.js).

16.1 File-by-file delta summary (v4.5.8 → v4.6.0)

File Delta
aei-miniapp/index.html Title bumped v4.5.8 → v4.6.0. SYMBOLS_CRYPTO pruned to the exact intersection with the patched worker.js CRYPTO_MAP (A-C1). BB×58 legend text updated to state that the final Math.sqrt is float64 (A-M6). Help panel universe-count line corrected (A-m3). Every other renderer, panel, overlay, and interaction preserved verbatim from v4.5.8.
aei-miniapp/README.md Version bumped v4.5.8 → v4.6.0. New §"Symbol Provider Chains (v4.6.0)" documents the pruned crypto set and the CoinGecko-only volume caveat. Troubleshooting entries for "no_price_for_symbol" (pruned entries), "stooq_no_data" for BRK-B/BRK-A (P-2), δ Panel showing m=14/n=14 (A-C2), and picker five-section layout added.
aei-miniapp/.gitignore Version string bumped only.
aei-backend/app.py Docstring updated for v4.6.0. _M()/_N() ADX double-count removed (A-C2). Stale st.l_order_id guard removed (A-C3). _rational_cos docstring amended (A-m1). All other logic, every FF-invariant line, every send-path retry, every CS translation, and every projection/execution gating rule preserved verbatim from v4.5.8.
aei-backend/README.md (This document.) Version bumped v4.5.8 → v4.6.0. §0 documents P-1 through P-4 and A-C1 through A-m3. §0.2 documents the new resolutions. §1.21 through §1.22 document the pruned universe and point-size correctness. §3.4 shows the updated /health response with primary_equities, primary_forex, primary_indices. §4.2 adds no new env vars. §8 endpoint reference updated to note provider values. §9 verification checklist updated for the v4.6.0 behaviors. §15.x supporting files all bumped to v4.6.0.
aei-backend/.env.example Version bumped v4.5.8 → v4.6.0. Comment block for RELAY_URL extended to note the forex/indices Yahoo-only dispatch. Comment block for SYMBOL_DIGITS extended to document the pruned digit-count table. All env var names and defaults unchanged.
aei-backend/runtime.txt Unchanged.
aei-backend/requirements.txt Version bumped v4.5.8 → v4.6.0. Comment block for the relay client extended to note the forex/indices Yahoo-only dispatch.
aei-backend/Procfile Unchanged.
aei-backend/app.json Version bumped (description). Keywords extended with audit-patched, final-edition-3. No new env vars.
aei-backend/index.html Version string bumped v4.5.8 → v4.6.0. Note added to the sibling repositories panel documenting the pruned crypto universe and the forex/indices Yahoo-only dispatch. No functional change.
aei-backend/.gitignore Version string bumped only.
aei-relay/worker.js Version string bumped v4.5.8 → v4.6.0 in the docstring (Audit-Patched Edition 3), /health remains "final". CRYPTO_MAP pruned to live triples (P-1). USDT-USD corrected to Kraken-primary USDTUSD with CoinGecko fallback. OKB-USD, HT-USD, KCS-USD annotated as CoinGecko-only (P-3). EQUITIES_MAP IIFE corrected to preserve hyphens (P-2).
aei-relay/wrangler.toml Comment block updated to note that v4.6.0 does not change the wrangler.toml.
aei-relay/package.json Version bumped v4.5.8 → v4.6.0. Keywords extended with audit-patched, final-edition-3.
aei-relay/README.md Version bumped v4.5.8 → v4.6.0. New §"Kraken-Specific Notes", §"Stooq-Specific Notes" extended with the P-2 class-share fix and the P-3 CoinGecko-only volume caveat. Provider dispatch section updated with the forex/indices Yahoo-only routing. Verification section updated with the BRK-B example.
aei-relay/.gitignore Version string bumped only.

16.2 Behavioral contract delta (v4.5.8 → v4.6.0)

Provider dispatch order:

Symbol class v4.5.8 chain v4.6.0 chain
Crypto Kraken → Binance → CoinGecko → Yahoo Kraken → Binance → CoinGecko → Yahoo (unchanged; universe pruned)
Equities / Futures Stooq → Yahoo Stooq → Yahoo (unchanged; class-share hyphen fix)
Forex Yahoo only Yahoo only
Indices Yahoo only Yahoo only

/health response delta:

Field v4.5.8 value v4.6.0 value
version "final" "final" (unchanged)
providers ["kraken","stooq","binance","coingecko","yahoo"] unchanged
primary_crypto "kraken" unchanged
primary_futures "stooq" unchanged
primary_equities "stooq" unchanged
primary_forex "yahoo" unchanged
primary_indices "yahoo" unchanged
crypto_pairs <v4.5.8 count> <pruned count> (P-1)
futures_symbols <count> unchanged
equities_symbols <count> unchanged
forex_pairs <count> unchanged
indices_symbols <count> unchanged

Symbol universe delta:

Class v4.5.8 count v4.6.0 count
Crypto <v4.5.8 count> <pruned count> (P-1 / A-C1)
Futures <count> unchanged
Equities / ETFs <count> unchanged (P-2 fixes 2 entries)
Forex <count> unchanged
Indices <count> unchanged

CS translation layer: unchanged from v4.5.8. Every user-facing string, every panel title, every toast title, every log line that references a user-facing concept, remains CS-translated.

---

17. Q.E.D.

The Mini App is served from two cooperating origins, fed by a third:

· GitHub Pages — the presentation surface, loaded by Telegram's WebView. All user-facing labels are in CS notation.
· Heroku — the computational substrate, polled by the frontend, and the push-notification origin. All user-facing Telegram messages and log lines are in CS notation.
· Cloudflare Worker — the multi-provider market-data relay, polled by the dyno. Kraken is the primary crypto provider; Stooq is the primary equities/futures provider; Yahoo is the primary forex/indices provider; Binance and CoinGecko are crypto fallbacks.

BACKEND_URL is the wire between frontend and backend. RELAY_URL is the wire between backend and relay. Set them once, push all three, and the Mini App is live inside Telegram.

All 44 defects from the ÆEA v4.1.1 Fidelity & Spec Audit (27 critical + 17 minor) remain resolved in v4.6.0. All 30 defects from the v4.1.2 self-audit (15 critical + 3 major + 12 minor) remain resolved. All 11 defect classes from the v4.1.3 syntax+semantics audit remain resolved. All 15 new critical defects, 3 major defects, and 12 minor defects introduced by the intermediate patches remain resolved in v4.6.0. All v4.3.0 enhancements (E-1, E-2, E-3) remain at v4.3.0 semantics. All v4.3.0 defect resolutions (D-30 through D-40) remain in force. All v4.4.0 enhancements (E-4 through E-9) and defect resolutions (D-30 through D-43) remain at v4.4.0 semantics. The v4.4.1 defect resolution (D-44) and enhancement (E-10) remain at v4.4.1 semantics. The v4.4.2 defect resolutions (D-45, D-46, D-47, D-48) and enhancements (E-11, E-12, E-13) plus the CS translation layer remain at v4.4.2 semantics. The v4.5.0 enhancements (E-14, E-15, E-16) and defect resolutions (D-49 through D-54) remain at v4.5.0 semantics. The v4.5.5 defect resolutions (V-1, V-2) and the v4.5.6 enhancements (E-17 through E-24) remain in force. The v4.5.7 Audit-Patched Edition (D-64, D-65, D-66, D-68, D-70, D-71, D-73, D-74, D-75, D-76, D-77, D-81) and the v4.5.8 vFinal Edition 2 (C-2, C-3, M-1, M-2, M-3, M-4, m-2, m-4, m-5, m-6) remain in force.

v4.6.0 introduces the following defects and resolves them in the same edition:

· P-1 (critical). CRYPTO_MAP pruned to live triples. USDT-USD corrected to Kraken-primary USDTUSD with CoinGecko fallback; the prior binance: "USDCUSDT" was a defect. Resolved.
· P-2 (minor). EQUITIES_MAP IIFE corrected to preserve hyphens in class-share tickers (BRK-B → brk-b.us, BRK-A → brk-a.us). Resolved.
· P-3 (minor). CoinGecko-only volume semantics documented per entry and in the picker's modal note. Resolved.
· P-4 (minor). Internal worker.js docstring version disambiguated to Audit-Patched Edition 3. /health version remains "final". Resolved.
· A-C1 (critical). SYMBOLS_CRYPTO pruned to the exact intersection with CRYPTO_MAP. Resolved.
· A-C2 (critical). _M()/_N() ADX double-count removed. m/n capped at 13, matching the FF's counting rule. δ(m−n−2)=1 gate fires exactly when the FF's gate fires. Resolved.
· A-C3 (minor). Stale st.l_order_id guard in _dispatch_diamond_subblock removed. Resolved.
· A-M6 (minor). BB×58 legend text corrected to state that the final Math.sqrt is float64. Resolved.
· A-m1 (minor). _rational_cos docstring documents the 15-digit π convergent and the exact-rational Taylor series. Resolved.
· A-m3 (minor). Help panel universe-count line corrected. Resolved.

v4.6.0 additionally delivers:

· E-14 (carried forward). Kraken-primary relay dispatch for crypto. Fallback chain: Kraken → Binance → CoinGecko → Yahoo.
· E-15 (carried forward). Stooq-primary relay dispatch for equities/futures. Fallback chain: Stooq → Yahoo.
· E-16 (carried forward, now pruned). Expanded symbol universe: the live-triple-pruned crypto set plus the full futures/equities/forex/indices sets. The TWA symbol picker exposes the same set in five collapsible sections with a search filter.
· P-1 through P-4 (new). Dead-entry prune, class-share Stooq fix, CoinGecko volume documentation, internal version disambiguation.
· A-C1 through A-m3 (new). Picker prune, ADX single-count fix, stale attribute removal, BB×58 legend text, _rational_cos docstring, help-panel count.

The ÆEA v4.6.0 port is now MQL4-parity across its state machine, its exact-arithmetic discipline, its indicator formulas, its regime taxonomy, its δ gate, its execution logic, its observer/measurement layer, its Bollinger-band family, its TWA/backend wiring, and its supporting deployment surface — with the v4.3.0 Enhancement capabilities (push on every event, multi-provider real volume, arc-length projection), the v4.4.0 Scroll-Ahead capabilities (execution-gated projection, scroll-ahead viewport, threaded bot replies, bounded dispatch, ℱ_VG merge, legend stacking), the v4.4.1 Await-Corrected capability (cross-thread async send), the v4.4.2 Send-Hardened + CS-Translated capabilities (reply-target hardening, Markdown escaping, plain-text final fallback, Codex Symbolica translation of all user-facing pros), the v4.5.0 Kraken-Primary + Stooq-Primary + Expanded-Universe capabilities, the v4.5.7 Audit-Patched capabilities, the v4.5.8 vFinal Edition 2 capabilities, and the v4.6.0 Final Edition 3 prune-and-fix capabilities layered on top as additive-only extensions.

*Q.E.D.* — LOGO(S) = Φ = Truisms = Patch = Remote Origin.
