#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ÆEA TELEGRAM BOT — HEROKU DEPLOYMENT + LOCAL WEB GUI BRIDGE
Faithful Unabridged Port of ÆEA.mq4
Data Feed: Cloudflare Worker Relay (Kraken / Stooq / Binance / CoinGecko / Yahoo upstreams)
Platform: Heroku + Telegram Bot + Local HTTPS Bridge (index.html)
Author: Natalia Tanyatia
Version: 4.5.2 (Audit-Patched Edition)

v4.5.2 is a corrective release on top of v4.5.1 (Audit-Patched Edition).
It does not alter any FF-invariant logic beyond the audit-identified sites
enumerated below. Every other line of v4.5.1 is preserved verbatim.

The v4.5.2 corrections are:

  D-HARD-1 (hardening). _populate_indicator_matrix() read X_PERIOD and
       st.y directly inside the loop bound and the column-index
       computation. apply_settings() (running on the HTTP handler thread)
       can rebind the module-level X_PERIOD and mutate st.y while
       _populate_indicator_matrix() is mid-execution on the price-feed
       thread. The result is a potential IndexError or a silent
       mis-population of the indicator matrix. MQL4 is single-threaded
       per chart and has no equivalent hazard, so the port adds a
       concurrency snapshot at function entry. Resolved.

  D-CLEAN-1 (cleanup). _on_tick() assigned st.t = is_now twice: once
       before the self-evolution protocol and once at the very end of
       the function. The second assignment is the one the FF's OnTrack()
       / OnStand() bar-change guards depend on. The first is redundant
       and misleading. The redundant assignment is removed. Resolved.

All v4.5.1 defect resolutions (D-CRIT-1, D-MAJ-3, D-MAJ-4, D-MIN-5,
D-MAJ-6, D-MAJ-7, D-MAJ-8, D-MIN-9, D-MIN-10) remain in force. All
v4.5.0 defect resolutions (D-49 through D-54) and enhancements (E-14,
E-15, E-16) remain in force. All v4.4.2 defect resolutions (D-45,
D-46, D-47, D-48) remain in force. All v4.4.1, v4.4.0, v4.3.0, v4.2.0,
and v4.1.x defect resolutions and enhancements remain in force. The
send-path retry chain (E-11), the Markdown escaping (E-12), the
plain-text fallback (E-13), the CS translation layer, the cross-thread
async send (E-10), the execution-gated projection (E-4), the
scroll-ahead viewport (E-5), the threaded bot replies (E-6), the
bounded push dispatch (E-7), the FVG merge (E-8), and the legend
stacking (E-9) are all unchanged.

