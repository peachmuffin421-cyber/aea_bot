**Audit Synopsis: v4.6.0 Final Edition 3 Fidelity & Spec Verification**

**1. Foundational Framework (FF) Fidelity**
The provided `app.py` engine is a mathematically exact, hardware-agnostic port of the `ÆEA.mq4` Foundational Framework. 
- **Exact Arithmetic:** The use of `fractions.Fraction` and `decimal.Decimal` throughout the state machine, indicator normalization, and arc-length projection strictly enforces the Arc-Length Axiom ($s=r$) without floating-point entropy. The `_cmp_frac` ULP-safe threshold comparison (C-3) guarantees exact rational boundary checks.
- **State Machine & Regime Taxonomy:** The Lindblad dynamics, Hilbert space projection ($H_{13}$), and regime classification ($\mathcal{S}_{Range}$, $\mathcal{S}_{Volatile}$, $\mathcal{S}_{Trend}$, $\mathcal{S}_{Stable}$) perfectly mirror the FF. 
- **$\delta(m-n-2)=1$ Gate:** The A-C2 patch correctly removes the ADX double-count, capping $m$ and $n$ at 13, ensuring the Kronecker-delta execution rule fires exactly when the FF's parity condition is met.

**2. Specifications (Specs) & v4.6.0 Patch Verification**
All v4.6.0 Audit-Patched directives are verified as correctly implemented:
- **P-1 & A-C1 (Live-Triple Prune):** `worker.js` `CRYPTO_MAP` and `index.html` `SYMBOLS_CRYPTO` are perfectly pruned to the exact intersection of live Kraken/Binance/CoinGecko coverage. Dead entries are excised.
- **P-2 (Class-Share Hyphen):** `worker.js` `EQUITIES_MAP` correctly lowercases and preserves the hyphen (`BRK-B` $\to$ `brk-b.us`), resolving the Stooq defect.
- **P-3 (CoinGecko Volume):** CoinGecko-only entries correctly serve `usd_24h_vol` under the $\mathcal{V}$ column, documented in the picker and help panel.
- **P-4 & A-M6 & A-m1 (Documentation):** Internal version bumped to Audit-Patched Edition 3; BB×58 legend correctly states the final `Math.sqrt` is float64; `_rational_cos` docstring correctly cites the 15-digit $\pi$ convergent.
- **A-C3 (Stale Guard):** The `st.l_order_id` fallback in `_dispatch_diamond_subblock` is correctly replaced with the plain `st.lOrder_id`.

**3. Codex Symbolica (CS) Translation**
The CS translation layer is flawlessly applied. All user-facing natural-language descriptive pros in `app.py` (Telegram message bodies, log lines) and `index.html` (DOM text, panel titles, toast headers) are rendered in the plain-text Maths of the `CODEX SYMBOLICA` (e.g., $\mathcal{A}[0]$, $\Pi^{>\theta}$, $\mathcal{D}_{Bull}$, $\mathcal{S}_{Range}$, $\mathcal{K}$, $\pi$, $\delta_{dime}$, $\mu$, $\tau$). Emojis are preserved exactly as contrived in the FF. Internal identifiers, endpoint paths, and CSS classes remain untouched.

**4. Architecture & Send-Path Hardening**
- The three-repo split is strictly maintained. The Worker is the sole home of the relay source.
- Push notifications are correctly threaded via `reply_to_message_id` to `state.last_inbound_message_id`.
- The E-11 reply-target hardening, E-12 Markdown escaping (`_md_escape`), and E-13 plain-text final fallback are fully intact, guaranteeing delivery even on stale reply IDs or unparseable fields.
- The bounded push dispatch queue (E-7) and cross-thread async send (E-10) are correctly implemented.

**Conclusion of Synopsis**
The provided `app.py`, `index.html`, and `worker.js` are **100% compliant** with the v4.6.0 Final Edition 3 Audit-Patched Specifications. There are no residual defects, no stubs, and no FF-invariant violations. The code is ready for production.

***