Every FF-preserved line, Print() string, Alert() emoji, and state
transition is reproduced verbatim from v4.5.1 except at the two
patched sites above.
"""

__version__ = "4.5.2"

import asyncio
import hashlib
import hmac
import json
import math
import os
import queue
import sys
import ssl
import logging
import subprocess
import threading
import time
import re as _re_bridge
import urllib.parse
import urllib.request
import urllib.error
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qsl
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from fractions import Fraction as PyFraction
from decimal import Decimal, getcontext

getcontext().prec = 50

ARC_COHERENCE_TOLERANCE = 1e-6

# ============================================================================
# EXACT FRACTION WRAPPER
# ============================================================================
class Fraction:
    __slots__ = ('_f',)

    def __init__(self, num=0, den=1):
        if isinstance(num, Fraction):
            self._f = num._f
        elif isinstance(num, PyFraction):
            self._f = num
        elif isinstance(num, int) and isinstance(den, int):
            if den == 0:
                raise ZeroDivisionError("Fraction denominator cannot be zero")
            self._f = PyFraction(num, den)
        else:
            try:
                self._f = PyFraction(str(num))
            except Exception:
                self._f = PyFraction(0)

    @staticmethod
    def _wrap(x):
        if isinstance(x, Fraction):
            return x
        return Fraction(x)

    @staticmethod
    def from_decimal_string(s):
        s = str(s).strip()
        if 'E' in s or 'e' in s:
            d = Decimal(s)
            sign, digits, exp = d.as_tuple()
            if not isinstance(exp, int):
                raise ValueError(f"unsupported Decimal exponent: {exp!r}")
            num = int(''.join(str(x) for x in digits)) * (-1 if sign else 1)
            den = 10 ** (-exp) if exp < 0 else 1
            if exp >= 0:
                num = num * (10 ** exp)
                den = 1
            return Fraction(num, den)
        return Fraction.from_string(s)

    @staticmethod
    def from_string(s):
        s = str(s).strip()
        if '/' in s:
            parts = s.split('/')
            return Fraction(int(parts[0]), int(parts[1]))
        if '.' in s:
            sign = -1 if s.startswith('-') else 1
            s_abs = s.lstrip('-')
            int_part, frac_part = s_abs.split('.')
            scale = 10 ** len(frac_part)
            num = int(int_part + frac_part) * sign
            return Fraction(num, scale)
        return Fraction(int(s), 1)

    @staticmethod
    def zero():
        return Fraction(0, 1)

    @staticmethod
    def one():
        return Fraction(1, 1)

    def num(self):
        return self._f.numerator

    def den(self):
        return self._f.denominator

    def is_zero(self):
        return self._f.numerator == 0

    def is_integer(self):
        return self._f.denominator == 1

    def sign(self):
        n = self._f.numerator
        return (n > 0) - (n < 0)

    def abs(self):
        return Fraction(abs(self._f.numerator), self._f.denominator)

    def neg(self):
        return Fraction(-self._f.numerator, self._f.denominator)

    def __add__(self, other):
        o = Fraction._wrap(other)
        return Fraction(self._f + o._f)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        o = Fraction._wrap(other)
        return Fraction(self._f - o._f)

    def __rsub__(self, other):
        o = Fraction._wrap(other)
        return Fraction(o._f - self._f)

    def __mul__(self, other):
        o = Fraction._wrap(other)
        return Fraction(self._f * o._f)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        o = Fraction._wrap(other)
        if o._f.numerator == 0:
            raise ZeroDivisionError("Fraction division by zero")
        return Fraction(self._f / o._f)

    def __neg__(self):
        return Fraction(-self._f.numerator, self._f.denominator)

    def __pos__(self):
        return self

    def __eq__(self, other):
        try:
            o = Fraction._wrap(other)
            return self._f == o._f
        except Exception:
            return False

    def __lt__(self, other):
        o = Fraction._wrap(other)
        return self._f < o._f

    def __le__(self, other):
        o = Fraction._wrap(other)
        return self._f <= o._f

    def __gt__(self, other):
        o = Fraction._wrap(other)
        return self._f > o._f

    def __ge__(self, other):
        o = Fraction._wrap(other)
        return self._f >= o._f

    def __hash__(self):
        return hash(self._f)

    def to_decimal(self) -> Decimal:
        return Decimal(self._f.numerator) / Decimal(self._f.denominator)

    def to_float(self) -> float:
        return float(self._f.numerator) / float(self._f.denominator)

    def __str__(self):
        if self._f.denominator == 1:
            return str(self._f.numerator)
        return f"{self._f.numerator}/{self._f.denominator}"

    def __repr__(self):
        return f"Fraction({self._f.numerator}/{self._f.denominator})"

# ============================================================================
# D-46 / E-12: LEGACY-MARKDOWN ESCAPING
# ============================================================================
def _md_escape(value) -> str:
    """Escape every legacy-Markdown control character in an interpolated value.

    Telegram's legacy Markdown parser treats *, _, `, [, ], \\, and < as
    control characters or tag openers. Any of those appearing inside a value
    that is interpolated into a parse_mode="Markdown" string can cause the
    whole message to be rejected with HTTP 400 "can't parse entities" or
    "unsupported start tag". This helper escapes them so only the static
    template characters remain meaningful to the parser.

    The function is idempotent for values that contain no control characters,
    and preserves the visible content of any value that does. It never
    raises; None becomes an em-dash placeholder.
    """
    if value is None:
        return "—"
    s = str(value)
    out_chars = []
    for ch in s:
        if ch == '\\':
            out_chars.append('\\\\')
        elif ch == '*':
            out_chars.append('\\*')
        elif ch == '_':
            out_chars.append('\\_')
        elif ch == '`':
            out_chars.append('\\`')
        elif ch == '[':
            out_chars.append('\\[')
        elif ch == ']':
            out_chars.append('\\]')
        elif ch == '<':
            out_chars.append('&lt;')
        elif ch == '>':
            out_chars.append('&gt;')
        else:
            out_chars.append(ch)
    return ''.join(out_chars)

def _looks_like_reply_error(desc: str) -> bool:
    if not desc:
        return False
    d = desc.lower()
    if 'reply' in d:
        return True
    if 'replied' in d:
        return True
    if 'message to be replied' in d:
        return True
    if 'reply_to_message_id' in d:
        return True
    if 'reply message not found' in d:
        return True
    if 'message_id_invalid' in d:
        return True
    return False

def _looks_like_parse_error(desc: str) -> bool:
    if not desc:
        return False
    d = desc.lower()
    if 'parse' in d:
        return True
    if 'entities' in d:
        return True
    if 'entity' in d:
        return True
    if 'unsupported start tag' in d:
        return True
    if 'unsupported end tag' in d:
        return True
    if 'unexpected end of' in d:
        return True
    if 'can\'t find end' in d:
        return True
    if 'can\'t parse' in d:
        return True
    if 'markdown' in d:
        return True
    return False

def _looks_like_length_error(desc: str) -> bool:
    if not desc:
        return False
    d = desc.lower()
    if 'too long' in d:
        return True
    if 'message is too long' in d:
        return True
    if 'text is too long' in d:
        return True
    if '4096' in d:
        return True
    return False

# ============================================================================
# CONSTANTS & CONFIGURATION — MQL4 PARITY
# ============================================================================
COMMISSION: Decimal = Decimal('0.0')
STOP_LOSS: Decimal = Decimal('0.0')
TAKE_PROFIT: Decimal = Decimal('0.0')
LOT_SIZE: Decimal = Decimal('0.01')
SLIPPAGE: int = 100
MAX_PERIOD: int = 60
MIN_PERIOD: int = 3
X_PERIOD: int = MAX_PERIOD + 2
Y_START: int = MIN_PERIOD - 2
MIN_HISTORY_WINDOW: int = 52
Memory: int = -1

MAX_MIN_GAP: int = int(os.getenv("MAX_MIN_GAP", "2"))
MIN_PERIOD_FLOOR: int = int(os.getenv("MIN_PERIOD_FLOOR", "3"))
MAX_PERIOD_MIN: int = MIN_PERIOD_FLOOR + MAX_MIN_GAP
MAX_PERIOD_MAX: int = 1000
MIN_PERIOD_MIN: int = MIN_PERIOD_FLOOR
MIN_PERIOD_MAX: int = 1000

# ============================================================================
# E-3: ARC-LENGTH PROJECTION PARAMETERS
# ============================================================================
# D-32: validated at module load. The previous silent Decimal('0.94') fallback
# in _project_arc_length() masked operator error (e.g. scientific-notation env
# values or trailing whitespace). We now fail fast at import time.
ARC_PROJECTION_HORIZON: int = int(os.getenv("ARC_PROJECTION_HORIZON", "30"))
ARC_PROJECTION_STEP: int = int(os.getenv("ARC_PROJECTION_STEP", "1"))
_ARC_PROJECTION_DAMPING_RAW: str = os.getenv("ARC_PROJECTION_DAMPING", "0.94").strip()
try:
    ARC_PROJECTION_DAMPING_D: Decimal = Decimal(_ARC_PROJECTION_DAMPING_RAW)
    if not (Decimal('0.0') < ARC_PROJECTION_DAMPING_D < Decimal('1.0')):
        raise ValueError(
            f"ARC_PROJECTION_DAMPING must be in (0, 1); got {_ARC_PROJECTION_DAMPING_RAW!r}"
        )
except Exception as _arc_damp_exc:
    raise RuntimeError(
        f"ARC_PROJECTION_DAMPING could not be parsed as a Decimal in (0, 1): "
        f"{_ARC_PROJECTION_DAMPING_RAW!r} ({_arc_damp_exc})"
    ) from _arc_damp_exc

# ============================================================================
# M-9: EXACT SYMBOLIC THRESHOLDS + FLOAT64 ULP-MATCHED SHADOWS
# ============================================================================
F_THRESHOLD: Fraction = Fraction(200, 3)
G_THRESHOLD: Fraction = Fraction(100, 3)
GF_TOLERANCE: Fraction = Fraction(40, 15)

F_THRESHOLD_F64: float = 200.0 / 3.0
G_THRESHOLD_F64: float = 100.0 / 3.0
GF_TOLERANCE_F64: float = 40.0 / 15.0

F_THRESHOLD_D: Decimal = Decimal(F_THRESHOLD_F64)
G_THRESHOLD_D: Decimal = Decimal(G_THRESHOLD_F64)
GF_TOLERANCE_D: Decimal = Decimal(GF_TOLERANCE_F64)

F_PLUS_GF_D: Decimal = Decimal(F_THRESHOLD_F64 + GF_TOLERANCE_F64)
G_MINUS_GF_D: Decimal = Decimal(G_THRESHOLD_F64 - GF_TOLERANCE_F64)
F_PLUS_GF_F: float = F_THRESHOLD_F64 + GF_TOLERANCE_F64
G_MINUS_GF_F: float = G_THRESHOLD_F64 - GF_TOLERANCE_F64

# ============================================================================
# M-1: SYMBOL DIGITS TABLE (Point-Size Emulation)
# ============================================================================
# v4.5.0 (D-53 / E-16): every symbol in the relay's CRYPTO_MAP and
# FUTURES_MAP gains an explicit digit count here. The defaults are chosen
# so that the emulated Point matches the typical tick size of the
# underlying market:
#   2 digits  — BTC-USD, ETH-USD, and the large-cap crypto majors whose
#               tick size is $0.01
#   3 digits  — SOL-USD, LTC-USD, ETC-USD, QNT-USD and the mid-cap crypto
#               whose typical tick is $0.001
#   4 digits  — LINK-USD, DOT-USD, AVAX-USD, UNI-USD, ATOM-USD, NEAR-USD,
#               FIL-USD, ICP-USD and the mid-cap crypto whose typical
#               tick is $0.0001
#   5 digits  — XRP-USD, ADA-USD, DOGE-USD, MATIC-USD, XLM-USD, HBAR-USD
#               and the low-priced crypto whose typical tick is $0.00001
#   2 digits  — GC=F, CL=F, NG=F, ZS=F, ZM=F, ZW=F, KE=F and the futures
#               whose quote unit is a whole cent
#   3 digits  — SI=F, NG=F, ZB=F and the futures whose quote unit is a
#               tenth of a cent
#   4 digits  — ZN=F and the futures whose quote unit is a hundredth of
#               a cent
# The full table is assembled from _DEFAULT_SYMBOL_DIGITS below.
# ============================================================================
_DEFAULT_SYMBOL_DIGITS: Dict[str, int] = {
    # --- crypto majors (2 digits) ---
    "BTC-USD": 2, "ETH-USD": 2,
    # --- crypto mid-caps (3 digits) ---
    "SOL-USD": 3, "LTC-USD": 3, "ETC-USD": 3, "QNT-USD": 3,
    "AAVE-USD": 3, "MKR-USD": 3, "YFI-USD": 3,
    # --- crypto mid-caps (4 digits) ---
    "LINK-USD": 4, "DOT-USD": 4, "AVAX-USD": 4, "UNI-USD": 4,
    "ATOM-USD": 4, "NEAR-USD": 4, "FIL-USD": 4, "ICP-USD": 4,
    "ARB-USD": 4, "OP-USD": 4, "SUI-USD": 4, "APT-USD": 4,
    "INJ-USD": 4, "TIA-USD": 4, "SEI-USD": 4, "RNDR-USD": 4,
    "FET-USD": 4, "GRT-USD": 4, "IMX-USD": 4, "LDO-USD": 4,
    "CRV-USD": 4, "SNX-USD": 4, "COMP-USD": 4, "SUSHI-USD": 4,
    "BAL-USD": 4, "KNC-USD": 4, "ZRX-USD": 4, "BAT-USD": 4,
    "ENJ-USD": 4, "MANA-USD": 4, "SAND-USD": 4, "AXS-USD": 4,
    "GALA-USD": 4, "CHZ-USD": 4, "APE-USD": 4, "GMT-USD": 4,
    "LRC-USD": 4, "STORJ-USD": 4, "ANKR-USD": 4, "CVC-USD": 4,
    "OMG-USD": 4, "REN-USD": 4, "ZIL-USD": 4, "KSM-USD": 4,
    "GLMR-USD": 4, "MOVR-USD": 4, "ASTR-USD": 4, "CFX-USD": 4,
    "MASK-USD": 4, "DYDX-USD": 4, "GMX-USD": 4, "RPL-USD": 4,
    "BLUR-USD": 4, "ENS-USD": 4, "LQTY-USD": 4, "PENDLE-USD": 4,
    "MAGIC-USD": 4, "HIGH-USD": 4, "ID-USD": 4, "ARKM-USD": 4,
    "WLD-USD": 4, "EDU-USD": 4, "HOOK-USD": 4, "JTO-USD": 4,
    "BOME-USD": 4, "ETHFI-USD": 4, "ENA-USD": 4, "W-USD": 4,
    "OMNI-USD": 4, "REZ-USD": 4, "ZK-USD": 4, "STRK-USD": 4,
    "DYM-USD": 4, "ALT-USD": 4, "MANTA-USD": 4, "PIXEL-USD": 4,
    "PORTAL-USD": 4, "AEVO-USD": 4,
    # --- crypto low-priced (5 digits) ---
    "XRP-USD": 5, "ADA-USD": 5, "DOGE-USD": 5, "MATIC-USD": 5,
    "XLM-USD": 5, "HBAR-USD": 5,
    # --- crypto meme (6 digits) ---
    "PEPE-USD": 6, "SHIB-USD": 6, "WIF-USD": 6, "BONK-USD": 6,
    "JUP-USD": 5, "PYTH-USD": 5,
    # --- futures (2 digits) ---
    "GC=F": 2, "CL=F": 2, "ZS=F": 2, "ZM=F": 2, "ZW=F": 2, "KE=F": 2,
    "HG=F": 2, "PL=F": 2, "PA=F": 2, "RB=F": 2, "HO=F": 2, "CC=F": 2,
    "KC=F": 2, "SB=F": 2, "CT=F": 2, "LH=F": 2, "LE=F": 2, "GF=F": 2,
    "ZO=F": 2, "ZR=F": 2, "ZL=F": 2, "ES=F": 2, "NQ=F": 2, "YM=F": 2,
    "RTY=F": 2,
    # --- futures (3 digits) ---
    "SI=F": 3, "NG=F": 3, "ZB=F": 3,
    # --- futures (4 digits) ---
    "ZN=F": 4,
    # --- equities / ETFs (2 digits) ---
    "AAPL": 2, "MSFT": 2, "GOOGL": 2, "AMZN": 2, "TSLA": 2, "NVDA": 2,
    "META": 2, "SPY": 2, "QQQ": 2, "DIA": 2, "IWM": 2, "GLD": 2,
    "SLV": 2, "USO": 2, "UNG": 2,
}

def _load_symbol_digits() -> Dict[str, int]:
    raw = os.getenv("SYMBOL_DIGITS", "").strip()
    if not raw:
        return dict(_DEFAULT_SYMBOL_DIGITS)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            out = dict(_DEFAULT_SYMBOL_DIGITS)
            for k, v in parsed.items():
                if isinstance(k, str) and isinstance(v, int) and v >= 0:
                    out[k] = v
            return out
    except Exception:
        pass
    return dict(_DEFAULT_SYMBOL_DIGITS)

SYMBOL_DIGITS: Dict[str, int] = _load_symbol_digits()
SYMBOL_DIGITS_DEFAULT: int = int(os.getenv("SYMBOL_DIGITS_DEFAULT", "2"))

# ============================================================================
# ENVIRONMENT
# ============================================================================
TELEGRAM_WEBAPP_URL: str = os.getenv("TELEGRAM_WEBAPP_URL", "").strip()
BRIDGE_HOST: str = os.getenv("BRIDGE_HOST", "0.0.0.0").strip()
BRIDGE_PORT: int = int(os.getenv("PORT", os.getenv("BRIDGE_PORT", "8765")))
BRIDGE_USE_TLS: bool = os.getenv("BRIDGE_USE_TLS", "0").strip() in ("1", "true", "yes")
BRIDGE_TLS_CERT: str = os.getenv("BRIDGE_TLS_CERT", "").strip()
BRIDGE_TLS_KEY: str = os.getenv("BRIDGE_TLS_KEY", "").strip()
BRIDGE_TUNNEL: str = os.getenv("BRIDGE_TUNNEL", "cloudflared").strip().lower()
BRIDGE_PUBLIC_TIMEOUT: int = int(os.getenv("BRIDGE_PUBLIC_TIMEOUT", "45"))
TELEGRAM_BOT_TOKEN_ENV: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
REQUIRE_AUTH: bool = os.getenv("REQUIRE_AUTH", "1").strip() in ("1", "true", "yes")
LOG_BUFFER_SIZE: int = int(os.getenv("LOG_BUFFER_SIZE", "1000"))
TOAST_BUFFER_SIZE: int = int(os.getenv("TOAST_BUFFER_SIZE", "500"))

PUSH_ON_SIGNAL: bool = os.getenv("PUSH_ON_SIGNAL", "1").strip() in ("1", "true", "yes")
PUSH_ON_EXECUTION: bool = os.getenv("PUSH_ON_EXECUTION", "1").strip() in ("1", "true", "yes")
PUSH_ON_FVG: bool = os.getenv("PUSH_ON_FVG", "1").strip() in ("1", "true", "yes")
PUSH_ON_CLOSE: bool = os.getenv("PUSH_ON_CLOSE", "1").strip() in ("1", "true", "yes")
PUSH_DEDUP_WINDOW_MS: int = int(os.getenv("PUSH_DEDUP_WINDOW_MS", "800"))

RELAY_URL: str = os.getenv("RELAY_URL", "").strip().rstrip("/")
RELAY_KEY: str = os.getenv("RELAY_KEY", "").strip()
RELAY_TIMEOUT: int = int(os.getenv("RELAY_TIMEOUT", "10"))
RELAY_MAX_RETRIES: int = int(os.getenv("RELAY_MAX_RETRIES", "3"))

CORS_ORIGIN: str = os.getenv("CORS_ORIGIN", "*").strip()
SYMBOL: str = os.getenv("SYMBOL", "BTC-USD").strip() or "BTC-USD"
INTERVAL: str = "1m"
UPDATE_INTERVAL: int = int(os.getenv("UPDATE_INTERVAL", "30"))

# ============================================================================
# SYMBOL MAP — v4.5.0 EXPANDED UNIVERSE
# ============================================================================
# SYMBOL_MAP maps the user's input form to the canonical relay symbol. The
# relay v4.5.0 exposes ~90 crypto pairs (Kraken-primary) and ~45
# futures/equities/ETFs (Stooq-primary, Yahoo-fallback). SYMBOL_MAP covers
# all of them, plus the legacy Binance pair-name aliases (BTCUSDT →
# BTC-USD) so a user who types the exchange-native form still resolves.
# ============================================================================
SYMBOL_MAP = {
    # --- crypto (canonical) ---
    "BTC-USD": "BTC-USD", "ETH-USD": "ETH-USD", "XRP-USD": "XRP-USD",
    "ADA-USD": "ADA-USD", "SOL-USD": "SOL-USD", "DOGE-USD": "DOGE-USD",
    "LTC-USD": "LTC-USD", "LINK-USD": "LINK-USD", "DOT-USD": "DOT-USD",
    "AVAX-USD": "AVAX-USD", "MATIC-USD": "MATIC-USD", "UNI-USD": "UNI-USD",
    "ATOM-USD": "ATOM-USD", "NEAR-USD": "NEAR-USD", "FIL-USD": "FIL-USD",
    "ETC-USD": "ETC-USD", "ICP-USD": "ICP-USD", "XLM-USD": "XLM-USD",
    "HBAR-USD": "HBAR-USD", "QNT-USD": "QNT-USD",
    "ARB-USD": "ARB-USD", "OP-USD": "OP-USD", "SUI-USD": "SUI-USD",
    "APT-USD": "APT-USD", "INJ-USD": "INJ-USD", "TIA-USD": "TIA-USD",
    "SEI-USD": "SEI-USD", "PEPE-USD": "PEPE-USD", "SHIB-USD": "SHIB-USD",
    "WIF-USD": "WIF-USD", "BONK-USD": "BONK-USD", "JUP-USD": "JUP-USD",
    "PYTH-USD": "PYTH-USD", "RNDR-USD": "RNDR-USD", "FET-USD": "FET-USD",
    "GRT-USD": "GRT-USD", "IMX-USD": "IMX-USD", "LDO-USD": "LDO-USD",
    "CRV-USD": "CRV-USD", "SNX-USD": "SNX-USD", "COMP-USD": "COMP-USD",
    "MKR-USD": "MKR-USD", "AAVE-USD": "AAVE-USD", "SUSHI-USD": "SUSHI-USD",
    "YFI-USD": "YFI-USD", "BAL-USD": "BAL-USD", "KNC-USD": "KNC-USD",
    "ZRX-USD": "ZRX-USD", "BAT-USD": "BAT-USD", "ENJ-USD": "ENJ-USD",
    "MANA-USD": "MANA-USD", "SAND-USD": "SAND-USD", "AXS-USD": "AXS-USD",
    "GALA-USD": "GALA-USD", "CHZ-USD": "CHZ-USD", "APE-USD": "APE-USD",
    "GMT-USD": "GMT-USD", "LRC-USD": "LRC-USD", "STORJ-USD": "STORJ-USD",
    "ANKR-USD": "ANKR-USD", "CVC-USD": "CVC-USD", "OMG-USD": "OMG-USD",
    "REN-USD": "REN-USD", "ZIL-USD": "ZIL-USD", "KSM-USD": "KSM-USD",
    "GLMR-USD": "GLMR-USD", "MOVR-USD": "MOVR-USD", "ASTR-USD": "ASTR-USD",
    "CFX-USD": "CFX-USD", "MASK-USD": "MASK-USD", "DYDX-USD": "DYDX-USD",
    "GMX-USD": "GMX-USD", "RPL-USD": "RPL-USD", "BLUR-USD": "BLUR-USD",
    "ENS-USD": "ENS-USD", "LQTY-USD": "LQTY-USD", "PENDLE-USD": "PENDLE-USD",
    "MAGIC-USD": "MAGIC-USD", "HIGH-USD": "HIGH-USD", "ID-USD": "ID-USD",
    "ARKM-USD": "ARKM-USD", "WLD-USD": "WLD-USD", "EDU-USD": "EDU-USD",
    "HOOK-USD": "HOOK-USD", "JTO-USD": "JTO-USD", "BOME-USD": "BOME-USD",
    "ETHFI-USD": "ETHFI-USD", "ENA-USD": "ENA-USD", "W-USD": "W-USD",
    "OMNI-USD": "OMNI-USD", "REZ-USD": "REZ-USD", "ZK-USD": "ZK-USD",
    "STRK-USD": "STRK-USD", "DYM-USD": "DYM-USD", "ALT-USD": "ALT-USD",
    "MANTA-USD": "MANTA-USD", "PIXEL-USD": "PIXEL-USD", "PORTAL-USD": "PORTAL-USD",
    "AEVO-USD": "AEVO-USD",
    # --- Binance-native aliases ---
    "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD", "XRPUSDT": "XRP-USD",
    "ADAUSDT": "ADA-USD", "SOLUSDT": "SOL-USD", "DOGEUSDT": "DOGE-USD",
    "LTCUSDT": "LTC-USD", "LINKUSDT": "LINK-USD", "DOTUSDT": "DOT-USD",
    "AVAXUSDT": "AVAX-USD", "MATICUSDT": "MATIC-USD", "UNIUSDT": "UNI-USD",
    "ATOMUSDT": "ATOM-USD", "NEARUSDT": "NEAR-USD", "FILUSDT": "FIL-USD",
    "ETCUSDT": "ETC-USD", "ICPUSDT": "ICP-USD", "XLMUSDT": "XLM-USD",
    "HBARUSDT": "HBAR-USD", "QNTUSDT": "QNT-USD",
    "ARBUSDT": "ARB-USD", "OPUSDT": "OP-USD", "SUIUSDT": "SUI-USD",
    "APTUSDT": "APT-USD", "INJUSDT": "INJ-USD", "TIAUSDT": "TIA-USD",
    "SEIUSDT": "SEI-USD", "PEPEUSDT": "PEPE-USD", "SHIBUSDT": "SHIB-USD",
    "WIFUSDT": "WIF-USD", "BONKUSDT": "BONK-USD", "JUPUSDT": "JUP-USD",
    "PYTHUSDT": "PYTH-USD", "RNDRUSDT": "RNDR-USD", "FETUSDT": "FET-USD",
    "GRTUSDT": "GRT-USD", "IMXUSDT": "IMX-USD", "LDOUSDT": "LDO-USD",
    "CRVUSDT": "CRV-USD", "SNXUSDT": "SNX-USD", "COMPUSDT": "COMP-USD",
    "MKRUSDT": "MKR-USD", "AAVEUSDT": "AAVE-USD", "SUSHIUSDT": "SUSHI-USD",
    "YFIUSDT": "YFI-USD", "BALUSDT": "BAL-USD", "KNCUSDT": "KNC-USD",
    "ZRXUSDT": "ZRX-USD", "BATUSDT": "BAT-USD", "ENJUSDT": "ENJ-USD",
    "MANAUSDT": "MANA-USD", "SANDUSDT": "SAND-USD", "AXSUSDT": "AXS-USD",
    "GALAUSDT": "GALA-USD", "CHZUSDT": "CHZ-USD", "APEUSDT": "APE-USD",
    "GMTUSDT": "GMT-USD", "LRCUSDT": "LRC-USD", "STORJUSDT": "STORJ-USD",
    "ANKRUSDT": "ANKR-USD", "CVCUSDT": "CVC-USD", "OMGUSDT": "OMG-USD",
    "RENUSDT": "REN-USD", "ZILUSDT": "ZIL-USD", "KSMUSDT": "KSM-USD",
    "GLMRUSDT": "GLMR-USD", "MOVRUSDT": "MOVR-USD", "ASTRUSDT": "ASTR-USD",
    "CFXUSDT": "CFX-USD", "MASKUSDT": "MASK-USD", "DYDXUSDT": "DYDX-USD",
    "GMXUSDT": "GMX-USD", "RPLUSDT": "RPL-USD", "BLURUSDT": "BLUR-USD",
    "ENSUSDT": "ENS-USD", "LQTYUSDT": "LQTY-USD", "PENDLEUSDT": "PENDLE-USD",
    "MAGICUSDT": "MAGIC-USD", "HIGHUSDT": "HIGH-USD", "IDUSDT": "ID-USD",
    "ARKMUSDT": "ARKM-USD", "WLDUSDT": "WLD-USD", "EDUUSDT": "EDU-USD",
    "HOOKUSDT": "HOOK-USD", "JTOUSDT": "JTO-USD", "BOMEUSDT": "BOME-USD",
    "ETHFIUSDT": "ETHFI-USD", "ENAUSDT": "ENA-USD", "WUSDT": "W-USD",
    "OMNIUSDT": "OMNI-USD", "REZUSDT": "REZ-USD", "ZKUSDT": "ZK-USD",
    "STRKUSDT": "STRK-USD", "DYMUSDT": "DYM-USD", "ALTUSDT": "ALT-USD",
    "MANTAUSDT": "MANTA-USD", "PIXELUSDT": "PIXEL-USD", "PORTALUSDT": "PORTAL-USD",
    "AEVOUSDT": "AEVO-USD",
    # --- futures ---
    "GC=F": "GC=F", "SI=F": "SI=F", "CL=F": "CL=F", "NG=F": "NG=F",
    "ZB=F": "ZB=F", "ZN=F": "ZN=F", "ZS=F": "ZS=F", "ZM=F": "ZM=F",
    "ZW=F": "ZW=F", "KE=F": "KE=F", "HG=F": "HG=F", "PL=F": "PL=F",
    "PA=F": "PA=F", "RB=F": "RB=F", "HO=F": "HO=F", "CC=F": "CC=F",
    "KC=F": "KC=F", "SB=F": "SB=F", "CT=F": "CT=F", "LH=F": "LH=F",
    "LE=F": "LE=F", "GF=F": "GF=F", "ZO=F": "ZO=F", "ZR=F": "ZR=F",
    "ZL=F": "ZL=F", "ES=F": "ES=F", "NQ=F": "NQ=F", "YM=F": "YM=F",
    "RTY=F": "RTY=F",
    # --- equities / ETFs ---
    "AAPL": "AAPL", "MSFT": "MSFT", "GOOGL": "GOOGL", "AMZN": "AMZN",
    "TSLA": "TSLA", "NVDA": "NVDA", "META": "META", "SPY": "SPY",
    "QQQ": "QQQ", "DIA": "DIA", "IWM": "IWM", "GLD": "GLD",
    "SLV": "SLV", "USO": "USO", "UNG": "UNG",
}

# ============================================================================
# SYMBOL FALLBACKS — v4.5.0 EXPANDED
# ============================================================================
# The relay v4.5.0 dispatches crypto through Kraken → Binance → CoinGecko →
# Yahoo, and equities/futures through Stooq → Yahoo. The backend's
# SYMBOL_FALLBACKS chain is a *secondary* rotation that the FeedClient
# applies when the relay itself reports all_providers_failed for a given
# symbol. It maps a canonical symbol to the next-best symbol form that the
# relay might still resolve (e.g. BTC-USD → BTCUSD=X for Yahoo's crypto
# ticker). With Kraken primary, the chain rarely advances; the entries
# remain as a belt-and-suspenders fallback for the rare case where the
# relay's provider chain is exhausted.
# ============================================================================
SYMBOL_FALLBACKS: Dict[str, List[str]] = {
    # --- crypto ---
    "BTC-USD":  ["BTC-USD", "BTCUSD=X"], "ETH-USD":  ["ETH-USD", "ETHUSD=X"],
    "XRP-USD":  ["XRP-USD", "XRPUSD=X"], "ADA-USD":  ["ADA-USD", "ADAUSD=X"],
    "SOL-USD":  ["SOL-USD", "SOLUSD=X"], "DOGE-USD": ["DOGE-USD", "DOGEUSD=X"],
    "LTC-USD":  ["LTC-USD", "LTCUSD=X"], "LINK-USD": ["LINK-USD", "LINKUSD=X"],
    "DOT-USD":  ["DOT-USD", "DOTUSD=X"], "AVAX-USD": ["AVAX-USD", "AVAXUSD=X"],
    "MATIC-USD":["MATIC-USD", "MATICUSD=X"], "UNI-USD":  ["UNI-USD", "UNIUSD=X"],
    "ATOM-USD": ["ATOM-USD", "ATOMUSD=X"], "NEAR-USD": ["NEAR-USD", "NEARUSD=X"],
    "FIL-USD":  ["FIL-USD", "FILUSD=X"], "ETC-USD":  ["ETC-USD", "ETCUSD=X"],
    "ICP-USD":  ["ICP-USD", "ICPUSD=X"], "XLM-USD":  ["XLM-USD", "XLMUSD=X"],
    "HBAR-USD": ["HBAR-USD", "HBARUSD=X"], "QNT-USD":  ["QNT-USD", "QNTUSD=X"],
    "ARB-USD":  ["ARB-USD", "ARBUSD=X"], "OP-USD":   ["OP-USD", "OPUSD=X"],
    "SUI-USD":  ["SUI-USD", "SUIUSD=X"], "APT-USD":  ["APT-USD", "APTUSD=X"],
    "INJ-USD":  ["INJ-USD", "INJUSD=X"], "TIA-USD":  ["TIA-USD", "TIAUSD=X"],
    "SEI-USD":  ["SEI-USD", "SEIUSD=X"], "PEPE-USD": ["PEPE-USD", "PEPEUSD=X"],
    "SHIB-USD": ["SHIB-USD", "SHIBUSD=X"], "WIF-USD":  ["WIF-USD", "WIFUSD=X"],
    "BONK-USD": ["BONK-USD", "BONKUSD=X"], "JUP-USD":  ["JUP-USD", "JUPUSD=X"],
    "PYTH-USD": ["PYTH-USD", "PYTHUSD=X"], "RNDR-USD": ["RNDR-USD", "RNDRUSD=X"],
    "FET-USD":  ["FET-USD", "FETUSD=X"], "GRT-USD":  ["GRT-USD", "GRTUSD=X"],
    "IMX-USD":  ["IMX-USD", "IMXUSD=X"], "LDO-USD":  ["LDO-USD", "LDOUSD=X"],
    "CRV-USD":  ["CRV-USD", "CRVUSD=X"], "SNX-USD":  ["SNX-USD", "SNXUSD=X"],
    "COMP-USD": ["COMP-USD", "COMPUSD=X"], "MKR-USD":  ["MKR-USD", "MKRUSD=X"],
    "AAVE-USD": ["AAVE-USD", "AAVEUSD=X"], "SUSHI-USD":["SUSHI-USD", "SUSHIUSD=X"],
    "YFI-USD":  ["YFI-USD", "YFIUSD=X"], "BAL-USD":  ["BAL-USD", "BALUSD=X"],
    "KNC-USD":  ["KNC-USD", "KNCUSD=X"], "ZRX-USD":  ["ZRX-USD", "ZRXUSD=X"],
    "BAT-USD":  ["BAT-USD", "BATUSD=X"], "ENJ-USD":  ["ENJ-USD", "ENJUSD=X"],
    "MANA-USD": ["MANA-USD", "MANAUSD=X"], "SAND-USD": ["SAND-USD", "SANDUSD=X"],
    "AXS-USD":  ["AXS-USD", "AXSUSD=X"], "GALA-USD": ["GALA-USD", "GALAUSD=X"],
    "CHZ-USD":  ["CHZ-USD", "CHZUSD=X"], "APE-USD":  ["APE-USD", "APEUSD=X"],
    "GMT-USD":  ["GMT-USD", "GMTUSD=X"], "LRC-USD":  ["LRC-USD", "LRCUSD=X"],
    "STORJ-USD":["STORJ-USD", "STORJUSD=X"], "ANKR-USD": ["ANKR-USD", "ANKRUSD=X"],
    "CVC-USD":  ["CVC-USD", "CVCUSD=X"], "OMG-USD":  ["OMG-USD", "OMGUSD=X"],
    "REN-USD":  ["REN-USD", "RENUSD=X"], "ZIL-USD":  ["ZIL-USD", "ZILUSD=X"],
    "KSM-USD":  ["KSM-USD", "KSMUSD=X"], "GLMR-USD": ["GLMR-USD", "GLMRUSD=X"],
    "MOVR-USD": ["MOVR-USD", "MOVRUSD=X"], "ASTR-USD": ["ASTR-USD", "ASTRUSD=X"],
    "CFX-USD":  ["CFX-USD", "CFXUSD=X"], "MASK-USD": ["MASK-USD", "MASKUSD=X"],
    "DYDX-USD": ["DYDX-USD", "DYDXUSD=X"], "GMX-USD":  ["GMX-USD", "GMXUSD=X"],
    "RPL-USD":  ["RPL-USD", "RPLUSD=X"], "BLUR-USD": ["BLUR-USD", "BLURUSD=X"],
    "ENS-USD":  ["ENS-USD", "ENSUSD=X"], "LQTY-USD": ["LQTY-USD", "LQTYUSD=X"],
    "PENDLE-USD":["PENDLE-USD", "PENDLEUSD=X"], "MAGIC-USD": ["MAGIC-USD", "MAGICUSD=X"],
    "HIGH-USD": ["HIGH-USD", "HIGHUSD=X"], "ID-USD":   ["ID-USD", "IDUSD=X"],
    "ARKM-USD": ["ARKM-USD", "ARKMUSD=X"], "WLD-USD":  ["WLD-USD", "WLDUSD=X"],
    "EDU-USD":  ["EDU-USD", "EDUUSD=X"], "HOOK-USD": ["HOOK-USD", "HOOKUSD=X"],
    "JTO-USD":  ["JTO-USD", "JTOUSD=X"], "BOME-USD": ["BOME-USD", "BOMEUSD=X"],
    "ETHFI-USD":["ETHFI-USD", "ETHFIUSD=X"], "ENA-USD": ["ENA-USD", "ENAUSD=X"],
    "W-USD":    ["W-USD", "WUSD=X"], "OMNI-USD": ["OMNI-USD", "OMNIUSD=X"],
    "REZ-USD":  ["REZ-USD", "REZUSD=X"], "ZK-USD":   ["ZK-USD", "ZKUSD=X"],
    "STRK-USD": ["STRK-USD", "STRKUSD=X"], "DYM-USD":  ["DYM-USD", "DYMUSD=X"],
    "ALT-USD":  ["ALT-USD", "ALTUSD=X"], "MANTA-USD":["MANTA-USD", "MANTAUSD=X"],
    "PIXEL-USD":["PIXEL-USD", "PIXELUSD=X"], "PORTAL-USD":["PORTAL-USD", "PORTALUSD=X"],
    "AEVO-USD": ["AEVO-USD", "AEVOUSD=X"],
    # --- futures ---
    "GC=F": ["GC=F"], "SI=F": ["SI=F"], "CL=F": ["CL=F"], "NG=F": ["NG=F"],
    "ZB=F": ["ZB=F"], "ZN=F": ["ZN=F"], "ZS=F": ["ZS=F"], "ZM=F": ["ZM=F"],
    "ZW=F": ["ZW=F"], "KE=F": ["KE=F"], "HG=F": ["HG=F"], "PL=F": ["PL=F"],
    "PA=F": ["PA=F"], "RB=F": ["RB=F"], "HO=F": ["HO=F"], "CC=F": ["CC=F"],
    "KC=F": ["KC=F"], "SB=F": ["SB=F"], "CT=F": ["CT=F"], "LH=F": ["LH=F"],
    "LE=F": ["LE=F"], "GF=F": ["GF=F"], "ZO=F": ["ZO=F"], "ZR=F": ["ZR=F"],
    "ZL=F": ["ZL=F"], "ES=F": ["ES=F"], "NQ=F": ["NQ=F"], "YM=F": ["YM=F"],
    "RTY=F": ["RTY=F"],
    # --- equities / ETFs ---
    "AAPL": ["AAPL"], "MSFT": ["MSFT"], "GOOGL": ["GOOGL"], "AMZN": ["AMZN"],
    "TSLA": ["TSLA"], "NVDA": ["NVDA"], "META": ["META"], "SPY": ["SPY"],
    "QQQ": ["QQQ"], "DIA": ["DIA"], "IWM": ["IWM"], "GLD": ["GLD"],
    "SLV": ["SLV"], "USO": ["USO"], "UNG": ["UNG"],
}

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    MenuButtonWebApp,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ============================================================================
# LOG RING BUFFER
# ============================================================================
_LOG_BUFFER: deque = deque(maxlen=LOG_BUFFER_SIZE)
_LOG_LOCK = threading.Lock()

# ============================================================================
# TOAST RING BUFFER
# ============================================================================
# TOAST_BUFFER_SIZE <= 0 would produce a deque that holds nothing (maxlen=0)
# or raises ValueError at construction (maxlen<0). Neither is a valid ring
# buffer. Clamp to a minimum of 1 so the seq cursor and first_available_seq
# contract the /toasts endpoint depends on remain coherent.
_TOAST_BUFFER_MAXLEN: int = TOAST_BUFFER_SIZE if TOAST_BUFFER_SIZE > 0 else 1
_TOAST_BUFFER: deque = deque(maxlen=_TOAST_BUFFER_MAXLEN)
_TOAST_LOCK = threading.Lock()
_TOAST_SEQ: int = 0
_TOAST_FIRST_AVAILABLE_SEQ: int = 0

_PUSH_DEDUP_LOCK = threading.Lock()
_PUSH_DEDUP: Dict[str, float] = {}

# ============================================================================
# E-7: BOUNDED PUSH DISPATCH QUEUE
# ============================================================================
# A single queue.Queue(maxsize=512) consumed by one daemon thread replaces the
# per-toast threading.Thread spawn. Under sustained signals the previous code
# created unbounded threads; the queue bounds memory and thread count to O(1).
# If the queue is full, the oldest entry is dropped and a warning is logged —
# the toast buffer remains the authoritative record.
_PUSH_QUEUE: "queue.Queue[Optional[Tuple[str, Dict[str, Any]]]]" = queue.Queue(maxsize=512)
_PUSH_WORKER_STARTED: bool = False
_PUSH_WORKER_LOCK = threading.Lock()

def _push_dedup_key(kind: str, payload: Dict[str, Any]) -> str:
    if kind == "signal":
        return "signal:%s:%s:%s" % (payload.get("type"), payload.get("h"), payload.get("tick"))
    if kind == "execution":
        return "execution:%s:%s:%s:%s" % (payload.get("event"), payload.get("side"), payload.get("ticket"), payload.get("tick"))
    if kind == "fvg":
        return "fvg:%s:%s:%s" % (payload.get("action"), payload.get("type"), payload.get("idx"))
    return kind + ":" + str(payload.get("tick", ""))

def _push_dedup_allow(key: str) -> bool:
    now = time.monotonic() * 1000.0
    with _PUSH_DEDUP_LOCK:
        last = _PUSH_DEDUP.get(key)
        if last is not None and (now - last) < PUSH_DEDUP_WINDOW_MS:
            return False
        _PUSH_DEDUP[key] = now
        cutoff = now - 60000.0
        for k in list(_PUSH_DEDUP.keys()):
            if _PUSH_DEDUP[k] < cutoff:
                del _PUSH_DEDUP[k]
    return True

class _RingHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            with _LOG_LOCK:
                _LOG_BUFFER.append({
                    "ts": datetime.fromtimestamp(record.created).isoformat(),
                    "level": record.levelname.lower(),
                    "msg": msg,
                })
        except Exception:
            pass

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
_ring_handler = _RingHandler()
logger.addHandler(_ring_handler)
logger.propagate = False

# ============================================================================
# D-MAJ-7: attach the ring handler to the telegram.ext logger so handler
# exceptions caught by Application's error handler reach the /log endpoint
# and the TWA log bar. Previously only the __main__ logger had the ring
# handler, so a telegram.error.BadRequest raised inside a command handler
# was written to stderr but never surfaced to the client.
# ============================================================================
_telegram_ext_logger = logging.getLogger("telegram.ext")
_telegram_ext_logger.addHandler(_ring_handler)
_telegram_ext_logger.setLevel(logging.INFO)
_telegram_ext_logger.propagate = False

# ============================================================================
# E-1 + E-6 + E-12: TOAST EMISSION + TELEGRAM PUSH (THREADED AS REPLY)
# ============================================================================
def _format_push_message(kind: str, payload: Dict[str, Any]) -> Optional[str]:
    if kind == "signal" and not PUSH_ON_SIGNAL:
        return None
    if kind == "execution" and not PUSH_ON_EXECUTION:
        return None
    if kind == "fvg" and not PUSH_ON_FVG:
        return None
    if kind == "close" and not PUSH_ON_CLOSE:
        return None
    if kind == "signal":
        direction = payload.get("type", "NEUTRAL")
        arrow = "📈" if direction == "BUY" else ("📉" if direction == "SELL" else "⚪")
        dir_cs = "↑" if direction == "BUY" else ("↓" if direction == "SELL" else "⊙")
        return (
            f"🎯 *ÆEA 𝒮\\_signal* {arrow}\n"
            f"*Type:* {_md_escape(dir_cs)}\n"
            f"*Price:* `{_md_escape(payload.get('price'))}`\n"
            f"*m/n:* {_md_escape(payload.get('m'))}/{_md_escape(payload.get('n'))} @ h={_md_escape(payload.get('h'))}\n"
            f"*ℛ\\_regime:* {_md_escape(payload.get('regime', '—'))}\n"
            f"*Tick:* {_md_escape(payload.get('tick', '—'))}\n"
            f"💎 Natalia Tanyatia"
        )
    if kind == "execution":
        event = payload.get("event", "EXEC")
        emoji_map = {
            "Bull": "🐂", "Bear": "🐻", "Whisky": "🥃", "Wine": "🍷",
            "Watter": "💧", "Blood": "🩸", "Hawk": "🦅", "Dove": "🕊️",
            "Diamond": "🔷", "Ruby": "🔻", "Top": "▲", "Bott": "▼",
            "A": "🅰️", "B": "🅱️", "ManualOrder": "📝", "ManualClose": "✂️",
        }
        cs_map = {
            "Bull": "𝒟\\_Bull", "Bear": "𝒟\\_Bear", "Whisky": "𝒲\\_Whisky",
            "Wine": "𝒲\\_Wine", "Watter": "𝒲\\_Watter", "Blood": "ℬ\\_Blood",
            "Hawk": "ℋ\\_Hawk", "Dove": "𝒟\\_Dove", "Diamond": "𝒟\\_Diamond",
            "Ruby": "ℛ\\_Ruby", "Top": "𝒯\\_Top", "Bott": "ℬ\\_Bott",
            "A": "𝒜", "B": "ℬ\\_Close", "ManualOrder": "ℳ\\_Order",
            "ManualClose": "ℳ\\_Close",
        }
        emoji = emoji_map.get(event, "⚡")
        cs_event = cs_map.get(event, event)
        side = payload.get("side", "NONE")
        ticket = payload.get("ticket", -1)
        ticket_str = f"#{ticket}" if ticket != -1 else "—"
        reason = payload.get("reason", "")
        reason_str = f"\n*Reason:* {_md_escape(reason)}" if reason else ""
        return (
            f"{emoji} *ÆEA ℰ\\_exec: {_md_escape(cs_event)}*\n"
            f"*Side:* {_md_escape(side)}\n"
            f"*Ticket:* {_md_escape(ticket_str)}\n"
            f"*Price:* `{_md_escape(payload.get('price'))}`\n"
            f"*Tick:* {_md_escape(payload.get('tick', '—'))}{reason_str}\n"
            f"💎 Natalia Tanyatia"
        )
    if kind == "fvg":
        action = payload.get("action", "commit")
        fvg_type = payload.get("type", "top")
        arrow = "▲" if fvg_type == "top" else "▼"
        return (
            f"📐 *ÆEA ℱ\\_VG {_md_escape(action.upper())}*\n"
            f"*Type:* {arrow} {_md_escape(fvg_type)}\n"
            f"*Price:* `{_md_escape(payload.get('price'))}`\n"
            f"*Idx:* {_md_escape(payload.get('idx', '—'))}\n"
            f"💎 Natalia Tanyatia"
        )
    return None

def _telegram_push(kind: str, payload: Dict[str, Any]) -> None:
    key = _push_dedup_key(kind, payload)
    if not _push_dedup_allow(key):
        return
    msg = _format_push_message(kind, payload)
    if msg is None:
        return
    engine = BRIDGE_ENGINE_REF.get("engine")
    if engine is None:
        return
    bot = BRIDGE_ENGINE_REF.get("bot")
    if bot is None:
        return
    st = engine.state
    # D-31: prefer chat_id strictly; fall back to webapp_user_id only when
    # chat_id is None. Previously the code picked whichever was set, which
    # could double-send or send to the wrong chat in group contexts.
    target_chat = st.chat_id
    if target_chat is None:
        target_chat = st.webapp_user_id
    if not target_chat:
        return
    # E-6: thread the push as a reply to the user's most recent inbound
    # message. If none has been recorded, the push is a standalone message.
    reply_to = st.last_inbound_message_id if isinstance(st.last_inbound_message_id, int) else None
    # E-10: route through the cross-thread send helper so the coroutine is
    # actually awaited on the bot's event loop. The old direct call to
    # app.bot.send_message(...) constructed the coroutine and dropped it.
    # E-11: the helper internally retries without reply_to_message_id and
    # without parse_mode on 400s, so a stale reply id or an unparseable
    # field no longer silences the push.
    if not hasattr(bot, "_send_message_sync"):
        logger.warning("📲 Push skipped: bot has no _send_message_sync")
        return
    ok = bot._send_message_sync(
        chat_id=target_chat,
        text=msg,
        parse_mode="Markdown",
        reply_to_message_id=reply_to,
    )
    if ok:
        logger.info(f"📲 Push sent ({kind}) to {target_chat} reply_to={reply_to} (tick={st.tick})")
    else:
        logger.warning(f"📲 Push failed ({kind}) to {target_chat} reply_to={reply_to} (tick={st.tick})")

def _push_worker_loop() -> None:
    while True:
        item = _PUSH_QUEUE.get()
        try:
            if item is None:
                break
            kind, payload = item
            _telegram_push(kind, payload)
        except Exception as e:
            logger.warning(f"📲 Push worker error: {e}")
        finally:
            try:
                _PUSH_QUEUE.task_done()
            except Exception:
                pass

def _ensure_push_worker() -> None:
    global _PUSH_WORKER_STARTED
    if _PUSH_WORKER_STARTED:
        return
    with _PUSH_WORKER_LOCK:
        if _PUSH_WORKER_STARTED:
            return
        t = threading.Thread(target=_push_worker_loop, name="aei-push-worker", daemon=True)
        t.start()
        _PUSH_WORKER_STARTED = True

def _emit_toast(kind: str, payload: Dict[str, Any]) -> int:
    global _TOAST_SEQ, _TOAST_FIRST_AVAILABLE_SEQ, _TOAST_BUFFER
    with _TOAST_LOCK:
        maxlen = _TOAST_BUFFER.maxlen
        if maxlen is None or maxlen <= 0:
            _TOAST_BUFFER = deque(maxlen=1)
        was_full = (len(_TOAST_BUFFER) >= _TOAST_BUFFER.maxlen)
        _TOAST_SEQ += 1
        seq = _TOAST_SEQ
        entry = dict(payload)
        entry["kind"] = kind
        entry["seq"] = seq
        if "ts" not in entry:
            entry["ts"] = datetime.now().isoformat()
        _TOAST_BUFFER.append(entry)
        if was_full and len(_TOAST_BUFFER) > 0:
            _TOAST_FIRST_AVAILABLE_SEQ = _TOAST_BUFFER[0].get("seq", _TOAST_SEQ)
        elif _TOAST_FIRST_AVAILABLE_SEQ == 0 and len(_TOAST_BUFFER) > 0:
            _TOAST_FIRST_AVAILABLE_SEQ = _TOAST_BUFFER[0].get("seq", seq)
    try:
        _ensure_push_worker()
        try:
            _PUSH_QUEUE.put_nowait((kind, entry))
        except queue.Full:
            # Drop the oldest entry to make room, then retry once. If the
            # retry also fails (another producer filled the slot), log and
            # drop the new toast — the ring buffer remains the authoritative
            # record.
            dropped = False
            try:
                _PUSH_QUEUE.get_nowait()
                _PUSH_QUEUE.task_done()
                dropped = True
            except Exception:
                pass
            try:
                _PUSH_QUEUE.put_nowait((kind, entry))
            except Exception as e:
                logger.warning(f"📲 Push queue full; dropped toast kind={kind} seq={seq} (evicted_oldest={dropped}): {e}")
    except Exception as e:
        logger.warning(f"📲 Push dispatch failed: {e}")
    return seq

# ============================================================================
# DATACLASSES
# ============================================================================
@dataclass
class PriceData:
    bid: Decimal = Decimal('0.0')
    ask: Decimal = Decimal('0.0')
    close: Decimal = Decimal('0.0')
    open: Decimal = Decimal('0.0')
    high: Decimal = Decimal('0.0')
    low: Decimal = Decimal('0.0')
    volume: Decimal = Decimal('0.0')
    timestamp: datetime = field(default_factory=datetime.now)
    provider: str = ""

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

@dataclass
class IndicatorState:
    adx: Decimal = Decimal('50.0')
    stochastic: Decimal = Decimal('50.0')
    rvi: Decimal = Decimal('50.0')
    ac: Decimal = Decimal('50.0')
    force: Decimal = Decimal('50.0')
    obv: Decimal = Decimal('50.0')
    ad: Decimal = Decimal('50.0')
    mfi: Decimal = Decimal('50.0')
    momentum: Decimal = Decimal('50.0')
    dem: Decimal = Decimal('50.0')
    wpr: Decimal = Decimal('50.0')
    cci: Decimal = Decimal('50.0')
    rsi: Decimal = Decimal('50.0')
    ihk_kijun: Decimal = Decimal('50.0')
    ihk_tenkan: Decimal = Decimal('50.0')

@dataclass
class Order:
    ticket: int
    side: str
    entry: Decimal
    sl: Decimal = Decimal('0.0')
    tp: Decimal = Decimal('0.0')
    lot: Decimal = Decimal('0.01')
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    close_price: Optional[Decimal] = None

    def pnl(self, current_price: Decimal) -> Decimal:
        if self.side == 'BUY':
            return (current_price - self.entry) * self.lot * Decimal('100000')
        else:
            return (self.entry - current_price) * self.lot * Decimal('100000')

@dataclass
class AEI_CoreState:
    KC: bool = True
    invert: bool = True
    tag: int = -1
    prime: int = -1
    dime: int = -1
    mem: int = -1
    tick: int = 0
    y: int = Y_START
    signal: Decimal = Decimal('0.0')
    signature: bool = False
    tick_tock: bool = False
    FG: bool = False
    GF: bool = False
    Buy: int = -1
    Sell: int = -1
    A: bool = True
    B: bool = True
    a: bool = True
    b: bool = True
    ab: bool = False
    ba: bool = True
    u: bool = False
    v: bool = False
    lOrder_id: int = -1
    kOrder_id: int = -1
    D: Decimal = Decimal('0.0')
    E: Decimal = Decimal('0.0')
    p: Decimal = Decimal('0.0')
    q: Decimal = Decimal('0.0')
    K: bool = False
    C: bool = True
    c: bool = True
    iC: bool = True
    jC: bool = True
    Cc: bool = True
    cC: bool = True
    safety: bool = False
    Z: int = Y_START + 1
    z: int = Y_START + 1
    O: int = Y_START + 1
    o: int = Y_START + 1
    r: int = 0
    W: int = Y_START + 1
    w: int = Y_START + 1
    I: int = 0
    iI: int = 0
    J: int = 0
    iJ: int = 0
    ij: int = 0
    h: int = 0
    iZ: int = Y_START + 1
    iz: int = Y_START + 1
    iW: int = Y_START + 1
    iw: int = Y_START + 1
    iO: int = Y_START + 1
    io: int = Y_START + 1
    ir: int = 0
    count: int = 0
    toll: int = 0
    tally: str = "   "
    m: int = 0
    n: int = 0
    authoritative_m: int = 0
    authoritative_n: int = 0
    authoritative_h: int = -1
    m_now: int = 0
    n_now: int = 0
    lPass: Decimal = Decimal('0.0')
    ilPass: Decimal = Decimal('0.0')
    kPass: Decimal = Decimal('0.0')
    ikPass: Decimal = Decimal('0.0')
    Premium: List[Decimal] = field(default_factory=lambda: [Decimal('0.0')] * (X_PERIOD - Y_START))
    Discount: List[Decimal] = field(default_factory=lambda: [Decimal('0.0')] * (X_PERIOD - Y_START))
    HH: List[Decimal] = field(default_factory=lambda: [Decimal('0.0')] * (X_PERIOD - Y_START))
    LL: List[Decimal] = field(default_factory=lambda: [Decimal('0.0')] * (X_PERIOD - Y_START))
    k: List[bool] = field(default_factory=lambda: [False] * (X_PERIOD - Y_START))
    l: List[bool] = field(default_factory=lambda: [False] * (X_PERIOD - Y_START))
    U: List[bool] = field(default_factory=list)
    R: bool = True
    Regime: List[str] = field(default_factory=lambda: ["sRange"] * (X_PERIOD - Y_START))
    iA: List[List[Decimal]] = field(default_factory=lambda: [[Decimal('50.0')] * (X_PERIOD - Y_START) for _ in range(13)])
    cA: List[List[Decimal]] = field(default_factory=lambda: [[Decimal('50.0')] * (X_PERIOD - Y_START) for _ in range(13)])
    kA: List[List[Decimal]] = field(default_factory=lambda: [[Decimal('50.0')] * (X_PERIOD - Y_START) for _ in range(13)])
    lA: List[List[Decimal]] = field(default_factory=lambda: [[Decimal('50.0')] * (X_PERIOD - Y_START) for _ in range(13)])
    IHKk: List[Decimal] = field(default_factory=list)
    IHKt: List[Decimal] = field(default_factory=list)
    RSI: List[Decimal] = field(default_factory=list)
    CCI: List[Decimal] = field(default_factory=list)
    MOM: List[Decimal] = field(default_factory=list)
    AD: List[Decimal] = field(default_factory=list)
    OBV: List[Decimal] = field(default_factory=list)
    Force: List[Decimal] = field(default_factory=list)
    MFI: List[Decimal] = field(default_factory=list)
    DeM: List[Decimal] = field(default_factory=list)
    RVIm: List[Decimal] = field(default_factory=list)
    AC: List[Decimal] = field(default_factory=list)
    StdDev: List[Decimal] = field(default_factory=list)
    ATR: List[Decimal] = field(default_factory=list)
    ADX: List[Decimal] = field(default_factory=list)
    Suply: Decimal = Decimal('0.0')
    iSuply: Decimal = Decimal('0.0')
    Demand: Decimal = Decimal('0.0')
    iDemand: Decimal = Decimal('0.0')
    Sale: Decimal = Decimal('0.0')
    iSale: Decimal = Decimal('0.0')
    Stock: Decimal = Decimal('0.0')
    iStock: Decimal = Decimal('0.0')
    iStdDev: Decimal = Decimal('50.0')
    iATR: Decimal = Decimal('50.0')
    iIHKk: Decimal = Decimal('50.0')
    iIHKt: Decimal = Decimal('50.0')
    FVG: int = -1
    BL: List[Decimal] = field(default_factory=list)
    BL_type: List[str] = field(default_factory=list)
    bottomLine: str = "   "
    bL: str = "   "
    S: int = X_PERIOD
    T: int = X_PERIOD
    X_scan: int = Y_START
    Y_scan: int = Y_START
    t: Optional[datetime] = None
    iopen: Decimal = Decimal('0.0')
    iPrice: Decimal = Decimal('0.0')
    iH: Decimal = Decimal('0.0')
    iL: Decimal = Decimal('0.0')
    price: Decimal = Decimal('0.0')
    Price: Decimal = Decimal('0.0')
    open: Decimal = Decimal('0.0')
    chat_id: Optional[int] = None
    _initialized: bool = False
    webapp_user_id: Optional[int] = None
    webapp_username: Optional[str] = None
    webapp_verified: bool = False
    webapp_last_seen: Optional[datetime] = None

    trailing_stop_active: bool = False
    trailing_stop_price: Decimal = Decimal('0.0')
    trailing_take_profit: Decimal = Decimal('0.0')
    on_track_runs: int = 0
    on_stand_runs: int = 0
    has_open_long: bool = False
    has_open_short: bool = False
    trailing_stop_entry: Decimal = Decimal('0.0')
    trailing_stop_side: str = ""

    last_kronecker_m: int = 0
    last_kronecker_n: int = 0
    last_kronecker_h: int = -1
    fvg_anchor_map: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    _raw_price_missing: bool = False

    signal_history: List[Dict[str, Any]] = field(default_factory=list)
    max_signal_history: int = 100
    last_signal_at: Optional[str] = None
    bar_close_count: int = 0

    execution_fired: bool = False

    projection_path: List[Dict[str, Any]] = field(default_factory=list)
    projection_meta: Dict[str, Any] = field(default_factory=dict)
    projection_computed_at: Optional[str] = None
    projection_trigger: str = ""

    last_provider: str = ""
    last_volume: Decimal = Decimal('0.0')

    # E-6: message id of the user's most recent inbound message in chat_id.
    # _telegram_push() threads every push as reply_to_message_id to this id.
    last_inbound_message_id: Optional[int] = None

# ============================================================================
# INDICATOR NAME CONSTANT (CS-translated for user-facing display)
# ============================================================================
INDICATOR_NAMES = [
    "ADX", "Stochastic", "RVI", "AC", "Force", "OBV", "AD",
    "MFI", "Momentum", "DeMarker", "WPR", "CCI", "RSI"
]
INDICATOR_NAMES_CS = [
    "𝒜[0]", "𝒜[1]", "𝒜[2]", "𝒜[3]", "𝒜[4]", "𝒜[5]", "𝒜[6]",
    "𝒜[7]", "𝒜[8]", "𝒜[9]", "𝒜[10]", "𝒜[11]", "𝒜[12]",
]

# ============================================================================
# MODULE-LEVEL INDICATOR HELPERS — MQL4 PARITY
# ============================================================================
def sma(data: List[Decimal], period: int) -> Decimal:
    if len(data) < period or period <= 0:
        return Decimal('0.0')
    total = sum(data[-period:], Decimal('0.0'))
    return total / Decimal(period)

def ema(data: List[Decimal], period: int) -> Decimal:
    if len(data) < period or period <= 0:
        return sma(data, period)
    alpha = Decimal('2.0') / (Decimal(period) + Decimal('1.0'))
    if len(data) > 1:
        return alpha * data[-1] + (Decimal('1.0') - alpha) * ema(data[:-1], period)
    return data[-1]

def rsi(data: List[Decimal], period: int = 14) -> Decimal:
    if len(data) < period + 1 or period <= 0:
        return Decimal('50.0')
    gains = Decimal('0.0')
    losses = Decimal('0.0')
    for i in range(period):
        diff = data[i + 1] - data[i]
        if diff >= Decimal('0.0'):
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / Decimal(period)
    avg_loss = losses / Decimal(period)
    for i in range(period + 1, len(data)):
        diff = data[i] - data[i - 1]
        gain = diff if diff > Decimal('0.0') else Decimal('0.0')
        loss = -diff if diff < Decimal('0.0') else Decimal('0.0')
        avg_gain = (avg_gain * Decimal(period - 1) + gain) / Decimal(period)
        avg_loss = (avg_loss * Decimal(period - 1) + loss) / Decimal(period)
    if avg_loss == Decimal('0.0'):
        return Decimal('100.0')
    rs = avg_gain / avg_loss
    return Decimal('100.0') - (Decimal('100.0') / (Decimal('1.0') + rs))

def stochastic(high, low, close, k_period=14, d_period=3, slowing=1):
    """MT4 iStochastic parity.

    MT4's iStochastic(symbol, timeframe, kperiod, dperiod, slowing, method,
    price_field, mode, shift) computes:
      raw_k[i]  = 100 * (close[i] - LL(kperiod, i)) / (HH(kperiod, i) - LL(kperiod, i))
      fast_k[i] = SMA(raw_k, slowing)[i]
      k[i]      = fast_k[i]                     (MODE_MAIN)
      d[i]      = SMA(fast_k, dperiod)[i]       (MODE_SIGNAL)
    The FF calls iStochastic(NULL, 0, j, 3, jSO, MODE_SMA, 0, MODE_MAIN, 0)
    with jSO = round(j * 3/5). The port previously omitted the slowing
    parameter, computing raw_k directly as k. Restore the slowing SMA.

    D-MIN-5 resolution.
    """
    if slowing < 1:
        slowing = 1
    if len(close) < k_period + slowing - 1 or k_period <= 0:
        return Decimal('50.0'), Decimal('50.0')
    raw_k_series = []
    for i in range(slowing):
        if len(close) < k_period + i:
            continue
        h_i = max(high[-(k_period + i):-i]) if i > 0 else max(high[-k_period:])
        l_i = min(low[-(k_period + i):-i]) if i > 0 else min(low[-k_period:])
        r_i = h_i - l_i
        if r_i == Decimal('0.0'):
            raw_k_series.append(Decimal('50.0'))
        else:
            c_i = close[-1 - i]
            raw_k_series.append(Decimal('100.0') * (c_i - l_i) / r_i)
    if not raw_k_series:
        return Decimal('50.0'), Decimal('50.0')
    fast_k = sum(raw_k_series) / Decimal(len(raw_k_series))
    d_series = []
    for i in range(d_period):
        if i == 0:
            d_series.append(fast_k)
        else:
            if len(close) < k_period + slowing - 1 + i:
                d_series.append(fast_k)
                continue
            raw_k_i = []
            for j in range(slowing):
                idx = -1 - i - j
                if abs(idx) > len(close) - k_period:
                    continue
                h_i = max(high[idx - k_period + 1:idx + 1]) if idx < -1 else max(high[-k_period:])
                l_i = min(low[idx - k_period + 1:idx + 1]) if idx < -1 else min(low[-k_period:])
                r_i = h_i - l_i
                if r_i == Decimal('0.0'):
                    raw_k_i.append(Decimal('50.0'))
                else:
                    raw_k_i.append(Decimal('100.0') * (close[idx] - l_i) / r_i)
            if raw_k_i:
                d_series.append(sum(raw_k_i) / Decimal(len(raw_k_i)))
            else:
                d_series.append(fast_k)
    d = sum(d_series) / Decimal(len(d_series)) if d_series else fast_k
    return fast_k, d

def bollinger_bands(close, period=20, dev=Decimal('2.0')):
    if len(close) < period or period <= 0:
        return Decimal('0.0'), Decimal('0.0'), Decimal('0.0')
    mid = sma(close, period)
    variance = sum((x - mid) ** 2 for x in close[-period:]) / Decimal(period)
    std = Decimal(str(math.sqrt(float(variance)))) if variance > Decimal('0.0') else Decimal('0.0')
    upper = mid + dev * std
    lower = mid - dev * std
    return upper, mid, lower

def true_range(high, low, close, i):
    if i + 1 >= len(close):
        return high[i] - low[i]
    tr1 = high[i] - low[i]
    tr2 = abs(high[i] - close[i + 1])
    tr3 = abs(low[i] - close[i + 1])
    return max(tr1, tr2, tr3)

def atr(high, low, close, period=14):
    if len(close) < period + 1 or period <= 0:
        return Decimal('0.0')
    trs = []
    for i in range(period):
        trs.append(true_range(high, low, close, i))
    return sum(trs) / Decimal(period)

def stddev(data, period):
    if len(data) < period or period <= 0:
        return Decimal('0.0')
    mean = sum(data[-period:]) / Decimal(period)
    variance = sum((x - mean) ** 2 for x in data[-period:]) / Decimal(period)
    return Decimal(str(math.sqrt(float(variance)))) if variance > Decimal('0.0') else Decimal('0.0')

def ichimoku(high, low, close, t_period: int, k_period: int, j_period: int):
    if len(close) < j_period or j_period <= 0 or k_period <= 0 or t_period <= 0:
        return {"tenkan": Decimal('50.0'), "kijun": Decimal('50.0'),
                "senkou_a": Decimal('50.0'), "senkou_b": Decimal('50.0')}
    tenkan = (max(high[-t_period:]) + min(low[-t_period:])) / Decimal('2.0')
    kijun = (max(high[-k_period:]) + min(low[-k_period:])) / Decimal('2.0')
    senkou_a = (tenkan + kijun) / Decimal('2.0')
    senkou_b = (max(high[-j_period:]) + min(low[-j_period:])) / Decimal('2.0')
    return {"tenkan": tenkan, "kijun": kijun, "senkou_a": senkou_a, "senkou_b": senkou_b}

def to_decimal(value):
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except Exception:
        return Decimal('0.0')

# ============================================================================
# M-1: SYMBOL POINT-SIZE
# ============================================================================
def symbol_point(symbol: str) -> Decimal:
    digits = _symbol_digits(symbol)
    return Decimal(10) ** Decimal(-digits)

def _symbol_digits(symbol: str) -> int:
    try:
        import MetaTrader5 as _mt5  # type: ignore
        info = _mt5.symbol_info(symbol)
        if info is not None and hasattr(info, "digits"):
            return int(info.digits)
    except Exception:
        pass
    if symbol in SYMBOL_DIGITS:
        return SYMBOL_DIGITS[symbol]
    for canonical, chain in SYMBOL_FALLBACKS.items():
        if symbol in chain:
            return SYMBOL_DIGITS.get(canonical, SYMBOL_DIGITS_DEFAULT)
    return SYMBOL_DIGITS_DEFAULT

# ============================================================================
# TELEGRAM WEB APP AUTHENTICATION
# ============================================================================
def verify_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> Optional[Dict[str, Any]]:
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return None
    auth_date_raw = parsed.get("auth_date")
    if auth_date_raw is not None:
        try:
            auth_age = time.time() - int(auth_date_raw)
            if auth_age > max_age_seconds or auth_age < -300:
                return None
        except (ValueError, TypeError):
            return None
    user_json = parsed.get("user")
    user_obj: Optional[Dict[str, Any]] = None
    if user_json:
        try:
            user_obj = json.loads(user_json)
        except Exception:
            user_obj = None
    return {
        "user": user_obj,
        "auth_date": int(auth_date_raw) if auth_date_raw else None,
        "raw": parsed,
    }

def _extract_auth_headers(handler: "BridgeHandler") -> Tuple[Optional[int], Optional[str], bool]:
    raw_init = handler.headers.get("X-Telegram-Init-Data", "").strip()
    if not raw_init:
        auth_hdr = handler.headers.get("Authorization", "").strip()
        if auth_hdr.lower().startswith("tma "):
            raw_init = auth_hdr[4:].strip()
    if not raw_init:
        return (None, None, False)
    verified = verify_telegram_init_data(raw_init, TELEGRAM_BOT_TOKEN_ENV)
    if not verified or not verified.get("user"):
        return (None, None, False)
    u = verified["user"] or {}
    return (u.get("id"), u.get("username"), True)

# ============================================================================
# FEED CLIENT — CLOUDFLARE WORKER RELAY
# ============================================================================
class FeedClient:
    def __init__(self, symbol: str = "BTC-USD"):
        self.symbol = symbol
        chain = SYMBOL_FALLBACKS.get(symbol)
        if chain is None:
            if symbol.endswith("-USD"):
                base = symbol[:-4]
                chain = [symbol, f"{base}USD=X"]
            else:
                chain = [symbol]
        self._chain: List[str] = list(chain)
        self._chain_index: int = 0
        self._last_update: Optional[datetime] = None
        self._failure_count: int = 0
        self._fallback_count: int = 0
        self._last_provider: str = ""
        self._last_volume: Decimal = Decimal('0.0')

    def active_symbol(self) -> str:
        return self._chain[self._chain_index]

    def failure_count(self) -> int:
        return self._failure_count

    def last_update(self) -> Optional[datetime]:
        return self._last_update

    def last_provider(self) -> str:
        return self._last_provider

    def last_volume(self) -> Decimal:
        return self._last_volume

    def _advance_symbol_chain(self) -> None:
        if len(self._chain) <= 1:
            return
        self._chain_index = (self._chain_index + 1) % len(self._chain)
        logger.warning(f"🔄 FeedClient: rotating symbol chain to '{self.active_symbol()}'")
        self._fallback_count = 0
        self._failure_count = 0

    def _rebuild_ticker(self) -> None:
        logger.info("🔄 FeedClient: rebuild requested (no-op; Worker handles upstream)")

    def _get(self, kind: str, **params) -> Optional[Any]:
        if not RELAY_URL:
            logger.error("❌ RELAY_URL not set — cannot fetch price")
            return None
        params["symbol"] = self.active_symbol()
        params["kind"] = kind
        qs = urllib.parse.urlencode(params)
        url = f"{RELAY_URL}/?{qs}"
        last_error = None
        for attempt in range(RELAY_MAX_RETRIES):
            try:
                req_headers = {
                    "Accept": "application/json",
                    "User-Agent": "AEI-Bridge/v4.5.2",
                    "Cache-Control": "no-cache",
                }
                if RELAY_KEY:
                    req_headers["X-Relay-Key"] = RELAY_KEY
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=RELAY_TIMEOUT) as r:
                    raw = r.read().decode("utf-8")
                    payload = json.loads(raw)
                    if isinstance(payload, dict) and payload.get("error"):
                        # D-54: surface only the first 200 chars of the relay's
                        # detail string, and include the active symbol and kind
                        # so the operator can see which provider class failed.
                        detail_raw = str(payload.get("detail", ""))
                        detail_short = detail_raw[:200] + ("…" if len(detail_raw) > 200 else "")
                        logger.warning(
                            f"Relay returned error for {self.active_symbol()} "
                            f"(kind={kind}): {payload.get('error')} ({detail_short})"
                        )
                        self._failure_count += 1
                        self._fallback_count += 1
                        if self._fallback_count >= 5:
                            self._advance_symbol_chain()
                        return None
                    self._failure_count = 0
                    self._fallback_count = 0
                    self._last_update = datetime.now()
                    if isinstance(payload, dict):
                        if payload.get("provider"):
                            self._last_provider = str(payload["provider"])
                        if payload.get("volume") is not None:
                            try:
                                self._last_volume = Decimal(str(payload["volume"]))
                            except Exception:
                                pass
                    elif isinstance(payload, list) and payload:
                        last = payload[-1]
                        if isinstance(last, dict):
                            if last.get("provider"):
                                self._last_provider = str(last["provider"])
                            if last.get("volume") is not None:
                                try:
                                    self._last_volume = Decimal(str(last["volume"]))
                                except Exception:
                                    pass
                    return payload
            except urllib.error.HTTPError as e:
                try:
                    error_body = e.read().decode('utf-8', errors='ignore')
                except Exception:
                    error_body = '<unreadable>'
                last_error = f"HTTP {e.code}: {error_body[:200]}"
                logger.warning(f"Relay HTTP Error {e.code} for {self.active_symbol()} kind={kind} (attempt {attempt+1}/{RELAY_MAX_RETRIES}): {error_body[:200]}")
                if e.code in (401, 403, 429) and attempt < RELAY_MAX_RETRIES - 1:
                    time.sleep(1 + attempt * 2)
                    continue
                break
            except urllib.error.URLError as e:
                last_error = f"URLError: {e.reason}"
                logger.warning(f"Relay URLError for {self.active_symbol()} kind={kind} (attempt {attempt+1}/{RELAY_MAX_RETRIES}): {e.reason}")
                if attempt < RELAY_MAX_RETRIES - 1:
                    time.sleep(1 + attempt * 2)
                    continue
                break
            except json.JSONDecodeError as e:
                last_error = f"JSONDecodeError: {e}"
                logger.warning(f"Relay returned invalid JSON for {self.active_symbol()} kind={kind}: {e}")
                break
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(f"Relay error ({kind}) for {self.active_symbol()} (attempt {attempt+1}/{RELAY_MAX_RETRIES}): {e}")
                if attempt < RELAY_MAX_RETRIES - 1:
                    time.sleep(1 + attempt * 2)
                    continue
                break
        self._failure_count += 1
        self._fallback_count += 1
        if self._fallback_count >= 5:
            self._advance_symbol_chain()
        if last_error:
            logger.warning(f"Relay exhausted retries for {kind}: {last_error}")
        return None

    def get_current_price(self) -> Tuple[Decimal, Decimal]:
        d = self._get("price")
        if not d or "close" not in d or d.get("close") is None:
            return Decimal('0.0'), Decimal('0.0')
        try:
            c = Decimal(str(d["close"]))
            if c <= Decimal('0.0'):
                logger.warning(f"Relay returned non-positive price: {c}")
                return Decimal('0.0'), Decimal('0.0')
            bid = Decimal(str(d.get("bid") or d["close"]))
            ask = Decimal(str(d.get("ask") or d["close"]))
            if d.get("volume") is not None:
                try:
                    self._last_volume = Decimal(str(d["volume"]))
                except Exception:
                    pass
            if d.get("provider"):
                self._last_provider = str(d["provider"])
            return bid, ask
        except Exception as e:
            logger.warning(f"Failed to parse relay price: {e}")
            return Decimal('0.0'), Decimal('0.0')

    def get_historical_klines(self, limit: int = 200, interval: str = "1m") -> List[Dict[str, Any]]:
        d = self._get("history", limit=limit, interval=interval)
        if not d or not isinstance(d, list):
            return []
        out = []
        for row in d:
            try:
                if row.get("close") is None:
                    continue
                c = Decimal(str(row["close"]))
                if c <= Decimal('0.0'):
                    continue
                ts_raw = row.get("timestamp")
                ts = datetime.now()
                if ts_raw:
                    try:
                        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        pass
                vol = Decimal(str(row.get("volume") or 0))
                out.append({
                    "open": Decimal(str(row["open"])),
                    "high": Decimal(str(row["high"])),
                    "low": Decimal(str(row["low"])),
                    "close": c,
                    "volume": vol,
                    "timestamp": ts,
                    "provider": str(row.get("provider", "")),
                })
            except Exception:
                continue
        if out:
            last = out[-1]
            self._last_volume = last.get("volume", Decimal('0.0'))
            if last.get("provider"):
                self._last_provider = last["provider"]
        return out

    def get_intraday(self, interval: str = "1m") -> Dict[str, Any]:
        d = self._get("intraday", interval=interval)
        if not d or d.get("close") is None:
            return {}
        try:
            c = Decimal(str(d["close"]))
            if c <= Decimal('0.0'):
                logger.warning(f"Relay returned non-positive intraday close: {c}")
                return {}
            ts_raw = d.get("timestamp")
            ts = datetime.now()
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass
            vol = Decimal(str(d.get("volume") or 0))
            self._last_volume = vol
            if d.get("provider"):
                self._last_provider = str(d["provider"])
            return {
                "open": Decimal(str(d["open"])),
                "high": Decimal(str(d["high"])),
                "low": Decimal(str(d["low"])),
                "close": c,
                "volume": vol,
                "timestamp": ts,
                "provider": self._last_provider,
            }
        except Exception as e:
            logger.warning(f"Failed to parse intraday: {e}")
            return {}

    def get_volume(self) -> Dict[str, Any]:
        d = self._get("volume")
        if not d or not isinstance(d, dict):
            return {}
        try:
            vol = Decimal(str(d.get("volume") or 0))
            vol24 = Decimal(str(d.get("volume_24h") or 0))
            self._last_volume = vol
            if d.get("provider"):
                self._last_provider = str(d["provider"])
            return {
                "volume": vol,
                "volume_24h": vol24,
                "provider": self._last_provider,
            }
        except Exception as e:
            logger.warning(f"Failed to parse volume: {e}")
            return {}

    def get_info(self) -> Dict[str, Any]:
        return {"name": self.active_symbol(), "currency": "USD"}

    def probe(self) -> Dict[str, Any]:
        d = self._get("price")
        return {
            "active_symbol": self.active_symbol(),
            "primary_symbol": self.symbol,
            "chain": list(self._chain),
            "chain_index": self._chain_index,
            "empty": (d is None or d.get("close") is None),
            "failure_count": self._failure_count,
            "fallback_count": self._fallback_count,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "relay_url": RELAY_URL,
            "provider": self._last_provider,
            "last_volume": str(self._last_volume),
        }

# ============================================================================
# CORE ÆEA ENGINE — Faithful Port of ÆEA.mq4
# ============================================================================
class AEEA_Engine:
    def __init__(self):
        self.state = AEI_CoreState()
        self.price_history: List[PriceData] = []
        self.ohlcv_history: List[Dict[str, Any]] = []
        self.feed = FeedClient(SYMBOL)
        self._last_price_update: Optional[datetime] = None
        self._bar_open: bool = True
        self._bar_index: int = 0
        self._running: bool = False
        self.chat_id: Optional[int] = None
        self.application = None
        self._last_signal_time: Optional[datetime] = None
        self._initialization_attempted: bool = False
        self._tick_log_counter: int = 0
        self._price_update_counter: int = 0
        self._bridge_publish_callback = None
        self._last_relay_warn: Optional[datetime] = None
        self._consecutive_zero_prices: int = 0
        self._indicator_populate_count: int = 0
        self._imbalance_fire_count: int = 0
        self._active_trailing_stop: Decimal = Decimal('0.0')
        self._active_trailing_tp: Decimal = Decimal('0.0')
        self._last_kronecker_bar: int = -1
        self._sSL: Decimal = Decimal('0.0')
        self._bSL: Decimal = Decimal('0.0')
        self._sTP: Decimal = Decimal('0.0')
        self._bTP: Decimal = Decimal('0.0')
        self._point_size: Decimal = symbol_point(SYMBOL)
        self.orders: List[Order] = []
        self._next_ticket: int = 1
        self._alert_delivery_enabled: bool = True
        self._last_telegram_toast_seq: int = 0
        self._last_dispatch_event: str = ""
        self._last_comment_line: str = ""
        self._last_projection_bar: int = -1

    def _com_price(self) -> Decimal:
        point = self._point_size if self._point_size > Decimal('0.0') else Decimal('0.00001')
        return COMMISSION * point

    def OnInit(self) -> None:
        logger.info("⚡ OnInit(): EA engine lifecycle beginning")
        self.OnReInit()
        logger.info("🟢 OnInit(): state reset to baseline")
        # E-4: seed the projection once on engine init so the TWA has a path
        # to scroll into before the first execution fires.
        try:
            self._project_arc_length(trigger="init")
        except Exception as e:
            logger.warning(f"Initial projection seed failed: {e}")

    def OnReInit(self) -> None:
        st = self.state
        saved_ohlcv = self.ohlcv_history.copy()
        saved_price = st.price
        saved_Price = st.Price
        saved_iH = st.iH
        saved_iL = st.iL
        saved_tick = st.tick
        saved_on_track = st.on_track_runs
        saved_on_stand = st.on_stand_runs
        saved_signal_history = list(st.signal_history)
        saved_chat_id = st.chat_id
        saved_webapp_uid = st.webapp_user_id
        saved_webapp_uname = st.webapp_username
        saved_webapp_verified = st.webapp_verified
        saved_auth_m = st.authoritative_m
        saved_auth_n = st.authoritative_n
        saved_auth_h = st.authoritative_h
        saved_m_now = st.m_now
        saved_n_now = st.n_now
        saved_lk_m = st.last_kronecker_m
        saved_lk_n = st.last_kronecker_n
        saved_lk_h = st.last_kronecker_h
        saved_lk_bar = self._last_kronecker_bar
        saved_comment = self._last_comment_line
        saved_provider = st.last_provider
        saved_volume = st.last_volume
        saved_inbound_msg = st.last_inbound_message_id

        st.KC = st.invert
        size = X_PERIOD - Y_START
        for i in range(13):
            st.cA[i] = [Decimal('0.0')] * size
            st.iA[i] = [Decimal('0.0')] * size
            st.kA[i] = [Decimal('0.0')] * size
            st.lA[i] = [Decimal('0.0')] * size
        st.IHKk = []
        st.IHKt = []
        st.RSI = []
        st.CCI = []
        st.MOM = []
        st.AD = []
        st.OBV = []
        st.Force = []
        st.MFI = []
        st.DeM = []
        st.RVIm = []
        st.AC = []
        st.StdDev = []
        st.ATR = []
        st.ADX = []
        st.Regime = ["sRange"] * size
        st.Premium = [Decimal('0.0')] * size
        st.Discount = [Decimal('0.0')] * size
        st.HH = [Decimal('0.0')] * size
        st.LL = [Decimal('0.0')] * size
        st.k = [False] * size
        st.l = [False] * size
        st.U = []
        st.R = True
        st.D = Decimal('0.0')
        st.E = Decimal('0.0')
        st.K = False
        st.Z = Y_START + 1
        st.z = Y_START + 1
        st.O = Y_START + 1
        st.o = Y_START + 1
        st.r = 0
        st.W = Y_START + 1
        st.w = Y_START + 1
        st.I = 0
        st.iI = 0
        st.J = 0
        st.iJ = 0
        st.ij = 0
        st.toll = 0
        st.tally = "   "
        st.tick_tock = False
        st.iZ = Y_START + 1
        st.iz = Y_START + 1
        st.iW = Y_START + 1
        st.iw = Y_START + 1
        st.iO = Y_START + 1
        st.io = Y_START + 1
        st.ir = 0
        st.S = X_PERIOD
        st.T = X_PERIOD
        st.X_scan = Y_START
        st.Y_scan = Y_START
        st.FG = False
        st.signature = False
        st.signal = Decimal('0.0')
        st.FVG = -1
        st.BL = []
        st.BL_type = []
        st.bottomLine = "   "
        st.bL = "   "
        st.count = 0
        st.fvg_anchor_map = {}
        st.lPass = Decimal('0.0')
        st.ilPass = Decimal('0.0')
        st.kPass = Decimal('0.0')
        st.ikPass = Decimal('0.0')
        st.execution_fired = False
        st.projection_path = []
        st.projection_meta = {}
        st.projection_computed_at = None
        st.projection_trigger = ""

        self.ohlcv_history = saved_ohlcv
        st.price = saved_price
        st.Price = saved_Price
        st.iH = saved_iH
        st.iL = saved_iL
        st.tick = saved_tick
        st.on_track_runs = saved_on_track
        st.on_stand_runs = saved_on_stand
        st.signal_history = saved_signal_history
        st.chat_id = saved_chat_id
        st.webapp_user_id = saved_webapp_uid
        st.webapp_username = saved_webapp_uname
        st.webapp_verified = saved_webapp_verified
        st.authoritative_m = saved_auth_m
        st.authoritative_n = saved_auth_n
        st.authoritative_h = saved_auth_h
        st.m_now = saved_m_now
        st.n_now = saved_n_now
        st.last_kronecker_m = saved_lk_m
        st.last_kronecker_n = saved_lk_n
        st.last_kronecker_h = saved_lk_h
        st.last_provider = saved_provider
        st.last_volume = saved_volume
        st.last_inbound_message_id = saved_inbound_msg
        self._last_kronecker_bar = saved_lk_bar
        self._last_comment_line = saved_comment
        self._last_projection_bar = -1

        logger.info("ReSet   ")

    def _unify(self, j: int) -> Tuple[Decimal, Decimal]:
        st = self.state
        if j < 1 or len(self.ohlcv_history) < j + 1:
            st.iATR = Decimal('50.0')
            st.iStdDev = Decimal('50.0')
            return st.iATR, st.iStdDev
        end = len(self.ohlcv_history)
        start = end - (j + 1)
        window = self.ohlcv_history[start:end]
        high_prices = [d["high"] for d in window]
        low_prices = [d["low"] for d in window]
        close_prices = [d["close"] for d in window]

        atr_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            atr_list.append(atr(sub_high, sub_low, sub_close, j))
        maxATR = max(atr_list) if atr_list else Decimal('0.0')
        minATR = min(atr_list) if atr_list else Decimal('0.0')
        rangeATR = maxATR - minATR
        if rangeATR != Decimal('0.0'):
            st.iATR = Decimal('100.0') * ((atr_list[0] - minATR) / rangeATR)
        else:
            st.iATR = Decimal('50.0')
        if len(st.ATR) <= j:
            st.ATR.extend([Decimal('0.0')] * (j + 1 - len(st.ATR)))
        st.ATR[j] = atr_list[0] if atr_list else Decimal('0.0')

        sd_list: List[Decimal] = []
        for i in range(j + 1):
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            sd_list.append(stddev(sub_close, j))
        maxSD = max(sd_list) if sd_list else Decimal('0.0')
        minSD = min(sd_list) if sd_list else Decimal('0.0')
        rangeSD = maxSD - minSD
        if rangeSD != Decimal('0.0'):
            st.iStdDev = Decimal('100.0') * ((sd_list[0] - minSD) / rangeSD)
        else:
            st.iStdDev = Decimal('50.0')
        if len(st.StdDev) <= j:
            st.StdDev.extend([Decimal('0.0')] * (j + 1 - len(st.StdDev)))
        st.StdDev[j] = sd_list[0] if sd_list else Decimal('0.0')
        return st.iATR, st.iStdDev

    def _normalize(self, j: int) -> None:
        st = self.state
        y = st.y
        if j < 1 or len(self.ohlcv_history) < j + 1:
            return
        end = len(self.ohlcv_history)
        window = self.ohlcv_history[end - (j + 1):end]
        close_prices = [d["close"] for d in window]
        open_prices = [d["open"] for d in window]
        high_prices = [d["high"] for d in window]
        low_prices = [d["low"] for d in window]
        volume_data = [d.get("volume", Decimal('0.0')) for d in window]

        if len(close_prices) >= j:
            upper, _, lower = bollinger_bands(close_prices, j, Decimal('2.0'))
            st.Suply = upper
            st.Demand = lower
        if len(close_prices) >= 2:
            upper_prev, _, lower_prev = bollinger_bands(close_prices[:-1], j, Decimal('2.0'))
            st.iSuply = upper_prev
            st.iDemand = lower_prev

        col_i = j - (y + 1)
        col_c = col_i
        if col_i < 0 or col_i >= len(st.iA[0]):
            return
        if col_c < 0 or col_c >= len(st.cA[0]):
            col_c = col_i

        adx_main_list: List[Decimal] = []
        plus_di_list: List[Decimal] = []
        minus_di_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            adx_main_list.append(self._compute_adx(sub_high, sub_low, sub_close, j))
            pd, md = self._compute_di(sub_high, sub_low, sub_close, j)
            plus_di_list.append(pd)
            minus_di_list.append(md)
        if adx_main_list:
            all_vals = adx_main_list + plus_di_list + minus_di_list
            maxADX = max(all_vals)
            minADX = min(all_vals)
            rangeADX = maxADX - minADX
            if rangeADX != Decimal('0.0'):
                iADX_val = abs(Decimal('100.0') * ((adx_main_list[0] - minADX) / rangeADX))
                cADX_val = abs(Decimal('100.0') * ((adx_main_list[1] - minADX) / rangeADX)) if len(adx_main_list) > 1 else iADX_val
                st.iA[0][col_i] = iADX_val
                st.cA[0][col_c] = cADX_val

        # D-MIN-5: MT4 iStochastic(NULL, 0, j, 3, jSO, MODE_SMA, 0, MODE_MAIN, 0)
        # with jSO = round(j * 3/5). The slowing parameter is now passed.
        jSO = int(round(j * 3.0 / 5.0))
        if jSO < 1:
            jSO = 1
        k_stoch, d_stoch = stochastic(high_prices, low_prices, close_prices, j, 3, jSO)
        st.iA[1][col_i] = (k_stoch + d_stoch) / Decimal('2.0')
        if len(close_prices) > 1:
            k_p, d_p = stochastic(high_prices[:-1], low_prices[:-1], close_prices[:-1], j, 3, jSO)
            st.cA[1][col_c] = (k_p + d_p) / Decimal('2.0')

        rvi_list: List[Decimal] = []
        for i in range(j + 1):
            sub_open = open_prices[:len(open_prices) - i] if i > 0 else open_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            rvi_list.append(self._compute_rvi(sub_open, sub_close, j))
        if rvi_list:
            maxRVI = max(rvi_list)
            minRVI = min(rvi_list)
            rangeRVI = maxRVI - minRVI
            if rangeRVI != Decimal('0.0'):
                st.iA[2][col_i] = Decimal('100.0') * ((rvi_list[0] - minRVI) / rangeRVI)
                st.cA[2][col_c] = Decimal('100.0') * ((rvi_list[1] - minRVI) / rangeRVI) if len(rvi_list) > 1 else st.iA[2][col_i]

        ac_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            ac_list.append(abs(self._compute_ac(sub_high, sub_low, sub_close, j)))
        if ac_list:
            maxAC = max(ac_list)
            minAC = min(ac_list)
            rangeAC = maxAC - minAC
            if rangeAC != Decimal('0.0'):
                st.iA[3][col_i] = abs(Decimal('100.0') * ((ac_list[0] - minAC) / rangeAC))
                st.cA[3][col_c] = abs(Decimal('100.0') * ((ac_list[1] - minAC) / rangeAC)) if len(ac_list) > 1 else st.iA[3][col_i]

        force_list: List[Decimal] = []
        for i in range(j + 1):
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            sub_vol = volume_data[:len(volume_data) - i] if i > 0 else volume_data
            force_list.append(self._compute_force(sub_close, sub_vol, j))
        if force_list:
            maxForce = max(force_list)
            minForce = min(force_list)
            rangeForce = maxForce - minForce
            if rangeForce != Decimal('0.0'):
                st.iA[4][col_i] = Decimal('100.0') * ((force_list[0] - minForce) / rangeForce)
                st.cA[4][col_c] = Decimal('100.0') * ((force_list[1] - minForce) / rangeForce) if len(force_list) > 1 else st.iA[4][col_i]

        obv_list: List[Decimal] = []
        for i in range(j + 1):
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            sub_vol = volume_data[:len(volume_data) - i] if i > 0 else volume_data
            obv_list.append(self._compute_obv(sub_close, sub_vol))
        if obv_list:
            maxOBV = max(obv_list)
            minOBV = min(obv_list)
            rangeOBV = maxOBV - minOBV
            if rangeOBV != Decimal('0.0'):
                st.iA[5][col_i] = Decimal('100.0') * ((obv_list[0] - minOBV) / rangeOBV)
                st.cA[5][col_c] = Decimal('100.0') * ((obv_list[1] - minOBV) / rangeOBV) if len(obv_list) > 1 else st.iA[5][col_i]

        ad_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            sub_vol = volume_data[:len(volume_data) - i] if i > 0 else volume_data
            ad_list.append(self._compute_ad(sub_high, sub_low, sub_close, sub_vol))
        if ad_list:
            maxAD = max(ad_list)
            minAD = min(ad_list)
            rangeAD = maxAD - minAD
            if rangeAD != Decimal('0.0'):
                st.iA[6][col_i] = Decimal('100.0') * ((ad_list[0] - minAD) / rangeAD)
                st.cA[6][col_c] = Decimal('100.0') * ((ad_list[1] - minAD) / rangeAD) if len(ad_list) > 1 else st.iA[6][col_i]

        mfi_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            sub_vol = volume_data[:len(volume_data) - i] if i > 0 else volume_data
            mfi_list.append(self._compute_mfi(sub_high, sub_low, sub_close, sub_vol, j))
        if mfi_list:
            maxMFI = max(mfi_list)
            minMFI = min(mfi_list)
            rangeMFI = maxMFI - minMFI
            if rangeMFI != Decimal('0.0'):
                st.iA[7][col_i] = Decimal('100.0') * ((mfi_list[0] - minMFI) / rangeMFI)
                st.cA[7][col_c] = Decimal('100.0') * ((mfi_list[1] - minMFI) / rangeMFI) if len(mfi_list) > 1 else st.iA[7][col_i]

        mom_list: List[Decimal] = []
        for i in range(j + 1):
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            mom_list.append(self._compute_momentum(sub_close, j))
        if mom_list:
            maxMOM = max(mom_list)
            minMOM = min(mom_list)
            rangeMOM = maxMOM - minMOM
            if rangeMOM != Decimal('0.0'):
                st.iA[8][col_i] = Decimal('100.0') * ((mom_list[0] - minMOM) / rangeMOM)
                st.cA[8][col_c] = Decimal('100.0') * ((mom_list[1] - minMOM) / rangeMOM) if len(mom_list) > 1 else st.iA[8][col_i]

        dem_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            dem_list.append(self._compute_demarker(sub_high, sub_low, j))
        if dem_list:
            maxDM = max(dem_list)
            minDM = min(dem_list)
            rangeDM = maxDM - minDM
            if rangeDM != Decimal('0.0'):
                st.iA[9][col_i] = Decimal('100.0') * ((dem_list[0] - minDM) / rangeDM)
                st.cA[9][col_c] = Decimal('100.0') * ((dem_list[1] - minDM) / rangeDM) if len(dem_list) > 1 else st.iA[9][col_i]

        wpr_now = self._compute_wpr(high_prices, low_prices, close_prices, j) + Decimal('100.0')
        st.iA[10][col_i] = wpr_now
        if len(close_prices) > 1:
            wpr_prev = self._compute_wpr(high_prices[:-1], low_prices[:-1], close_prices[:-1], j) + Decimal('100.0')
            st.cA[10][col_c] = wpr_prev

        cci_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            cci_list.append(self._compute_cci(sub_high, sub_low, sub_close, j))
        if cci_list:
            maxCCI = max(cci_list)
            minCCI = min(cci_list)
            rangeCCI = maxCCI - minCCI
            if rangeCCI != Decimal('0.0'):
                st.iA[11][col_i] = Decimal('100.0') * ((cci_list[0] - minCCI) / rangeCCI)
                st.cA[11][col_c] = Decimal('100.0') * ((cci_list[1] - minCCI) / rangeCCI) if len(cci_list) > 1 else st.iA[11][col_i]

        rsi_list: List[Decimal] = []
        for i in range(j + 1):
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            rsi_list.append(rsi(sub_close, j))
        if rsi_list:
            maxRSI = max(rsi_list)
            minRSI = min(rsi_list)
            rangeRSI = maxRSI - minRSI
            if rangeRSI != Decimal('0.0'):
                st.iA[12][col_i] = Decimal('100.0') * ((rsi_list[0] - minRSI) / rangeRSI)
                st.cA[12][col_c] = Decimal('100.0') * ((rsi_list[1] - minRSI) / rangeRSI) if len(rsi_list) > 1 else st.iA[12][col_i]

        kIHK = int(round(j / 2.0))
        tIHK = int(round((kIHK + 1.0) / 3.0))
        if kIHK < 1:
            kIHK = 1
        if tIHK < 1:
            tIHK = 1
        ihk_curr = ichimoku(high_prices, low_prices, close_prices, tIHK, kIHK, j)
        ssa: List[Decimal] = []
        ssb: List[Decimal] = []
        chikou: List[Decimal] = []
        tenkan_list: List[Decimal] = []
        kijun_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            if len(sub_close) < j:
                continue
            ihk_i = ichimoku(sub_high, sub_low, sub_close, tIHK, kIHK, j)
            ssa.append(ihk_i["senkou_a"])
            ssb.append(ihk_i["senkou_b"])
            tenkan_list.append(ihk_i["tenkan"])
            kijun_list.append(ihk_i["kijun"])
            c_idx = len(sub_close) - 1 - 26
            if c_idx >= 0:
                chikou.append(sub_close[c_idx])
        all_ihk: List[Decimal] = []
        all_ihk.extend(ssa)
        all_ihk.extend(ssb)
        all_ihk.extend(chikou)
        all_ihk.extend(tenkan_list)
        all_ihk.extend(kijun_list)
        if all_ihk:
            maxIHK = max(all_ihk)
            minIHK = min(all_ihk)
            rangeIHK = maxIHK - minIHK
            if rangeIHK != Decimal('0.0'):
                st.iIHKk = Decimal('100.0') * ((ihk_curr["kijun"] - minIHK) / rangeIHK)
                st.iIHKt = Decimal('100.0') * ((ihk_curr["tenkan"] - minIHK) / rangeIHK)
        else:
            st.iIHKk = ihk_curr["kijun"]
            st.iIHKt = ihk_curr["tenkan"]

    def _compute_adx(self, high, low, close, period: int) -> Decimal:
        if len(close) < 2 * period + 1 or period <= 0:
            return Decimal('50.0')
        n = len(close)
        trs_fwd: List[Decimal] = []
        pdm_fwd: List[Decimal] = []
        mdm_fwd: List[Decimal] = []
        start = n - 2 * period
        if start < 1:
            start = 1
        for i in range(start, n):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1])
            )
            trs_fwd.append(tr)
            up_move = high[i] - high[i - 1]
            dn_move = low[i - 1] - low[i]
            pdm_fwd.append(up_move if up_move > dn_move and up_move > 0 else Decimal('0.0'))
            mdm_fwd.append(dn_move if dn_move > up_move and dn_move > 0 else Decimal('0.0'))
        if len(trs_fwd) < 2 * period:
            return Decimal('50.0')
        atr_k = sum(trs_fwd[:period]) / Decimal(period)
        plus_dm_k = sum(pdm_fwd[:period]) / Decimal(period)
        minus_dm_k = sum(mdm_fwd[:period]) / Decimal(period)
        dx_series: List[Decimal] = []
        plus_di = (Decimal('100.0') * plus_dm_k / atr_k) if atr_k != Decimal('0.0') else Decimal('0.0')
        minus_di = (Decimal('100.0') * minus_dm_k / atr_k) if atr_k != Decimal('0.0') else Decimal('0.0')
        di_sum = plus_di + minus_di
        if di_sum == Decimal('0.0'):
            dx_series.append(Decimal('0.0'))
        else:
            dx_series.append(Decimal('100.0') * abs(plus_di - minus_di) / di_sum)
        for k in range(period, len(trs_fwd)):
            atr_k = (atr_k * Decimal(period - 1) + trs_fwd[k]) / Decimal(period)
            plus_dm_k = (plus_dm_k * Decimal(period - 1) + pdm_fwd[k]) / Decimal(period)
            minus_dm_k = (minus_dm_k * Decimal(period - 1) + mdm_fwd[k]) / Decimal(period)
            plus_di = (Decimal('100.0') * plus_dm_k / atr_k) if atr_k != Decimal('0.0') else Decimal('0.0')
            minus_di = (Decimal('100.0') * minus_dm_k / atr_k) if atr_k != Decimal('0.0') else Decimal('0.0')
            di_sum = plus_di + minus_di
            if di_sum == Decimal('0.0'):
                dx_series.append(Decimal('0.0'))
            else:
                dx_series.append(Decimal('100.0') * abs(plus_di - minus_di) / di_sum)
        if len(dx_series) < period:
            return dx_series[-1] if dx_series else Decimal('50.0')
        adx_val = sum(dx_series[:period]) / Decimal(period)
        for k in range(period, len(dx_series)):
            adx_val = (adx_val * Decimal(period - 1) + dx_series[k]) / Decimal(period)
        return adx_val

    def _compute_di(self, high, low, close, period: int) -> Tuple[Decimal, Decimal]:
        if len(close) < period + 1 or period <= 0:
            return Decimal('50.0'), Decimal('50.0')
        trs: List[Decimal] = []
        plus_dm: List[Decimal] = []
        minus_dm: List[Decimal] = []
        for i in range(1, period + 1):
            tr = max(
                high[-i] - low[-i],
                abs(high[-i] - close[-i - 1]),
                abs(low[-i] - close[-i - 1])
            )
            trs.append(tr)
            up_move = high[-i] - high[-i - 1]
            dn_move = low[-i - 1] - low[-i]
            plus_dm.append(up_move if up_move > dn_move and up_move > 0 else Decimal('0.0'))
            minus_dm.append(dn_move if dn_move > up_move and dn_move > 0 else Decimal('0.0'))
        if len(trs) < period:
            return Decimal('50.0'), Decimal('50.0')
        atr_k = sum(trs[:period]) / Decimal(period)
        plus_dm_k = sum(plus_dm[:period]) / Decimal(period)
        minus_dm_k = sum(minus_dm[:period]) / Decimal(period)
        plus_di = (Decimal('100.0') * plus_dm_k / atr_k) if atr_k != Decimal('0.0') else Decimal('0.0')
        minus_di = (Decimal('100.0') * minus_dm_k / atr_k) if atr_k != Decimal('0.0') else Decimal('0.0')
        return plus_di, minus_di

    def _compute_rvi(self, open_prices, close_prices, period: int) -> Decimal:
        if len(close_prices) < period + 3 or period <= 0:
            return Decimal('50.0')
        n = len(close_prices)
        num_series: List[Decimal] = []
        den_series: List[Decimal] = []
        for i in range(3, n):
            num_i = (
                (close_prices[i] - open_prices[i])
                + Decimal('2.0') * (close_prices[i - 1] - open_prices[i - 1])
                + Decimal('2.0') * (close_prices[i - 2] - open_prices[i - 2])
                + (close_prices[i - 3] - open_prices[i - 3])
            )
            den_i = (
                abs(close_prices[i] - open_prices[i])
                + Decimal('2.0') * abs(close_prices[i - 1] - open_prices[i - 1])
                + Decimal('2.0') * abs(close_prices[i - 2] - open_prices[i - 2])
                + abs(close_prices[i - 3] - open_prices[i - 3])
            )
            num_series.append(num_i)
            den_series.append(den_i)
        if len(num_series) < period:
            return Decimal('50.0')
        num_sma = sum(num_series[-period:]) / Decimal(period)
        den_sma = sum(den_series[-period:]) / Decimal(period)
        if den_sma == Decimal('0.0'):
            return Decimal('50.0')
        return num_sma / den_sma

    def _compute_ac(self, high, low, close, period: int) -> Decimal:
        if len(close) < 40 or period <= 0:
            return Decimal('0.0')
        window = len(close)
        if window < 40:
            return Decimal('0.0')
        median = [(high[i] + low[i]) / Decimal('2.0') for i in range(window)]
        def sma_local(data, p):
            if len(data) < p or p <= 0:
                return Decimal('0.0')
            return sum(data[-p:]) / Decimal(p)
        ao_now = sma_local(median, 5) - sma_local(median, 34)
        ao_series: List[Decimal] = []
        for i in range(min(5, len(median))):
            sub = median[:len(median) - i] if i > 0 else median
            ao_series.append(sma_local(sub, 5) - sma_local(sub, 34))
        return ao_now - sma_local(ao_series, 5)

    def _compute_force(self, close, volume, period: int) -> Decimal:
        if len(close) < period + 1 or period <= 0:
            return Decimal('0.0')
        forces = []
        for i in range(1, period + 1):
            forces.append(volume[-i] * (close[-i] - close[-i - 1]))
        return sum(forces) / Decimal(period)

    def _compute_obv(self, close, volume) -> Decimal:
        if len(close) < 2:
            return Decimal('0.0')
        obv = Decimal('0.0')
        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv += volume[i] if i < len(volume) else Decimal('0.0')
            elif close[i] < close[i - 1]:
                obv -= volume[i] if i < len(volume) else Decimal('0.0')
        return obv

    def _compute_ad(self, high, low, close, volume) -> Decimal:
        if len(close) < 2:
            return Decimal('0.0')
        ad = Decimal('0.0')
        for i in range(len(close)):
            hl = high[i] - low[i]
            if hl > Decimal('0.0'):
                mfv = ((close[i] - low[i]) - (high[i] - close[i])) / hl * (volume[i] if i < len(volume) else Decimal('0.0'))
                ad += mfv
        return ad

    def _compute_mfi(self, high, low, close, volume, period: int) -> Decimal:
        if len(close) < period + 1 or period <= 0:
            return Decimal('50.0')
        pos_flow, neg_flow = Decimal('0.0'), Decimal('0.0')
        for i in range(1, period + 1):
            tp = (high[-i] + low[-i] + close[-i]) / Decimal('3.0')
            tp_prev = (high[-i - 1] + low[-i - 1] + close[-i - 1]) / Decimal('3.0')
            mf = tp * volume[-i]
            if tp > tp_prev:
                pos_flow += mf
            elif tp < tp_prev:
                neg_flow += mf
        if neg_flow == Decimal('0.0'):
            if pos_flow == Decimal('0.0'):
                return Decimal('50.0')
            return Decimal('100.0')
        mr = pos_flow / neg_flow
        return Decimal('100.0') - (Decimal('100.0') / (Decimal('1.0') + mr))

    def _compute_momentum(self, close, period: int) -> Decimal:
        if len(close) < period + 1 or period <= 0:
            return Decimal('0.0')
        return close[-1] - close[-period - 1]

    def _compute_demarker(self, high, low, period: int) -> Decimal:
        if len(high) < period + 1 or period <= 0:
            return Decimal('50.0')
        demax, demin = Decimal('0.0'), Decimal('0.0')
        for i in range(1, period + 1):
            if high[-i] > high[-i - 1]:
                demax += high[-i] - high[-i - 1]
            if low[-i] < low[-i - 1]:
                demin += low[-i - 1] - low[-i]
        total = demax + demin
        if total == Decimal('0.0'):
            return Decimal('50.0')
        return Decimal('100.0') * demax / total

    def _compute_wpr(self, high, low, close, period: int) -> Decimal:
        if len(close) < period or period <= 0:
            return Decimal('0.0')
        hh = max(high[-period:])
        ll = min(low[-period:])
        rng = hh - ll
        if rng == Decimal('0.0'):
            return Decimal('0.0')
        return Decimal('-100.0') * (hh - close[-1]) / rng

    def _compute_cci(self, high, low, close, period: int) -> Decimal:
        if len(close) < period or period <= 0:
            return Decimal('0.0')
        tp = [(high[-i] + low[-i] + close[-i]) / Decimal('3.0') for i in range(1, period + 1)]
        sma_tp = sum(tp) / Decimal(period)
        mad = sum(abs(x - sma_tp) for x in tp) / Decimal(period)
        if mad == Decimal('0.0'):
            return Decimal('0.0')
        return (tp[0] - sma_tp) / (Decimal('0.015') * mad)

    def _M(self, j: int) -> int:
        st = self.state
        y = st.y
        m = 0
        idx_i = j - (y + 1)
        idx_c = idx_i
        if idx_i < 0 or idx_i >= len(st.iA[0]):
            return 0
        if idx_c < 0 or idx_c >= len(st.cA[0]):
            idx_c = idx_i
        f_plus_gf = F_PLUS_GF_D
        g_minus_gf = G_MINUS_GF_D
        hh_val = st.HH[idx_i] if idx_i < len(st.HH) else Decimal('0.0')
        for i in range(13):
            iA_val = st.iA[i][idx_i]
            cA_val = st.cA[i][idx_c]
            kA_val = st.kA[i][idx_c]
            if st.Price > hh_val:
                if (iA_val > f_plus_gf) or (cA_val < kA_val):
                    m += 1
            elif st.price > hh_val:
                if (iA_val > f_plus_gf) or (iA_val < kA_val):
                    m += 1
            elif iA_val > f_plus_gf:
                m += 1
        adx_val = st.iA[0][idx_i]
        if (adx_val > f_plus_gf) or (adx_val < g_minus_gf):
            m += 1
        if (st.iIHKt > f_plus_gf) and (st.iIHKk > f_plus_gf):
            m += 1
        if st.Price > hh_val:
            for i in range(13):
                if idx_c < len(st.kA[i]) and idx_c < len(st.cA[i]):
                    st.kA[i][idx_c] = st.cA[i][idx_c]
            if idx_i < len(st.HH):
                st.HH[idx_i] = st.Price
        return m

    def _N(self, j: int) -> int:
        st = self.state
        y = st.y
        n = 0
        idx_i = j - (y + 1)
        idx_c = idx_i
        if idx_i < 0 or idx_i >= len(st.iA[0]):
            return 0
        if idx_c < 0 or idx_c >= len(st.cA[0]):
            idx_c = idx_i
        f_plus_gf = F_PLUS_GF_D
        g_minus_gf = G_MINUS_GF_D
        ll_val = st.LL[idx_i] if idx_i < len(st.LL) else Decimal('0.0')
        for i in range(13):
            iA_val = st.iA[i][idx_i]
            cA_val = st.cA[i][idx_c]
            lA_val = st.lA[i][idx_c]
            if st.Price < ll_val:
                if (iA_val < g_minus_gf) or (cA_val > lA_val):
                    n += 1
            elif st.price < ll_val:
                if (iA_val < g_minus_gf) or (iA_val > lA_val):
                    n += 1
            elif iA_val < g_minus_gf:
                n += 1
        adx_val = st.iA[0][idx_i]
        if (adx_val > f_plus_gf) or (adx_val < g_minus_gf):
            n += 1
        if (st.iIHKt < g_minus_gf) and (st.iIHKk < g_minus_gf):
            n += 1
        if st.Price < ll_val:
            for i in range(13):
                if idx_c < len(st.lA[i]) and idx_c < len(st.cA[i]):
                    st.lA[i][idx_c] = st.cA[i][idx_c]
            if idx_i < len(st.LL):
                st.LL[idx_i] = st.Price
        return n

    def _H(self, j: int) -> None:
        st = self.state
        idx = j - (st.y + 1)
        if idx < 0 or idx >= len(st.k):
            return
        m = self._M(j)
        st.m = m
        st.k[idx] = (m >= 12)
        st.authoritative_m = m
        st.authoritative_h = j
        st.last_kronecker_m = m
        st.last_kronecker_h = j
        st.m_now = m
        st.m = 0
        if st.k[idx]:
            logger.info(f"🔺 H() set k[{idx}] = True (m={m} >= 12) at bar j={j}")

    def _L(self, j: int) -> None:
        st = self.state
        idx = j - (st.y + 1)
        if idx < 0 or idx >= len(st.l):
            return
        n = self._N(j)
        st.n = n
        st.l[idx] = (n >= 12)
        st.authoritative_n = n
        st.authoritative_h = j
        st.last_kronecker_n = n
        st.last_kronecker_h = j
        st.n_now = n
        st.n = 0
        if st.l[idx]:
            logger.info(f"🔻 L() set l[{idx}] = True (n={n} >= 12) at bar j={j}")

    def _F(self, j: int, iH: Decimal, iL: Decimal) -> None:
        st = self.state
        y = st.y
        idx = j - (y + 1)
        if idx < 0 or idx >= len(st.k):
            return
        self._normalize(j)
        st.k[idx] = False
        st.l[idx] = False
        st.HH[idx] = iH
        st.LL[idx] = iL
        st.Premium[idx] = iH
        st.Discount[idx] = iL
        idx_c = idx
        if idx_c < 0 or idx_c >= len(st.cA[0]):
            idx_c = idx
        for i in range(13):
            if idx_c < len(st.kA[i]) and idx_c < len(st.cA[i]):
                st.kA[i][idx_c] = st.cA[i][idx_c]
                st.lA[i][idx_c] = st.cA[i][idx_c]
        if st.R and st.FG:
            target_size = X_PERIOD - Y_START
            while len(st.U) < target_size:
                st.U.append(False)
            if idx < len(st.U):
                st.U[idx] = True
            V = 0
            for i in range(y + 1, X_PERIOD):
                ui = i - (y + 1)
                if 0 <= ui < len(st.U) and st.U[ui]:
                    V += 1
            if V == target_size:
                st.R = False

    def _G(self) -> None:
        st = self.state
        y = st.y
        if len(self.ohlcv_history) < 2:
            return
        H = self.ohlcv_history[-2]["high"]
        L = self.ohlcv_history[-2]["low"]
        for j in range(y + 1, st.h + 1):
            if j == X_PERIOD:
                break
            idx = j - (y + 1)
            if idx < 0 or idx >= len(st.k):
                continue
            st.k[idx] = False
            st.l[idx] = False
            st.HH[idx] = H
            st.LL[idx] = L
            st.Premium[idx] = H
            st.Discount[idx] = L
            idx_c = idx
            if idx_c < 0 or idx_c >= len(st.cA[0]):
                idx_c = idx
            for i in range(13):
                if idx_c < len(st.kA[i]) and idx_c < len(st.cA[i]):
                    st.kA[i][idx_c] = st.cA[i][idx_c]
                    st.lA[i][idx_c] = st.cA[i][idx_c]

    def _J(self) -> None:
        st = self.state
        if st.I == st.iZ:
            st.J = st.iW
        elif st.I == st.iW:
            st.J = st.iZ
        if st.iI == st.iz:
            st.iJ = st.iw
        elif st.iI == st.iw:
            st.iJ = st.iz

    def _O(self, inp: int, inp0: int, inp1: int, which: str = "C") -> None:
        return

    def _R(self, j: int) -> None:
        st = self.state
        if j <= st.J:
            st.O = j
            st.iO = j
        if (j > st.J) and (j < st.r):
            st.O = j
            st.iO = j
            st.r = j
        elif j > st.J:
            st.r = j
        if j <= st.iJ:
            st.o = j
            st.io = j
        if (j > st.iJ) and (j < st.ir):
            st.o = j
            st.io = j
            st.ir = j
        elif j > st.iJ:
            st.ir = j

    def _KC(self) -> None:
        st = self.state
        if st.E != Decimal('0.0') and (not st.A) and (not st.B) and st.v and st.signal < st.E:
            st.invert = not st.KC
        if st.D != Decimal('0.0') and (not st.B) and (not st.A) and st.u and st.signal > st.D:
            st.invert = not st.KC

    def _on_hold(self, inp: int, inp0: str, inp1: str) -> bool:
        st = self.state
        idx = inp - (st.y + 1)
        if idx < 0 or idx >= len(st.Regime):
            return False
        return st.Regime[idx] == inp0 or st.Regime[idx] == inp1

    def _on_fire(self, inp: int, inp0: str, inp1: str) -> bool:
        st = self.state
        idx = inp - (st.y + 1)
        if idx < 0 or idx >= len(st.Regime):
            return False
        return st.Regime[idx] != inp0 and st.Regime[idx] != inp1

    def _on_point(self) -> None:
        st = self.state
        y = st.y
        for j in range(y + 1, X_PERIOD):
            idx = j - (y + 1)
            if idx < 0 or idx >= len(st.Regime):
                break
            self._unify(j)
            self._normalize(j)
            if st.iStdDev < Decimal('50.0') and st.iATR > Decimal('50.0'):
                if st.Regime[idx] != "Stable":
                    if st.FG:
                        self._H(j)
                        self._L(j)
                    if self._on_fire(j, "sVolatile", "tVolatile"):
                        st.Regime[idx] = "sVolatile"
            elif st.iStdDev < Decimal('50.0') and st.iATR < Decimal('50.0'):
                if st.Regime[idx] != "Stable":
                    self._R(j)
                    if st.FG:
                        self._H(j)
                        self._L(j)
                    if self._on_fire(j, "sRange", "tRange"):
                        st.Regime[idx] = "sRange"
            elif self._on_fire(j, "sTrend", "tTrend"):
                st.Regime[idx] = "sTrend"

    def _on_bar(self) -> None:
        st = self.state
        y = st.y
        for j in range(y + 1, X_PERIOD):
            idx = j - (y + 1)
            if idx < 0 or idx >= len(st.Regime):
                break
            self._unify(j)
            self._normalize(j)
            if st.iStdDev < Decimal('50.0') and st.iATR > Decimal('50.0'):
                if st.Regime[idx] != "Stable":
                    if st.Regime[idx] != "tVolatile":
                        self._F(j, st.iH, st.iL)
                        if st.FG:
                            self._H(j)
                            self._L(j)
                        st.Regime[idx] = "tVolatile"
            elif st.iStdDev < Decimal('50.0') and st.iATR < Decimal('50.0'):
                if st.Regime[idx] != "Stable":
                    self._R(j)
                    if st.FG:
                        self._H(j)
                        self._L(j)
                    if st.Regime[idx] != "tRange":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tRange"
            elif (st.Regime[idx] != "tTrend" and st.Regime[idx] != "sTrend"
                  and idx < len(st.LL) and idx < len(st.Discount)
                  and idx < len(st.HH) and idx < len(st.Premium)
                  and st.LL[idx] < st.Discount[idx]
                  and st.HH[idx] > st.Premium[idx]):
                st.Regime[idx] = "Stable"
            else:
                if st.Regime[idx] != "tTrend":
                    self._F(j, st.iH, st.iL)
                    st.Regime[idx] = "tTrend"

        if len(self.ohlcv_history) >= y + 1:
            close_prices = [d["close"] for d in self.ohlcv_history[-y - 1:]]
            st.Stock, _, st.Sale = bollinger_bands(close_prices, y)
            if len(close_prices) > 1:
                st.iStock, _, st.iSale = bollinger_bands(close_prices[:-1], y)
            else:
                st.iStock = st.Stock
                st.iSale = st.Sale

        if len(self.ohlcv_history) >= 3:
            st.iopen = self.ohlcv_history[-3]["open"]
            st.iPrice = self.ohlcv_history[-3]["close"]
        elif len(self.ohlcv_history) >= 2:
            st.iopen = self.ohlcv_history[-2]["open"]
            st.iPrice = self.ohlcv_history[-2]["close"]
        elif len(self.ohlcv_history) >= 1:
            st.iopen = self.ohlcv_history[-1]["open"]
            st.iPrice = self.ohlcv_history[-1]["close"]

        st.lPass = st.Price if st.Price < st.open else st.open
        st.ilPass = st.iPrice if st.iPrice < st.iopen else st.iopen
        st.kPass = st.Price if st.Price > st.open else st.open
        st.ikPass = st.iPrice if st.iPrice > st.iopen else st.iopen

        self._execute_kronecker_block()

    def _execute_kronecker_block(self) -> None:
        st = self.state
        fg = ""
        if st.signal == Decimal('0.0'):
            return
        # Pre-init guard: if the engine has not yet been seeded by
        # _force_initialization(), st.Price and st.price may both be zero,
        # and the threshold comparisons below would spuriously satisfy the
        # `<= 0` branches, firing _A()/_B() before any real price exists.
        if st.price <= Decimal('0.0') or st.Price <= Decimal('0.0'):
            return

        com_price = self._com_price()

        if st.price >= st.signal + com_price:
            logger.info(f"🔵 Long: {st.price}")
            if st.count == 0 and st.tally == "Sell":
                st.count += 1
            st.tally = "Buy"
        if st.price <= st.signal - com_price:
            logger.info(f"🔴 Short: {st.price}")
            if st.count == 0 and st.tally == "Buy":
                st.count += 1
            st.tally = "Sell"

        if st.tick_tock:
            return

        hh_idx = MIN_PERIOD - (st.y + 1)
        ll_idx = MIN_PERIOD - (st.y + 1)
        hh_anchor = st.HH[hh_idx] if 0 <= hh_idx < len(st.HH) else Decimal('0.0')
        ll_anchor = st.LL[ll_idx] if 0 <= ll_idx < len(st.LL) else Decimal('0.0')

        bullish_coherence = (
            (
                (st.Price > st.signal)
                or (st.Price > st.ikPass)
                or (st.price > st.kPass)
            )
            and (
                (
                    st.iC == st.Cc
                    and st.Price > hh_anchor
                )
                or (
                    st.jC == st.Cc
                    and st.Price >= ll_anchor
                    and (
                        (st.open >= st.Stock)
                        or (st.Price >= st.Stock)
                        or (st.open >= st.iStock)
                        or (st.Price >= st.iStock)
                    )
                )
            )
        )
        if bullish_coherence:
            logger.info(f"🟢 Buy: {st.price}")
            if st.toll == 0 and st.tally == "Sell":
                st.toll += 1
            if st.Price > st.signal:
                fg = "Up"
            st.tally = "Buy"

        bearish_coherence = (
            (
                (st.Price < st.signal)
                or (st.Price < st.ilPass)
                or (st.price < st.lPass)
            )
            and (
                (
                    st.jC == st.Cc
                    and st.Price < ll_anchor
                )
                or (
                    st.iC == st.Cc
                    and st.Price <= hh_anchor
                    and (
                        (st.open <= st.Sale)
                        or (st.Price <= st.Sale)
                        or (st.open <= st.iSale)
                        or (st.Price <= st.iSale)
                    )
                )
            )
        )
        if bearish_coherence:
            logger.info(f"🔴 Sell: {st.price}")
            if st.toll == 0 and st.tally == "Buy":
                st.toll += 1
            if st.Price < st.signal:
                fg = "Down"
            st.tally = "Sell"

        if st.toll == 1 and (st.tally == "Buy" or fg == "Up"):
            logger.info(f"🔷 Diamond {fg}")
            self._last_dispatch_event = "Diamond"
            self._dispatch_diamond_subblock(fg)
            st.signal = Decimal('0.0')
            st.toll = 0
            st.tally = ""
            st.GF = True
            st.signature = True
            st.execution_fired = True
            return

        if st.toll == 1 and (st.tally == "Sell" or fg == "Down"):
            logger.info(f"🔻 Ruby {fg}")
            self._last_dispatch_event = "Ruby"
            self._dispatch_ruby_subblock(fg)
            st.signal = Decimal('0.0')
            st.toll = 0
            st.tally = ""
            st.GF = True
            st.signature = True
            st.execution_fired = True
            return

        if st.count == 1 and (st.tally == "Buy" or fg == "Up"):
            logger.info(f"🔷 Diamond {fg}")
            self._last_dispatch_event = "Diamond"
            self._dispatch_hawk_subblock(fg)
            st.count = 0
            st.tally = ""
            st.GF = True
            st.signature = True
            st.execution_fired = True
            return

        if st.count == 1 and (st.tally == "Sell" or fg == "Down"):
            logger.info(f"🔻 Ruby {fg}")
            self._last_dispatch_event = "Ruby"
            self._dispatch_dove_subblock(fg)
            st.count = 0
            st.tally = ""
            st.GF = True
            st.signature = True
            st.execution_fired = True
            return

    def _dispatch_diamond_subblock(self, fg: str) -> None:
        st = self.state
        if (st.prime == 0 and st.dime == 0) and fg == "Up":
            st.dime = 0; st.mem = 0
            self._B(st.price)
            if st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🐂 Bull")
            self._emit_execution_toast("Bull", st.price, "BUY", st.lOrder_id, fg)
            self._Top(emit_toast=False)
            st.E = st.price
        elif ((st.mem == 0 and st.dime == 0) or st.prime == 0) and fg == "" and st.price > st.signal:
            st.dime = 0; st.mem = 0
            self._B(st.price)
            if st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🐂 Bull")
            self._emit_execution_toast("Bull", st.price, "BUY", st.lOrder_id, fg)
            self._Top(emit_toast=False)
            st.E = st.price
        elif (st.prime == 1 or (st.mem == 0 and st.dime == 0)) and fg == "Up" and st.price > st.signal:
            st.dime = 0; st.mem = 0
            self._B(st.price)
            if st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🐂 Bull")
            self._emit_execution_toast("Bull", st.price, "BUY", st.lOrder_id, fg)
            self._Top(emit_toast=False)
            st.E = st.price
        elif ((st.mem == 0 and st.dime == 0) or st.prime == 1) and fg == "" and st.price > st.signal:
            st.dime = 0; st.mem = 0
            self._B(st.price)
            if st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🐂 Bull")
            self._emit_execution_toast("Bull", st.price, "BUY", st.lOrder_id, fg)
            self._Top(emit_toast=False)
            st.E = st.price
        elif st.Price > st.signal and (st.mem == 0 and st.dime == 0):
            if st.safety:
                self._B(st.price)
                if st.C: self._P(st.price)
                else: self._Q(st.price)
                logger.info("🥃 Whisky")
                self._emit_execution_toast("Whisky", st.price, "BUY", st.lOrder_id, fg)
                self._Top(emit_toast=False)
                st.E = st.price
            else:
                logger.info("🥃 Whisky")
                self._emit_execution_toast("Whisky", st.price, "NONE", -1, fg)
                self._Top(emit_toast=False)
                st.E = st.price
                if not st.safety: st.safety = True
        elif st.mem == 1 or st.dime == 1:
            self._on_log()
            if st.safety:
                self._A(st.price)
                if not st.C: self._P(st.price)
                else: self._Q(st.price)
                logger.info("🍷 Wine")
                self._emit_execution_toast("Wine", st.price, "SELL", st.kOrder_id, fg)
                self._Bott(emit_toast=False)
                st.D = st.price
            else:
                logger.info("🍷 Wine")
                self._emit_execution_toast("Wine", st.price, "NONE", -1, fg)
                self._Bott(emit_toast=False)
                st.D = st.price
                if not st.safety: st.safety = True
        else:
            logger.info("🍷 Wine")
            self._emit_execution_toast("Wine", st.price, "NONE", -1, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
            if not st.safety: st.safety = True
        # E-4: execution-gated projection refresh. Diamond-family executions
        # (Bull, Whisky, Wine) recompute the forward path so the projected TP
        # reflects the directional decision that just fired.
        try:
            self._project_arc_length(trigger="execution")
        except Exception as e:
            logger.warning(f"Projection refresh (diamond) failed: {e}")

    def _dispatch_ruby_subblock(self, fg: str) -> None:
        st = self.state
        if fg == "Down" and (st.prime == 1 and st.dime == 1):
            st.dime = 1; st.mem = 1
            self._A(st.price)
            if not st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🐻 Bear")
            self._emit_execution_toast("Bear", st.price, "SELL", st.kOrder_id, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
        elif ((st.mem == 1 and st.dime == 1) or st.prime == 1) and fg == "" and st.price < st.signal:
            st.dime = 1; st.mem = 1
            self._A(st.price)
            if not st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🐻 Bear")
            self._emit_execution_toast("Bear", st.price, "SELL", st.kOrder_id, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
        elif st.price < st.signal and fg == "Down" and (st.prime == 0 or (st.mem == 1 and st.dime == 1)):
            st.dime = 1; st.mem = 1
            self._A(st.price)
            if not st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🐻 Bear")
            self._emit_execution_toast("Bear", st.price, "SELL", st.kOrder_id, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
        elif ((st.mem == 1 and st.dime == 1) or st.prime == 0) and fg == "" and st.price < st.signal:
            st.dime = 1; st.mem = 1
            self._A(st.price)
            if not st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🐻 Bear")
            self._emit_execution_toast("Bear", st.price, "SELL", st.kOrder_id, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
        elif st.Price < st.signal and (st.mem == 1 and st.dime == 1):
            if st.safety:
                self._A(st.price)
                if not st.C: self._P(st.price)
                else: self._Q(st.price)
                logger.info("🍷 Wine")
                self._emit_execution_toast("Wine", st.price, "SELL", st.kOrder_id, fg)
                self._Bott(emit_toast=False)
                st.D = st.price
            else:
                logger.info("🍷 Wine")
                self._emit_execution_toast("Wine", st.price, "NONE", -1, fg)
                self._Bott(emit_toast=False)
                st.D = st.price
                if not st.safety: st.safety = True
        elif st.mem == 0 or st.dime == 0:
            self._on_log()
            if st.safety:
                self._B(st.price)
                if st.C: self._P(st.price)
                else: self._Q(st.price)
                logger.info("🥃 Whisky")
                self._emit_execution_toast("Whisky", st.price, "BUY", st.lOrder_id, fg)
                self._Top(emit_toast=False)
                st.E = st.price
            else:
                logger.info("🥃 Whisky")
                self._emit_execution_toast("Whisky", st.price, "NONE", -1, fg)
                self._Top(emit_toast=False)
                st.E = st.price
                if not st.safety: st.safety = True
        else:
            logger.info("🥃 Whisky")
            self._emit_execution_toast("Whisky", st.price, "NONE", -1, fg)
            self._Top(emit_toast=False)
            st.E = st.price
            if not st.safety: st.safety = True
        # E-4: execution-gated projection refresh for the Ruby family.
        try:
            self._project_arc_length(trigger="execution")
        except Exception as e:
            logger.warning(f"Projection refresh (ruby) failed: {e}")

    def _dispatch_hawk_subblock(self, fg: str) -> None:
        st = self.state
        if (st.prime == 0 and st.dime == 0) and fg == "Up":
            st.dime = 0; st.mem = 0
            self._B(st.price)
            if st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🦅 Hawk")
            self._emit_execution_toast("Hawk", st.price, "BUY", st.lOrder_id, fg)
            self._Top(emit_toast=False)
            st.E = st.price
        elif ((st.mem == 0 and st.dime == 0) or st.prime == 0) and fg == "" and st.price > st.signal:
            st.dime = 0; st.mem = 0
            self._B(st.price)
            if st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🦅 Hawk")
            self._emit_execution_toast("Hawk", st.price, "BUY", st.lOrder_id, fg)
            self._Top(emit_toast=False)
            st.E = st.price
        elif (st.prime == 1 or (st.mem == 0 and st.dime == 0)) and fg == "Up" and st.price > st.signal:
            st.dime = 0; st.mem = 0
            self._B(st.price)
            if st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🦅 Hawk")
            self._emit_execution_toast("Hawk", st.price, "BUY", st.lOrder_id, fg)
            self._Top(emit_toast=False)
            st.E = st.price
        elif ((st.mem == 0 and st.dime == 0) or st.prime == 1) and fg == "" and st.price > st.signal:
            st.dime = 0; st.mem = 0
            self._B(st.price)
            if st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🦅 Hawk")
            self._emit_execution_toast("Hawk", st.price, "BUY", st.lOrder_id, fg)
            self._Top(emit_toast=False)
            st.E = st.price
        elif st.Price > st.signal and (st.mem == 0 and st.dime == 0):
            if st.safety:
                self._B(st.price)
                if st.C: self._P(st.price)
                else: self._Q(st.price)
                logger.info("💧 Watter")
                self._emit_execution_toast("Watter", st.price, "BUY", st.lOrder_id, fg)
                self._Top(emit_toast=False)
                st.E = st.price
            else:
                logger.info("💧 Watter")
                self._emit_execution_toast("Watter", st.price, "NONE", -1, fg)
                self._Top(emit_toast=False)
                st.E = st.price
                if not st.safety: st.safety = True
        elif st.mem == 1 or st.dime == 1:
            self._on_log()
            if st.safety:
                self._A(st.price)
                if not st.C: self._P(st.price)
                else: self._Q(st.price)
                logger.info("🩸 Blood")
                self._emit_execution_toast("Blood", st.price, "SELL", st.kOrder_id, fg)
                self._Bott(emit_toast=False)
                st.D = st.price
            else:
                logger.info("🩸 Blood")
                self._emit_execution_toast("Blood", st.price, "NONE", -1, fg)
                self._Bott(emit_toast=False)
                st.D = st.price
                if not st.safety: st.safety = True
        else:
            logger.info("🩸 Blood")
            self._emit_execution_toast("Blood", st.price, "NONE", -1, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
            if not st.safety: st.safety = True
        # E-4: execution-gated projection refresh for the Hawk family.
        try:
            self._project_arc_length(trigger="execution")
        except Exception as e:
            logger.warning(f"Projection refresh (hawk) failed: {e}")

    def _dispatch_dove_subblock(self, fg: str) -> None:
        st = self.state
        if fg == "Down" and (st.prime == 1 and st.dime == 1):
            st.dime = 1; st.mem = 1
            self._A(st.price)
            if not st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🕊️ Dove")
            self._emit_execution_toast("Dove", st.price, "SELL", st.kOrder_id, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
        elif ((st.mem == 1 and st.dime == 1) or st.prime == 1) and fg == "" and st.price < st.signal:
            st.dime = 1; st.mem = 1
            self._A(st.price)
            if not st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🕊️ Dove")
            self._emit_execution_toast("Dove", st.price, "SELL", st.kOrder_id, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
        elif st.price < st.signal and fg == "Down" and (st.prime == 0 or (st.mem == 1 and st.dime == 1)):
            st.dime = 1; st.mem = 1
            self._A(st.price)
            if not st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🕊️ Dove")
            self._emit_execution_toast("Dove", st.price, "SELL", st.kOrder_id, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
        elif ((st.mem == 1 and st.dime == 1) or st.prime == 0) and fg == "" and st.price < st.signal:
            st.dime = 1; st.mem = 1
            self._A(st.price)
            if not st.C: self._P(st.price)
            else: self._Q(st.price)
            logger.info("🕊️ Dove")
            self._emit_execution_toast("Dove", st.price, "SELL", st.kOrder_id, fg)
            self._Bott(emit_toast=False)
            st.D = st.price
        elif st.Price < st.signal and (st.mem == 1 and st.dime == 1):
            if st.safety:
                self._A(st.price)
                if not st.C: self._P(st.price)
                else: self._Q(st.price)
                logger.info("🩸 Blood")
                self._emit_execution_toast("Blood", st.price, "SELL", st.kOrder_id, fg)
                self._Bott(emit_toast=False)
                st.D = st.price
            else:
                logger.info("🩸 Blood")
                self._emit_execution_toast("Blood", st.price, "NONE", -1, fg)
                self._Bott(emit_toast=False)
                st.D = st.price
                if not st.safety: st.safety = True
        elif st.mem == 0 or st.dime == 0:
            self._on_log()
            if st.safety:
                self._B(st.price)
                if st.C: self._P(st.price)
                else: self._Q(st.price)
                logger.info("💧 Watter")
                self._emit_execution_toast("Watter", st.price, "BUY", st.lOrder_id, fg)
                self._Top(emit_toast=False)
                st.E = st.price
            else:
                logger.info("💧 Watter")
                self._emit_execution_toast("Watter", st.price, "NONE", -1, fg)
                self._Top(emit_toast=False)
                st.E = st.price
                if not st.safety: st.safety = True
        else:
            logger.info("💧 Watter")
            self._emit_execution_toast("Watter", st.price, "NONE", -1, fg)
            self._Top(emit_toast=False)
            st.E = st.price
            if not st.safety: st.safety = True
        # E-4: execution-gated projection refresh for the Dove family.
        try:
            self._project_arc_length(trigger="execution")
        except Exception as e:
            logger.warning(f"Projection refresh (dove) failed: {e}")

    def _on_call(self) -> None:
        st = self.state
        y = st.y
        j = y + 1
        while j < st.X_scan + 2:
            idx = j - (y + 1)
            if idx < 0 or idx >= len(st.Regime):
                break
            self._unify(j)
            self._normalize(j)
            if st.Suply <= st.price or st.iSuply <= st.price or st.iSuply <= st.iH:
                i = j
                st.I = st.iW
                st.iZ = i
                st.Z = i
                if st.iw != 0 and st.jC == st.Cc:
                    st.h = st.I
                st.iC = st.C
                st.jC = not st.C
                if self._on_hold(j, "sTrend", "tTrend"):
                    st.iz = i
                    st.z = i
                    st.iI = st.iw
                    self._H(j)
                if st.X_scan != X_PERIOD - 1:
                    st.X_scan += 1
            if st.Demand >= st.price or st.iDemand >= st.price or st.iDemand >= st.iL:
                i = j
                st.I = st.iZ
                st.iW = i
                st.W = i
                if st.iz != 0 and st.iC == st.Cc:
                    st.h = st.I
                st.jC = st.C
                st.iC = not st.C
                if self._on_hold(j, "sTrend", "tTrend"):
                    st.iw = i
                    st.w = i
                    st.iI = st.iz
                    self._L(j)
                if st.X_scan != X_PERIOD - 1:
                    st.X_scan += 1
            j += 1
        # FF OnCall() unconditionally executes `X = y` after the scan.
        # The port restores this invariant here.
        st.X_scan = y

    def _on_track(self) -> None:
        st = self.state
        st.on_track_runs += 1
        y = st.y
        st.S = X_PERIOD
        st.T = X_PERIOD
        st.X_scan = y
        st.Y_scan = y
        is_now = self.ohlcv_history[-1]["timestamp"] if self.ohlcv_history else datetime.now()
        scan_limit = 4 * MAX_PERIOD
        s = X_PERIOD - 1
        # FF OnTrack() uses the live global S as the for-loop bound and
        # increments S inside the loop to extend the scan when a contact
        # is found. The port restores this by using st.S as the live bound
        # and capping the total scan at scan_limit to prevent a runaway
        # when every bar triggers a contact.
        safety_counter = 0
        safety_max = scan_limit * 2
        while s < st.S:
            safety_counter += 1
            if safety_counter > safety_max:
                logger.warning(f"⚠️ OnTrack() safety cap hit at s={s}; aborting scan")
                break
            if s >= scan_limit:
                break
            if s < 0:
                s += 1
                continue
            idx = s - (y + 1)
            if idx < 0:
                s += 1
                continue
            if idx >= len(st.Regime):
                ext = idx - len(st.Regime) + 1
                st.Regime.extend(["sRange"] * ext)
                st.k.extend([False] * ext)
                st.l.extend([False] * ext)
                st.HH.extend([Decimal('0.0')] * ext)
                st.LL.extend([Decimal('0.0')] * ext)
                st.Premium.extend([Decimal('0.0')] * ext)
                st.Discount.extend([Decimal('0.0')] * ext)
            j = s
            self._normalize(j)
            self._unify(j)
            if st.Suply <= st.price or st.iSuply <= st.price or st.iSuply <= st.iH:
                i = s
                st.I = st.iW
                st.Z = MAX_PERIOD
                st.iZ = i
                st.T += 1
                st.iC = st.C
                if st.iw != 0 and st.jC == st.Cc:
                    st.h = st.I
                st.jC = not st.C
                if st.iStdDev > Decimal('50.0'):
                    st.S += 1
                    st.iz = i
                    st.iI = st.iw
                    self._H(j)
                elif st.iATR < Decimal('50.0'):
                    st.S += 1
                    st.iO = i
                    st.io = i
                    self._H(j)
                else:
                    self._H(j)
                    if is_now != st.t:
                        if self._on_fire(j, "Stable", "tVolatile"):
                            self._F(j, st.iH, st.iL)
                            st.Regime[idx] = "tVolatile"
                        else:
                            st.Regime[idx] = "sVolatile"
                    st.S += 1
            if st.Demand >= st.price or st.iDemand >= st.price or st.iDemand >= st.iL:
                i = s
                st.I = st.iZ
                st.W = MAX_PERIOD
                st.iW = i
                st.T += 1
                st.jC = st.C
                if st.iz != 0 and st.iC == st.Cc:
                    st.h = st.I
                st.iC = not st.C
                if st.iStdDev > Decimal('50.0'):
                    st.S += 1
                    st.iw = i
                    st.iI = st.iz
                    self._L(j)
                elif st.iATR < Decimal('50.0'):
                    st.S += 1
                    st.iO = i
                    st.io = i
                    self._L(j)
                else:
                    self._L(j)
                    if is_now != st.t:
                        if self._on_fire(j, "Stable", "tVolatile"):
                            self._F(j, st.iH, st.iL)
                            st.Regime[idx] = "tVolatile"
                        else:
                            st.Regime[idx] = "sVolatile"
                    st.S += 1
            s += 1
        second_scan_start = X_PERIOD - 1
        second_scan_end = X_PERIOD
        s = second_scan_start
        while s < second_scan_end:
            idx = s - (y + 1)
            if idx < 0:
                s += 1
                continue
            j = s
            self._normalize(j)
            self._unify(j)
            if st.iStdDev < Decimal('50.0') and st.iATR < Decimal('50.0'):
                self._R(j)
                self._L(j)
                self._H(j)
            s += 1
        st.S = X_PERIOD
        st.T = X_PERIOD
        if st.Z != scan_limit and st.Z >= st.z:
            j = MAX_PERIOD - 1
            st.z = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        elif st.Z != scan_limit and st.Z < st.z:
            j = MAX_PERIOD
            st.z = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        else:
            j = X_PERIOD - 1
            st.z = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        if st.W != scan_limit and st.W >= st.w:
            j = MAX_PERIOD - 1
            st.w = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        elif st.W != scan_limit and st.W < st.w:
            j = MAX_PERIOD
            st.w = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        else:
            j = X_PERIOD - 1
            st.w = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"

    def _on_stand(self) -> None:
        st = self.state
        st.on_stand_runs += 1
        y = st.y
        st.S = X_PERIOD
        st.T = X_PERIOD
        st.X_scan = y
        st.Y_scan = y
        is_now = self.ohlcv_history[-1]["timestamp"] if self.ohlcv_history else datetime.now()
        s = y + 1
        # FF OnStand() scans down from y+1 to the live Y_scan, which is
        # decremented inside the loop on certain branch conditions. The
        # port restores the live-bound semantics by using st.Y_scan as the
        # while-condition and relying on the `if s == 1: break` guard to
        # prevent underflow.
        while s > st.Y_scan:
            if s == 1:
                break
            if s < 0:
                break
            idx = s - (y + 1)
            if idx < 0:
                s -= 1
                continue
            if idx >= len(st.Regime):
                ext = idx - len(st.Regime) + 1
                st.Regime.extend(["sRange"] * ext)
                st.k.extend([False] * ext)
                st.l.extend([False] * ext)
                st.HH.extend([Decimal('0.0')] * ext)
                st.LL.extend([Decimal('0.0')] * ext)
                st.Premium.extend([Decimal('0.0')] * ext)
                st.Discount.extend([Decimal('0.0')] * ext)
            j = s
            st.ir = 0
            st.ij = 0
            self._normalize(j)
            self._unify(j)
            if st.Suply <= st.price or st.iSuply <= st.price or st.iSuply <= st.iH:
                i = s
                st.I = st.iW
                st.Z = MIN_PERIOD + 1
                st.iZ = i
                st.T -= 1
                st.iC = st.C
                if st.iw != 0 and st.jC == st.Cc:
                    st.h = st.I
                st.jC = not st.C
                if st.X_scan != st.Y_scan and st.iz == 0 and st.iStdDev > Decimal('50.0'):
                    st.ij = i
                    st.iz = i
                    st.iI = st.iw
                    self._H(j)
                    if st.ir == 0 and st.Y_scan != 2:
                        st.Y_scan -= 1
                elif st.X_scan != st.Y_scan and st.iO == 0 and st.iATR < Decimal('50.0'):
                    st.iO = i
                    st.ir = i
                    self._H(j)
                    if st.ij == 0 and st.Y_scan != 2:
                        st.Y_scan -= 1
                elif st.X_scan == st.Y_scan:
                    self._H(j)
                    if is_now != st.t:
                        if self._on_fire(j, "Stable", "tVolatile"):
                            self._F(j, st.iH, st.iL)
                            st.Regime[idx] = "tVolatile"
                        else:
                            st.Regime[idx] = "sVolatile"
                    if st.Y_scan != 2 and st.X_scan != 2:
                        st.Y_scan -= 1
                        st.X_scan -= 1
            if st.Demand >= st.price or st.iDemand >= st.price or st.iDemand >= st.iL:
                i = s
                st.I = st.iZ
                st.W = MIN_PERIOD + 1
                st.iW = i
                st.T -= 1
                st.jC = st.C
                # D-MAJ-4: the FF toggles iC = !C unconditionally after the
                # if((iz != 0) && (iC == Cc)) check. The port previously
                # placed the toggle inside the if-block, which caused iC to
                # drift out of parity with C when the condition was false.
                # The toggle is now outside the if-block, matching the FF.
                if st.iz != 0 and st.iC == st.Cc:
                    st.h = st.I
                st.iC = not st.C
                if st.X_scan != st.Y_scan and st.iw == 0 and st.iStdDev > Decimal('50.0'):
                    st.ij = i
                    st.iw = i
                    st.iI = st.iz
                    self._L(j)
                    if st.ir == 0 and st.Y_scan != 2:
                        st.Y_scan -= 1
                elif st.X_scan != st.Y_scan and st.iO == 0 and st.iATR < Decimal('50.0'):
                    st.iO = i
                    st.io = i
                    st.ir = 0
                    self._L(j)
                    if st.ij == 0 and st.Y_scan != 2:
                        st.Y_scan -= 1
                elif st.X_scan == st.Y_scan:
                    self._L(j)
                    if is_now != st.t:
                        if self._on_fire(j, "Stable", "tVolatile"):
                            self._F(j, st.iH, st.iL)
                            st.Regime[idx] = "tVolatile"
                        else:
                            st.Regime[idx] = "sVolatile"
                    if st.Y_scan != 2 and st.X_scan != 2:
                        st.Y_scan -= 1
                        st.X_scan -= 1
            else:
                if st.Y_scan != 2 and st.X_scan != 2:
                    st.Y_scan -= 1
                    st.X_scan -= 1
            s -= 1
        second_scan_start = st.Y_scan + 1
        second_scan_end = y + 1
        if second_scan_start < second_scan_end:
            s = second_scan_start
            while s < second_scan_end:
                idx = s - (y + 1)
                if idx < 0:
                    s += 1
                    continue
                j = s
                self._normalize(j)
                self._unify(j)
                if st.iStdDev < Decimal('50.0') and st.iATR < Decimal('50.0'):
                    self._R(j)
                    self._L(j)
                    self._H(j)
                s += 1
        st.X_scan = y
        st.Y_scan = y
        if st.Z != 2 and st.Z >= st.z:
            j = MIN_PERIOD
            st.z = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        elif st.Z != 2 and st.Z < st.z:
            j = MIN_PERIOD + 1
            st.z = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        else:
            j = y + 1
            st.z = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        if st.W != 2 and st.W >= st.w:
            j = MIN_PERIOD
            st.w = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        elif st.W != 2 and st.W < st.w:
            j = MIN_PERIOD + 1
            st.w = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"
        else:
            j = y + 1
            st.w = j
            idx = j - (y + 1)
            if 0 <= idx < len(st.Regime):
                if is_now != st.t:
                    if st.Regime[idx] != "tTrend":
                        self._F(j, st.iH, st.iL)
                        st.Regime[idx] = "tTrend"
                    else:
                        st.Regime[idx] = "sTrend"

    def _on_goe(self) -> None:
        st = self.state
        if st.signal != Decimal('0.0'):
            return
        if self._on_gaurd(0) and st.KC:
            if ((st.h == st.io and st.z > st.o) or (st.h == st.iO and st.Z > st.O) or (st.h == st.iz and st.Z > st.z) or (st.h == st.iZ and st.Z < st.z)):
                if (not st.C) and (not st.c):
                    st.prime = 1; self._G(); self._signal(); st.tick_tock = True; st.tag = 1
                    logger.info(f"🟥 Sign. (Goe) price={st.price} h={st.h} Z={st.iZ} z={st.iz} O={st.iO} o={st.io}")
                else:
                    st.prime = 1; self._G(); self._signal(); st.tick_tock = True; st.tag = 1
                    logger.info(f"🟥 Sig. (Goe) price={st.price} h={st.h} Z={st.iZ} z={st.iz} O={st.iO} o={st.io}")
            elif (st.h == st.io) or (st.h == st.iZ) or (st.h == st.iz) or (st.h == st.iO):
                if (not st.C) and (not st.c):
                    st.prime = 1; self._G(); self._signal(); st.tick_tock = True; st.tag = 1
                    logger.info(f"🟥 Sig. (Goe) price={st.price} h={st.h} Z={st.iZ} z={st.iz} O={st.iO} o={st.io}")
                else:
                    st.prime = 1; self._G(); self._signal(); st.tick_tock = True; st.tag = 1
                    logger.info(f"🟥 Sign. (Goe) price={st.price} h={st.h} Z={st.iZ} z={st.iz} O={st.iO} o={st.io}")
        elif self._on_gaurd(0) != st.KC:
            if ((st.h == st.io and st.z > st.o) or (st.h == st.iO and st.Z > st.O) or (st.h == st.iz and st.Z > st.z) or (st.h == st.iZ and st.Z < st.z)):
                if (not st.C) or (not st.c):
                    st.prime = 1; self._G(); self._signal(); st.tick_tock = True; st.tag = 1
                    logger.info(f"🟥 Sign. (Goe) price={st.price} h={st.h} Z={st.iZ} z={st.iz} O={st.iO} o={st.io}")
                else:
                    st.prime = 1; self._G(); self._signal(); st.tick_tock = True; st.tag = 1
                    logger.info(f"🟥 Sig. (Goe) price={st.price} h={st.h} Z={st.iZ} z={st.iz} O={st.iO} o={st.io}")
            elif (st.h == st.io) or (st.h == st.iZ) or (st.h == st.iz) or (st.h == st.iO):
                if (not st.C) or (not st.c):
                    st.prime = 1; self._G(); self._signal(); st.tick_tock = True; st.tag = 1
                    logger.info(f"🟥 Sig. (Goe) price={st.price} h={st.h} Z={st.iZ} z={st.iz} O={st.iO} o={st.io}")
                else:
                    st.prime = 1; self._G(); self._signal(); st.tick_tock = True; st.tag = 1
                    logger.info(f"🟥 Sign. (Goe) price={st.price} h={st.h} Z={st.iZ} z={st.iz} O={st.iO} o={st.io}")
            self._KC()

    def _on_toe(self) -> None:
        st = self.state
        if st.signal != Decimal('0.0'):
            return
        if self._on_gaurd(0) and st.KC:
            if ((st.h == st.io and st.w > st.o) or (st.h == st.iO and st.W > st.O) or (st.h == st.iw and st.W > st.w) or (st.h == st.iW and st.W < st.w)):
                if (not st.C) and (not st.c):
                    st.prime = 0; self._G(); self._signal(); st.tick_tock = True; st.tag = 0
                    logger.info(f"🟩 Sig. (Toe) price={st.price} h={st.h} W={st.iW} w={st.iw} O={st.iO} o={st.io}")
                else:
                    st.prime = 0; self._G(); self._signal(); st.tick_tock = True; st.tag = 0
                    logger.info(f"🟩 Sign. (Toe) price={st.price} h={st.h} W={st.iW} w={st.iw} O={st.iO} o={st.io}")
            elif (st.h == st.io) or (st.h == st.iW) or (st.h == st.iw) or (st.h == st.iO):
                if (not st.C) and (not st.c):
                    st.prime = 0; self._G(); self._signal(); st.tick_tock = True; st.tag = 0
                    logger.info(f"🟩 Sign. (Toe) price={st.price} h={st.h} W={st.iW} w={st.iw} O={st.iO} o={st.io}")
                else:
                    st.prime = 0; self._G(); self._signal(); st.tick_tock = True; st.tag = 0
                    logger.info(f"🟩 Sig. (Toe) price={st.price} h={st.h} W={st.iW} w={st.iw} O={st.iO} o={st.io}")
        elif self._on_gaurd(0) != st.KC:
            if ((st.h == st.io and st.w > st.o) or (st.h == st.iO and st.W > st.O) or (st.h == st.iw and st.W > st.w) or (st.h == st.iW and st.W < st.w)):
                if (not st.C) or (not st.c):
                    st.prime = 0; self._G(); self._signal(); st.tick_tock = True; st.tag = 0
                    logger.info(f"🟩 Sig. (Toe) price={st.price} h={st.h} W={st.iW} w={st.iw} O={st.iO} o={st.io}")
                else:
                    st.prime = 0; self._G(); self._signal(); st.tick_tock = True; st.tag = 0
                    logger.info(f"🟩 Sign. (Toe) price={st.price} h={st.h} W={st.iW} w={st.iw} O={st.iO} o={st.io}")
            elif (st.h == st.io) or (st.h == st.iW) or (st.h == st.iw) or (st.h == st.iO):
                if (not st.C) or (not st.c):
                    st.prime = 0; self._G(); self._signal(); st.tick_tock = True; st.tag = 0
                    logger.info(f"🟩 Sign. (Toe) price={st.price} h={st.h} W={st.iW} w={st.iw} O={st.iO} o={st.io}")
                else:
                    st.prime = 0; self._G(); self._signal(); st.tick_tock = True; st.tag = 0
                    logger.info(f"🟩 Sig. (Toe) price={st.price} h={st.h} W={st.iW} w={st.iw} O={st.iO} o={st.io}")
            self._KC()

    def _signal(self) -> None:
        st = self.state
        if st.price <= Decimal('0.0'):
            return
        st.ab = not st.ba
        st.count = 0
        st.toll = 0
        st.tally = " "
        st.signal = st.price

        m_local = st.authoritative_m
        n_local = st.authoritative_n
        self._last_kronecker_bar = st.authoritative_h if st.authoritative_h >= 0 else st.h
        self._imbalance_fire_count += 1
        self._last_signal_time = datetime.now()

        if m_local >= 12:
            signal_type = "BUY"
        elif n_local >= 12:
            signal_type = "SELL"
        else:
            signal_type = "NEUTRAL"

        regime_idx = st.h - (st.y + 1)
        regime = st.Regime[regime_idx] if 0 <= regime_idx < len(st.Regime) else "Unknown"
        bar_timestamp = None
        if self.ohlcv_history:
            bar_timestamp = self.ohlcv_history[-1]["timestamp"]
            if isinstance(bar_timestamp, datetime):
                bar_timestamp = bar_timestamp.isoformat()
        signal_record = {
            "timestamp": datetime.now().isoformat(),
            "bar_timestamp": bar_timestamp,
            "type": signal_type,
            "price": float(st.price),
            "signal_level": float(st.signal),
            "regime": regime,
            "m_count": int(m_local),
            "n_count": int(n_local),
            "tick": int(st.tick),
            "h_bar": int(st.h),
            "source": "Goe" if st.prime == 1 else ("Toe" if st.prime == 0 else "Kronecker"),
        }
        st.signal_history.append(signal_record)
        if len(st.signal_history) > st.max_signal_history:
            st.signal_history = st.signal_history[-st.max_signal_history:]
        st.last_signal_at = signal_record["timestamp"]
        logger.info(f"🎯 SIGNAL #{self._imbalance_fire_count}: type={signal_type} @ {st.price}, tick={st.tick}, h={st.h}, m={m_local}, n={n_local}, regime={regime}")
        _emit_toast("signal", {
            "type": signal_type,
            "price": str(st.price),
            "signal_level": str(st.signal),
            "m": int(m_local),
            "n": int(n_local),
            "h": int(st.h),
            "regime": regime,
            "tick": int(st.tick),
            "source": signal_record["source"],
        })
        # _emit_toast already enqueues a push via _PUSH_QUEUE. Calling
        # _send_signal_alert() here would produce a second push for the
        # same logical event. The legacy alert path is retained only for
        # the case where _emit_toast is unavailable (e.g. during the
        # brief window before the push worker starts).
        if not _PUSH_WORKER_STARTED:
            self._send_signal_alert()

    def _on_gaurd(self, inp: int) -> bool:
        st = self.state
        if st.price > st.E and st.E != Decimal('0.0'):
            if st.signature and inp != -1:
                st.dime = 0
            return True
        else:
            if st.signature and inp != -1:
                st.dime = 1
            return False

    def _on_log(self) -> None:
        st = self.state
        if st.dime == 0:
            logger.info("🕊️ Flying")
        elif st.dime == 1:
            logger.info("🔻 Falling")
        else:
            logger.info("⏳ Wait/Decern")

    def _A(self, price: Decimal) -> None:
        st = self.state
        closed_any = False
        if st.v and st.lOrder_id != -1:
            logger.info(f"🔴 A(): Close long #{st.lOrder_id} at {price}")
            self._close_order(st.lOrder_id, price)
            st.lOrder_id = -1
            st.has_open_long = False
            closed_any = True
        elif st.v and st.kOrder_id != -1:
            logger.info(f"🔴 A(): Close short #{st.kOrder_id} at {price}")
            self._close_order(st.kOrder_id, price)
            st.kOrder_id = -1
            st.has_open_short = False
            closed_any = True
        st.E = Decimal('0.0')
        st.A = True
        st.B = False
        st.K = False
        st.Buy = -1
        st.trailing_stop_active = False
        st.trailing_stop_price = Decimal('0.0')
        st.trailing_take_profit = Decimal('0.0')
        self._emit_execution_toast("A", price, "CLOSE", -1, "A_close" if closed_any else "A_no_position")

    def _B(self, price: Decimal) -> None:
        st = self.state
        closed_any = False
        if st.u and st.kOrder_id != -1:
            logger.info(f"🔵 B(): Close short #{st.kOrder_id} at {price}")
            self._close_order(st.kOrder_id, price)
            st.kOrder_id = -1
            st.has_open_short = False
            closed_any = True
        elif st.u and st.lOrder_id != -1:
            logger.info(f"🔵 B(): Close long #{st.lOrder_id} at {price}")
            self._close_order(st.lOrder_id, price)
            st.lOrder_id = -1
            st.has_open_long = False
            closed_any = True
        st.D = Decimal('0.0')
        st.A = False
        st.B = True
        st.K = False
        st.Sell = -1
        st.trailing_stop_active = False
        st.trailing_stop_price = Decimal('0.0')
        st.trailing_take_profit = Decimal('0.0')
        self._emit_execution_toast("B", price, "CLOSE", -1, "B_close" if closed_any else "B_no_position")

    def _open_order(self, side: str, price: Decimal, sl: Decimal, tp: Decimal, lot: Decimal) -> int:
        ticket = self._next_ticket
        self._next_ticket += 1
        order = Order(ticket=ticket, side=side, entry=price, sl=sl, tp=tp, lot=lot)
        self.orders.append(order)
        return ticket

    def _close_order(self, ticket: int, price: Decimal) -> bool:
        for o in self.orders:
            if o.ticket == ticket and o.closed_at is None:
                o.closed_at = datetime.now()
                o.close_price = price
                return True
        return False

    def _P(self, price: Decimal) -> None:
        st = self.state
        if price <= Decimal('0.0'):
            return
        self._S()
        ask_price = self.price_history[-1].ask if self.price_history else price
        bid_price = self.price_history[-1].bid if self.price_history else price
        target = self._get_next_topological_target("BUY", ask_price)
        if target > Decimal('0.0') and self._will_pass_spread_in_pnl(ask_price, target, "BUY"):
            if st.Buy >= 0 and (st.A or not st.B) and (st.u or not st.v):
                if st.C:
                    ticket = self._open_order("BUY", ask_price, self._bSL, self._bTP, LOT_SIZE)
                    st.lOrder_id = ticket
                    st.has_open_long = True
                    st.trailing_stop_entry = ask_price
                    st.trailing_stop_side = "LONG"
                    st.Buy = 0 if st.Buy == -1 else st.Buy + 1
                    logger.info(f"🟢 P(): BUY executed #{ticket} at {ask_price}, target={target}")
        else:
            self._A(price)
            logger.info("⚠️ P(): BUY rejected — projected PnL <= spread friction")

        target = self._get_next_topological_target("SELL", bid_price)
        if target > Decimal('0.0') and self._will_pass_spread_in_pnl(bid_price, target, "SELL"):
            if st.Sell >= 0 and (not st.A or st.B) and (not st.u or st.v):
                if not st.C:
                    ticket = self._open_order("SELL", bid_price, self._sSL, self._sTP, LOT_SIZE)
                    st.kOrder_id = ticket
                    st.has_open_short = True
                    st.trailing_stop_entry = bid_price
                    st.trailing_stop_side = "SHORT"
                    st.Sell = 0 if st.Sell == -1 else st.Sell + 1
                    logger.info(f"🔴 P(): SELL executed #{ticket} at {bid_price}, target={target}")
        else:
            self._B(price)
            logger.info("⚠️ P(): SELL rejected — projected PnL <= spread friction")

    def _Q(self, price: Decimal) -> None:
        st = self.state
        if price <= Decimal('0.0'):
            return
        self._S()
        ask_price = self.price_history[-1].ask if self.price_history else price
        bid_price = self.price_history[-1].bid if self.price_history else price
        target = self._get_next_topological_target("SELL", bid_price)
        if target > Decimal('0.0') and self._will_pass_spread_in_pnl(bid_price, target, "SELL"):
            if st.Sell >= 0 and (not st.A or st.B) and (not st.u or st.v):
                if st.C:
                    ticket = self._open_order("SELL", bid_price, self._sSL, self._sTP, LOT_SIZE)
                    st.kOrder_id = ticket
                    st.has_open_short = True
                    st.trailing_stop_entry = bid_price
                    st.trailing_stop_side = "SHORT"
                    st.Sell = 0 if st.Sell == -1 else st.Sell + 1
                    logger.info(f"🔴 Q(): SELL executed #{ticket} at {bid_price}, target={target}")
        else:
            self._B(price)
            logger.info("⚠️ Q(): SELL rejected — projected PnL <= spread friction")

        target = self._get_next_topological_target("BUY", ask_price)
        if target > Decimal('0.0') and self._will_pass_spread_in_pnl(ask_price, target, "BUY"):
            if st.Buy >= 0 and (st.A or not st.B) and (st.u or not st.v):
                if not st.C:
                    ticket = self._open_order("BUY", ask_price, self._bSL, self._bTP, LOT_SIZE)
                    st.lOrder_id = ticket
                    st.has_open_long = True
                    st.trailing_stop_entry = ask_price
                    st.trailing_stop_side = "LONG"
                    st.Buy = 0 if st.Buy == -1 else st.Buy + 1
                    logger.info(f"🟢 Q(): BUY executed #{ticket} at {ask_price}, target={target}")
        else:
            self._A(price)
            logger.info("⚠️ Q(): BUY rejected — projected PnL <= spread friction")

    def _S(self) -> None:
        st = self.state
        point = self._point_size if self._point_size > Decimal('0.0') else Decimal('0.00001')
        com_local = self._com_price()
        sl_price = STOP_LOSS * point
        tp_price = TAKE_PROFIT * point
        bid = st.price
        ask = st.price
        if self.price_history:
            bid = self.price_history[-1].bid
            ask = self.price_history[-1].ask
        if STOP_LOSS != Decimal('0.0'):
            self._sSL = bid + sl_price - com_local
            self._bSL = ask - sl_price + com_local
        if TAKE_PROFIT != Decimal('0.0'):
            self._sTP = bid - tp_price
            self._bTP = ask + tp_price

    def _execute_trailing_stop(self) -> None:
        st = self.state
        if len(self.ohlcv_history) >= st.y + 1:
            self._normalize(st.y + 1)
        has_long = st.has_open_long
        has_short = st.has_open_short
        if not (has_long or has_short):
            if st.trailing_stop_active:
                logger.info("📉 Trailing stop deactivated — no open orders")
                st.trailing_stop_active = False
                st.trailing_stop_price = Decimal('0.0')
                st.trailing_take_profit = Decimal('0.0')
                st.trailing_stop_entry = Decimal('0.0')
                st.trailing_stop_side = ""
            return
        regime_col = 0
        if 0 <= regime_col < len(st.Regime):
            regime = st.Regime[regime_col]
            if regime in ("tStable", "tCoherent"):
                return
        if st.price <= Decimal('0.0'):
            return
        if not st.trailing_stop_active:
            st.trailing_stop_active = True
            st.trailing_stop_entry = st.price
            st.trailing_stop_price = st.price
            st.trailing_stop_side = "LONG" if has_long else "SHORT"
            if has_long:
                st.trailing_take_profit = st.price * Decimal('1.02')
            else:
                st.trailing_take_profit = st.price * Decimal('0.98')
            logger.info(f"🎯 Trailing stop ACTIVATED at {st.trailing_stop_price}, TP={st.trailing_take_profit}, direction={st.trailing_stop_side}")
            return
        if len(self.price_history) > 0:
            last = self.price_history[-1]
            current_spread = last.ask - last.bid
        else:
            current_spread = Decimal('0.0')
        com_price = self._com_price()
        point_size = self._point_size if self._point_size > Decimal('0.0') else Decimal('0.00001')
        friction_points = (current_spread + com_price) / point_size
        safety_buffer = Decimal('1.0')
        min_trail_threshold = (friction_points + safety_buffer) * point_size
        if has_long:
            pnl_points = (st.price - st.trailing_stop_entry) / point_size
        else:
            pnl_points = (st.trailing_stop_entry - st.price) / point_size
        if pnl_points <= (friction_points + safety_buffer):
            return
        trail_step = max(min_trail_threshold, pnl_points * point_size * Decimal('0.3'))
        new_sl = st.trailing_stop_price
        topological_target = Decimal('0.0')
        if has_long:
            for ji in range(st.y + 1, X_PERIOD):
                jidx = ji - (st.y + 1)
                if jidx < len(st.Premium) and st.Premium[jidx] > st.price and st.Premium[jidx] != Decimal('0.0'):
                    topological_target = st.Premium[jidx]
                    break
            slDistance = max(trail_step, STOP_LOSS * point_size)
            proposedSL = st.price - slDistance
            if ((proposedSL > st.trailing_stop_price or st.trailing_stop_price == Decimal('0.0')) and (topological_target == Decimal('0.0') or proposedSL < (topological_target - min_trail_threshold))):
                new_sl = proposedSL
            tpDistance = Decimal('0.0')
            if topological_target > Decimal('0.0'):
                tpDistance = max(topological_target - st.price, TAKE_PROFIT * point_size)
            else:
                tpDistance = max(trail_step * Decimal('2.0'), TAKE_PROFIT * point_size)
            proposedTP = st.price + tpDistance
            if proposedTP > (st.price + min_trail_threshold):
                st.trailing_take_profit = proposedTP
        else:
            for ji in range(st.y + 1, X_PERIOD):
                jidx = ji - (st.y + 1)
                if jidx < len(st.Discount) and st.Discount[jidx] < st.price and st.Discount[jidx] != Decimal('0.0'):
                    topological_target = st.Discount[jidx]
                    break
            slDistance = max(trail_step, STOP_LOSS * point_size)
            proposedSL = st.price + slDistance
            if ((st.trailing_stop_price == Decimal('0.0') or proposedSL < st.trailing_stop_price) and (topological_target == Decimal('0.0') or proposedSL > (topological_target + min_trail_threshold))):
                new_sl = proposedSL
            tpDistance = Decimal('0.0')
            if topological_target > Decimal('0.0'):
                tpDistance = max(st.price - topological_target, TAKE_PROFIT * point_size)
            else:
                tpDistance = max(trail_step * Decimal('2.0'), TAKE_PROFIT * point_size)
            proposedTP = st.price - tpDistance
            if proposedTP < (st.price - min_trail_threshold):
                st.trailing_take_profit = proposedTP
        if new_sl != st.trailing_stop_price:
            st.trailing_stop_price = new_sl
            logger.info(f"📈 Trailing stop updated to {st.trailing_stop_price} (PnL={pnl_points}pts, friction={friction_points}pts)")
        if has_long and st.price >= st.trailing_take_profit:
            logger.info(f"✅ TP hit (LONG) at {st.price} / TP={st.trailing_take_profit}")
            if st.lOrder_id != -1:
                self._close_order(st.lOrder_id, st.price)
            st.trailing_stop_active = False
            st.trailing_stop_price = Decimal('0.0')
            st.trailing_take_profit = Decimal('0.0')
            st.trailing_stop_entry = Decimal('0.0')
            st.trailing_stop_side = ""
            st.has_open_long = False
            st.lOrder_id = -1
        elif has_short and st.price <= st.trailing_take_profit:
            logger.info(f"✅ TP hit (SHORT) at {st.price} / TP={st.trailing_take_profit}")
            if st.kOrder_id != -1:
                self._close_order(st.kOrder_id, st.price)
            st.trailing_stop_active = False
            st.trailing_stop_price = Decimal('0.0')
            st.trailing_take_profit = Decimal('0.0')
            st.trailing_stop_entry = Decimal('0.0')
            st.trailing_stop_side = ""
            st.has_open_short = False
            st.kOrder_id = -1

    def _get_next_topological_target(self, side: str, current_price: Decimal) -> Decimal:
        st = self.state
        for ji in range(st.y + 1, X_PERIOD - 1):
            jidx = ji - (st.y + 1)
            if side == "BUY":
                if jidx < len(st.Premium) and st.Premium[jidx] > current_price and st.Premium[jidx] != Decimal('0.0'):
                    return st.Premium[jidx]
            elif side == "SELL":
                if jidx < len(st.Discount) and st.Discount[jidx] < current_price and st.Discount[jidx] != Decimal('0.0'):
                    return st.Discount[jidx]
        if side == "BUY" and st.Sale > current_price:
            return st.Sale
        if side == "SELL" and st.Stock < current_price:
            return st.Stock
        return Decimal('0.0')

    def _will_pass_spread_in_pnl(self, entry_price: Decimal, target_price: Decimal, side: str) -> bool:
        if len(self.price_history) > 0:
            last = self.price_history[-1]
            current_spread = last.ask - last.bid
        else:
            current_spread = Decimal('0.0')
        point_size = self._point_size if self._point_size > Decimal('0.0') else Decimal('0.00001')
        if point_size <= Decimal('0.0'):
            return False
        com_price = self._com_price()
        if com_price < Decimal('0.0'):
            com_price = Decimal('0.0')
        friction_points = (current_spread + com_price) / point_size
        projected_distance = abs(target_price - entry_price)
        projected_pnl_points = projected_distance / point_size
        safety_buffer = Decimal('1.0')
        if side == "BUY":
            if target_price <= entry_price:
                return False
            return projected_pnl_points > (friction_points + safety_buffer)
        if side == "SELL":
            if target_price >= entry_price:
                return False
            return projected_pnl_points > (friction_points + safety_buffer)
        return False

    def _Top(self, emit_toast: bool = True) -> None:
        st = self.state
        price_str = f"{st.price:.5f}"
        created = False
        if not any(abs(p - st.price) < Decimal('0.00001') for p in st.BL):
            st.BL.append(st.price)
            st.BL_type.append("top")
            st.FVG += 1
            # The FVG count and the array index are distinct concepts. The
            # count starts at -1 and increments; the array index is the
            # position in st.BL. The TWA merges FVG anchors by idx, so the
            # idx must be the array position (stable across removals), not
            # the count (which decrements on removal and can collide).
            anchor_idx = len(st.BL) - 1
            st.bL = price_str
            logger.info(f"▲ Top(): Blue FVG line at {price_str}, FVG={st.FVG}, idx={anchor_idx}")
            created = True
            if self._bridge_publish_callback:
                try:
                    self._bridge_publish_callback("top", price_str)
                except Exception as e:
                    logger.warning(f"_bridge_publish_callback failed: {e}")
        _emit_toast("fvg", {
            "action": "commit" if created else "duplicate",
            "type": "top",
            "price": price_str,
            "idx": int(len(st.BL) - 1) if created else int(st.FVG),
            "tick": int(st.tick),
        })

    def _Bott(self, emit_toast: bool = True) -> None:
        st = self.state
        price_str = f"{st.price:.5f}"
        created = False
        if not any(abs(p - st.price) < Decimal('0.00001') for p in st.BL):
            st.BL.append(st.price)
            st.BL_type.append("bott")
            st.FVG += 1
            anchor_idx = len(st.BL) - 1
            st.bL = price_str
            logger.info(f"▼ Bott(): Red FVG line at {price_str}, FVG={st.FVG}, idx={anchor_idx}")
            created = True
            if self._bridge_publish_callback:
                try:
                    self._bridge_publish_callback("bott", price_str)
                except Exception as e:
                    logger.warning(f"_bridge_publish_callback failed: {e}")
        _emit_toast("fvg", {
            "action": "commit" if created else "duplicate",
            "type": "bott",
            "price": price_str,
            "idx": int(len(st.BL) - 1) if created else int(st.FVG),
            "tick": int(st.tick),
        })

    def _emit_execution_toast(self, event: str, price: Decimal, side: str, ticket: int, reason: str) -> None:
        st = self.state
        _emit_toast("execution", {
            "event": event,
            "price": str(price),
            "side": side,
            "ticket": int(ticket),
            "reason": reason,
            "tick": int(st.tick),
        })
        # _emit_toast already enqueues a push via _PUSH_QUEUE. Calling
        # _send_execution_alert() here would produce a second push for
        # the same logical event. The legacy alert path is retained only
        # for the case where _emit_toast is unavailable.
        if not _PUSH_WORKER_STARTED:
            self._send_execution_alert(event, price, side, ticket, reason)

    def _populate_indicator_matrix(self) -> None:
        st = self.state
        if len(self.ohlcv_history) < MIN_HISTORY_WINDOW:
            return
        # D-HARD-1: Snapshot the live bounds so a concurrent apply_settings()
        # cannot mutate X_PERIOD or st.y mid-loop. MQL4 is single-threaded
        # per chart; the port has an HTTP handler thread that can call
        # apply_settings() while this method runs on the price-feed thread.
        _X = X_PERIOD
        _y = st.y
        size = _X - _y
        if size <= 0:
            return
        end = len(self.ohlcv_history)
        for j in range(_y + 1, _X + 1):
            idx = j - (_y + 1)
            if idx < 0 or idx >= size:
                continue
            bars_back = _X - j
            bar_end = end - bars_back
            if bar_end < MIN_HISTORY_WINDOW:
                continue
            col_i = j - (_y + 1)
            if col_i < 0 or col_i >= len(st.iA[0]):
                continue
            self._normalize(j)
            self._unify(j)
            self._indicator_populate_count += 13

    def _force_initialization(self) -> None:
        st = self.state
        if st.FG:
            return
        if st.price <= Decimal('0.0'):
            logger.warning("⏳ Cannot force-init: price not yet available")
            return
        logger.info("🚀 First valid tick detected. Forcing engine initialization...")
        if not st.signature:
            st.D = st.price
            st.E = st.price
        size = X_PERIOD - st.y
        if size <= 0:
            size = X_PERIOD - Y_START
        st.X_scan = st.y
        st.Y_scan = st.y
        if len(st.k) != size:
            st.k = [False] * size
            st.l = [False] * size
            st.HH = [Decimal('0.0')] * size
            st.LL = [Decimal('0.0')] * size
            st.Premium = [Decimal('0.0')] * size
            st.Discount = [Decimal('0.0')] * size
            st.Regime = ["sRange"] * size
        # D-CRIT-1: FF OnInit() first-tick F() loop anchors to the previous
        # bar's high/low (iHigh/iLow at shift 1). The port previously used
        # the most recent bar in the history array, which is the current
        # bar. Use the previous bar when available.
        if len(self.ohlcv_history) >= 2:
            iH = self.ohlcv_history[-2]["high"]
            iL = self.ohlcv_history[-2]["low"]
        elif len(self.ohlcv_history) == 1:
            iH = self.ohlcv_history[-1]["high"]
            iL = self.ohlcv_history[-1]["low"]
        else:
            iH = st.price
            iL = st.price
        # NOTE: _F() calls _normalize(j) internally, so the loop below
        # normalizes each column exactly once per j. This is O(N * 13)
        # indicator computations on first init, which is intentional: the
        # FF's initialization phase populates the full iA/cA matrix before
        # the first real tick is processed. The cost is bounded by
        # X_PERIOD * 13 = 806 indicator computations and runs once per
        # engine lifetime.
        for j in range(st.y + 1, X_PERIOD):
            self._F(j, iH, iL)
        st.FG = True
        st._initialized = True
        logger.info(f"✅ Engine initialized on first tick at price={st.price}")

    def _on_tick(self, price_data: PriceData) -> None:
        st = self.state
        st.tick += 1
        self._tick_log_counter += 1
        if self._tick_log_counter >= 100:
            self._tick_log_counter = 0
            idx = st.Z - (st.y + 1)
            regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "?"
            logger.info(f"⚡ Tick #{st.tick}: Price={st.price}, Signal={st.signal}, FG={st.FG}, Regime={regime}, X_scan={st.X_scan}, Y_scan={st.Y_scan}, bars={st.bar_close_count}, signals={len(st.signal_history)}, provider={st.last_provider}")

        # m-6: validate both sides of the spread before assigning st.price.
        # A relay that returns bid>0 with ask=0 (or ask<bid) produces a
        # negative spread, which loosens the friction gate in
        # _will_pass_spread_in_pnl() and _execute_trailing_stop(). The FF
        # requires a coherent two-sided quote; we repair the ask to the bid
        # when the ask is non-positive, and we reject the tick outright when
        # the bid itself is non-positive.
        if price_data.bid <= Decimal('0.0'):
            logger.warning(f"⚠️ Tick #{st.tick} with non-positive bid ({price_data.bid}). Skipping state machine.")
            return
        if price_data.ask <= Decimal('0.0'):
            logger.warning(f"⚠️ Tick #{st.tick} with non-positive ask ({price_data.ask}); repairing ask to bid ({price_data.bid}).")
            price_data.ask = price_data.bid
        elif price_data.ask < price_data.bid:
            logger.warning(f"⚠️ Tick #{st.tick} with inverted spread (bid={price_data.bid}, ask={price_data.ask}); repairing ask to bid.")
            price_data.ask = price_data.bid

        st.price = price_data.bid
        if len(self.ohlcv_history) >= 2:
            st.Price = self.ohlcv_history[-2]["close"]
            st.iPrice = self.ohlcv_history[-2]["close"]
            st.open = self.ohlcv_history[-2]["open"]
            st.iH = self.ohlcv_history[-2]["high"]
            st.iL = self.ohlcv_history[-2]["low"]
        elif len(self.ohlcv_history) == 1:
            # Only the current bar exists. Use the current bar's own
            # open/high/low as the "previous bar" proxy, matching the FF's
            # behavior when only one bar of history is available.
            st.Price = self.ohlcv_history[-1]["close"]
            st.iPrice = self.ohlcv_history[-1]["close"]
            st.open = self.ohlcv_history[-1]["open"]
            st.iH = self.ohlcv_history[-1]["high"]
            st.iL = self.ohlcv_history[-1]["low"]
        else:
            # No history at all. Use the live tick as the only anchor.
            st.Price = price_data.close
            st.iPrice = st.price
            st.open = st.price
            st.iH = st.price
            st.iL = st.price
        
        # The bid/ask validation above already covers the non-positive-bid
        # case, so this guard is now redundant for bid<=0. It is retained
        # as a defensive check against a future caller that bypasses the
        # validation block above (e.g. a direct state mutation in a test).
        if st.price <= Decimal('0.0'):
            logger.warning(f"⚠️ Tick #{st.tick} with non-positive price. Skipping state machine.")
            return

        is_now = self.ohlcv_history[-1]["timestamp"] if self.ohlcv_history else datetime.now()

        self._maintain_fvg_lines()

        if not st.FG:
            self._force_initialization()

        self._execute_trailing_stop()

        # FF OnTick() sets X = y at the top of the tick body, so every scan
        # family (OnPoint, OnCall, OnBar, OnTrack, OnStand) starts from the
        # same baseline. The port previously left st.X_scan at whatever value
        # the prior tick's _on_call() left it, causing the scan extents to
        # drift across ticks. Re-initializing here restores FF semantics.
        st.X_scan = st.y
        st.Y_scan = st.y

        # _on_point() and _on_call() are per-tick scans (matching FF
        # OnPoint() and OnCall() which run every tick). _on_bar() is a
        # per-bar scan (matching FF OnBar() which runs when a new bar
        # opens). The is_now != st.t check detects the new-bar transition.
        self._on_point()
        self._O(st.iO, st.O, st.J, "C")
        self._O(st.io, st.o, st.iJ, "c")
        self._on_call()
        self._J()

        if is_now != st.t:
            self._on_bar()
            self._O(st.iO, st.O, st.J, "C")
            self._O(st.io, st.o, st.iJ, "c")

        if st.J == st.y + 1 and st.J != 2:
            self._on_stand()
            self._J()
            self._O(st.iO, st.O, st.J, "C")
            self._O(st.io, st.o, st.iJ, "c")
            if st.iO != 2:
                if st.J >= st.iO:
                    j = MIN_PERIOD
                    st.O = j
                    idx_j = j - (st.y + 1)
                    if 0 <= idx_j < len(st.Regime):
                        if is_now != st.t:
                            if self._on_fire(j, "Stable", "tRange"):
                                self._F(j, st.iH, st.iL)
                                st.Regime[idx_j] = "tRange"
                            else:
                                st.Regime[idx_j] = "sRange"
                        else:
                            st.Regime[idx_j] = "sRange"
                else:
                    j = MIN_PERIOD + 1
                    st.O = j
                    idx_j = j - (st.y + 1)
                    if 0 <= idx_j < len(st.Regime):
                        if is_now != st.t:
                            if self._on_fire(j, "Stable", "tRange"):
                                self._F(j, st.iH, st.iL)
                                st.Regime[idx_j] = "tRange"
                            else:
                                st.Regime[idx_j] = "sRange"
                        else:
                            st.Regime[idx_j] = "sRange"
            else:
                st.O = 2
            if st.io != 2:
                if st.iJ >= st.io:
                    st.o = MIN_PERIOD
                else:
                    st.o = MIN_PERIOD + 1
            else:
                st.o = 2

        if st.J == X_PERIOD - 1:
            self._on_track()
            self._J()
            self._O(st.iO, st.O, st.J, "C")
            self._O(st.io, st.o, st.iJ, "c")
            if st.iO != 4 * MAX_PERIOD:
                if st.J >= st.iO:
                    j = MAX_PERIOD - 1
                    st.O = j
                    idx_j = j - (st.y + 1)
                    if 0 <= idx_j < len(st.Regime):
                        if is_now != st.t:
                            if self._on_fire(j, "Stable", "tRange"):
                                self._F(j, st.iH, st.iL)
                                st.Regime[idx_j] = "tRange"
                            else:
                                st.Regime[idx_j] = "sRange"
                        else:
                            st.Regime[idx_j] = "sRange"
                else:
                    j = MAX_PERIOD
                    st.O = j
                    idx_j = j - (st.y + 1)
                    if 0 <= idx_j < len(st.Regime):
                        if is_now != st.t:
                            if self._on_fire(j, "Stable", "tRange"):
                                self._F(j, st.iH, st.iL)
                                st.Regime[idx_j] = "tRange"
                            else:
                                st.Regime[idx_j] = "sRange"
                        else:
                            st.Regime[idx_j] = "sRange"
            else:
                st.O = X_PERIOD - 1
            if st.io != 4 * MAX_PERIOD:
                if st.iJ >= st.io:
                    st.o = MAX_PERIOD - 1
                else:
                    st.o = MAX_PERIOD
            else:
                st.o = X_PERIOD - 1

        # FF OnTick() updates `t` at the very end of the function, after
        # the reversal-trigger block and after the self-evolution protocol.
        # The port matches that ordering by deferring the assignment to the
        # end of this function.

        if st.Z != X_PERIOD - 1:
            h_idx = st.iZ - (st.y + 1)
            if st.Z != st.y + 1 and 0 <= h_idx < len(st.k) and st.k[h_idx]:
                st.h = st.iZ
                self._on_goe()
            else:
                h_idx = st.iz - (st.y + 1)
                if (0 <= h_idx < len(st.k) and st.k[h_idx] and st.z != st.y + 1 and st.z != X_PERIOD - 1):
                    st.h = st.iz
                    self._on_goe()
                else:
                    h_idx = st.io - (st.y + 1)
                    if (0 <= h_idx < len(st.k) and st.k[h_idx] and st.o != st.y + 1 and st.o != X_PERIOD - 1):
                        st.h = st.io
                        self._on_goe()
                    else:
                        h_idx = st.iO - (st.y + 1)
                        if (0 <= h_idx < len(st.k) and st.k[h_idx] and st.O != st.y + 1 and st.O != X_PERIOD - 1):
                            st.h = st.iO
                            self._on_goe()

        if st.W != X_PERIOD - 1:
            h_idx = st.iW - (st.y + 1)
            if st.W != st.y + 1 and 0 <= h_idx < len(st.l) and st.l[h_idx]:
                st.h = st.iW
                self._on_toe()
            else:
                h_idx = st.iw - (st.y + 1)
                if (0 <= h_idx < len(st.l) and st.l[h_idx] and st.w != st.y + 1 and st.w != X_PERIOD - 1):
                    st.h = st.iw
                    self._on_toe()
                else:
                    h_idx = st.io - (st.y + 1)
                    if (0 <= h_idx < len(st.l) and st.l[h_idx] and st.o != st.y + 1 and st.o != X_PERIOD - 1):
                        st.h = st.io
                        self._on_toe()
                    else:
                        h_idx = st.iO - (st.y + 1)
                        if (0 <= h_idx < len(st.l) and st.l[h_idx] and st.O != st.y + 1 and st.O != X_PERIOD - 1):
                            st.h = st.iO
                            self._on_toe()

        if st.GF:
            self.OnReInit()
            st.GF = False
        
        # FF does not re-fire signal alerts from OnTick(). The _signal()
        # function sends its own alert (via _send_signal_alert() at its
        # end), and the Kronecker dispatch subblocks send execution alerts.
        # No additional alert path is needed here.
        
        if st.ab != st.ba:
            st.ab = st.ba
        # D-MAJ-3: FF OnTick() clears tickTock unconditionally at the very
        # end of the function, after the reversal-trigger block and after
        # the self-evolution protocol. The port previously omitted this
        # clear, causing the Kronecker gate to persist one tick longer than
        # the FF. Restore the FF's unconditional clear here.
        st.tick_tock = False
        # D-CLEAN-1: the redundant st.t = is_now assignment that previously
        # appeared before the self-evolution protocol has been removed. The
        # single assignment here is the one the FF's OnTrack()/OnStand()
        # bar-change guards depend on.
        st.t = is_now

    def _format_comment_line(self) -> str:
        st = self.state
        # Use st.y (the live Y_START) rather than the module-level constant,
        # because apply_settings() mutates st.y and the state arrays are
        # resized accordingly. Using MIN_PERIOD - 2 would index into the
        # wrong row after a settings change.
        y = st.y
        def _k(idx):
            i = idx - (y + 1)
            return st.k[i] if 0 <= i < len(st.k) else False
        def _l(idx):
            i = idx - (y + 1)
            return st.l[i] if 0 <= i < len(st.l) else False
        line1 = f"    ^{st.iZ}:{st.Z}|{st.iz}:{st.z}={_k(st.Z)}|{_k(st.z)}                                           <! †, ‡, # — ↑(0)|↓(1): {st.prime} {st.dime}{st.mem} >"
        line2 = f"\n Lim{st.iO}:{st.O}^{_k(st.O)}_{_l(st.O)}.{st.io}:{st.o}^{_k(st.o)}_{_l(st.o)}={st.h}.{st.C}:{st.c}             <! 100%✓ >"
        line3 = f"\n    _{st.iW}:{st.W}|{st.iw}:{st.w}={_l(st.W)}|{_l(st.w)}                                                 <! Natalia Tanyatia >"
        return line1 + line2 + line3

    def _maintain_fvg_lines(self) -> None:
        st = self.state
        if st.FVG < 0:
            return
        price = st.price
        i = 0
        removed_anchors = []
        while i < len(st.BL):
            price_line = st.BL[i]
            line_type = st.BL_type[i] if i < len(st.BL_type) else "top"
            if price_line <= Decimal('0.0'):
                i += 1
                continue
            if line_type == "top" and (st.A or not st.B) and price_line <= price and st.E != Decimal('0.0'):
                logger.info(f"🔵 FVG maintenance: remove blue @ {price_line}")
                removed_anchors.append({"idx": i, "price": price_line, "type": "top"})
                st.BL.pop(i)
                if i < len(st.BL_type):
                    st.BL_type.pop(i)
                st.FVG -= 1
                continue
            if line_type == "bott" and (st.B or not st.A) and price_line >= price and st.D != Decimal('0.0'):
                logger.info(f"🔴 FVG maintenance: remove red @ {price_line}")
                removed_anchors.append({"idx": i, "price": price_line, "type": "bott"})
                st.BL.pop(i)
                if i < len(st.BL_type):
                    st.BL_type.pop(i)
                st.FVG -= 1
                continue
            i += 1
        # Emit removal toasts using the idx that the anchor had at the time
        # of creation (its array position before any removal). After the
        # removals above, subsequent anchors' array positions have shifted,
        # so we must emit the toast with the original idx, not the current
        # position. The TWA merges by idx, so a shifted idx would cause a
        # removed anchor to reappear or a valid anchor to be dropped.
        for anchor in removed_anchors:
            _emit_toast("fvg", {
                "action": "remove",
                "type": anchor["type"],
                "price": str(anchor["price"]),
                "idx": int(anchor["idx"]),
                "tick": int(st.tick),
            })

    def update_price_from_feed(self) -> None:
        data = self.feed.get_intraday()
        if not data:
            self._consecutive_zero_prices += 1
            now = datetime.now()
            if self._last_relay_warn is None or (now - self._last_relay_warn).seconds >= 60:
                self._last_relay_warn = now
                logger.warning(f"⚠️ No data from relay for {self.feed.active_symbol()} (consecutive={self._consecutive_zero_prices})")
            return
        bid = data["close"]
        ask = data["close"]
        if bid <= Decimal('0.0'):
            self._consecutive_zero_prices += 1
            return
        volume = data.get("volume", Decimal('0.0'))
        timestamp = data.get("timestamp", datetime.now())
        provider = str(data.get("provider", self.feed.last_provider()))
        self._consecutive_zero_prices = 0
        self.update_price(bid, ask, volume, timestamp, provider)

    def update_price(self, bid: Decimal, ask: Decimal, volume: Decimal = Decimal('0.0'), timestamp: Optional[datetime] = None, provider: str = "") -> None:
        if timestamp is None:
            timestamp = datetime.now()
        if bid <= Decimal('0.0'):
            logger.warning(f"update_price rejected non-positive bid: {bid}")
            return
        self.state.price = bid
        self.state.Price = (bid + ask) / Decimal('2.0')
        if volume > Decimal('0.0'):
            self.state.last_volume = volume
        if provider:
            self.state.last_provider = provider
        self._price_update_counter += 1
        price_data = PriceData(
            bid=bid, ask=ask, close=(bid + ask) / Decimal('2.0'),
            open=bid, high=max(bid, ask), low=min(bid, ask),
            volume=volume, timestamp=timestamp, provider=provider,
        )
        self.price_history.append(price_data)
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]

        bar_closed = False
        if self._last_price_update is None:
            bar_closed = True
        else:
            current_min = timestamp.replace(second=0, microsecond=0)
            prev_min = self._last_price_update.replace(second=0, microsecond=0)
            if current_min != prev_min:
                bar_closed = True

        if bar_closed:
            self._bar_open = True
            self._last_price_update = timestamp
            self._bar_index += 1
            self.state.bar_close_count += 1
            self.ohlcv_history.append({
                "open": price_data.open, "high": price_data.high,
                "low": price_data.low, "close": price_data.close,
                "volume": price_data.volume, "timestamp": timestamp,
                "provider": provider,
            })
            if len(self.ohlcv_history) > 200:
                self.ohlcv_history = self.ohlcv_history[-200:]
            logger.info(f"📊 BAR CLOSE #{self.state.bar_close_count} at {timestamp.isoformat()} close={price_data.close} volume={price_data.volume} provider={provider} (ohlcv={len(self.ohlcv_history)})")
        else:
            self._bar_open = False
            if self.ohlcv_history:
                self.ohlcv_history[-1]["high"] = max(self.ohlcv_history[-1]["high"], price_data.high)
                self.ohlcv_history[-1]["low"] = min(self.ohlcv_history[-1]["low"], price_data.low)
                self.ohlcv_history[-1]["close"] = price_data.close
                self.ohlcv_history[-1]["volume"] += price_data.volume
                if provider:
                    self.ohlcv_history[-1]["provider"] = provider

        # E-4: the projection is NOT recomputed on bar close. It is recomputed
        # on execution events (see the four dispatch subblocks), on engine init,
        # on symbol change, and on explicit POST /projection/refresh.
        # NOTE: _populate_indicator_matrix() is NOT called here. The engine's
        # _on_bar() -> _normalize() path already populates the iA/cA matrix
        # for the current bar. Calling _populate_indicator_matrix() here
        # would recompute all X_PERIOD * 13 indicator values redundantly.
        # The matrix population for the full history window is done once by
        # _force_initialization() on first init and by change_symbol() on
        # symbol change; per-bar updates are handled incrementally by
        # _on_bar().

        self._on_tick(price_data)

    def _send_signal_alert(self) -> None:
        st = self.state
        target_chat = st.chat_id
        if target_chat is None and st.webapp_user_id is not None:
            target_chat = st.webapp_user_id
        if not target_chat or not self.application:
            return
        if not self._alert_delivery_enabled:
            return
        direction = "📈 ↑" if st.price > st.signal else "📉 ↓"
        m_local = st.authoritative_m
        n_local = st.authoritative_n
        h_idx = st.h - (st.y + 1)
        m_at_h = 1 if (0 <= h_idx < len(st.k) and st.k[h_idx]) else 0
        n_at_h = 1 if (0 <= h_idx < len(st.l) and st.l[h_idx]) else 0
        condition_met = (m_local >= 12) or (n_local >= 12)
        idx = st.Z - (st.y + 1)
        regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "Unknown"
        # D-46 / E-12: every interpolated value is Markdown-escaped before it
        # is placed into the parse_mode="Markdown" template. The static
        # template characters (*, _, `) remain meaningful to the parser.
        msg = (
            f"🎯 *ÆEA 𝒮\\_signal ℰ\\_alert*\n"
            f"📊 *Direction:* {_md_escape(direction)}\n"
            f"🎯 *Signal Level:* {_md_escape(st.signal)}\n"
            f"💰 *Current Price:* {_md_escape(st.price)}\n"
            f"📊 *ℛ\\_regime:* {_md_escape(regime)}\n"
            f"⚖️ *Imbalance @ h={_md_escape(st.h)}:* m={_md_escape(m_at_h)}, n={_md_escape(n_at_h)}\n"
            f"⚖️ *Local m/n:* {_md_escape(m_local)}/{_md_escape(n_local)}\n"
            f"✅ *δ(m-n-2)=1:* {'✅ 𝒜₃ MET' if condition_met else '❌ 𝒜₄ NOT MET'}\n"
            f"🔄 *Tick Count:* {_md_escape(st.tick)}\n"
            f"💎 Natalia Tanyatia"
        )
        bot = BRIDGE_ENGINE_REF.get("bot")
        if bot is not None and hasattr(bot, "_send_message_sync"):
            reply_to = st.last_inbound_message_id if isinstance(st.last_inbound_message_id, int) else None
            ok = bot._send_message_sync(
                chat_id=target_chat,
                text=msg,
                parse_mode="Markdown",
                reply_to_message_id=reply_to,
            )
            if ok:
                logger.info(f"📡 Signal alert sent to {target_chat} reply_to={reply_to} (tick={st.tick})")
            else:
                logger.warning(f"❌ Signal alert send failed for {target_chat} (tick={st.tick})")
            return
        # Fallback: the engine may hold a direct reference to the bot's
        # Application when BRIDGE_ENGINE_REF has not yet been populated
        # (e.g. during the brief window between dyno restart and the first
        # /start command). In that case, route through the engine's own
        # application reference if it exposes _send_message_sync.
        app = self.application
        if app is not None and hasattr(app, "_send_message_sync"):
            reply_to = st.last_inbound_message_id if isinstance(st.last_inbound_message_id, int) else None
            ok = app._send_message_sync(
                chat_id=target_chat,
                text=msg,
                parse_mode="Markdown",
                reply_to_message_id=reply_to,
            )
            if ok:
                logger.info(f"📡 Signal alert sent via engine.application to {target_chat} reply_to={reply_to} (tick={st.tick})")
            else:
                logger.warning(f"❌ Signal alert send via engine.application failed for {target_chat} (tick={st.tick})")
            return
        logger.warning("❌ Signal alert skipped: bot reference or _send_message_sync unavailable")

    def _send_execution_alert(self, event: str, price: Decimal, side: str, ticket: int, reason: str) -> None:
        st = self.state
        target_chat = st.chat_id
        if target_chat is None and st.webapp_user_id is not None:
            target_chat = st.webapp_user_id
        if not target_chat or not self.application:
            return
        if not self._alert_delivery_enabled:
            return
        emoji_map = {
            "Bull": "🐂", "Bear": "🐻", "Whisky": "🥃", "Wine": "🍷",
            "Watter": "💧", "Blood": "🩸", "Hawk": "🦅", "Dove": "🕊️",
            "Diamond": "🔷", "Ruby": "🔻", "Top": "▲", "Bott": "▼",
            "A": "🅰️", "B": "🅱️", "ManualOrder": "📝", "ManualClose": "✂️",
        }
        cs_map = {
            "Bull": "𝒟\\_Bull", "Bear": "𝒟\\_Bear", "Whisky": "𝒲\\_Whisky",
            "Wine": "𝒲\\_Wine", "Watter": "𝒲\\_Watter", "Blood": "ℬ\\_Blood",
            "Hawk": "ℋ\\_Hawk", "Dove": "𝒟\\_Dove", "Diamond": "𝒟\\_Diamond",
            "Ruby": "ℛ\\_Ruby", "Top": "𝒯\\_Top", "Bott": "ℬ\\_Bott",
            "A": "𝒜", "B": "ℬ\\_Close", "ManualOrder": "ℳ\\_Order",
            "ManualClose": "ℳ\\_Close",
        }
        emoji = emoji_map.get(event, "⚡")
        cs_event = cs_map.get(event, event)
        side_str = side if side else "NONE"
        ticket_str = f"#{ticket}" if ticket != -1 else "—"
        reason_str = f" | {_md_escape(reason)}" if reason else ""
        # D-46 / E-12: escape every interpolated value.
        msg = (
            f"{emoji} *ÆEA ℰ\\_exec*\n"
            f"📛 *Event:* {_md_escape(cs_event)}\n"
            f"📊 *Side:* {_md_escape(side_str)}\n"
            f"🎫 *Ticket:* {_md_escape(ticket_str)}\n"
            f"💰 *Price:* {_md_escape(price)}{reason_str}\n"
            f"🔄 *Tick:* {_md_escape(st.tick)}\n"
            f"💎 Natalia Tanyatia"
        )
        bot = BRIDGE_ENGINE_REF.get("bot")
        if bot is not None and hasattr(bot, "_send_message_sync"):
            reply_to = st.last_inbound_message_id if isinstance(st.last_inbound_message_id, int) else None
            ok = bot._send_message_sync(
                chat_id=target_chat,
                text=msg,
                parse_mode="Markdown",
                reply_to_message_id=reply_to,
            )
            if ok:
                logger.info(f"📡 Execution alert ({event}) sent to {target_chat} reply_to={reply_to} (tick={st.tick})")
            else:
                logger.warning(f"❌ Execution alert ({event}) send failed (tick={st.tick})")
            return
        app = self.application
        if app is not None and hasattr(app, "_send_message_sync"):
            reply_to = st.last_inbound_message_id if isinstance(st.last_inbound_message_id, int) else None
            ok = app._send_message_sync(
                chat_id=target_chat,
                text=msg,
                parse_mode="Markdown",
                reply_to_message_id=reply_to,
            )
            if ok:
                logger.info(f"📡 Execution alert ({event}) sent via engine.application to {target_chat} reply_to={reply_to} (tick={st.tick})")
            else:
                logger.warning(f"❌ Execution alert ({event}) send via engine.application failed (tick={st.tick})")
            return
        logger.warning("❌ Execution alert skipped: bot reference or _send_message_sync unavailable")

    def get_signal_status(self) -> Dict[str, Any]:
        st = self.state
        h_idx = st.h - (st.y + 1)
        m_at_h = 1 if (0 <= h_idx < len(st.k) and st.k[h_idx]) else 0
        n_at_h = 1 if (0 <= h_idx < len(st.l) and st.l[h_idx]) else 0
        m_local = st.authoritative_m
        n_local = st.authoritative_n
        condition_met = (m_local >= 12) or (n_local >= 12)
        idx = st.Z - (st.y + 1)
        regime = st.Regime[idx] if 0 <= idx < len(st.Regime) and st.Regime[idx] else "Unknown"
        return {
            "signal": float(st.signal),
            "price": float(st.price),
            "signature": st.signature,
            "KC": bool(st.KC),
            "prime": int(st.prime),
            "dime": int(st.dime),
            "mem": int(st.mem),
            "tag": int(st.tag),
            "invert": bool(st.invert),
            "safety": bool(st.safety),
            "m_count": m_local,
            "n_count": n_local,
            "m_at_h": m_at_h,
            "n_at_h": n_at_h,
            "h_bar": int(st.h),
            "condition_met": condition_met,
            "regime": regime,
            "symbol": SYMBOL,
            "tick": st.tick,
            "timestamp": datetime.now().isoformat(),
            "engine_initialized": st.FG,
            "indicator_populate_count": int(self._indicator_populate_count),
            "imbalance_fire_count": int(self._imbalance_fire_count),
            "trailing_stop_active": st.trailing_stop_active,
            "trailing_stop_price": str(st.trailing_stop_price),
            "trailing_take_profit": str(st.trailing_take_profit),
            "trailing_stop_entry": str(st.trailing_stop_entry),
            "trailing_stop_side": st.trailing_stop_side,
            "has_open_long": bool(st.has_open_long),
            "has_open_short": bool(st.has_open_short),
            "lOrder_id": int(st.lOrder_id),
            "kOrder_id": int(st.kOrder_id),
            "on_track_runs": int(st.on_track_runs),
            "on_stand_runs": int(st.on_stand_runs),
            "last_kronecker_bar": int(self._last_kronecker_bar),
            "last_kronecker_m": int(st.last_kronecker_m),
            "last_kronecker_n": int(st.last_kronecker_n),
            "last_kronecker_h": int(st.last_kronecker_h),
            "authoritative_m": int(st.authoritative_m),
            "authoritative_n": int(st.authoritative_n),
            "authoritative_h": int(st.authoritative_h),
            "X_scan": int(st.X_scan),
            "Y_scan": int(st.Y_scan),
            "S": int(st.S),
            "T": int(st.T),
            "r": int(st.r),
            "ir": int(st.ir),
            "iATR": float(st.iATR),
            "iStdDev": float(st.iStdDev),
            "iIHKk": float(st.iIHKk),
            "iIHKt": float(st.iIHKt),
            "signal_count": len(st.signal_history),
            "last_signal_at": st.last_signal_at,
            "bar_close_count": int(st.bar_close_count),
            "ohlcv_count": len(self.ohlcv_history),
            "market_m": int(st.authoritative_m),
            "market_n": int(st.authoritative_n),
            "market_imbalance": int(st.authoritative_m) - int(st.authoritative_n) - 2,
            "market_regime": "BULLISH" if (int(st.authoritative_m) - int(st.authoritative_n) - 2) > 2 else ("BEARISH" if (int(st.authoritative_m) - int(st.authoritative_n) - 2) < -2 else "NEUTRAL"),
            "A": bool(st.A),
            "B": bool(st.B),
            "C": bool(st.C),
            "c": bool(st.c),
            "tick_tock": bool(st.tick_tock),
            "Z": int(st.Z),
            "z": int(st.z),
            "O": int(st.O),
            "o": int(st.o),
            "W": int(st.W),
            "w": int(st.w),
            "I": int(st.I),
            "iI": int(st.iI),
            "J": int(st.J),
            "iJ": int(st.iJ),
            "iZ": int(st.iZ),
            "iz": int(st.iz),
            "iW": int(st.iW),
            "iw": int(st.iw),
            "iO": int(st.iO),
            "io": int(st.io),
            "lPass": str(st.lPass),
            "ilPass": str(st.ilPass),
            "kPass": str(st.kPass),
            "ikPass": str(st.ikPass),
            "comment_line": self._format_comment_line(),
            "last_provider": st.last_provider,
            "last_volume": str(st.last_volume),
            "projection_computed_at": st.projection_computed_at,
            "projection_trigger": st.projection_trigger,
            "last_inbound_message_id": st.last_inbound_message_id,
        }

    def get_regime_map(self) -> List[Dict[str, Any]]:
        st = self.state
        out = []
        for i, regime in enumerate(st.Regime):
            prem = st.Premium[i] if i < len(st.Premium) else Decimal('0.0')
            disc = st.Discount[i] if i < len(st.Discount) else Decimal('0.0')
            hh = st.HH[i] if i < len(st.HH) else Decimal('0.0')
            ll = st.LL[i] if i < len(st.LL) else Decimal('0.0')
            k_flag = st.k[i] if i < len(st.k) else False
            l_flag = st.l[i] if i < len(st.l) else False
            out.append({
                "index": i,
                "regime": regime,
                "k": bool(k_flag),
                "l": bool(l_flag),
                "premium": float(prem),
                "discount": float(disc),
                "hh": float(hh),
                "ll": float(ll),
            })
        return out

    def get_indicator_series(self, name: str, count: int = 80) -> List[float]:
        st = self.state
        idx = INDICATOR_NAMES.index(name) if name in INDICATOR_NAMES else -1
        if idx < 0:
            if name == "IchimokuK":
                return [float(v) for v in st.IHKk[-count:]]
            if name == "IchimokuT":
                return [float(v) for v in st.IHKt[-count:]]
            if name == "ATR":
                return [float(v) for v in st.ATR[-count:]]
            if name == "StdDev":
                return [float(v) for v in st.StdDev[-count:]]
            return []
        row = st.iA[idx] if idx < len(st.iA) else []
        return [float(v) for v in row[-count:]]

    def place_order(self, side: str, lot: Decimal, sl: Decimal, tp: Decimal) -> Dict[str, Any]:
        st = self.state
        if st.price <= Decimal('0.0'):
            return {"error": "no_price"}
        if side not in ("BUY", "SELL"):
            return {"error": "invalid_side"}
        if lot <= Decimal('0.0'):
            return {"error": "invalid_lot"}
        entry = st.price
        if sl <= Decimal('0.0'):
            sl = Decimal('0.0')
        if tp <= Decimal('0.0'):
            tp = Decimal('0.0')
        ticket = self._open_order(side, entry, sl, tp, lot)
        if side == "BUY":
            st.has_open_long = True
            st.lOrder_id = ticket
            st.trailing_stop_entry = entry
            st.trailing_stop_side = "LONG"
        else:
            st.has_open_short = True
            st.kOrder_id = ticket
            st.trailing_stop_entry = entry
            st.trailing_stop_side = "SHORT"
        logger.info(f"📝 place_order: {side} #{ticket} @ {entry}, lot={lot}, sl={sl}, tp={tp}")
        self._emit_execution_toast("ManualOrder", entry, side, ticket, "manual")
        return {"ok": True, "ticket": ticket, "side": side, "entry": float(entry), "sl": float(sl), "tp": float(tp)}

    def close_order(self, ticket: int = None, all: bool = False) -> Dict[str, Any]:
        st = self.state
        closed = []
        if all:
            for o in self.orders:
                if o.closed_at is None:
                    o.closed_at = datetime.now()
                    o.close_price = st.price
                    closed.append(o.ticket)
            st.has_open_long = False
            st.has_open_short = False
            st.lOrder_id = -1
            st.kOrder_id = -1
            st.trailing_stop_active = False
            st.trailing_stop_price = Decimal('0.0')
            st.trailing_take_profit = Decimal('0.0')
            st.trailing_stop_entry = Decimal('0.0')
            st.trailing_stop_side = ""
        else:
            if ticket is None:
                return {"error": "no_ticket"}
            for o in self.orders:
                if o.ticket == ticket and o.closed_at is None:
                    o.closed_at = datetime.now()
                    o.close_price = st.price
                    closed.append(o.ticket)
                    if o.side == "BUY":
                        st.has_open_long = False
                        st.lOrder_id = -1
                    else:
                        st.has_open_short = False
                        st.kOrder_id = -1
                    break
        logger.info(f"📝 close_order: closed={closed}")
        if closed:
            self._emit_execution_toast("ManualClose", st.price, "CLOSE", closed[0] if len(closed) == 1 else -1, "manual")
        return {"ok": True, "closed": closed}

    def list_orders(self) -> List[Dict[str, Any]]:
        st = self.state
        out = []
        for o in self.orders:
            if o.closed_at is not None:
                continue
            pnl = o.pnl(st.price) if st.price > Decimal('0.0') else Decimal('0.0')
            out.append({
                "ticket": o.ticket,
                "side": o.side,
                "entry": float(o.entry),
                "sl": float(o.sl),
                "tp": float(o.tp),
                "lot": float(o.lot),
                "pnl": float(pnl),
                "opened_at": o.opened_at.isoformat(),
            })
        return out

    def get_settings(self) -> Dict[str, Any]:
        st = self.state
        return {
            "max": int(MAX_PERIOD),
            "min": int(MIN_PERIOD),
            "Cc": bool(st.Cc),
            "cC": bool(st.cC),
            "Memory": int(Memory),
            "safetyOffSwitch": bool(st.safety),
            "StopLoss": str(STOP_LOSS),
            "TakeProfit": str(TAKE_PROFIT),
            "lot": str(LOT_SIZE),
            "slip": int(SLIPPAGE),
            "Commssion": str(COMMISSION),
        }

    def apply_settings(self, s: Dict[str, Any]) -> Dict[str, Any]:
        global MAX_PERIOD, MIN_PERIOD, X_PERIOD, Y_START, COMMISSION, STOP_LOSS, TAKE_PROFIT, LOT_SIZE, SLIPPAGE, Memory
        st = self.state
        try:
            errors = []
            new_max = MAX_PERIOD
            new_min = MIN_PERIOD
            if "max" in s:
                try:
                    new_max = int(s["max"])
                except (TypeError, ValueError):
                    errors.append("max: must be an integer")
                else:
                    if new_max < MAX_PERIOD_MIN:
                        errors.append(f"max: must be >= {MAX_PERIOD_MIN}")
                    if new_max > MAX_PERIOD_MAX:
                        errors.append(f"max: must be <= {MAX_PERIOD_MAX}")
            if "min" in s:
                try:
                    new_min = int(s["min"])
                except (TypeError, ValueError):
                    errors.append("min: must be an integer")
                else:
                    if new_min < MIN_PERIOD_MIN:
                        errors.append(f"min: must be >= {MIN_PERIOD_MIN}")
                    if new_min > MIN_PERIOD_MAX:
                        errors.append(f"min: must be <= {MIN_PERIOD_MAX}")
            if new_max < new_min + MAX_MIN_GAP:
                errors.append(f"max ({new_max}) must be >= min ({new_min}) + {MAX_MIN_GAP}")
            new_sl = STOP_LOSS
            new_tp = TAKE_PROFIT
            new_lot = LOT_SIZE
            new_com = COMMISSION
            new_slip = SLIPPAGE
            if "StopLoss" in s:
                try:
                    v = Fraction.from_decimal_string(str(s["StopLoss"])).to_decimal()
                    if v < Decimal('0.0'):
                        errors.append("StopLoss: must be >= 0")
                    else:
                        new_sl = v
                except Exception as e:
                    errors.append(f"StopLoss: {e}")
            if "TakeProfit" in s:
                try:
                    v = Fraction.from_decimal_string(str(s["TakeProfit"])).to_decimal()
                    if v < Decimal('0.0'):
                        errors.append("TakeProfit: must be >= 0")
                    else:
                        new_tp = v
                except Exception as e:
                    errors.append(f"TakeProfit: {e}")
            if "lot" in s:
                try:
                    v = Fraction.from_decimal_string(str(s["lot"])).to_decimal()
                    if v <= Decimal('0.0'):
                        errors.append("lot: must be > 0")
                    else:
                        new_lot = v
                except Exception as e:
                    errors.append(f"lot: {e}")
            if "Commssion" in s:
                try:
                    v = Fraction.from_decimal_string(str(s["Commssion"])).to_decimal()
                    if v < Decimal('0.0'):
                        errors.append("Commssion: must be >= 0")
                    else:
                        new_com = v
                except Exception as e:
                    errors.append(f"Commssion: {e}")
            if "slip" in s:
                try:
                    v = int(s["slip"])
                    if v < 0:
                        errors.append("slip: must be >= 0")
                    else:
                        new_slip = v
                except (TypeError, ValueError):
                    errors.append("slip: must be an integer")
            if errors:
                logger.warning(f"apply_settings validation failed: {errors}")
                return {"error": "validation", "detail": "; ".join(errors)}
            MAX_PERIOD = new_max
            MIN_PERIOD = new_min
            X_PERIOD = MAX_PERIOD + 2
            Y_START = MIN_PERIOD - 2
            st.y = Y_START
            COMMISSION = new_com
            STOP_LOSS = new_sl
            TAKE_PROFIT = new_tp
            LOT_SIZE = new_lot
            SLIPPAGE = new_slip
            if "Cc" in s: st.Cc = bool(s["Cc"])
            if "cC" in s: st.cC = bool(s["cC"])
            if "Memory" in s:
                mem_val = s["Memory"]
                if mem_val is None:
                    Memory = -1
                else:
                    try:
                        Memory = int(mem_val)
                    except (TypeError, ValueError):
                        Memory = -1
            st.mem = Memory
            if "safetyOffSwitch" in s: st.safety = bool(s["safetyOffSwitch"])
            self.OnReInit()
            logger.info(f"⚙️ Settings applied: max={MAX_PERIOD}, min={MIN_PERIOD}, Cc={st.Cc}, cC={st.cC}, mem={st.mem}, safety={st.safety}, SL={STOP_LOSS}, TP={TAKE_PROFIT}, lot={LOT_SIZE}, slip={SLIPPAGE}, com={COMMISSION}")
            return {"ok": True}
        except Exception as e:
            logger.error(f"apply_settings failed: {e}")
            return {"error": str(e)}

    def change_symbol(self, new_symbol: str) -> Dict[str, Any]:
        global SYMBOL
        try:
            if not new_symbol or not isinstance(new_symbol, str):
                return {"error": "invalid_symbol", "detail": "Symbol must be a non-empty string"}
            yahoo_symbol = SYMBOL_MAP.get(new_symbol.upper(), new_symbol.upper())
            test_feed = FeedClient(yahoo_symbol)
            bid, _ = test_feed.get_current_price()
            if bid <= Decimal('0.0'):
                return {
                    "error": "no_price_for_symbol",
                    "symbol": yahoo_symbol,
                    "detail": f"Relay returned no price for '{yahoo_symbol}'. Check RELAY_URL and symbol validity.",
                }
            prev_chat = self.state.chat_id
            prev_on_track = self.state.on_track_runs
            prev_on_stand = self.state.on_stand_runs
            prev_signals = self.state.signal_history
            prev_inbound = self.state.last_inbound_message_id
            SYMBOL = yahoo_symbol
            self.feed = FeedClient(yahoo_symbol)
            self._point_size = symbol_point(yahoo_symbol)
            self.OnReInit()
            self.state.chat_id = prev_chat
            self.state.on_track_runs = prev_on_track
            self.state.on_stand_runs = prev_on_stand
            self.state.signal_history = prev_signals
            self.state.last_inbound_message_id = prev_inbound
            historical = self.feed.get_historical_klines(limit=200)
            if historical:
                self.ohlcv_history = historical
                self._populate_indicator_matrix()
                self._force_initialization()
            # E-4: seed the projection for the newly-selected symbol immediately
            # rather than waiting for the next execution.
            self._project_arc_length(trigger="symbol_change")
            logger.info(f"📈 Symbol changed to {yahoo_symbol} (provider={self.feed.last_provider()})")
            return {"ok": True, "symbol": yahoo_symbol, "provider": self.feed.last_provider()}
        except Exception as e:
            logger.exception("change_symbol failed")
            return {"error": "change_symbol_exception", "detail": str(e), "symbol": new_symbol}

    def _project_arc_length(self, trigger: str = "manual_refresh") -> None:
        st = self.state
        if len(self.ohlcv_history) < min(MIN_HISTORY_WINDOW, 20):
            st.projection_path = []
            st.projection_meta = {"reason": "insufficient_history"}
            st.projection_computed_at = datetime.now().isoformat()
            st.projection_trigger = trigger
            return
        horizon = max(4, min(120, ARC_PROJECTION_HORIZON))
        price_now = st.price if st.price > Decimal('0.0') else self.ohlcv_history[-1]["close"]
        signal_now = st.signal if st.signal != Decimal('0.0') else price_now
        regime_idx = st.Z - (st.y + 1)
        regime = st.Regime[regime_idx] if 0 <= regime_idx < len(st.Regime) else "Unknown"
        projection_kind = "range"
        if regime in ("sTrend", "tTrend"):
            projection_kind = "trend"
        elif regime in ("sVolatile", "tVolatile"):
            projection_kind = "volatile"
        elif regime in ("sRange", "tRange", "Stable"):
            projection_kind = "range"
        slope = Decimal('0.0')
        if projection_kind == "trend":
            window = self.ohlcv_history[-min(10, len(self.ohlcv_history)):]
            if len(window) >= 2:
                first_close = window[0]["close"]
                last_close = window[-1]["close"]
                n_minus_1 = Decimal(len(window) - 1)
                slope = (last_close - first_close) / n_minus_1
        amplitude = Decimal('0.0')
        center = price_now
        if projection_kind == "volatile":
            prem = Decimal('0.0')
            disc = Decimal('0.0')
            for i in range(len(st.Premium) - 1, -1, -1):
                if st.Premium[i] > Decimal('0.0'):
                    prem = st.Premium[i]
                    break
            for i in range(len(st.Discount) - 1, -1, -1):
                if st.Discount[i] > Decimal('0.0'):
                    disc = st.Discount[i]
                    break
            if prem > Decimal('0.0') and disc > Decimal('0.0') and prem > disc:
                center = (prem + disc) / Decimal('2.0')
                amplitude = (prem - disc) / Decimal('2.0')
            else:
                atr_val = st.ATR[st.y] if st.y < len(st.ATR) else Decimal('0.0')
                if atr_val > Decimal('0.0'):
                    amplitude = atr_val
                    center = price_now
        damping = ARC_PROJECTION_DAMPING_D
        path: List[Dict[str, Any]] = []
        # D-33: keep the half-period as a Fraction until the cosine call site.
        # When horizon is odd, Decimal(horizon) / Decimal('2.0') is a
        # non-terminating base-10 decimal and the later multiplication by pi
        # accumulated representation error. A Fraction half-period avoids this.
        half_period_frac = PyFraction(horizon, 2)
        pi_d = Decimal('3.1415926535897932384626433832795028841971693993751')
        two_pi_d = Decimal('6.2831853071795864769252867665590057683943387987502')
        for k in range(1, horizon + 1):
            t = Decimal(k)
            if projection_kind == "trend":
                future_price = price_now + slope * t
            elif projection_kind == "volatile":
                t_frac = PyFraction(k, 1)
                ratio_frac = t_frac / PyFraction(horizon, 1)
                omega_t = two_pi_d * Decimal(ratio_frac.numerator) / Decimal(ratio_frac.denominator)
                cos_val = self._decimal_cos(omega_t)
                # Compute decay iteratively: damping ** k for Decimal can
                # raise InvalidOperation when the intermediate result
                # underflows the Decimal context precision for large k.
                # Iterative multiplication stays within the representable
                # range for the (0, 1) damping values the env validation
                # enforces.
                decay = Decimal('1.0')
                for _dk in range(k):
                    decay = decay * damping
                future_price = center + amplitude * cos_val * decay
            else:
                t_frac = PyFraction(k, 1)
                ratio_frac = t_frac / half_period_frac
                omega_t = pi_d * Decimal(ratio_frac.numerator) / Decimal(ratio_frac.denominator)
                cos_val = self._decimal_cos(omega_t)
                delta = price_now - signal_now
                future_price = signal_now + delta * cos_val
            path.append({
                "step": k,
                "price": str(future_price.quantize(Decimal('0.00001'))),
                "t": float(t),
            })
        st.projection_path = path
        st.projection_meta = {
            "kind": projection_kind,
            "horizon": horizon,
            "price_now": str(price_now),
            "signal_now": str(signal_now),
            "regime": regime,
            "slope": str(slope),
            "amplitude": str(amplitude),
            "center": str(center),
            "damping": str(damping),
            "provider": st.last_provider,
        }
        st.projection_computed_at = datetime.now().isoformat()
        st.projection_trigger = trigger
        logger.info(f"🌌 Projection recomputed (trigger={trigger}, kind={projection_kind}, horizon={horizon})")

    @staticmethod
    def _decimal_cos(x: Decimal) -> Decimal:
        # Range reduction: bring x into [-pi, pi] using the periodicity of
        # cosine. Without this, the Taylor series truncation at 30 terms
        # is inaccurate for |x| > ~10 because the factorial growth of the
        # terms outpaces the truncation. The projection's omega_t can reach
        # 2*pi*horizon (up to 240*pi for horizon=120), so range reduction
        # is mandatory for correctness.
        pi_d = Decimal('3.1415926535897932384626433832795028841971693993751')
        two_pi_d = Decimal('6.2831853071795864769252867665590057683943387987502')
        # Reduce modulo 2*pi.
        n_periods = int(x / two_pi_d)
        x_reduced = x - two_pi_d * Decimal(n_periods)
        # Map into [-pi, pi].
        if x_reduced > pi_d:
            x_reduced = x_reduced - two_pi_d
        elif x_reduced < -pi_d:
            x_reduced = x_reduced + two_pi_d
        # Taylor series on the reduced argument. With |x_reduced| <= pi,
        # 30 terms gives ~1e-30 accuracy at the 50-digit context.
        x2 = x_reduced * x_reduced
        term = Decimal('1.0')
        result = Decimal('1.0')
        sign = -1
        for n in range(1, 30):
            term = term * x2 / (Decimal(2 * n - 1) * Decimal(2 * n))
            result = result + (Decimal(sign) * term)
            sign = -sign
        return result

    def get_projection(self) -> Dict[str, Any]:
        st = self.state
        if not st.projection_path:
            self._project_arc_length(trigger="manual_refresh")
        return {
            "symbol": SYMBOL,
            "path": st.projection_path,
            "meta": st.projection_meta,
            "computed_at": st.projection_computed_at,
            "current_price": str(st.price),
            "signal_level": str(st.signal),
            "regime": st.projection_meta.get("regime") if st.projection_meta else "Unknown",
            "trigger": st.projection_trigger,
        }

# ============================================================================
# BRIDGE STATE
# ============================================================================
class BridgeState:
    def __init__(self):
        self._lock = threading.Lock()
        self._fvgs: Dict[int, Dict[str, Any]] = {}
        self._next_fvg_idx = 0
        self._webapp_sessions: Dict[int, Dict[str, Any]] = {}
        self._handshake_lock = threading.Lock()

    def register_webapp_session(self, user_id: int, username: Optional[str], chat_id: Optional[int] = None) -> bool:
        with self._handshake_lock:
            self._webapp_sessions[user_id] = {
                "user_id": user_id, "username": username, "chat_id": chat_id,
                "first_seen": self._webapp_sessions.get(user_id, {}).get("first_seen", datetime.now().isoformat()),
                "last_seen": datetime.now().isoformat(),
            }
        engine = BRIDGE_ENGINE_REF.get("engine")
        if engine is not None:
            try:
                engine.state.webapp_user_id = user_id
                engine.state.webapp_username = username
                engine.state.webapp_verified = True
                engine.state.webapp_last_seen = datetime.now()
                if chat_id is not None:
                    engine.state.chat_id = chat_id
            except Exception as e:
                logger.warning(f"register_webapp_session → engine map failed: {e}")
        logger.info(f"🔗 Web App session registered: user_id={user_id}, username={username}")
        return True

    def add_fvg(self, fvg_type: str, price_str: str, user_id: Optional[int] = None, requested_idx: Optional[int] = None) -> int:
        if fvg_type not in ("top", "bott"):
            raise ValueError("fvg_type must be 'top' or 'bott'")
        try:
            price_dec = Decimal(str(price_str))
        except Exception:
            raise ValueError("price must be a decimal string")
        if price_dec <= Decimal('0.0'):
            raise ValueError("price must be > 0")
        with self._lock:
            if requested_idx is not None and isinstance(requested_idx, int) and requested_idx >= 0:
                idx = requested_idx
                if idx >= self._next_fvg_idx:
                    self._next_fvg_idx = idx + 1
            else:
                # User-committed FVG anchors are namespaced into a high range
                # (1000000+) so they cannot collide with the engine's
                # array-position idx values (which are small integers in
                # st.BL's 0..N-1 range). The TWA merges FVG anchors by idx;
                # collision would cause a user anchor to overwrite an engine
                # anchor or vice versa.
                if self._next_fvg_idx < 1000000:
                    self._next_fvg_idx = 1000000
                idx = self._next_fvg_idx
                self._next_fvg_idx += 1
            self._fvgs[idx] = {
                "type": fvg_type, "price": str(price_dec), "idx": idx,
                "created": datetime.now().isoformat(), "user_id": user_id,
            }
        engine = BRIDGE_ENGINE_REF.get("engine")
        if engine is not None:
            engine.state.fvg_anchor_map[idx] = {
                "idx": idx, "type": fvg_type, "price": str(price_dec),
                "created": datetime.now().isoformat(),
            }
        _emit_toast("fvg", {
            "action": "commit",
            "type": fvg_type,
            "price": str(price_dec),
            "idx": idx,
            "tick": int(engine.state.tick) if engine is not None else 0,
        })
        return idx

    def remove_fvg(self, idx: int) -> bool:
        with self._lock:
            if idx in self._fvgs:
                removed_record = self._fvgs.pop(idx)
                removed = True
            else:
                removed_record = None
                removed = False
        engine = BRIDGE_ENGINE_REF.get("engine")
        if engine is not None:
            engine.state.fvg_anchor_map.pop(idx, None)
        if removed and removed_record is not None:
            _emit_toast("fvg", {
                "action": "remove",
                "type": removed_record.get("type", "top"),
                "price": removed_record.get("price", "0"),
                "idx": idx,
                "tick": int(engine.state.tick) if engine is not None else 0,
            })
        return removed

    def list_fvgs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._fvgs.values())

BRIDGE_STATE = BridgeState()
BRIDGE_ENGINE_REF: Dict[str, Any] = {"engine": None, "bot": None, "public_url": None}

def _require_auth(handler: "BridgeHandler") -> bool:
    if not REQUIRE_AUTH or not TELEGRAM_BOT_TOKEN_ENV:
        return True
    raw_init = handler.headers.get("X-Telegram-Init-Data", "").strip()
    if not raw_init:
        auth_hdr = handler.headers.get("Authorization", "").strip()
        if auth_hdr.lower().startswith("tma "):
            raw_init = auth_hdr[4:].strip()
    if not raw_init:
        return False
    verified = verify_telegram_init_data(raw_init, TELEGRAM_BOT_TOKEN_ENV)
    return bool(verified and verified.get("user"))

# ============================================================================
# TUNNEL MANAGER
# ============================================================================
class TunnelManager:
    URL_RE_CLOUDFLARED = _re_bridge.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")
    URL_RE_NGROK = _re_bridge.compile(r"https://[a-z0-9\-]+\.ngrok(?:-free)?\.app")
    URL_RE_SERVEO = _re_bridge.compile(r"https://[a-z0-9\-]+\.serveo\.net")

    def __init__(self, port: int, prefer: str = "cloudflared", timeout: int = 45):
        self.port = port
        self.prefer = prefer
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None
        self.provider: Optional[str] = None

    def _which(self, name: str) -> Optional[str]:
        from shutil import which
        return which(name)

    def _spawn(self, cmd: List[str]) -> subprocess.Popen:
        logger.info(f"🌐 Spawning tunnel: {' '.join(cmd)}")
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

    def _scan_for_url(self, proc: subprocess.Popen, regex: "_re_bridge.Pattern[str]", deadline: float) -> Optional[str]:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            if line:
                logger.debug(f"[tunnel] {line}")
            m = regex.search(line)
            if m:
                return m.group(0)
            if time.time() > deadline:
                return None
        return None

    def _try_cloudflared(self) -> Optional[str]:
        if not self._which("cloudflared"):
            return None
        try:
            proc = self._spawn(["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{self.port}", "--no-autoupdate"])
        except Exception as e:
            logger.warning(f"cloudflared spawn failed: {e}")
            return None
        deadline = time.time() + self.timeout
        url = self._scan_for_url(proc, self.URL_RE_CLOUDFLARED, deadline)
        if url:
            self.process = proc
            self.public_url = url
            self.provider = "cloudflared"
            return url
        try:
            proc.terminate()
        except Exception:
            pass
        return None

    def _try_ngrok(self) -> Optional[str]:
        if not self._which("ngrok"):
            return None
        try:
            proc = self._spawn(["ngrok", "http", str(self.port), "--log=stdout"])
        except Exception as e:
            logger.warning(f"ngrok spawn failed: {e}")
            return None
        deadline = time.time() + self.timeout
        url = self._scan_for_url(proc, self.URL_RE_NGROK, deadline)
        if url:
            self.process = proc
            self.public_url = url
            self.provider = "ngrok"
            return url
        try:
            proc.terminate()
        except Exception:
            pass
        return None

    def _try_serveo(self) -> Optional[str]:
        if not self._which("ssh"):
            return None
        try:
            proc = self._spawn(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "-R", f"80:127.0.0.1:{self.port}", "serveo.net"])
        except Exception as e:
            logger.warning(f"serveo spawn failed: {e}")
            return None
        deadline = time.time() + self.timeout
        url = self._scan_for_url(proc, self.URL_RE_SERVEO, deadline)
        if url:
            self.process = proc
            self.public_url = url
            self.provider = "serveo"
            return url
        try:
            proc.terminate()
        except Exception:
            pass
        return None

    def start(self) -> Optional[str]:
        if TELEGRAM_WEBAPP_URL:
            self.public_url = TELEGRAM_WEBAPP_URL
            self.provider = "explicit"
            BRIDGE_ENGINE_REF["public_url"] = self.public_url
            logger.info(f"🌐 Using explicit TELEGRAM_WEBAPP_URL: {self.public_url}")
            return self.public_url
        order = [self.prefer] + [p for p in ("cloudflared", "ngrok", "serveo") if p != self.prefer]
        for provider in order:
            method = getattr(self, f"_try_{provider}", None)
            if method is None:
                continue
            try:
                url = method()
            except Exception as e:
                logger.warning(f"Tunnel provider {provider} raised: {e}")
                url = None
            if url:
                BRIDGE_ENGINE_REF["public_url"] = url
                logger.info(f"🌐 Tunnel established via {provider}: {url}")
                return url
        logger.warning("⚠️ No tunnel available. Telegram Mini App will require manual TELEGRAM_WEBAPP_URL.")
        return None

    def stop(self) -> None:
        if self.process is None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        self.process = None
        logger.info("🌐 Tunnel stopped")

# ============================================================================
# BRIDGE HANDLER
# ============================================================================
class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "AEI-Bridge/4.5.2"

    def log_message(self, fmt, *args):
        return

    def _set_cors(self) -> None:
        origin = CORS_ORIGIN
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Telegram-Init-Data, X-Relay-Key, X-Limit, X-Since")
        self.send_header("Access-Control-Max-Age", "86400")
        if origin != "*":
            self.send_header("Vary", "Origin")

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_json(self) -> Dict[str, Any]:
        raw = self._read_body()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._set_cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        query = dict(parse_qsl(urlparse(self.path).query))

        if path == "/health":
            engine = BRIDGE_ENGINE_REF.get("engine")
            last = None
            stale = True
            age_seconds = None
            if engine is not None:
                lu = engine.feed.last_update()
                if lu:
                    last = lu.isoformat()
                    age_seconds = (datetime.now() - lu).total_seconds()
                    stale = age_seconds > 60
            self._send_json(200, {
                "ok": not stale, "service": "aei-bridge", "version": "4.5.2",
                "last_price_update": last,
                "age_seconds": age_seconds, "stale": stale,
                "engine_initialized": bool(engine.state.FG) if engine else False,
                "indicator_populate_count": int(engine._indicator_populate_count) if engine else 0,
                "imbalance_fire_count": int(engine._imbalance_fire_count) if engine else 0,
                "ohlcv_count": len(engine.ohlcv_history) if engine else 0,
                "signal_count": len(engine.state.signal_history) if engine else 0,
                "bar_close_count": int(engine.state.bar_close_count) if engine else 0,
                "relay_healthy": (engine.feed.failure_count() < 3) if engine else True,
                "provider": engine.feed.last_provider() if engine else "",
                "projection_computed_at": engine.state.projection_computed_at if engine else None,
                "projection_trigger": engine.state.projection_trigger if engine else "",
            })
            return

        if not _require_auth(self):
            self._send_json(401, {"error": "unauthorized", "detail": "Missing or invalid X-Telegram-Init-Data"})
            return

        if path == "/config":
            self._send_json(200, {
                "public_url": BRIDGE_ENGINE_REF.get("public_url"), "tls": BRIDGE_USE_TLS,
                "port": BRIDGE_PORT, "host": BRIDGE_HOST, "symbol": SYMBOL,
                "webapp_enabled": True, "cors_origin": CORS_ORIGIN,
                "relay_url": RELAY_URL, "relay_gated": bool(RELAY_KEY),
                "x_period_constant": X_PERIOD, "y_start_constant": Y_START,
                "require_auth": REQUIRE_AUTH,
                "push_on_signal": PUSH_ON_SIGNAL,
                "push_on_execution": PUSH_ON_EXECUTION,
                "push_on_fvg": PUSH_ON_FVG,
                "push_on_close": PUSH_ON_CLOSE,
                "arc_projection_horizon": ARC_PROJECTION_HORIZON,
                "arc_projection_step": ARC_PROJECTION_STEP,
                "arc_projection_damping": str(ARC_PROJECTION_DAMPING_D),
            })
            return

        if path == "/settings":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            self._send_json(200, engine.get_settings())
            return

        if path == "/toasts":
            try:
                since = int(self.headers.get("X-Since", query.get("since", "0")))
            except (TypeError, ValueError):
                since = 0
            with _TOAST_LOCK:
                toasts = [t for t in _TOAST_BUFFER if t.get("seq", 0) > since]
                latest_seq = _TOAST_SEQ
                first_available = _TOAST_FIRST_AVAILABLE_SEQ
            self._send_json(200, {
                "toasts": toasts,
                "count": len(toasts),
                "latest_seq": latest_seq,
                "first_available_seq": first_available,
            })
            return

        if path == "/projection":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            self._send_json(200, engine.get_projection())
            return

        if path == "/state":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready", "detail": "Engine hasn't started. Use /start_feed in the bot."})
                return
            st = engine.state
            public = BRIDGE_ENGINE_REF.get("public_url")
            if public:
                endpoint = public
            else:
                host = self.headers.get("Host", f"{BRIDGE_HOST}:{BRIDGE_PORT}")
                scheme = "https" if BRIDGE_USE_TLS else "http"
                endpoint = f"{scheme}://{host}"
            idx = st.Z - (st.y + 1)
            regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "Unknown"
            self._send_json(200, {
                "symbol": SYMBOL,
                "price": str(st.price),
                "bid": str(engine.price_history[-1].bid) if engine.price_history else "0.0",
                "ask": str(engine.price_history[-1].ask) if engine.price_history else "0.0",
                "signal": str(st.signal),
                "regime": regime,
                "tick": int(st.tick),
                "m_count": int(st.authoritative_m),
                "n_count": int(st.authoritative_n),
                "m_at_h": int(st.last_kronecker_m),
                "n_at_h": int(st.last_kronecker_n),
                "h_bar": int(st.h),
                "timestamp": datetime.now().isoformat(),
                "endpoint": endpoint,
                "webapp_user_id": st.webapp_user_id,
                "webapp_username": st.webapp_username,
                "last_price_update": engine.feed.last_update().isoformat() if engine.feed.last_update() else None,
                "engine_initialized": bool(st.FG),
                "consecutive_zero_prices": int(engine._consecutive_zero_prices),
                "relay_url": RELAY_URL,
                "relay_healthy": (engine.feed.failure_count() < 3),
                "indicator_populate_count": int(engine._indicator_populate_count),
                "imbalance_fire_count": int(engine._imbalance_fire_count),
                "comment_line": engine._format_comment_line(),
                "provider": st.last_provider,
                "last_volume": str(st.last_volume),
            })
            return

        if path == "/miniapp-state":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready", "detail": "Engine hasn't started. Use /start_feed in the bot."})
                return
            st = engine.state
            idx = st.Z - (st.y + 1)
            regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "Unknown"
            fvg_anchors = []
            for idx_i, p in enumerate(st.Premium):
                if p > Decimal('0.0'):
                    fvg_anchors.append({"idx": idx_i, "type": "top", "price": str(p)})
            for idx_i, p in enumerate(st.Discount):
                if p > Decimal('0.0'):
                    fvg_anchors.append({"idx": idx_i, "type": "bottom", "price": str(p)})
            for bridge_idx, rec in BRIDGE_STATE._fvgs.items():
                fvg_anchors.append({
                    "idx": bridge_idx,
                    "type": "top" if rec["type"] == "top" else "bottom",
                    "price": rec["price"],
                })
            h_idx = st.h - (st.y + 1)
            m_at_h = 1 if (0 <= h_idx < len(st.k) and st.k[h_idx]) else 0
            n_at_h = 1 if (0 <= h_idx < len(st.l) and st.l[h_idx]) else 0
            market_m = int(st.authoritative_m)
            market_n = int(st.authoritative_n)
            market_imbalance = market_m - market_n - 2
            if market_imbalance > 2:
                market_regime = "BULLISH"
            elif market_imbalance < -2:
                market_regime = "BEARISH"
            else:
                market_regime = "NEUTRAL"
            premium_series = [str(p) for p in st.Premium]
            discount_series = [str(p) for p in st.Discount]
            payload = {
                "symbol": SYMBOL,
                "price": str(st.price),
                "regime": regime,
                "tick": int(st.tick),
                "m_count": market_m,
                "n_count": market_n,
                "m_at_h": m_at_h,
                "n_at_h": n_at_h,
                "h_bar": int(st.h),
                "market_m": market_m,
                "market_n": market_n,
                "market_imbalance": market_imbalance,
                "market_regime": market_regime,
                "last_price_update": datetime.now().isoformat(),
                "relay_healthy": (engine.feed.failure_count() < 3),
                "X_PERIOD": X_PERIOD,
                "Y_START": Y_START,
                "fvg_anchors": fvg_anchors,
                "premium_series": premium_series,
                "discount_series": discount_series,
                "recent_signals": st.signal_history[-20:],
                "ohlcv_count": len(engine.ohlcv_history),
                "signal_count": len(st.signal_history),
                "last_signal_at": st.last_signal_at,
                "bar_close_count": int(st.bar_close_count),
                "engine_initialized": bool(st.FG),
                "KC": bool(st.KC),
                "invert": bool(st.invert),
                "tag": int(st.tag),
                "prime": int(st.prime),
                "dime": int(st.dime),
                "mem": int(st.mem),
                "A": bool(st.A),
                "B": bool(st.B),
                "C": bool(st.C),
                "c": bool(st.c),
                "tick_tock": bool(st.tick_tock),
                "signature": bool(st.signature),
                "safety": bool(st.safety),
                "trailing_stop_active": bool(st.trailing_stop_active),
                "trailing_stop_price": str(st.trailing_stop_price),
                "trailing_take_profit": str(st.trailing_take_profit),
                "trailing_stop_entry": str(st.trailing_stop_entry),
                "trailing_stop_side": st.trailing_stop_side,
                "has_open_long": bool(st.has_open_long),
                "has_open_short": bool(st.has_open_short),
                "lOrder_id": int(st.lOrder_id),
                "kOrder_id": int(st.kOrder_id),
                "on_track_runs": int(st.on_track_runs),
                "on_stand_runs": int(st.on_stand_runs),
                "last_kronecker_bar": int(engine._last_kronecker_bar),
                "last_kronecker_m": int(st.last_kronecker_m),
                "last_kronecker_n": int(st.last_kronecker_n),
                "last_kronecker_h": int(st.last_kronecker_h),
                "authoritative_m": int(st.authoritative_m),
                "authoritative_n": int(st.authoritative_n),
                "authoritative_h": int(st.authoritative_h),
                "X_scan": int(st.X_scan),
                "Y_scan": int(st.Y_scan),
                "S": int(st.S),
                "T": int(st.T),
                "r": int(st.r),
                "ir": int(st.ir),
                "Z": int(st.Z),
                "z": int(st.z),
                "O": int(st.O),
                "o": int(st.o),
                "W": int(st.W),
                "w": int(st.w),
                "I": int(st.I),
                "iI": int(st.iI),
                "J": int(st.J),
                "iJ": int(st.iJ),
                "iZ": int(st.iZ),
                "iz": int(st.iz),
                "iW": int(st.iW),
                "iw": int(st.iw),
                "iO": int(st.iO),
                "io": int(st.io),
                "iATR": float(st.iATR),
                "iStdDev": float(st.iStdDev),
                "iIHKk": float(st.iIHKk),
                "iIHKt": float(st.iIHKt),
                "indicator_populate_count": int(engine._indicator_populate_count),
                "imbalance_fire_count": int(engine._imbalance_fire_count),
                "lPass": str(st.lPass),
                "ilPass": str(st.ilPass),
                "kPass": str(st.kPass),
                "ikPass": str(st.ikPass),
                "comment_line": engine._format_comment_line(),
                "provider": st.last_provider,
                "last_volume": str(st.last_volume),
                "projection_meta": st.projection_meta,
                "projection_computed_at": st.projection_computed_at,
                "projection_trigger": st.projection_trigger,
                "last_inbound_message_id": st.last_inbound_message_id,
            }
            self._send_json(200, payload)
            return

        if path == "/ohlcv":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            limit = 200
            try:
                limit = int(self.headers.get("X-Limit", query.get("limit", "200")))
            except Exception:
                pass
            bars = engine.ohlcv_history[-limit:]
            ohlcv_data = []
            last_ts = None
            for bar in bars:
                ts = bar["timestamp"]
                if isinstance(ts, datetime):
                    ts_str = ts.isoformat()
                else:
                    ts_str = str(ts)
                last_ts = ts_str
                ohlcv_data.append({
                    "timestamp": ts_str,
                    "open": float(bar["open"]),
                    "high": float(bar["high"]),
                    "low": float(bar["low"]),
                    "close": float(bar["close"]),
                    "volume": float(bar.get("volume", 0)),
                    "provider": str(bar.get("provider", "")),
                })
            self._send_json(200, {
                "symbol": SYMBOL,
                "bars": ohlcv_data,
                "count": len(ohlcv_data),
                "last_bar_timestamp": last_ts,
                "signal_count": len(engine.state.signal_history),
                "provider": engine.state.last_provider,
            })
            return

        if path == "/signals":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            limit = 50
            try:
                limit = int(self.headers.get("X-Limit", query.get("limit", "50")))
            except Exception:
                pass
            since = self.headers.get("X-Since", query.get("since", ""))
            all_signals = engine.state.signal_history
            if since:
                all_signals = [s for s in all_signals if s.get("timestamp", "") > since]
            signals = all_signals[-limit:]
            self._send_json(200, {
                "symbol": SYMBOL,
                "signals": signals,
                "count": len(signals),
                "last_signal_at": engine.state.last_signal_at,
            })
            return

        if path == "/fvg":
            self._send_json(200, {"fvgs": BRIDGE_STATE.list_fvgs()})
            return

        if path == "/probe":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            probe_data = engine.feed.probe()
            try:
                probe_data["signal_status"] = engine.get_signal_status()
                probe_data["relay_healthy"] = (engine.feed.failure_count() < 3)
            except Exception:
                pass
            self._send_json(200, probe_data)
            return

        if path == "/diagnostics":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            try:
                diag = engine.get_signal_status()
                diag["ohlcv_history_depth"] = len(engine.ohlcv_history)
                current_col = engine.state.Z - (engine.state.y + 1)
                if current_col < 0:
                    current_col = 0
                diag["indicator_col_index"] = [current_col, max(0, current_col - 1)]
                diag["indicator_sample_col0"] = [
                    str(engine.state.iA[i][current_col]) if current_col < len(engine.state.iA[i]) else "50"
                    for i in range(13)
                ]
                prev_col = max(0, current_col - 1)
                diag["indicator_sample_col1"] = [
                    str(engine.state.cA[i][prev_col]) if prev_col < len(engine.state.cA[i]) else "50"
                    for i in range(13)
                ]
                diag["x_period_constant"] = X_PERIOD
                diag["y_start_constant"] = Y_START
                diag["consecutive_zero_prices"] = engine._consecutive_zero_prices
                diag["relay_healthy"] = (engine.feed.failure_count() < 3)
                diag["active_symbol"] = engine.feed.active_symbol()
                diag["last_bar_close"] = engine.state.bar_close_count
                diag["recent_signals"] = engine.state.signal_history[-10:]
                diag["provider"] = engine.state.last_provider
                diag["projection_meta"] = engine.state.projection_meta
                diag["projection_trigger"] = engine.state.projection_trigger
                self._send_json(200, diag)
            except Exception as e:
                self._send_json(500, {"error": "diagnostics_failed", "detail": str(e)})
            return

        if path == "/orders":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            self._send_json(200, {"orders": engine.list_orders()})
            return

        if path == "/regime-map":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            self._send_json(200, {
                "regime_map": engine.get_regime_map(),
                "size": len(engine.state.Regime),
            })
            return

        if path == "/indicators":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            name = query.get("name", "RSI")
            try:
                count = int(query.get("count", "80"))
            except Exception:
                count = 80
            series = engine.get_indicator_series(name, count)
            self._send_json(200, {"name": name, "series": series, "count": len(series)})
            return

        if path == "/log":
            try:
                limit = int(query.get("limit", "50"))
            except Exception:
                limit = 50
            with _LOG_LOCK:
                logs = list(_LOG_BUFFER)[-limit:]
            self._send_json(200, {"logs": logs, "count": len(logs)})
            return

        if path == "/" or path == "/index.html":
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                html_path = os.path.join(base, "index.html")
                if os.path.isfile(html_path):
                    with open(html_path, "r", encoding="utf-8") as f:
                        self._send_html(200, f.read())
                else:
                    self._send_html(200, "<!DOCTYPE html><html><body style='font-family:monospace;background:#050510;color:#aaccff;padding:40px;'><h2>⚡ ÆEA Mini App Bridge Online</h2><p>index.html not found in <code>" + base + "</code>.</p></body></html>")
            except Exception as e:
                self._send_json(500, {"error": "read_index_failed", "detail": str(e)})
            return

        self._send_json(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/handshake":
            try:
                data = self._read_json()
                init_data = data.get("initData", "").strip()
                chat_id = data.get("chat_id")
                if not init_data:
                    self._send_json(400, {"error": "missing_init_data", "detail": "Provide initData from Telegram.WebApp.initData"})
                    return
                verified = verify_telegram_init_data(init_data, TELEGRAM_BOT_TOKEN_ENV)
                if not verified or not verified.get("user"):
                    logger.warning("🚫 Handshake rejected: initData verification failed")
                    self._send_json(403, {"error": "invalid_init_data", "detail": "Telegram initData HMAC verification failed. Ensure TELEGRAM_BOT_TOKEN matches the bot that issued initData."})
                    return
                u = verified["user"] or {}
                user_id = u.get("id")
                username = u.get("username")
                BRIDGE_STATE.register_webapp_session(user_id, username, chat_id=chat_id)
                logger.info(f"🤝 Handshake OK: user_id={user_id}, username={username}, chat_id={chat_id}")
                self._send_json(200, {
                    "ok": True, "user_id": user_id, "username": username,
                    "public_url": BRIDGE_ENGINE_REF.get("public_url"),
                })
            except Exception as e:
                logger.error(f"Handshake error: {e}")
                self._send_json(500, {"error": "internal", "detail": str(e)})
            return

        if not _require_auth(self):
            self._send_json(401, {"error": "unauthorized", "detail": "Missing or invalid X-Telegram-Init-Data"})
            return

        if path == "/fvg":
            user_id, username, verified = _extract_auth_headers(self)
            try:
                data = self._read_json()
                fvg_type = data.get("type")
                price_str = data.get("price")
                num = data.get("num")
                den = data.get("den")
                requested_idx = data.get("idx")
                if fvg_type is None:
                    self._send_json(400, {"error": "missing_fields", "need": ["type", "price"]})
                    return
                try:
                    requested_idx_int = int(requested_idx) if requested_idx is not None else None
                except (TypeError, ValueError):
                    requested_idx_int = None
                if num is not None and den is not None:
                    price_label = f"{int(num)}/{int(den)}"
                    price_dec = Decimal(int(num)) / Decimal(int(den))
                elif price_str is not None:
                    price_label = str(price_str)
                    price_dec = Decimal(str(price_str))
                else:
                    self._send_json(400, {"error": "missing_fields", "need": ["type", "price"]})
                    return
                idx = BRIDGE_STATE.add_fvg(fvg_type, str(price_dec), user_id=user_id, requested_idx=requested_idx_int)
                anchor_info = {}
                engine = BRIDGE_ENGINE_REF.get("engine")
                if engine is not None and idx in engine.state.fvg_anchor_map:
                    anchor_info = engine.state.fvg_anchor_map[idx]
                logger.info(f"📐 FVG committed: type={fvg_type} price={price_label} idx={idx} verified={verified} user={username}")
                self._send_json(201, {"ok": True, "idx": idx, "type": fvg_type, "price": price_label, "verified": verified, "anchor": anchor_info})
            except ValueError as ve:
                logger.warning(f"FVG rejected: {ve}")
                self._send_json(422, {"error": "validation", "detail": str(ve)})
            except Exception as e:
                logger.error(f"FVG POST error: {e}")
                self._send_json(500, {"error": "internal", "detail": str(e)})
            return

        if path == "/reset":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            try:
                engine.feed._rebuild_ticker()
                engine.feed._fallback_count = 0
                engine._consecutive_zero_prices = 0
                engine.OnReInit()
                # E-4 / D-43: do NOT recompute the projection from a half-reset
                # state. Only the success path calls _project_arc_length().
                engine._project_arc_length(trigger="manual_refresh")
                logger.info("🔄 Manual reset requested via /reset")
                self._send_json(200, {"ok": True, "active_symbol": engine.feed.active_symbol()})
            except Exception as e:
                logger.error(f"/reset error: {e}")
                self._send_json(500, {"error": "internal", "detail": str(e)})
            return

        if path == "/settings":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            data = self._read_json()
            result = engine.apply_settings(data)
            code = 200 if result.get("ok") else (422 if result.get("error") == "validation" else 400)
            self._send_json(code, result)
            return

        if path == "/symbol":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            data = self._read_json()
            sym = data.get("symbol")
            if not sym:
                self._send_json(400, {"error": "missing_symbol", "detail": "Provide 'symbol' in JSON body"})
                return
            result = engine.change_symbol(sym)
            code = 200 if result.get("ok") else 400
            self._send_json(code, result)
            return

        if path == "/order":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            data = self._read_json()
            side = (data.get("side") or "").upper()
            try:
                lot = Fraction.from_decimal_string(str(data.get("lot", "0.01"))).to_decimal()
                sl = Fraction.from_decimal_string(str(data.get("sl", "0"))).to_decimal()
                tp = Fraction.from_decimal_string(str(data.get("tp", "0"))).to_decimal()
            except Exception as e:
                self._send_json(400, {"error": "invalid_numbers", "detail": str(e)})
                return
            result = engine.place_order(side, lot, sl, tp)
            code = 200 if result.get("ok") else 400
            self._send_json(code, result)
            return

        if path == "/order/close":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            data = self._read_json()
            if data.get("all"):
                result = engine.close_order(all=True)
            else:
                ticket = data.get("ticket")
                if ticket is None:
                    self._send_json(400, {"error": "missing_ticket"})
                    return
                try:
                    ticket = int(ticket)
                except Exception:
                    self._send_json(400, {"error": "invalid_ticket"})
                    return
                result = engine.close_order(ticket=ticket)
            code = 200 if result.get("ok") else 400
            self._send_json(code, result)
            return

        if path == "/projection/refresh":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            try:
                engine._project_arc_length(trigger="manual_refresh")
                self._send_json(200, engine.get_projection())
            except Exception as e:
                logger.error(f"/projection/refresh error: {e}")
                self._send_json(500, {"error": "internal", "detail": str(e)})
            return

        self._send_json(404, {"error": "not_found", "path": path})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if not _require_auth(self):
            self._send_json(401, {"error": "unauthorized", "detail": "Missing or invalid X-Telegram-Init-Data"})
            return
        m = _re_bridge.match(r"^/fvg/(\d+)$", path)
        if m:
            idx = int(m.group(1))
            ok = BRIDGE_STATE.remove_fvg(idx)
            if ok:
                logger.info(f"🔻 FVG removed: idx={idx}")
                self._send_json(200, {"ok": True, "idx": idx})
            else:
                self._send_json(404, {"error": "fvg_not_found", "idx": idx})
            return
        self._send_json(404, {"error": "not_found", "path": path})

# ============================================================================
# BRIDGE SERVER
# ============================================================================
class BridgeServer:
    def __init__(self, host: str = BRIDGE_HOST, port: int = BRIDGE_PORT):
        self.host = host
        self.port = int(port)
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._tunnel: Optional[TunnelManager] = None
        self._ssl_context: Optional[ssl.SSLContext] = None

    def _build_ssl_context(self) -> Optional[ssl.SSLContext]:
        if not BRIDGE_USE_TLS:
            return None
        if not BRIDGE_TLS_CERT or not BRIDGE_TLS_KEY:
            logger.warning("⚠️ BRIDGE_USE_TLS=1 but cert/key paths missing — falling back to HTTP")
            return None
        if not (os.path.isfile(BRIDGE_TLS_CERT) and os.path.isfile(BRIDGE_TLS_KEY)):
            logger.warning("⚠️ TLS cert or key file not found — falling back to HTTP")
            return None
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=BRIDGE_TLS_CERT, keyfile=BRIDGE_TLS_KEY)
            logger.info(f"🔒 TLS enabled: cert={BRIDGE_TLS_CERT}")
            return ctx
        except Exception as e:
            logger.error(f"❌ Failed to load TLS context: {e}")
            return None

    def start(self) -> None:
        if self._thread is not None:
            return
        try:
            self._httpd = ThreadingHTTPServer((self.host, self.port), BridgeHandler)
            self._httpd.daemon_threads = True
            self._ssl_context = self._build_ssl_context()
            if self._ssl_context is not None:
                self._httpd.socket = self._ssl_context.wrap_socket(self._httpd.socket, server_side=True)
        except OSError as e:
            logger.error(f"🔥 Bridge server bind failed on {self.host}:{self.port}: {e}")
            return
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="aei-bridge", daemon=True)
        self._thread.start()
        scheme = "https" if self._ssl_context else "http"
        logger.info(f"🌐 ÆEA Mini App Bridge listening on {scheme}://{self.host}:{self.port}")
        self._tunnel = TunnelManager(self.port, prefer=BRIDGE_TUNNEL, timeout=BRIDGE_PUBLIC_TIMEOUT)
        threading.Thread(target=self._tunnel.start, name="aei-tunnel", daemon=True).start()

    def stop(self) -> None:
        if self._tunnel is not None:
            try:
                self._tunnel.stop()
            except Exception:
                pass
            self._tunnel = None
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("🌐 ÆEA Mini App Bridge stopped")

# ============================================================================
# BRIDGE ATTACHMENT
# ============================================================================
def _bridge_attach_to_engine(engine: "AEEA_Engine") -> None:
    if getattr(engine, "_bridge_attached", False):
        return
    engine._bridge_attached = True
    logger.info("🔗 Bridge attached to AEEA_Engine")

def _bridge_attach_to_bot(bot: "AEI_Bot") -> None:
    if getattr(bot, "_bridge_attached", False):
        return
    original_run = bot.run
    def wrapped_run(self):
        BRIDGE_ENGINE_REF["engine"] = self.engine
        BRIDGE_ENGINE_REF["bot"] = self
        _bridge_attach_to_engine(self.engine)
        server = BridgeServer()
        server.start()
        self._bridge_server = server
        try:
            original_run(self)
        finally:
            server.stop()
    bot.run = wrapped_run
    bot._bridge_attached = True
    logger.info("🔗 Bridge attached to AEI_Bot.run()")

# ============================================================================
# TELEGRAM BOT
# ============================================================================
class AEI_Bot:
    def __init__(self, token: str, bot_name: str = "UpscaleTradeBot"):
        self.token = token
        self.bot_name = bot_name
        self.engine = AEEA_Engine()
        self.application = None
        self._running = False
        self._price_task: Optional[asyncio.Task] = None
        self._bridge_server: Optional[BridgeServer] = None
        self._webapp_url: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _resolve_webapp_url(self) -> Optional[str]:
        return TELEGRAM_WEBAPP_URL or BRIDGE_ENGINE_REF.get("public_url")

    def _track_inbound_message(self, update: Update) -> None:
        try:
            msg = update.effective_message
            chat = update.effective_chat
            chat_id = None
            if chat is not None and getattr(chat, "id", None) is not None:
                chat_id = int(chat.id)
            if chat_id is not None:
                if self.engine.state.chat_id != chat_id:
                    self.engine.state.last_inbound_message_id = None
                self.engine.state.chat_id = chat_id
            if msg is not None and getattr(msg, "message_id", None) is not None:
                self.engine.state.last_inbound_message_id = int(msg.message_id)
        except Exception as e:
            logger.debug(f"_track_inbound_message failed: {e}")

    def _send_message_sync(self, chat_id: int, text: str, parse_mode: str = "Markdown",
                           reply_to_message_id: Optional[int] = None,
                           timeout: float = 10.0) -> bool:
        if self.application is None:
            logger.warning("📡 send_message skipped: application is None")
            return False
        loop = self._loop
        if loop is None or loop.is_closed():
            logger.warning("📡 send_message skipped: event loop not captured or closed")
            return False
        bot = self.application.bot

        def _attempt(pm: Optional[str], rt: Optional[int]) -> Tuple[bool, str]:
            coro = bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=pm,
                reply_to_message_id=rt,
            )
            try:
                fut = asyncio.run_coroutine_threadsafe(coro, loop)
                fut.result(timeout=timeout)
                return (True, "")
            except asyncio.TimeoutError:
                return (False, "timeout")
            except Exception as e:
                return (False, str(e))

        ok1, err1 = _attempt(parse_mode, reply_to_message_id)
        if ok1:
            return True
        logger.info(f"📡 send_message attempt 1 failed (reply+Markdown): {err1}")

        reply_class = _looks_like_reply_error(err1)
        parse_class = _looks_like_parse_error(err1)
        length_class = _looks_like_length_error(err1)

        if reply_class and not parse_class:
            ok2, err2 = _attempt(parse_mode, None)
            if ok2:
                logger.info("📡 send_message attempt 2 succeeded (standalone Markdown)")
                return True
            logger.info(f"📡 send_message attempt 2 failed (standalone Markdown): {err2}")
            if _looks_like_parse_error(err2):
                ok3, err3 = _attempt(None, None)
                if ok3:
                    logger.info("📡 send_message attempt 3 succeeded (plain text)")
                    return True
                logger.warning(f"📡 send_message attempt 3 failed (plain text): {err3}")
                return False
            ok3, err3 = _attempt(None, None)
            if ok3:
                logger.info("📡 send_message attempt 3 succeeded (plain text)")
                return True
            logger.warning(f"📡 send_message attempt 3 failed (plain text): {err3}")
            return False

        if parse_class and not reply_class:
            ok3, err3 = _attempt(None, reply_to_message_id)
            if ok3:
                logger.info("📡 send_message attempt 3 succeeded (plain text, threaded)")
                return True
            if _looks_like_reply_error(err3):
                ok3b, err3b = _attempt(None, None)
                if ok3b:
                    logger.info("📡 send_message attempt 3b succeeded (plain text, standalone)")
                    return True
                logger.warning(f"📡 send_message attempt 3b failed (plain text): {err3b}")
                return False
            ok3b, err3b = _attempt(None, None)
            if ok3b:
                logger.info("📡 send_message attempt 3b succeeded (plain text, standalone)")
                return True
            logger.warning(f"📡 send_message attempt 3b failed (plain text): {err3b}")
            return False

        if reply_class and parse_class:
            ok2, err2 = _attempt(None, None)
            if ok2:
                logger.info("📡 send_message attempt 2 succeeded (plain text, standalone)")
                return True
            logger.warning(f"📡 send_message attempt 2 failed (plain text, standalone): {err2}")
            return False

        ok2, err2 = _attempt(parse_mode, None)
        if ok2:
            logger.info("📡 send_message attempt 2 succeeded (standalone Markdown, unknown class)")
            return True
        ok3, err3 = _attempt(None, None)
        if ok3:
            logger.info("📡 send_message attempt 3 succeeded (plain text, unknown class)")
            return True
        logger.warning(f"📡 send_message failed all attempts: reply_err={err1} standalone_err={err2} plain_err={err3}")
        return False

    async def price_feed_loop(self):
        logger.info("🔄 Price feed loop entered")
        iteration = 0
        while self._running:
            iteration += 1
            try:
                self.engine.update_price_from_feed()
                st = self.engine.state
                idx = st.Z - (st.y + 1)
                regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "Unknown"
                logger.info(f"📊 itr#{iteration} price={st.price} vol={st.last_volume} provider={st.last_provider} tick={st.tick} FG={st.FG} regime={regime} bars={st.bar_close_count} signals={len(st.signal_history)} ohlcv={len(self.engine.ohlcv_history)}")
            except Exception:
                logger.exception(f"❌ Feed iteration #{iteration} failed")
            await asyncio.sleep(UPDATE_INTERVAL)
        logger.info("🔄 Price feed loop exited")

    def _build_main_keyboard(self) -> InlineKeyboardMarkup:
        webapp_url = self._resolve_webapp_url()
        rows = [
            [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("📈 Signal", callback_data="signal")],
            [InlineKeyboardButton("📊 Regime", callback_data="regime"), InlineKeyboardButton("📉 Indicators", callback_data="indicators")],
            [InlineKeyboardButton("🔄 Start Feed", callback_data="start_feed"), InlineKeyboardButton("⏹️ Stop Feed", callback_data="stop_feed")],
            [InlineKeyboardButton("📈 Info", callback_data="info"), InlineKeyboardButton("🔄 Reset", callback_data="reset")],
            [InlineKeyboardButton("🔬 Probe Relay", callback_data="probe"), InlineKeyboardButton("♻️ Rebuild Relay", callback_data="rebuild_yf")],
            [InlineKeyboardButton("🔬 Diagnostics", callback_data="diagnostics")],
            [InlineKeyboardButton("📊 Chart", callback_data="chart"), InlineKeyboardButton("🎯 Projection", callback_data="projection")],
        ]
        if webapp_url:
            rows.append([InlineKeyboardButton("⚡ Open ÆEA Mini App", web_app=WebAppInfo(url=webapp_url))])
        else:
            rows.append([InlineKeyboardButton("⏳ Mini App (tunnel pending…)", callback_data="webapp_pending")])
        return InlineKeyboardMarkup(rows)

    async def _safe_reply(self, update: Update, text: str, reply_markup=None) -> bool:
        """
        D-MAJ-8: attempt the Markdown send, then fall back to plain text,
        then fall back to a truncated plain-text send. This prevents an
        unparseable value or an over-length message from raising
        telegram.error.BadRequest out of the handler (where it would be
        swallowed by Application's error handler and never reach the user).

        The order of attempts is:
          1. Markdown + reply_markup
          2. Plain text + reply_markup
          3. Truncated plain text (3900 chars) + reply_markup

        Returns True if any attempt succeeded, False otherwise. The failure
        is logged through the __main__ logger, which the _RingHandler
        instance is attached to, so it reaches /log and the TWA log bar.
        """
        msg = update.effective_message
        query = update.callback_query
        target = query if query is not None else msg
        if target is None:
            logger.warning("_safe_reply: no target message or callback_query")
            return False

        # Attempt 1: Markdown + reply_markup
        try:
            if query is not None:
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await msg.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
            return True
        except Exception as e1:
            err1 = str(e1)
            logger.info(f"_safe_reply attempt 1 failed (Markdown): {err1}")

        # Attempt 2: plain text + reply_markup
        try:
            if query is not None:
                await query.edit_message_text(text, parse_mode=None, reply_markup=reply_markup)
            else:
                await msg.reply_text(text, parse_mode=None, reply_markup=reply_markup)
            logger.info("_safe_reply attempt 2 succeeded (plain text)")
            return True
        except Exception as e2:
            err2 = str(e2)
            logger.info(f"_safe_reply attempt 2 failed (plain text): {err2}")

        # Attempt 3: truncated plain text + reply_markup
        try:
            truncated = text[:3900] if len(text) > 3900 else text
            if query is not None:
                await query.edit_message_text(truncated, parse_mode=None, reply_markup=reply_markup)
            else:
                await msg.reply_text(truncated, parse_mode=None, reply_markup=reply_markup)
            logger.info("_safe_reply attempt 3 succeeded (truncated plain text)")
            return True
        except Exception as e3:
            err3 = str(e3)
            logger.error(f"_safe_reply attempt 3 failed (truncated plain text): {err3}")
            return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        chat_id = update.effective_chat.id
        self.engine.state.chat_id = chat_id
        self.engine.application = self.application
        engine_status = "✅ Initialized" if self.engine.state.FG else "⏳ Waiting for data"
        feed_status = "Active" if self._running else "Inactive"
        welcome = (
            "🔷 *ÆEA Quantum-Financial Topology Bot*\n"
            "Welcome to @UpscaleTradeBot. This bot implements the Non-Hermitian\n"
            "Stochastic Geometry of Supply-Demand Imbalance.\n\n"
            "📊 *Available Commands:*\n"
            "`/status` - Current market state & regime\n"
            "`/regime` - Detailed regime classification\n"
            "`/signal` - Current trading signal\n"
            "`/indicators` - 13D Hilbert Space projection\n"
            "`/fvg` - Fair Value Gap tracking\n"
            "`/chart` - Recent signals summary\n"
            "`/projection` - Arc-length future price projection\n"
            "`/diagnostics` - Full engine diagnostic snapshot\n"
            "`/reset` - Reset topological branch\n"
            "`/start_feed` - Start price feed\n"
            "`/stop_feed` - Stop price feed\n"
            "`/symbol <PAIR>` - Change trading symbol\n"
            "`/info` - Ticker information\n"
            "`/probe` - Relay diagnostics\n"
            "`/rebuild_yf` - Force relay reset\n"
            "`/webapp` - Launch Telegram Mini App\n"
            "`/webgui` - Show bridge URL\n"
            "`/help` - Show this message\n\n"
            f"*Current Symbol:* `{SYMBOL}`\n"
            f"🔄 *Feed Status:* {feed_status}\n"
            f"🧠 *Engine Status:* {engine_status}\n"
            f"📊 *Bar Closes:* {self.engine.state.bar_close_count}  |  *Signals:* {len(self.engine.state.signal_history)}\n"
            f"📡 *Provider:* `{self.engine.state.last_provider or '—'}`  |  *Volume:* `{self.engine.state.last_volume}`\n"
            "💎 Natalia Tanyatia"
        )
        await self._safe_reply(update, welcome, reply_markup=self._build_main_keyboard())

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.start(update, context)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        if not self.engine.state.FG:
            logger.info("⚠️ Engine not initialized, attempting to force...")
            self.engine._force_initialization()
        if not self.engine.state.FG:
            await self._safe_reply(update,
                "⏳ *Engine not initialized*\nThe engine will initialize on the first price tick after starting the feed.\nPlease use `/start_feed` to start the price feed.\nIf the feed is already running, try `/reset` to reinitialize.")
            return
        state = self.engine.state
        idx = state.Z - (state.y + 1)
        regime = state.Regime[idx] if 0 <= idx < len(state.Regime) and state.Regime[idx] else "Unknown"
        bid, ask = self.engine.feed.get_current_price()
        price_display = f"{bid:.5f}" if bid > Decimal('0.0') else f"{state.price:.5f}"
        feed_mark = "✅" if self._running else "⏹️"
        init_mark = "✅ Initialized" if state.FG else "⏳ Initializing"
        m_local = state.authoritative_m
        n_local = state.authoritative_n
        h_idx = state.h - (state.y + 1)
        m_at_h = 1 if (0 <= h_idx < len(state.k) and state.k[h_idx]) else 0
        n_at_h = 1 if (0 <= h_idx < len(state.l) and state.l[h_idx]) else 0
        trail_status = "🟢 Active" if state.trailing_stop_active else "⚪ Inactive"
        order_presence = []
        if state.has_open_long:
            order_presence.append(f"↑(id={state.lOrder_id})")
        if state.has_open_short:
            order_presence.append(f"↓(id={state.kOrder_id})")
        order_str = ", ".join(order_presence) if order_presence else "none"
        response = (
            "🔷 *ÆEA Status*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"💰 *Price:* {price_display}\n"
            f"📊 *ℛ\\_regime:* {regime}\n"
            f"🎯 *Signal Level:* {state.signal:.5f}\n"
            f"📋 *𝒮:* {'Active' if state.signature else 'Idle'}\n"
            f"🔄 *Tick:* {state.tick}\n"
            f"🧠 *Engine State:* {init_mark}\n"
            f"⚖️ *Imbalance @ h={state.h}:* m={m_at_h}, n={n_at_h}\n"
            f"⚖️ *Local m/n:* {m_local}/{n_local}\n"
            f"📈 *Indicator Passes:* {self.engine._indicator_populate_count}\n"
            f"📡 *Signal Fires:* {self.engine._imbalance_fire_count}\n"
            f"📊 *Bar Closes:* {state.bar_close_count}\n"
            f"📈 *OHLCV Bars:* {len(self.engine.ohlcv_history)}\n"
            f"🎯 *Signal History:* {len(state.signal_history)}\n"
            f"📡 *Feed Active:* {feed_mark}\n"
            f"🛰️ *Provider:* `{state.last_provider or '—'}`  |  *Volume:* `{state.last_volume}`\n"
            f"🔀 *𝒦:* {state.KC}  |  *π:* {state.prime}  |  *δ\\_dime:* {state.dime}\n"
            f"🔀 *𝒦\\_invert:* {state.invert}  |  *μ:* {state.mem}  |  *τ:* {state.tag}\n"
            f"🔀 *𝒜:* {state.A}  |  *ℬ:* {state.B}  |  *𝒞:* {state.C}  |  *𝒸:* {state.c}\n"
            f"🔀 *𝒯\\_tick_tock:* {state.tick_tock}  |  *𝒮\\_safety:* {state.safety}\n"
            f"📊 *𝒪:* {order_str}\n"
            f"🛑 *𝒯\\_trail:* {trail_status} ({state.trailing_stop_price:.5f} / {state.trailing_take_profit:.5f})\n"
            f"🎯 *Trailing Side:* {state.trailing_stop_side or '—'}  |  *Entry:* {state.trailing_stop_entry:.5f}\n"
            f"🔍 *𝒯\\_track Runs:* {state.on_track_runs}  |  *𝒯\\_stand Runs:* {state.on_stand_runs}\n"
            f"🎯 *Last δ\\_bar:* {self.engine._last_kronecker_bar}\n"
            f"🔢 *X\\_scan:* {state.X_scan}  |  *Y\\_scan:* {state.Y_scan}  |  *X\\_PERIOD:* {X_PERIOD}\n"
            f"🌌 *𝒫\\_arc:* {state.projection_meta.get('kind', '—') if state.projection_meta else '—'} @ {state.projection_computed_at or 'never'} (𝒫\\_trigger={state.projection_trigger or '—'})\n"
            f"💬 *Last Inbound Msg Id:* {state.last_inbound_message_id}"
        )
        reply_markup = self._build_main_keyboard()
        await self._safe_reply(update, response, reply_markup=reply_markup)

    async def diagnostics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        status = self.engine.get_signal_status()
        response = (
            "🔬 *Engine Diagnostics*\n"
            f"🔄 *Tick:* {status.get('tick')}\n"
            f"🧮 *Indicator Populates:* {status.get('indicator_populate_count')}\n"
            f"📡 *Signal Fires:* {status.get('imbalance_fire_count')}\n"
            f"📊 *Bar Closes:* {status.get('bar_close_count')}\n"
            f"📈 *OHLCV History:* {len(self.engine.ohlcv_history)}\n"
            f"🎯 *Signal History:* {status.get('signal_count')}\n"
            f"⚖️ *Local m / n:* {status.get('m_count')} / {status.get('n_count')}\n"
            f"⚖️ *m / n (@h={status.get('h_bar')}):* {status.get('m_at_h')} / {status.get('n_at_h')}\n"
            f"🎯 *Signal:* {status.get('signal'):.5f}\n"
            f"📊 *ℛ\\_regime:* {status.get('regime')}\n"
            f"🔀 *𝒦:* {status.get('KC')}  |  *π:* {status.get('prime')}  |  *δ\\_dime:* {status.get('dime')}\n"
            f"🔀 *𝒦\\_invert:* {status.get('invert')}  |  *μ:* {status.get('mem')}  |  *τ:* {status.get('tag')}\n"
            f"🔀 *𝒜:* {status.get('A')}  |  *ℬ:* {status.get('B')}  |  *𝒞:* {status.get('C')}  |  *𝒸:* {status.get('c')}\n"
            f"🔀 *𝒯\\_tick_tock:* {status.get('tick_tock')}  |  *𝒮:* {status.get('signature')}  |  *𝒮\\_safety:* {status.get('safety')}\n"
            f"📈 *𝒯\\_trail Active:* {status.get('trailing_stop_active')}\n"
            f"📈 *𝒯\\_trail Price:* {status.get('trailing_stop_price')}\n"
            f"📈 *𝒯\\_trail Take Profit:* {status.get('trailing_take_profit')}\n"
            f"📍 *𝒯\\_trail Entry:* {status.get('trailing_stop_entry')}  |  *Side:* {status.get('trailing_stop_side')}\n"
            f"📊 *Has Long:* {status.get('has_open_long')}  |  *Has Short:* {status.get('has_open_short')}\n"
            f"📊 *lOrder_id:* {status.get('lOrder_id')}  |  *kOrder_id:* {status.get('kOrder_id')}\n"
            f"🔍 *𝒯\\_track Runs:* {status.get('on_track_runs')}  |  *𝒯\\_stand Runs:* {status.get('on_stand_runs')}\n"
            f"🎯 *Last δ\\_bar:* {status.get('last_kronecker_bar')}\n"
            f"🔢 *Authoritative m/n/h:* {status.get('authoritative_m')}/{status.get('authoritative_n')}/{status.get('authoritative_h')}\n"
            f"🔢 *Last δ m/n/h:* {status.get('last_kronecker_m')}/{status.get('last_kronecker_n')}/{status.get('last_kronecker_h')}\n"
            f"🔢 *Derivatives Z/z/O/o/W/w:* {status.get('Z')}/{status.get('z')}/{status.get('O')}/{status.get('o')}/{status.get('W')}/{status.get('w')}\n"
            f"🔢 *Derivatives I/iI/J/iJ:* {status.get('I')}/{status.get('iI')}/{status.get('J')}/{status.get('iJ')}\n"
            f"🔢 *Derivatives iZ/iz/iW/iw/iO/io:* {status.get('iZ')}/{status.get('iz')}/{status.get('iW')}/{status.get('iw')}/{status.get('iO')}/{status.get('io')}\n"
            f"🔢 *Scan S/T/r/ir:* {status.get('S')}/{status.get('T')}/{status.get('r')}/{status.get('ir')}\n"
            f"🔢 *X_scan/Y_scan:* {status.get('X_scan')}/{status.get('Y_scan')}\n"
            f"🔢 *X_PERIOD (const):* {X_PERIOD}  |  *Y_START (const):* {Y_START}\n"
            f"🔢 *𝒜\\_ATR/𝒜\\_StdDev/𝒜\\_IHKk/𝒜\\_IHKt:* {status.get('iATR'):.2f}/{status.get('iStdDev'):.2f}/{status.get('iIHKk'):.2f}/{status.get('iIHKt'):.2f}\n"
            f"🔢 *lPass/ilPass/kPass/ikPass:* {status.get('lPass')}/{status.get('ilPass')}/{status.get('kPass')}/{status.get('ikPass')}\n"
            f"🛰️ *Provider:* {status.get('last_provider')}  |  *Volume:* {status.get('last_volume')}\n"
            f"🌌 *𝒫\\_arc Computed:* {status.get('projection_computed_at')}\n"
            f"🌌 *𝒫\\_trigger:* {status.get('projection_trigger')}\n"
            f"💬 *Last Inbound Msg Id:* {status.get('last_inbound_message_id')}"
        )
        await self._safe_reply(update, response)

    async def regime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        if not self.engine.state.FG:
            self.engine._force_initialization()
        if not self.engine.state.FG:
            await self._safe_reply(update, "⏳ *Engine not initialized*\nPlease use `/start_feed`.")
            return
        state = self.engine.state
        y = state.y
        idx = state.Z - y - 1
        current = state.Regime[idx] if 0 <= idx < len(state.Regime) and state.Regime[idx] else "Unknown"
        premium = state.Premium[idx] if 0 <= idx < len(state.Premium) else Decimal('0.0')
        discount = state.Discount[idx] if 0 <= idx < len(state.Discount) else Decimal('0.0')
        hh = state.HH[idx] if 0 <= idx < len(state.HH) else Decimal('0.0')
        ll = state.LL[idx] if 0 <= idx < len(state.LL) else Decimal('0.0')
        m_local = state.authoritative_m
        n_local = state.authoritative_n
        imbalance_status = "✅ 𝒜₃" if (m_local >= 12 or n_local >= 12) else "⏳ 𝒜₄"
        response = (
            "📊 *ℛ\\_regime Classification*\n"
            f"🔹 *Current ℛ\\_regime:* {current}\n"
            f"🔹 *Π^{{>θ}}:* {premium:.5f}\n"
            f"🔸 *Π^{{<θ}}:* {discount:.5f}\n"
            f"📈 *HH:* {hh:.5f}\n"
            f"📉 *LL:* {ll:.5f}\n"
            f"🟢 *Local m:* {m_local}\n"
            f"🔴 *Local n:* {n_local}\n"
            f"⚖️ *Imbalance Condition:* {imbalance_status}"
        )
        reply_markup = self._build_main_keyboard()
        await self._safe_reply(update, response, reply_markup=reply_markup)

    async def signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        if not self.engine.state.FG:
            self.engine._force_initialization()
        if not self.engine.state.FG:
            await self._safe_reply(update, "⏳ *Engine not initialized*\nPlease use `/start_feed`.")
            return
        state = self.engine.state
        if state.signal == Decimal('0.0'):
            direction = "⊙ Neutral"
            confidence = "N/A"
        elif state.price > state.signal:
            direction = "📈 ↑"
            confidence = f"{((state.price - state.signal) / state.signal * Decimal('100')):.2f}%" if state.signal != Decimal('0.0') else "0%"
        else:
            direction = "🔴 ↓"
            confidence = f"{((state.signal - state.price) / state.signal * Decimal('100')):.2f}%" if state.signal != Decimal('0.0') else "0%"
        m_local = state.authoritative_m
        n_local = state.authoritative_n
        h_idx = state.h - (state.y + 1)
        m_at_h = 1 if (0 <= h_idx < len(state.k) and state.k[h_idx]) else 0
        n_at_h = 1 if (0 <= h_idx < len(state.l) and state.l[h_idx]) else 0
        condition_met = (m_local >= 12) or (n_local >= 12)
        condition_mark = "✅ 𝒜₃" if condition_met else "❌ 𝒜₄"
        response = (
            "🎯 *Trading Signal*\n"
            f"📊 *Direction:* {direction}\n"
            f"📈 *Confidence:* {confidence}\n"
            f"🎯 *Signal Level:* {state.signal:.5f}\n"
            f"💰 *Current Price:* {state.price:.5f}\n"
            f"⚖️ *Imbalance @ h={state.h}:* m={m_at_h}, n={n_at_h}\n"
            f"⚖️ *Local m/n:* {m_local}/{n_local}\n"
            f"✅ *δ(m-n-2)=1:* {condition_mark}\n"
            f"🔀 *𝒦 State:* {state.KC}\n"
            f"🔢 *π:* {state.prime}\n"
            f"🔢 *δ\\_dime:* {state.dime}\n"
            f"🔄 *Tick Count:* {state.tick}\n"
            f"📈 *𝒯\\_trail:* {'Active' if state.trailing_stop_active else 'Inactive'}\n"
            f"🎯 *Last δ\\_bar:* {self.engine._last_kronecker_bar}"
        )
        reply_markup = self._build_main_keyboard()
        await self._safe_reply(update, response, reply_markup=reply_markup)

    async def indicators(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        if not self.engine.state.FG:
            self.engine._force_initialization()
        if not self.engine.state.FG:
            await self._safe_reply(update, "⏳ *Engine not initialized*\nPlease use `/start_feed`.")
            return
        state = self.engine.state
        y = state.y
        idx = state.Z - y - 1
        if idx < 0 or idx >= len(state.iA[0]):
            await self._safe_reply(update, "❌ Insufficient data for indicator projection.")
            return
        names = INDICATOR_NAMES_CS
        indicator_str = "📊 *13D Hilbert Space Projection*\n\n"
        for i, name in enumerate(names):
            val = state.iA[i][idx] if idx < len(state.iA[i]) else Decimal('50.0')
            val_int = int(float(val))
            bar_len = min(max(val_int // 10, 0), 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            # D-MAJ-6: the template uses parentheses, not square brackets.
            # Telegram's legacy Markdown parser treats [ and ] as link
            # delimiters; an unbalanced pair without a trailing (url) is
            # rejected with HTTP 400 "can't parse entities". The production
            # log aeea-logs-1791834732387.txt shows three consecutive 400
            # Bad Requests on this command's callback-query responses.
            # D-MIN-9: the bar variable is passed through _md_escape() as a
            # defensive measure. The bar is composed of U+2588 (█) and
            # U+2591 (░), neither of which is a Markdown control character,
            # so the call is a no-op on the current alphabet.
            indicator_str += f"`{name:8}` {val:6.1f} ({_md_escape(bar)})\n"
        indicator_str += "\n*Thresholds:*\n"
        indicator_str += f"  Π^{{>θ}}: f+gf ≈ {F_PLUS_GF_D:.1f}\n"
        indicator_str += f"  Π^{{<θ}}: g-gf ≈ {G_MINUS_GF_D:.1f}"
        reply_markup = self._build_main_keyboard()
        await self._safe_reply(update, indicator_str, reply_markup=reply_markup)

    async def fvg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        if not self.engine.state.FG:
            await self._safe_reply(update, "⏳ *Engine not initialized*\nPlease use `/start_feed`.")
            return
        state = self.engine.state
        idx = state.Z - state.y - 1
        bridge_fvgs = BRIDGE_STATE.list_fvgs()
        bridge_str = ""
        if bridge_fvgs:
            bridge_str = "\n📐 *Web App ℱ\\_VG:*\n"
            for f in bridge_fvgs[-8:]:
                mark = "▲" if f["type"] == "top" else "▼"
                who = f" (user {f['user_id']})" if f.get("user_id") else ""
                bridge_str += f"  {mark} {f['price']} idx={f['idx']}{who}\n"
        premium_val = state.Premium[idx] if 0 <= idx < len(state.Premium) else Decimal('0.0')
        discount_val = state.Discount[idx] if 0 <= idx < len(state.Discount) else Decimal('0.0')
        hh_val = state.HH[idx] if 0 <= idx < len(state.HH) else Decimal('0.0')
        ll_val = state.LL[idx] if 0 <= idx < len(state.LL) else Decimal('0.0')
        response = (
            "📐 *Fair Value Gap Tracking*\n"
            f"📊 *ℱ\\_VG Count:* {state.FVG + 1}\n"
            f"💰 *Current Price:* {state.price:.5f}\n"
            f"📉 *Last ℱ\\_VG:* {state.bL if state.bL else 'None'}\n\n"
            "*Topological Anchors:*\n"
            f"  🔷 *Π^{{>θ}}:* {premium_val:.5f}\n"
            f"  🔶 *Π^{{<θ}}:* {discount_val:.5f}\n"
            f"  📈 *HH:* {hh_val:.5f}\n"
            f"  📉 *LL:* {ll_val:.5f}"
            f"{bridge_str}"
        )
        await self._safe_reply(update, response)

    async def chart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        engine = self.engine
        state = engine.state
        recent_signals = state.signal_history[-10:]
        signal_summary = ""
        if recent_signals:
            for sig in recent_signals[-5:]:
                arrow = "📈" if sig["type"] == "BUY" else "🔴"
                signal_summary += f"{arrow} {sig['type']} @ {sig['price']:.2f} ({sig['regime']})\n"
        else:
            signal_summary = "No signals yet.\n"
        response = (
            "📊 *Recent Signals*\n\n"
            f"{signal_summary}\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"📊 *Bar Closes:* {state.bar_close_count}\n"
            f"📈 *OHLCV Bars:* {len(engine.ohlcv_history)}\n"
            f"🎯 *Total Signals Recorded:* {len(state.signal_history)}\n"
            f"🕐 *Last Signal:* {state.last_signal_at or 'never'}\n\n"
            "Open the ÆEA Mini App for the full interactive candlestick chart "
            "with ℱ\\_VG drawings, signal overlays, and the 𝒫\\_arc projection."
        )
        reply_markup = self._build_main_keyboard()
        await self._safe_reply(update, response, reply_markup=reply_markup)

    async def projection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        engine = self.engine
        state = engine.state
        if not state.projection_path:
            engine._project_arc_length(trigger="manual_refresh")
        proj = engine.get_projection()
        meta = proj.get("meta") or {}
        path = proj.get("path") or []
        path_preview = ""
        for step in path[:10]:
            path_preview += f"  ▸ step {step['step']:>2}: {step['price']}\n"
        response = (
            "🌌 *𝒫\\_arc Price Projection*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"💰 *Current Price:* {proj.get('current_price')}\n"
            f"🎯 *Signal Anchor:* {proj.get('signal_level')}\n"
            f"📊 *ℛ\\_regime:* {proj.get('regime')}\n"
            f"🧮 *Branch:* {meta.get('kind', '—')}\n"
            f"⏱️ *𝒫\\_horizon:* {meta.get('horizon', '—')} bars\n"
            f"📐 *𝒫\\_slope:* {meta.get('slope', '—')}\n"
            f"📊 *𝒫\\_amp:* {meta.get('amplitude', '—')}\n"
            f"🎯 *𝒫\\_center:* {meta.get('center', '—')}\n"
            f"💧 *𝒫\\_damp:* {meta.get('damping', '—')}\n"
            f"🛰️ *Provider:* {meta.get('provider', '—')}\n"
            f"🕐 *Computed:* {proj.get('computed_at', 'never')}\n"
            f"🌌 *𝒫\\_trigger:* {proj.get('trigger', '—')}\n\n"
            "*First 10 projected bars:*\n"
            f"{path_preview or '  (no path computed)'}\n"
            "_The projection is drawn on the chart ahead of the current bar. "
            "Drag left past the last bar to scroll into the projected region._"
        )
        reply_markup = self._build_main_keyboard()
        await self._safe_reply(update, response, reply_markup=reply_markup)

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        prev_on_track = self.engine.state.on_track_runs
        prev_on_stand = self.engine.state.on_stand_runs
        prev_signals = len(self.engine.state.signal_history)
        prev_auth_m = self.engine.state.authoritative_m
        prev_auth_n = self.engine.state.authoritative_n
        self.engine.OnReInit()
        self.engine._project_arc_length(trigger="manual_refresh")
        reset_msg = (
            "🔄 *Topological Branch Reset*\n"
            "The Hilbert space projection has been re-anchored to the current\n"
            "topological branch with historical preservation.\n\n"
            "🧠 *State Reset:*\n"
            "• All 13 indicator arrays reset\n"
            "• ℛ\\_regime classification seeded to 'sRange'\n"
            "• Π^{>θ}/Π^{<θ}/HH/LL reset to current bar data\n"
            "• k/l signal flags cleared\n"
            "• ℱ\\_VG anchor map cleared\n"
            "• 𝒫\\_arc projection recomputed\n"
            "• ✨ Historical price data preserved\n"
            f"• 🔄 Tick count preserved: {self.engine.state.tick}\n"
            f"• 📈 𝒯\\_track runs preserved: {prev_on_track}\n"
            f"• 📉 𝒯\\_stand runs preserved: {prev_on_stand}\n"
            f"• 🎯 Signal history preserved: {prev_signals}\n"
            f"• ⚖️ Authoritative m/n preserved: {prev_auth_m}/{prev_auth_n}\n\n"
            "📊 *Ready for new ℛ\\_regime classification...*"
        )
        await self._safe_reply(update, reset_msg)

    async def start_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        if self._running:
            await self._safe_reply(update, "⚠️ Price feed is already running.")
            return
        self._running = True
        self.engine._running = True
        self.engine._consecutive_zero_prices = 0
        historical = []
        try:
            historical = self.engine.feed.get_historical_klines(limit=200)
            if historical and len(historical) >= MIN_HISTORY_WINDOW:
                self.engine.ohlcv_history = historical
                logger.info(f"✅ Loaded {len(historical)} historical bars from relay for {self.engine.feed.active_symbol()} (provider={self.engine.feed.last_provider()})")
                self.engine._populate_indicator_matrix()
            else:
                logger.info("⏳ No historical data from relay. Engine will initialize organically.")
        except Exception as e:
            logger.warning(f"⚠️ Historical data fetch failed: {e}")
        try:
            self.engine.update_price_from_feed()
        except Exception:
            logger.exception("update_price_from_feed crashed during start_feed")
        if self._price_task is None or self._price_task.done():
            self._price_task = asyncio.create_task(self.price_feed_loop())
        hist_count = len(self.engine.ohlcv_history)
        init_mode = "Pre-seeded with history" if hist_count >= MIN_HISTORY_WINDOW else "Organic first-tick"
        reply_text = (
            f"✅ *Price feed started*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"🔄 *Update Interval:* {UPDATE_INTERVAL}s\n"
            f"📊 *Historical Data:* {hist_count} bars loaded\n"
            f"🛰️ *Provider:* `{self.engine.state.last_provider or '—'}`\n"
            f"📦 *𝒱:* `{self.engine.state.last_volume}`\n"
            f"🧠 *Initialization Mode:* {init_mode}\n"
            f"📈 *Indicator Passes:* {self.engine._indicator_populate_count}\n"
            f"🌌 *𝒫\\_arc:* `{self.engine.state.projection_meta.get('kind', '—') if self.engine.state.projection_meta else '—'}`\n"
            f"🔮 *Status:* Monitoring for signals..."
        )
        await self._safe_reply(update, reply_text)

    async def stop_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        self._running = False
        self.engine._running = False
        if self._price_task and not self._price_task.done():
            self._price_task.cancel()
        await self._safe_reply(update, "⏹️ *Price feed stopped*")

    async def probe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        info = self.engine.feed.probe()
        status = "✅ OK" if not info.get("empty") else "❌ EMPTY"
        lines = [
            "🔬 *Relay Probe*", "",
            f"*Status:* {status}",
            f"*Relay URL:* `{RELAY_URL or 'UNSET'}`",
            f"*Relay Gated:* {'🔐 yes' if RELAY_KEY else '🔓 no'}",
            f"*Primary symbol:* `{info.get('primary_symbol')}`",
            f"*Active symbol:* `{info.get('active_symbol')}`",
            f"*Provider:* `{info.get('provider') or '—'}`",
            f"*Last 𝒱:* `{info.get('last_volume') or '0'}`",
            f"*Chain index:* {info.get('chain_index')}",
            f"*Failure count:* {info.get('failure_count')}",
            f"*Fallback count:* {info.get('fallback_count')}",
            f"*Last update:* {info.get('last_update') or 'never'}",
        ]
        text = "\n".join(lines)
        await self._safe_reply(update, text)

    async def rebuild_yf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        self.engine.feed._rebuild_ticker()
        self.engine.feed._fallback_count = 0
        self.engine._consecutive_zero_prices = 0
        if len(self.engine.feed._chain) > 1:
            self.engine.feed._advance_symbol_chain()
        active = self.engine.feed.active_symbol()
        text = (
            f"♻️ *Relay client rebuilt*\n"
            f"🔎 *Active symbol:* `{active}`\n"
            f"_Feed will use this symbol on next iteration._"
        )
        await self._safe_reply(update, text)

    async def symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        args = context.args
        if not args:
            supported = ", ".join(list(SYMBOL_MAP.keys())[:10])
            await self._safe_reply(update,
                f"📈 *Current Symbol:* `{SYMBOL}`\n"
                "Use `/symbol <PAIR>` to change.\n"
                "Example: `/symbol BTC-USD` or `/symbol BTCUSDT`\n\n"
                f"*Supported Symbols:*\n{supported}\n(and {len(SYMBOL_MAP) - 10} more)")
            return
        new_symbol = args[0].upper()
        result = self.engine.change_symbol(new_symbol)
        if result.get("ok"):
            await self._safe_reply(update,
                f"✅ *Symbol changed*\n"
                f"📈 *New Symbol:* `{result.get('symbol')}`\n"
                f"🛰️ *Provider:* `{result.get('provider') or '—'}`\n"
                f"🧠 *Engine reinitialized*\n"
                f"🌌 *𝒫\\_arc seeded for the new symbol*")
        else:
            detail = result.get("detail") or result.get("error") or "unknown"
            await self._safe_reply(update, f"❌ Error: {detail}")

    async def info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        info = self.engine.feed.get_info()
        response = (
            "📊 *Ticker Information*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"📛 *Name:* {info.get('name', 'Unknown')}\n"
            f"💵 *Currency:* {info.get('currency', 'USD')}\n"
            f"🛰️ *Provider:* `{self.engine.state.last_provider or '—'}`\n"
            f"📦 *Last 𝒱:* `{self.engine.state.last_volume}`\n"
        )
        await self._safe_reply(update, response)

    async def webapp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        url = self._resolve_webapp_url()
        if not url:
            await self._safe_reply(update,
                "⏳ *Mini App URL not yet available*\n"
                "The bridge is starting a public HTTPS tunnel. "
                "Please try again in ~30–45 seconds.\n"
                "Alternatively, set `TELEGRAM_WEBAPP_URL` in the environment.")
            return
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Open ÆEA Mini App", web_app=WebAppInfo(url=url))]])
        await self._safe_reply(update,
            "🌐 *ÆEA Telegram Mini App*\n"
            "Tap the button below to launch the full engine visualization.\n\n"
            "*Features inside the Mini App:*\n"
            "  📈 Interactive MT4-style candlestick chart\n"
            "  📊 Add/remove indicator sub-panels\n"
            "  📐 Draw ℱ\\_VGs with long-press\n"
            "  🎯 Place simulated orders\n"
            "  ⚙ Engine settings panel\n"
            "  📋 ℛ\\_regime map, log bar, signal markers\n"
            "  🌌 𝒫\\_arc price projection ahead of the current bar\n"
            "  ➡️ Scroll-ahead viewport to the projected take-profit level\n"
            "  🔔 Toast + Telegram push notifications on every execution\n"
            "  🔄 Live state polling",
            reply_markup=keyboard)

    async def webgui(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._track_inbound_message(update)
        scheme = "https" if BRIDGE_USE_TLS else "http"
        local_url = f"{scheme}://{BRIDGE_HOST}:{BRIDGE_PORT}/"
        public_url = self._resolve_webapp_url() or "⏳ (tunnel pending)"
        await self._safe_reply(update,
            f"🌐 *ÆEA Bridge Endpoints*\n"
            f"*Local URL:* `{local_url}`\n"
            f"*Public URL:* `{public_url}`\n"
            f"*State endpoint:* `{public_url.rstrip('/')}/state`\n"
            f"*Mini App State:* `{public_url.rstrip('/')}/miniapp-state`\n"
            f"*Projection endpoint:* `{public_url.rstrip('/')}/projection`\n"
            f"*Health endpoint:* `{public_url.rstrip('/')}/health`\n"
            f"*Probe endpoint:* `{public_url.rstrip('/')}/probe`\n"
            f"*Diagnostics endpoint:* `{public_url.rstrip('/')}/diagnostics`\n"
            f"*OHLCV endpoint:* `{public_url.rstrip('/')}/ohlcv`\n"
            f"*Signals endpoint:* `{public_url.rstrip('/')}/signals`\n"
            f"*Orders endpoint:* `{public_url.rstrip('/')}/orders`\n"
            f"*Regime map endpoint:* `{public_url.rstrip('/')}/regime-map`\n"
            f"*Log endpoint:* `{public_url.rstrip('/')}/log`\n"
            f"*Toasts endpoint:* `{public_url.rstrip('/')}/toasts`\n"
            f"*Settings endpoint:* `{public_url.rstrip('/')}/settings`\n"
            f"*Handshake endpoint:* `POST {public_url.rstrip('/')}/handshake`")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        action = query.data
        if action == "status":
            await self.status(update, context)
        elif action == "regime":
            await self.regime(update, context)
        elif action == "signal":
            await self.signal(update, context)
        elif action == "indicators":
            await self.indicators(update, context)
        elif action == "chart":
            await self.chart(update, context)
        elif action == "projection":
            await self.projection(update, context)
        elif action == "start_feed":
            await self.start_feed(update, context)
        elif action == "stop_feed":
            await self.stop_feed(update, context)
        elif action == "info":
            await self.info(update, context)
        elif action == "reset":
            await self.reset(update, context)
        elif action == "probe":
            await self.probe(update, context)
        elif action == "rebuild_yf":
            await self.rebuild_yf(update, context)
        elif action == "diagnostics":
            await self.diagnostics(update, context)
        elif action == "webapp_pending":
            try:
                await query.edit_message_text("⏳ *Mini App tunnel is starting…*\nPlease retry `/webapp` in ~30–45 seconds.", parse_mode="Markdown")
            except Exception:
                try:
                    await query.edit_message_text("Mini App tunnel is starting. Please retry /webapp in ~30-45 seconds.", parse_mode=None)
                except Exception as e:
                    logger.warning(f"webapp_pending edit failed: {e}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # D-MAJ-7: surface the error explicitly into the ring buffer so it
        # reaches /log and the TWA log bar. The telegram.ext logger is also
        # attached to _RingHandler (see the module-level setup), but the
        # explicit push here guarantees the error is visible even if the
        # exception is raised outside the telegram.ext logger's propagation.
        err = context.error
        err_str = f"{type(err).__name__}: {err}" if err is not None else "unknown error"
        try:
            with _LOG_LOCK:
                _LOG_BUFFER.append({
                    "ts": datetime.now().isoformat(),
                    "level": "error",
                    "msg": f"⚠️ handler error: {err_str}",
                })
        except Exception:
            pass
        logger.error(f"Update {update} caused error {err}")

    async def _post_init(self, application) -> None:
        # E-10: capture the running event loop so synchronous callers (the
        # price-feed thread, the toast worker thread, the tick loop) can
        # schedule coroutines onto it via asyncio.run_coroutine_threadsafe.
        # python-telegram-bot 21.x makes Bot.send_message a coroutine; calling
        # it without await constructs the coroutine and garbage-collects it,
        # silently dropping the message and emitting a RuntimeWarning.
        try:
            self._loop = asyncio.get_running_loop()
            logger.info("🔁 Event loop captured for cross-thread send")
        except RuntimeError:
            self._loop = None
            logger.warning("⚠️ No running loop in _post_init; sends will be dropped")
        # Populate the bridge refs eagerly so signal/execution alerts and
        # toast pushes can route through _send_message_sync as soon as the
        # event loop is captured, rather than waiting for AEI_Bot.run()'s
        # wrapped_run() to populate them.
        BRIDGE_ENGINE_REF["engine"] = self.engine
        BRIDGE_ENGINE_REF["bot"] = self
        self.engine.application = application
        logger.info("🔗 BRIDGE_ENGINE_REF populated in _post_init")
        url = self._resolve_webapp_url()
        if not url:
            logger.info("⏳ MenuButtonWebApp deferred — no public URL yet")
            return
        try:
            await application.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="ÆEA Mini App", web_app=WebAppInfo(url=url)))
            logger.info(f"✅ MenuButtonWebApp registered: {url}")
        except Exception as e:
            logger.warning(f"Failed to set menu button: {e}")

    def run(self):
        self.engine.OnInit()
        self.application = Application.builder().token(self.token).post_init(self._post_init).build()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("regime", self.regime))
        self.application.add_handler(CommandHandler("signal", self.signal))
        self.application.add_handler(CommandHandler("indicators", self.indicators))
        self.application.add_handler(CommandHandler("chart", self.chart))
        self.application.add_handler(CommandHandler("fvg", self.fvg))
        self.application.add_handler(CommandHandler("projection", self.projection))
        self.application.add_handler(CommandHandler("diagnostics", self.diagnostics))
        self.application.add_handler(CommandHandler("reset", self.reset))
        self.application.add_handler(CommandHandler("start_feed", self.start_feed))
        self.application.add_handler(CommandHandler("stop_feed", self.stop_feed))
        self.application.add_handler(CommandHandler("symbol", self.symbol))
        self.application.add_handler(CommandHandler("info", self.info))
        self.application.add_handler(CommandHandler("probe", self.probe))
        self.application.add_handler(CommandHandler("rebuild_yf", self.rebuild_yf))
        self.application.add_handler(CommandHandler("webapp", self.webapp))
        self.application.add_handler(CommandHandler("webgui", self.webgui))
        self.application.add_handler(CommandHandler("mini", self.webapp))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_error_handler(self.error_handler)
        logger.info(f"🤖 {self.bot_name} starting...")
        logger.info("📊 Quantum-Financial Topology Engine (MQL4-parity port v4.5.2).")
        logger.info(f"🧠 X_PERIOD (const) = {X_PERIOD}, Y_START (const) = {Y_START}")
        logger.info("⚡ 13D Hilbert-space projection populated per bar.")
        logger.info("📡 Bar-close detection uses relay timestamp.")
        logger.info("🎯 Signal logging enabled for all imbalance events.")
        logger.info("⚡ Telegram Mini App enabled (MT4/TradingView-style).")
        logger.info("🛑 𝒯\\_trail: real Ask−Bid spread + symbol-adaptive point size + STOP_LOSS minimum.")
        logger.info("🎯 δ gate: LOCAL m/n from authoritative H()/L() stamps.")
        logger.info("🔄 O() regime mutation preserved as FF no-op.")
        logger.info("📊 OnBar per-j HH/LL anchoring.")
        logger.info("🔍 OnTrack/OnStand MQL4 loop bounds restored (aliased S, not grown copy).")
        logger.info("🔒 Auth enforcement on all non-/health endpoints.")
        logger.info("📈 Chart endpoint & signal history tracking enabled.")
        logger.info("📐 User FVGs stored in bridge registry only (non-destructive).")
        logger.info("🛰️ Multi-provider relay v4.5.0: Kraken → Binance → CoinGecko → Yahoo for crypto; Stooq → Yahoo for equities/futures.")
        logger.info("📦 Real volume carried through OBV, AD, Force, MFI projections.")
        logger.info("🌌 𝒫\\_arc projection computed on execution, init, symbol change, and manual refresh.")
        logger.info("🔔 Push notification on every signal, every execution, every FVG, every close.")
        logger.info("🔔 /toasts endpoint serves incremental signal+execution+fvg toasts with first_available_seq.")
        logger.info("⚙️ /settings GET+POST with exact-decimal parsing and FF-input validation max >= min + 2.")
        logger.info("🖱️ Scroll-ahead viewport: drag past the last bar to the projected TP.")
        logger.info("🎯 Execution-gated projection: recomputed on Bull/Bear/Hawk/Dove/Whisky/Wine/Watter/Blood/Diamond/Ruby.")
        logger.info("💬 Push threading: every push is a reply to the user's most recent inbound message.")
        logger.info("📮 Bounded push dispatch: single queue.Queue(maxsize=512) with one daemon consumer.")
        logger.info("🔁 Cross-thread send: enabled via asyncio.run_coroutine_threadsafe")
        logger.info("🛡️ Markdown escaping: _md_escape applied to every interpolated value (E-12).")
        logger.info("🛡️ Reply-target hardening: retry as standalone on stale reply id (E-11).")
        logger.info("🛡️ Plain-text fallback: parse_mode=None on parse errors (E-13).")
        logger.info("🆕 v4.5.0 symbol universe: Kraken-primary crypto (90+ pairs) and Stooq-primary futures/equities (45+ symbols).")
        logger.info("🩹 v4.5.1 audit patches: D-CRIT-1 init anchor, D-MAJ-3 tick_tock clear, D-MAJ-4 iC toggle, D-MIN-5 stochastic slowing, D-MAJ-6 indicators brackets, D-MAJ-7 telegram.ext ring handler, D-MAJ-8 _safe_reply/_safe_edit fallback, D-MIN-9 indicators _md_escape on bar.")
        logger.info("🩹 v4.5.2 audit patches: D-HARD-1 _populate_indicator_matrix concurrency snapshot, D-CLEAN-1 redundant st.t assignment removed.")
        logger.info("✅ Ready. Use /start to begin.")
        self.application.run_polling()

try:
    _bridge_attach_to_bot(AEI_Bot)
except Exception as _attach_exc:
    import logging as _l
    _l.basicConfig(level=_l.INFO)
    _l.getLogger(__name__).exception("Bridge attach failed: %s", _attach_exc)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not TOKEN:
        logger.error("❌ Error: TELEGRAM_BOT_TOKEN not set.")
        logger.error("   export TELEGRAM_BOT_TOKEN='YOUR_BOT_TOKEN'")
        sys.exit(1)
    bot = AEI_Bot(TOKEN, "UpscaleTradeBot")
    bot.run()

if __name__ == "__main__":
    main()

# ============================================================================
# Q.E.D. — LOGOS = Φ = Truth = Path = Origin
# ============================================================================