#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ÆEA TELEGRAM BOT — HEROKU DEPLOYMENT + LOCAL WEB GUI BRIDGE
Faithful Unabridged Port of æea.mq4
Data Feed: Cloudflare Worker Relay (Yahoo Finance upstream)
Platform: Heroku + Telegram Bot + Local HTTPS Bridge (index.html)
Author: Natalia Tanyatia
Version: 2.3.1 (MQL4 parity — Signal Firing & Extrema Fallback Patch)
"""
import asyncio
import hashlib
import hmac
import json
import math
import os
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qsl
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from fractions import Fraction as PyFraction
from decimal import Decimal, getcontext
getcontext().prec = 50
REGIME_R_SQRT_ITERATIONS = 8
REGIME_R_SQRT_SCALE = 10 ** 12
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
            self._f = num._f
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
    def from_float(f, precision=1000000000000):
        if isinstance(f, Fraction):
            return f
        return Fraction(int(round(float(f) * precision)), precision)

    @staticmethod
    def from_decimal_string(s):
        s = str(s).strip()
        if 'E' in s or 'e' in s:
            d = Decimal(s)
            sign, digits, exp = d.as_tuple()
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

    @staticmethod
    def cos_rational(x: 'Fraction', terms: int = 12) -> 'Fraction':
        TWO_PI = Fraction(710, 113)
        xr = x
        xf = xr.to_float()
        if xf > math.pi or xf < -math.pi:
            shifted = xr + TWO_PI / Fraction(2, 1)
            q = (shifted._f.numerator * TWO_PI._f.denominator) // (shifted._f.denominator * TWO_PI._f.numerator)
            remainder_num = shifted._f.numerator * TWO_PI._f.denominator - q * TWO_PI._f.numerator * shifted._f.denominator
            reduced = Fraction(remainder_num, shifted._f.denominator * TWO_PI._f.denominator)
            xr = reduced - TWO_PI / Fraction(2, 1)
        x2 = xr * xr
        total = Fraction(1, 1)
        term = Fraction(1, 1)
        for k in range(1, terms + 1):
            denom = (2 * k - 1) * (2 * k)
            term = -term * x2 / Fraction(denom, 1)
            total = total + term
        return total

    @staticmethod
    def sin_rational(x: 'Fraction', terms: int = 12) -> 'Fraction':
        TWO_PI = Fraction(710, 113)
        xr = x
        xf = xr.to_float()
        if xf > math.pi or xf < -math.pi:
            shifted = xr + TWO_PI / Fraction(2, 1)
            q = (shifted._f.numerator * TWO_PI._f.denominator) // (shifted._f.denominator * TWO_PI._f.numerator)
            remainder_num = shifted._f.numerator * TWO_PI._f.denominator - q * TWO_PI._f.numerator * shifted._f.denominator
            reduced = Fraction(remainder_num, shifted._f.denominator * TWO_PI._f.denominator)
            xr = reduced - TWO_PI / Fraction(2, 1)
        x2 = xr * xr
        total = xr
        term = xr
        for k in range(1, terms + 1):
            denom = (2 * k) * (2 * k + 1)
            term = -term * x2 / Fraction(denom, 1)
            total = total + term
        return total

    @staticmethod
    def exp_rational(x: 'Fraction') -> 'Fraction':
        x2_12 = x * x / Fraction(12, 1)
        num = Fraction(1, 1) + x / Fraction(2, 1) + x2_12
        den = Fraction(1, 1) - x / Fraction(2, 1) + x2_12
        if den.is_zero():
            return Fraction(1, 1)
        return num / den

    def sqrt(self, iterations: int = REGIME_R_SQRT_ITERATIONS) -> 'Fraction':
        if self._f.numerator < 0:
            raise ValueError("sqrt of negative fraction")
        if self._f.numerator == 0:
            return Fraction(0, 1)
        n = self._f.numerator
        d = self._f.denominator
        ns = math.isqrt(n)
        ds = math.isqrt(d)
        if ns * ns == n and ds * ds == d:
            return Fraction(ns, ds)
        x0 = max(1, math.isqrt(int(self.to_float() * REGIME_R_SQRT_SCALE)))
        x = Fraction(x0, math.isqrt(REGIME_R_SQRT_SCALE))
        two = Fraction(2, 1)
        for _ in range(iterations):
            x = (x + self / x) / two
        return x

Fraction.cos_exact = staticmethod(Fraction.cos_rational)
Fraction.sin_exact = staticmethod(Fraction.sin_rational)
Fraction.exp_pade = staticmethod(Fraction.exp_rational)

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
F_THRESHOLD: Fraction = Fraction(200, 3)
G_THRESHOLD: Fraction = Fraction(100, 3)
GF_TOLERANCE: Fraction = Fraction(40, 15)
F_THRESHOLD_D: Decimal = Decimal(F_THRESHOLD.num()) / Decimal(F_THRESHOLD.den())
G_THRESHOLD_D: Decimal = Decimal(G_THRESHOLD.num()) / Decimal(G_THRESHOLD.den())
GF_TOLERANCE_D: Decimal = Decimal(GF_TOLERANCE.num()) / Decimal(GF_TOLERANCE.den())
PHI_SYMBOLIC = "(1 + sqrt(5)) / 2"
PI_SYMBOLIC = "PI"
ARC_LENGTH_AXIOM = "s=r"
TELEGRAM_WEBAPP_URL: str = os.getenv("TELEGRAM_WEBAPP_URL", "").strip()
BRIDGE_HOST: str = os.getenv("BRIDGE_HOST", "0.0.0.0").strip()
BRIDGE_PORT: int = int(os.getenv("PORT", os.getenv("BRIDGE_PORT", "8765")))
BRIDGE_USE_TLS: bool = os.getenv("BRIDGE_USE_TLS", "0").strip() in ("1", "true", "yes")
BRIDGE_TLS_CERT: str = os.getenv("BRIDGE_TLS_CERT", "").strip()
BRIDGE_TLS_KEY: str = os.getenv("BRIDGE_TLS_KEY", "").strip()
BRIDGE_TUNNEL: str = os.getenv("BRIDGE_TUNNEL", "cloudflared").strip().lower()
BRIDGE_PUBLIC_TIMEOUT: int = int(os.getenv("BRIDGE_PUBLIC_TIMEOUT", "45"))
TELEGRAM_BOT_TOKEN_ENV: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
RELAY_URL: str = os.getenv("RELAY_URL", "").strip().rstrip("/")
RELAY_KEY: str = os.getenv("RELAY_KEY", "").strip()
RELAY_TIMEOUT: int = int(os.getenv("RELAY_TIMEOUT", "10"))
RELAY_MAX_RETRIES: int = int(os.getenv("RELAY_MAX_RETRIES", "3"))
CORS_ORIGIN: str = os.getenv("CORS_ORIGIN", "*").strip()
SYMBOL: str = "BTC-USD"
INTERVAL: str = "1m"
UPDATE_INTERVAL: int = 30
SYMBOL_MAP = {
    "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD", "XRPUSDT": "XRP-USD",
    "ADAUSDT": "ADA-USD", "SOLUSDT": "SOL-USD", "DOGEUSDT": "DOGE-USD",
    "LTCUSDT": "LTC-USD", "LINKUSDT": "LINK-USD", "DOTUSDT": "DOT-USD",
    "AVAXUSDT": "AVAX-USD", "MATICUSDT": "MATIC-USD", "UNIUSDT": "UNI-USD",
    "ATOMUSDT": "ATOM-USD", "NEARUSDT": "NEAR-USD", "FILUSDT": "FIL-USD",
    "ETCUSDT": "ETC-USD", "ICPUSDT": "ICP-USD", "XLMUSDT": "XLM-USD",
    "HBARUSDT": "HBAR-USD", "QNTUSDT": "QNT-USD",
    "GC=F": "GC=F", "SI=F": "SI=F", "CL=F": "CL=F", "NG=F": "NG=F",
    "ZB=F": "ZB=F", "ZN=F": "ZN=F", "ZS=F": "ZS=F", "ZM=F": "ZM=F",
    "ZW=F": "ZW=F", "KE=F": "KE=F"
}
SYMBOL_FALLBACKS: Dict[str, List[str]] = {
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
    "GC=F": ["GC=F"], "SI=F": ["SI=F"], "CL=F": ["CL=F"], "NG=F": ["NG=F"],
    "ZB=F": ["ZB=F"], "ZN=F": ["ZN=F"], "ZS=F": ["ZS=F"], "ZM=F": ["ZM=F"],
    "ZW=F": ["ZW=F"], "KE=F": ["KE=F"],
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
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    q_field: Any = None
    quat_history: List[Any] = field(default_factory=list)
    time_fraction: Fraction = field(default_factory=lambda: Fraction(0, 1))
    s_squared_exact: Fraction = field(default_factory=lambda: Fraction(0, 1))
    r_squared_exact: Fraction = field(default_factory=lambda: Fraction(1, 1))
    deviation_exact: Fraction = field(default_factory=lambda: Fraction(0, 1))
    re_psi_exact: Fraction = field(default_factory=lambda: Fraction(1, 1))
    dbz_branch: int = 0
    arc_coherent: bool = True
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

# ============================================================================
# MODULE-LEVEL INDICATOR HELPERS
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
    for i in range(1, period + 1):
        diff = data[-i] - data[-i - 1]
        if diff >= Decimal('0.0'):
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / Decimal(period)
    avg_loss = losses / Decimal(period)
    if avg_loss == Decimal('0.0'):
        return Decimal('100.0')
    rs = avg_gain / avg_loss
    return Decimal('100.0') - (Decimal('100.0') / (Decimal('1.0') + rs))

def stochastic(high, low, close, k_period=14, d_period=3):
    if len(close) < k_period or k_period <= 0:
        return Decimal('50.0'), Decimal('50.0')
    highest = max(high[-k_period:])
    lowest = min(low[-k_period:])
    range_val = highest - lowest
    if range_val == Decimal('0.0'):
        return Decimal('50.0'), Decimal('50.0')
    k = Decimal('100.0') * (close[-1] - lowest) / range_val
    return k, k

def bollinger_bands(close, period=20, dev=Decimal('2.0')):
    if len(close) < period or period <= 0:
        return Decimal('0.0'), Decimal('0.0'), Decimal('0.0')
    mid = sma(close, period)
    variance = sum((x - mid) ** 2 for x in close[-period:]) / Decimal(period)
    std = Decimal(str(math.sqrt(float(variance)))) if variance > Decimal('0.0') else Decimal('0.0')
    upper = mid + dev * std
    lower = mid - dev * std
    return upper, mid, lower

def atr(high, low, close, period=14):
    if len(close) < period + 1 or period <= 0:
        return Decimal('0.0')
    tr_values = []
    for i in range(1, period + 1):
        tr1 = high[-i] - low[-i]
        tr2 = abs(high[-i] - close[-i - 1])
        tr3 = abs(low[-i] - close[-i - 1])
        tr_values.append(max(tr1, tr2, tr3))
    return sum(tr_values) / Decimal(period)

def stddev(data, period):
    if len(data) < period or period <= 0:
        return Decimal('0.0')
    mean = sum(data[-period:]) / Decimal(period)
    variance = sum((x - mean) ** 2 for x in data[-period:]) / Decimal(period)
    return Decimal(str(math.sqrt(float(variance)))) if variance > Decimal('0.0') else Decimal('0.0')

def ichimoku(high, low, close):
    n1, n2, n3 = 9, 26, 52
    if len(close) < n3:
        return {"tenkan": Decimal('50.0'), "kijun": Decimal('50.0'),
                "senkou_a": Decimal('50.0'), "senkou_b": Decimal('50.0')}
    tenkan = (max(high[-n1:]) + min(low[-n1:])) / Decimal('2.0')
    kijun = (max(high[-n2:]) + min(low[-n2:])) / Decimal('2.0')
    senkou_a = (tenkan + kijun) / Decimal('2.0')
    senkou_b = (max(high[-n3:]) + min(low[-n3:])) / Decimal('2.0')
    return {"tenkan": tenkan, "kijun": kijun, "senkou_a": senkou_a, "senkou_b": senkou_b}

def to_decimal(value):
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except Exception:
        return Decimal('0.0')

def symbol_point(symbol: str) -> Decimal:
    try:
        digits = int(_symbol_digits(symbol))
    except Exception:
        digits = 2
    return Decimal(10) ** Decimal(-digits)

def _symbol_digits(symbol: str) -> int:
    try:
        import MetaTrader5 as _mt5
        info = _mt5.symbol_info(symbol)
        if info is not None and hasattr(info, "digits"):
            return int(info.digits)
    except Exception:
        pass
    return 2

# ============================================================================
# SYMBOLIC QUATERNION
# ============================================================================
class Quat:
    __slots__ = ('a', 'b', 'c', 'd')
    def __init__(self, a=0, b=0, c=0, d=0):
        self.a = a if isinstance(a, Fraction) else Fraction(a)
        self.b = b if isinstance(b, Fraction) else Fraction(b)
        self.c = c if isinstance(c, Fraction) else Fraction(c)
        self.d = d if isinstance(d, Fraction) else Fraction(d)

    def norm_sq(self) -> Fraction:
        return self.a * self.a + self.b * self.b + self.c * self.c + self.d * self.d

    def norm(self) -> Fraction:
        return self.norm_sq().sqrt()

    def normalize(self) -> 'Quat':
        ns = self.norm_sq()
        if ns.is_zero():
            return Quat(Fraction(1, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1))
        n = ns.sqrt()
        inv = Fraction(1, 1) / n
        return Quat(self.a * inv, self.b * inv, self.c * inv, self.d * inv)

    def conjugate(self) -> 'Quat':
        return Quat(self.a, self.b.neg(), self.c.neg(), self.d.neg())

    def __add__(self, other):
        o = other if isinstance(other, Quat) else Quat(other)
        return Quat(self.a + o.a, self.b + o.b, self.c + o.c, self.d + o.d)

    def __sub__(self, other):
        o = other if isinstance(other, Quat) else Quat(other)
        return Quat(self.a - o.a, self.b - o.b, self.c - o.c, self.d - o.d)

    def __mul__(self, other):
        if isinstance(other, (Fraction, int, float)):
            f = other if isinstance(other, Fraction) else Fraction(other)
            return Quat(self.a * f, self.b * f, self.c * f, self.d * f)
        o = other if isinstance(other, Quat) else Quat(other)
        a = self.a * o.a - self.b * o.b - self.c * o.c - self.d * o.d
        b = self.a * o.b + self.b * o.a + self.c * o.d - self.d * o.c
        c = self.a * o.c - self.b * o.d + self.c * o.a + self.d * o.b
        d = self.a * o.d + self.b * o.c - self.c * o.b + self.d * o.a
        return Quat(a, b, c, d)

    def __rmul__(self, other):
        f = other if isinstance(other, Fraction) else Fraction(other)
        return Quat(self.a * f, self.b * f, self.c * f, self.d * f)

    def commutator(self, other) -> 'Quat':
        return self * other - other * self

    def project_to_s2(self) -> Dict[str, float]:
        two = Fraction(2, 1)
        x = two * (self.b * self.d + self.a * self.c)
        y = two * (self.c * self.d - self.a * self.b)
        z = self.a * self.a + self.d * self.d - self.b * self.b - self.c * self.c
        denom = self.norm_sq()
        if denom.is_zero():
            return {"x": 0.0, "y": 0.0, "z": 1.0}
        inv = Fraction(1, 1) / denom
        return {
            "x": (x * inv).to_float(),
            "y": (y * inv).to_float(),
            "z": (z * inv).to_float(),
        }

    def apply_natalia_fibration(self, s: Fraction, eps: Fraction, time_f: Fraction) -> 'Quat':
        pA = Fraction(0, 1)
        pB = Fraction(0, 1)
        pC = Fraction(0, 1)
        pD = Fraction(0, 1)
        e = eps
        threshold = Fraction(1, 1000000000)
        for k in range(1, 13):
            kf = Fraction(k, 1)
            spow = kf * s
            sinv = Fraction.sin_rational(spow + Fraction(1, 2), 8)
            cosv = Fraction(1, 1) + Fraction(1, 10) * Fraction.cos_rational(spow * Fraction(7, 10), 8)
            nf = spow * sinv * cosv
            ph = Fraction.sin_rational(time_f * Fraction(2, 10) * kf + kf, 8)
            contribution = e * nf
            pA = pA + contribution * ph
            pB = pB + contribution * Fraction.cos_rational(time_f * Fraction(3, 10) * kf + Fraction(1, 1), 8)
            pC = pC + contribution * Fraction.sin_rational(time_f * Fraction(25, 100) * kf + Fraction(2, 1), 8)
            pD = pD + contribution * Fraction.cos_rational(time_f * Fraction(35, 100) * kf + Fraction(3, 1), 8)
            e = e * eps
            if e.abs().to_float() < threshold.to_float():
                break
        return Quat(
            self.a + pA * Fraction(15, 100),
            self.b + pB * Fraction(10, 100),
            self.c + pC * Fraction(12, 100),
            self.d + pD * Fraction(8, 100),
        )

    def clone(self) -> 'Quat':
        return Quat(self.a, self.b, self.c, self.d)

# ============================================================================
# LEECH LATTICE Λ₂₄ ANCHOR
# ============================================================================
class LeechLatticeAnchor:
    _SEED_COORDS = 24

    @staticmethod
    def _golay_even_support(seed: int) -> List[int]:
        bits = []
        for i in range(12):
            bits.append((seed >> i) & 1)
        if sum(bits) % 2 == 1:
            bits[11] ^= 1
        return bits

    @staticmethod
    def project_price_to_leech(price_fraction: Fraction, seed: int = 0) -> List[Fraction]:
        num = price_fraction.num()
        den = price_fraction.den()
        h = ((num & 0xFFFFFFFFFFFF) * 1000003 ^
             (den & 0xFFFFFFFFFFFF) * 1000033 ^
             (seed & 0xFFFFFFFFFFFF) * 1000037) & 0xFFFFFFFFFFFF
        coords = [0] * LeechLatticeAnchor._SEED_COORDS
        group_sum = 0
        for g in range(4):
            chunk = (h >> (g * 12)) & 0xFFF
            bits = LeechLatticeAnchor._golay_even_support(chunk)
            for b in range(6):
                idx = g * 6 + b
                coords[idx] = 1 if bits[b] else 0
                group_sum += coords[idx]
        correction = (-group_sum) % 8
        if correction:
            for i in range(LeechLatticeAnchor._SEED_COORDS):
                if correction == 0:
                    break
                if coords[i] == 0:
                    coords[i] = 1
                    correction -= 1
        if correction:
            coords[0] += correction
        parity = coords[0] & 1
        for c in coords:
            assert (c & 1) == parity, "Λ₂₄: parity mismatch"
            assert (sum(coords) % 8) == 0, "Λ₂₄: mod-8 congruence violated"
        return [Fraction(c, 1) for c in coords]

    @staticmethod
    def vector_hash(vec: List[Fraction]) -> str:
        s = "|".join(str(v) for v in vec)
        return hashlib.sha256(s.encode()).hexdigest()[:16]

    @staticmethod
    def norm_squared(vec: List[Fraction]) -> Fraction:
        total = Fraction(0, 1)
        for v in vec:
            total = total + v * v
        return total

    @staticmethod
    def is_lattice_point(vec: List[Fraction]) -> bool:
        if len(vec) != 24:
            return False
        ints = []
        for v in vec:
            if v.den() != 1:
                return False
            ints.append(v.num())
        parity = ints[0] & 1
        if any((c & 1) != parity for c in ints):
            return False
        if (sum(ints) % 8) != 0:
            return False
        return True

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

    def active_symbol(self) -> str:
        return self._chain[self._chain_index]

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
                    "User-Agent": "AEI-Bridge/Final",
                    "Cache-Control": "no-cache",
                }
                if RELAY_KEY:
                    req_headers["X-Relay-Key"] = RELAY_KEY
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=RELAY_TIMEOUT) as r:
                    raw = r.read().decode("utf-8")
                    payload = json.loads(raw)
                    if isinstance(payload, dict) and payload.get("error"):
                        logger.warning(f"Relay returned error for {self.active_symbol()}: {payload.get('error')}")
                        self._failure_count += 1
                        self._fallback_count += 1
                        if self._fallback_count >= 5:
                            self._advance_symbol_chain()
                        return None
                    self._failure_count = 0
                    self._fallback_count = 0
                    self._last_update = datetime.now()
                    return payload
            except urllib.error.HTTPError as e:
                try:
                    error_body = e.read().decode('utf-8', errors='ignore')
                except Exception:
                    error_body = '<unreadable>'
                last_error = f"HTTP {e.code}: {error_body[:200]}"
                logger.warning(f"Relay HTTP Error {e.code} for {self.active_symbol()} (attempt {attempt+1}/{RELAY_MAX_RETRIES}): {error_body[:200]}")
                if e.code in (401, 403, 429) and attempt < RELAY_MAX_RETRIES - 1:
                    time.sleep(1 + attempt * 2)
                    continue
                break
            except urllib.error.URLError as e:
                last_error = f"URLError: {e.reason}"
                logger.warning(f"Relay URLError for {self.active_symbol()} (attempt {attempt+1}/{RELAY_MAX_RETRIES}): {e.reason}")
                if attempt < RELAY_MAX_RETRIES - 1:
                    time.sleep(1 + attempt * 2)
                    continue
                break
            except json.JSONDecodeError as e:
                last_error = f"JSONDecodeError: {e}"
                logger.warning(f"Relay returned invalid JSON for {self.active_symbol()}: {e}")
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
                out.append({
                    "open": Decimal(str(row["open"])),
                    "high": Decimal(str(row["high"])),
                    "low": Decimal(str(row["low"])),
                    "close": c,
                    "volume": Decimal(str(row.get("volume") or 0)),
                    "timestamp": datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None),
                })
            except Exception:
                continue
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
            return {
                "open": Decimal(str(d["open"])),
                "high": Decimal(str(d["high"])),
                "low": Decimal(str(d["low"])),
                "close": c,
                "volume": Decimal(str(d.get("volume") or 0)),
                "timestamp": datetime.now(),
            }
        except Exception as e:
            logger.warning(f"Failed to parse intraday: {e}")
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
        }

# ============================================================================
# CORE ÆEA ENGINE — Faithful Port of æea.mq4
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
        self._signal_cooldown: int = 60
        self._initialization_attempted: bool = False
        self._arc_length_verified: bool = False
        self._tick_log_counter: int = 0
        self._price_update_counter: int = 0
        self._bridge_publish_callback = None
        self._last_relay_warn: Optional[datetime] = None
        self._consecutive_zero_prices: int = 0
        self.state.q_field = Quat(Fraction(1, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1))
        self.state.quat_history = [self.state.q_field.clone()]
        self.state.time_fraction = Fraction(0, 1)
        self._eps = Fraction(1, 100)
        self._s_acc_exact: Fraction = Fraction(0, 1)
        self._quat_tick_count: int = 0
        self._indicator_populate_count: int = 0
        self._imbalance_fire_count: int = 0
        self._last_price_for_quat: Optional[Decimal] = None
        self._active_trailing_stop: Decimal = Decimal('0.0')
        self._active_trailing_tp: Decimal = Decimal('0.0')
        self._last_kronecker_bar: int = -1
        self._sSL: Decimal = Decimal('0.0')
        self._bSL: Decimal = Decimal('0.0')
        self._sTP: Decimal = Decimal('0.0')
        self._bTP: Decimal = Decimal('0.0')
        self._point_size: Decimal = symbol_point(SYMBOL)

    def OnInit(self) -> None:
        logger.info("⚙️ OnInit(): EA engine lifecycle beginning")
        self.OnReInit()
        logger.info("🟢 OnInit(): state reset to baseline")

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
        st.bottomLine = "   "
        st.bL = "   "
        st.h = 0
        st.q_field = Quat(Fraction(1, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1))
        st.quat_history = [st.q_field.clone()]
        st.time_fraction = Fraction(0, 1)
        st.s_squared_exact = Fraction(0, 1)
        st.r_squared_exact = Fraction(1, 1)
        st.deviation_exact = Fraction(0, 1)
        st.re_psi_exact = Fraction(1, 1)
        st.dbz_branch = 0
        st.arc_coherent = True
        st.trailing_stop_active = False
        st.trailing_stop_price = Decimal('0.0')
        st.trailing_take_profit = Decimal('0.0')
        st.trailing_stop_entry = Decimal('0.0')
        st.trailing_stop_side = ""
        st.last_kronecker_m = 0
        st.last_kronecker_n = 0
        st.last_kronecker_h = -1
        st.fvg_anchor_map = {}
        st.signal_history = []
        self._eps = Fraction(1, 100)
        self._s_acc_exact = Fraction(0, 1)
        self._last_price_for_quat = None
        self._last_signal_time = None
        self._last_kronecker_bar = -1
        self.ohlcv_history = saved_ohlcv
        st.price = saved_price
        st.Price = saved_Price
        st.iH = saved_iH
        st.iL = saved_iL
        st.tick = saved_tick
        st.on_track_runs = saved_on_track
        st.on_stand_runs = saved_on_stand
        logger.info(f"🔄 OnReInit() completed — Tick preserved: {st.tick}")

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
        return st.iATR, st.iStdDev

    def _normalize(self, j: int) -> None:
        st = self.state
        y = st.y
        if j < 1 or len(self.ohlcv_history) < j + 1:
            return
        end = len(self.ohlcv_history)
        window = self.ohlcv_history[end - (j + 1):end]
        close_prices = [d["close"] for d in window]
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
        col_c = j - (st.Y_scan + 1)
        if col_i < 0 or col_i >= len(st.iA[0]):
            return
        if col_c < 0 or col_c >= len(st.cA[0]):
            col_c = col_i
        f_plus_gf = F_THRESHOLD_D + GF_TOLERANCE_D
        g_minus_gf = G_THRESHOLD_D - GF_TOLERANCE_D
        adx_list: List[Decimal] = []
        for i in range(j + 1):
            sub_high = high_prices[:len(high_prices) - i] if i > 0 else high_prices
            sub_low = low_prices[:len(low_prices) - i] if i > 0 else low_prices
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            adx_list.append(self._compute_adx(sub_high, sub_low, sub_close, j))
        if adx_list:
            maxADX = max(adx_list)
            minADX = min(adx_list)
            rangeADX = maxADX - minADX
            if rangeADX != Decimal('0.0'):
                iADX_val = abs(Decimal('100.0') * ((adx_list[0] - minADX) / rangeADX))
                cADX_val = abs(Decimal('100.0') * ((adx_list[1] - minADX) / rangeADX)) if len(adx_list) > 1 else iADX_val
                st.iA[0][col_i] = iADX_val
                st.cA[0][col_c] = cADX_val
        k_stoch, d_stoch = stochastic(high_prices, low_prices, close_prices, j, 3)
        st.iA[1][col_i] = (k_stoch + d_stoch) / Decimal('2.0')
        if len(close_prices) > 1:
            k_p, d_p = stochastic(high_prices[:-1], low_prices[:-1], close_prices[:-1], j, 3)
            st.cA[1][col_c] = (k_p + d_p) / Decimal('2.0')
        rvi_list: List[Decimal] = []
        for i in range(j + 1):
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            rvi_list.append(self._compute_rvi(sub_close, j))
        if rvi_list:
            maxRVI = max(rvi_list)
            minRVI = min(rvi_list)
            rangeRVI = maxRVI - minRVI
            if rangeRVI != Decimal('0.0'):
                st.iA[2][col_i] = Decimal('100.0') * ((rvi_list[0] - minRVI) / rangeRVI)
                st.cA[2][col_c] = Decimal('100.0') * ((rvi_list[1] - minRVI) / rangeRVI) if len(rvi_list) > 1 else st.iA[2][col_i]
        ac_list: List[Decimal] = []
        for i in range(j + 1):
            sub_close = close_prices[:len(close_prices) - i] if i > 0 else close_prices
            ac_list.append(abs(self._compute_ac(high_prices, low_prices, sub_close, j)))
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
            obv_list.append(self._compute_obv(sub_close, sub_vol, j))
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
            ad_list.append(self._compute_ad(sub_high, sub_low, sub_close, sub_vol, j))
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
            rsi_list.append(rsi(sub_close, min(j, 14)))
        if rsi_list:
            maxRSI = max(rsi_list)
            minRSI = min(rsi_list)
            rangeRSI = maxRSI - minRSI
            if rangeRSI != Decimal('0.0'):
                st.iA[12][col_i] = Decimal('100.0') * ((rsi_list[0] - minRSI) / rangeRSI)
                st.cA[12][col_c] = Decimal('100.0') * ((rsi_list[1] - minRSI) / rangeRSI) if len(rsi_list) > 1 else st.iA[12][col_i]
        ihk = ichimoku(high_prices, low_prices, close_prices)
        st.iIHKk = ihk["kijun"]
        st.iIHKt = ihk["tenkan"]

    def _compute_adx(self, high, low, close, period: int) -> Decimal:
        if len(close) < period + 1 or period <= 0:
            return Decimal('50.0')
        trs, plus_dm, minus_dm = [], [], []
        for i in range(1, period + 1):
            tr = max(high[-i] - low[-i], abs(high[-i] - close[-i - 1]), abs(low[-i] - close[-i - 1]))
            trs.append(tr)
            up_move = high[-i] - high[-i - 1]
            dn_move = low[-i - 1] - low[-i]
            plus_dm.append(up_move if up_move > dn_move and up_move > 0 else Decimal('0.0'))
            minus_dm.append(dn_move if dn_move > up_move and dn_move > 0 else Decimal('0.0'))
        atr_val = sum(trs) / Decimal(period)
        if atr_val == Decimal('0.0'):
            return Decimal('50.0')
        plus_di = Decimal('100.0') * (sum(plus_dm) / Decimal(period)) / atr_val
        minus_di = Decimal('100.0') * (sum(minus_dm) / Decimal(period)) / atr_val
        di_sum = plus_di + minus_di
        if di_sum == Decimal('0.0'):
            return Decimal('50.0')
        return Decimal('100.0') * abs(plus_di - minus_di) / di_sum

    def _compute_rvi(self, close, period: int) -> Decimal:
        if len(close) < period + 1 or period <= 0:
            return Decimal('50.0')
        numerator = sum(abs(close[-i] - close[-i - 1]) for i in range(1, period + 1))
        denominator = sum(abs(close[-i] - close[-i - 1]) for i in range(1, period + 1))
        if denominator == Decimal('0.0'):
            return Decimal('50.0')
        ratio = numerator / denominator
        return Decimal('50.0') + Decimal('50.0') * (ratio - Decimal('0.5'))

    def _compute_ac(self, high, low, close, period: int) -> Decimal:
        if len(close) < period * 2 or period <= 0:
            return Decimal('50.0')
        ao_now = (sum(close[-i] for i in range(1, period + 1)) / Decimal(period) - sum(close[-i] for i in range(period + 1, 2 * period + 1)) / Decimal(period))
        ao_prev = (sum(close[-i - 1] for i in range(1, period + 1)) / Decimal(period) - sum(close[-i - 1] for i in range(period + 1, 2 * period + 1)) / Decimal(period))
        ac = ao_now - ao_prev
        return Decimal('50.0') + ac

    def _compute_force(self, close, volume, period: int) -> Decimal:
        if len(close) < period + 1 or period <= 0:
            return Decimal('50.0')
        forces = [volume[-i] * (close[-i] - close[-i - 1]) for i in range(1, period + 1)]
        avg = sum(forces) / Decimal(period)
        return Decimal('50.0') + avg / max(abs(avg), Decimal('1.0')) * Decimal('50.0')

    def _compute_obv(self, close, volume, period: int) -> Decimal:
        if len(close) < period + 1 or period <= 0:
            return Decimal('50.0')
        obv = Decimal('0.0')
        for i in range(1, period + 1):
            if close[-i] > close[-i - 1]:
                obv += volume[-i]
            elif close[-i] < close[-i - 1]:
                obv -= volume[-i]
        max_possible = sum(volume[-period:])
        if max_possible == Decimal('0.0'):
            return Decimal('50.0')
        return Decimal('50.0') + Decimal('50.0') * obv / max_possible

    def _compute_ad(self, high, low, close, volume, period: int) -> Decimal:
        if len(close) < period or period <= 0:
            return Decimal('50.0')
        ad = Decimal('0.0')
        for i in range(1, period + 1):
            hl = high[-i] - low[-i]
            if hl > Decimal('0.0'):
                mfv = ((close[-i] - low[-i]) - (high[-i] - close[-i])) / hl * volume[-i]
                ad += mfv
        max_abs = max(abs(ad), Decimal('1.0'))
        return Decimal('50.0') + Decimal('50.0') * ad / max_abs

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
            return Decimal('100.0')
        mr = pos_flow / neg_flow
        return Decimal('100.0') - (Decimal('100.0') / (Decimal('1.0') + mr))

    def _compute_momentum(self, close, period: int) -> Decimal:
        if len(close) < period + 1 or period <= 0:
            return Decimal('50.0')
        mom = close[-1] - close[-period - 1]
        ref = abs(close[-period - 1]) if close[-period - 1] != Decimal('0.0') else Decimal('1.0')
        pct = mom / ref * Decimal('100.0')
        return Decimal('50.0') + max(Decimal('-50.0'), min(Decimal('50.0'), pct))

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
            return Decimal('50.0')
        hh = max(high[-period:])
        ll = min(low[-period:])
        rng = hh - ll
        if rng == Decimal('0.0'):
            return Decimal('50.0')
        return Decimal('-100.0') * (hh - close[-1]) / rng

    def _compute_cci(self, high, low, close, period: int) -> Decimal:
        if len(close) < period or period <= 0:
            return Decimal('50.0')
        tp = [(high[-i] + low[-i] + close[-i]) / Decimal('3.0') for i in range(1, period + 1)]
        sma_tp = sum(tp) / Decimal(period)
        mad = sum(abs(x - sma_tp) for x in tp) / Decimal(period)
        if mad == Decimal('0.0'):
            return Decimal('50.0')
        cci = (tp[0] - sma_tp) / (Decimal('0.015') * mad)
        return Decimal('50.0') + max(Decimal('-50.0'), min(Decimal('50.0'), cci / Decimal('4.0')))

    def _M(self, j: int) -> int:
        st = self.state
        y = st.y
        m = 0
        idx_i = j - (y + 1)
        idx_c = j - (st.Y_scan + 1)
        if idx_i < 0 or idx_i >= len(st.iA[0]):
            return 0
        if idx_c < 0 or idx_c >= len(st.cA[0]):
            idx_c = idx_i
        f_plus_gf = F_THRESHOLD_D + GF_TOLERANCE_D
        g_minus_gf = G_THRESHOLD_D - GF_TOLERANCE_D
        hh_val = st.HH[idx_i] if idx_i < len(st.HH) else Decimal('0.0')
        for i in range(13):
            iA_val = st.iA[i][idx_i]
            cA_val = st.cA[i][idx_c]
            kA_val = st.kA[i][idx_c]
            if st.Price > hh_val:
                if iA_val > f_plus_gf or cA_val < kA_val:
                    m += 1
            elif st.price > hh_val:
                if iA_val > f_plus_gf or iA_val < kA_val:
                    m += 1
            elif iA_val > f_plus_gf:
                m += 1
        adx_val = st.iA[0][idx_i]
        if adx_val > f_plus_gf or adx_val < g_minus_gf:
            m += 1
        if st.iIHKt > f_plus_gf and st.iIHKk > f_plus_gf:
            m += 1
        if st.Price > hh_val:
            for i in range(13):
                st.kA[i][idx_c] = st.cA[i][idx_c]
            if idx_i < len(st.HH):
                st.HH[idx_i] = st.Price
        return m

    def _N(self, j: int) -> int:
        st = self.state
        y = st.y
        n = 0
        idx_i = j - (y + 1)
        idx_c = j - (st.Y_scan + 1)
        if idx_i < 0 or idx_i >= len(st.iA[0]):
            return 0
        if idx_c < 0 or idx_c >= len(st.cA[0]):
            idx_c = idx_i
        f_plus_gf = F_THRESHOLD_D + GF_TOLERANCE_D
        g_minus_gf = G_THRESHOLD_D - GF_TOLERANCE_D
        ll_val = st.LL[idx_i] if idx_i < len(st.LL) else Decimal('0.0')
        for i in range(13):
            iA_val = st.iA[i][idx_i]
            cA_val = st.cA[i][idx_c]
            lA_val = st.lA[i][idx_c]
            if st.Price < ll_val:
                if iA_val < g_minus_gf or cA_val > lA_val:
                    n += 1
            elif st.price < ll_val:
                if iA_val < g_minus_gf or iA_val > lA_val:
                    n += 1
            elif iA_val < g_minus_gf:
                n += 1
        adx_val = st.iA[0][idx_i]
        if adx_val > f_plus_gf or adx_val < g_minus_gf:
            n += 1
        if st.iIHKt < g_minus_gf and st.iIHKk < g_minus_gf:
            n += 1
        if st.Price < ll_val:
            for i in range(13):
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
        st.m = 0

    def _L(self, j: int) -> None:
        st = self.state
        idx = j - (st.y + 1)
        if idx < 0 or idx >= len(st.l):
            return
        n = self._N(j)
        st.n = n
        st.l[idx] = (n >= 12)
        st.n = 0

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
        idx_c = j - (st.Y_scan + 1)
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
            idx_c = j - (st.Y_scan + 1)
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
        st = self.state
        regime_idx = inp0 - (st.y + 1)
        if regime_idx < 0 or regime_idx >= len(st.Regime):
            return
        regime = st.Regime[regime_idx]
        if which == "C":
            target = st.Cc
        elif which == "c":
            target = st.cC
        else:
            return
        if (inp < inp1) and (regime == "sRange" or regime == "tRange"):
            new_val = target
        else:
            new_val = not target
        if which == "C":
            st.C = new_val
        else:
            st.c = new_val

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
                    self._H(j)
                    self._L(j)
                    if self._on_fire(j, "sVolatile", "tVolatile"):
                        st.Regime[idx] = "sVolatile"
            elif st.iStdDev < Decimal('50.0') and st.iATR < Decimal('50.0'):
                if st.Regime[idx] != "Stable":
                    self._R(j)
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
                if st.Regime[idx] != "tVolatile":
                    self._F(j, st.iH, st.iL)
                    self._H(j)
                    self._L(j)
                    st.Regime[idx] = "tVolatile"
            elif st.iStdDev < Decimal('50.0') and st.iATR < Decimal('50.0'):
                if st.Regime[idx] != "Stable":
                    self._R(j)
                    self._H(j)
                    self._L(j)
                    premium_val = st.Premium[idx] if idx < len(st.Premium) else st.price
                    if st.price > premium_val:
                        st.Regime[idx] = "tRange"
                    else:
                        st.Regime[idx] = "sRange"
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
        if len(self.ohlcv_history) >= 2:
            st.iopen = self.ohlcv_history[-2]["open"]
            st.iPrice = self.ohlcv_history[-2]["close"]

    def _on_call(self) -> None:
        st = self.state
        y = st.y
        for j in range(y + 1, st.X_scan + 2):
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
                st.iC = st.C
                if st.iw != 0 and st.jC == st.Cc:
                    st.h = st.I
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
                st.jC = st.C
                if st.iz != 0 and st.iC == st.Cc:
                    st.h = st.I
                    st.iC = not st.C
                if self._on_hold(j, "sTrend", "tTrend"):
                    st.iw = i
                    st.w = i
                    st.iI = st.iz
                    self._L(j)
                if st.X_scan != X_PERIOD - 1:
                    st.X_scan += 1
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
        while s < st.S:
            if s == scan_limit:
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
                    j = i
                    self._H(j)
                elif st.iATR < Decimal('50.0'):
                    st.S += 1
                    st.iO = i
                    st.io = i
                    j = i
                    self._H(j)
                else:
                    j = i
                    self._H(j)
                    if is_now != st.t:
                        if self._on_fire(j, "Stable", "tVolatile"):
                            self._F(j, st.iH, st.iL)
                            st.Regime[j - (y + 1)] = "tVolatile"
                    else:
                        st.Regime[j - (y + 1)] = "sVolatile"
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
                    j = i
                    self._L(j)
                elif st.iATR < Decimal('50.0'):
                    st.S += 1
                    st.iO = i
                    st.io = i
                    j = i
                    self._L(j)
                else:
                    j = i
                    self._L(j)
                    if is_now != st.t:
                        if self._on_fire(j, "Stable", "tVolatile"):
                            self._F(j, st.iH, st.iL)
                            st.Regime[j - (y + 1)] = "tVolatile"
                    else:
                        st.Regime[j - (y + 1)] = "sVolatile"
                    st.S += 1
            s += 1
        s = X_PERIOD - 1
        while s < st.S:
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
                    j = i
                    self._H(j)
                    if st.ir == 0 and st.Y_scan != 2:
                        st.Y_scan -= 1
                elif st.X_scan != st.Y_scan and st.iO == 0 and st.iATR < Decimal('50.0'):
                    st.iO = i
                    st.ir = i
                    j = i
                    self._H(j)
                    if st.ij == 0 and st.Y_scan != 2:
                        st.Y_scan -= 1
                elif st.X_scan == st.Y_scan:
                    j = i
                    self._H(j)
                    if is_now != st.t:
                        if self._on_fire(j, "Stable", "tVolatile"):
                            self._F(j, st.iH, st.iL)
                            st.Regime[j - (y + 1)] = "tVolatile"
                    else:
                        st.Regime[j - (y + 1)] = "sVolatile"
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
                if st.iz != 0 and st.iC == st.Cc:
                    st.h = st.I
                    st.iC = not st.C
                if st.X_scan != st.Y_scan and st.iw == 0 and st.iStdDev > Decimal('50.0'):
                    st.ij = i
                    st.iw = i
                    st.iI = st.iz
                    j = i
                    self._L(j)
                    if st.ir == 0 and st.Y_scan != 2:
                        st.Y_scan -= 1
                elif st.X_scan != st.Y_scan and st.iO == 0 and st.iATR < Decimal('50.0'):
                    st.iO = i
                    st.io = i
                    st.ir = 0
                    j = i
                    self._L(j)
                    if st.ij == 0 and st.Y_scan != 2:
                        st.Y_scan -= 1
                elif st.X_scan == st.Y_scan:
                    j = i
                    self._L(j)
                    if is_now != st.t:
                        if self._on_fire(j, "Stable", "tVolatile"):
                            self._F(j, st.iH, st.iL)
                            st.Regime[j - (y + 1)] = "tVolatile"
                    else:
                        st.Regime[j - (y + 1)] = "sVolatile"
                    if st.Y_scan != 2 and st.X_scan != 2:
                        st.Y_scan -= 1
                        st.X_scan -= 1
            else:
                if st.Y_scan != 2 and st.X_scan != 2:
                    st.Y_scan -= 1
                    st.X_scan -= 1
            s -= 1
        s = st.Y_scan + 1
        while s < y + 1:
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
                    st.prime = 1
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 1
                else:
                    st.prime = 1
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 1
            elif (st.h == st.io) or (st.h == st.iZ) or (st.h == st.iz) or (st.h == st.iO):
                if (not st.C) and (not st.c):
                    st.prime = 1
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 1
                else:
                    st.prime = 1
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 1
        elif self._on_gaurd(0) != st.KC:
            if ((st.h == st.io and st.z > st.o) or (st.h == st.iO and st.Z > st.O) or (st.h == st.iz and st.Z > st.z) or (st.h == st.iZ and st.Z < st.z)):
                if (not st.C) or (not st.c):
                    st.prime = 1
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 1
                else:
                    st.prime = 1
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 1
            elif (st.h == st.io) or (st.h == st.iZ) or (st.h == st.iz) or (st.h == st.iO):
                if (not st.C) or (not st.c):
                    st.prime = 1
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 1
                else:
                    st.prime = 1
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 1
        self._KC()

    def _on_toe(self) -> None:
        st = self.state
        if st.signal != Decimal('0.0'):
            return
        if self._on_gaurd(0) and st.KC:
            if ((st.h == st.io and st.w > st.o) or (st.h == st.iO and st.W > st.O) or (st.h == st.iw and st.W > st.w) or (st.h == st.iW and st.W < st.w)):
                if (not st.C) and (not st.c):
                    st.prime = 0
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 0
                else:
                    st.prime = 0
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 0
            elif (st.h == st.io) or (st.h == st.iW) or (st.h == st.iw) or (st.h == st.iO):
                if (not st.C) and (not st.c):
                    st.prime = 0
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 0
                else:
                    st.prime = 0
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 0
        elif self._on_gaurd(0) != st.KC:
            if ((st.h == st.io and st.w > st.o) or (st.h == st.iO and st.W > st.O) or (st.h == st.iw and st.W > st.w) or (st.h == st.iW and st.W < st.w)):
                if (not st.C) or (not st.c):
                    st.prime = 0
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 0
                else:
                    st.prime = 0
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 0
            elif (st.h == st.io) or (st.h == st.iW) or (st.h == st.iw) or (st.h == st.iO):
                if (not st.C) or (not st.c):
                    st.prime = 0
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 0
                else:
                    st.prime = 0
                    self._G()
                    self._signal()
                    st.tick_tock = True
                    st.tag = 0
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
        st.signature = True
        h_idx = st.h - (st.y + 1)
        m_local = self._M(st.h) if 0 <= h_idx < len(st.k) else 0
        n_local = self._N(st.h) if 0 <= h_idx < len(st.l) else 0
        st.last_kronecker_m = m_local
        st.last_kronecker_n = n_local
        st.last_kronecker_h = st.h
        self._last_kronecker_bar = st.h
        self._imbalance_fire_count += 1
        regime_idx = st.h - (st.y + 1)
        regime = st.Regime[regime_idx] if 0 <= regime_idx < len(st.Regime) else "Unknown"
        signal_record = {
            "timestamp": datetime.now().isoformat(),
            "type": "BUY" if st.price > st.signal else "SELL",
            "price": float(st.price),
            "signal_level": float(st.signal),
            "regime": regime,
            "m_count": int(m_local),
            "n_count": int(n_local),
            "dbz_branch": int(st.dbz_branch),
            "tick": int(st.tick),
            "h_bar": int(st.h),
        }
        st.signal_history.append(signal_record)
        if len(st.signal_history) > st.max_signal_history:
            st.signal_history = st.signal_history[-st.max_signal_history:]
        logger.info(f"🎯 SIGNAL #{self._imbalance_fire_count}: price={st.price:.5f}, tick={st.tick}, h={st.h}, m_local={m_local}, n_local={n_local}, prime={st.prime}, dime={st.dime}")

    def _on_gaurd(self, inp: int) -> bool:
        st = self.state
        if st.price > st.E and st.E != Decimal('0.0'):
            if st.signature and inp != -1:
                st.dime = 0
                st.mem = 0
            return True
        elif st.price < st.D and st.D != Decimal('0.0'):
            if st.signature and inp != -1:
                st.dime = 1
                st.mem = 1
            return True
        else:
            if st.signature and inp != -1:
                st.dime = 1
                st.mem = 1
            return False

    def _A(self, price: Decimal) -> None:
        st = self.state
        if st.v and st.lOrder_id != -1:
            logger.info(f"🔴 A(): Close long #{st.lOrder_id} at {price}")
            st.lOrder_id = -1
            st.has_open_long = False
        elif st.v and st.kOrder_id != -1:
            logger.info(f"🔴 A(): Close short #{st.kOrder_id} at {price}")
            st.kOrder_id = -1
            st.has_open_short = False
        st.E = Decimal('0.0')
        st.A = True
        st.B = False
        st.K = False
        st.Buy = -1
        st.trailing_stop_active = False
        st.trailing_stop_price = Decimal('0.0')
        st.trailing_take_profit = Decimal('0.0')

    def _B(self, price: Decimal) -> None:
        st = self.state
        if st.u and st.kOrder_id != -1:
            logger.info(f"🔵 B(): Close short #{st.kOrder_id} at {price}")
            st.kOrder_id = -1
            st.has_open_short = False
        elif st.u and st.lOrder_id != -1:
            logger.info(f"🔵 B(): Close long #{st.lOrder_id} at {price}")
            st.lOrder_id = -1
            st.has_open_long = False
        st.D = Decimal('0.0')
        st.A = False
        st.B = True
        st.K = False
        st.Sell = -1
        st.trailing_stop_active = False
        st.trailing_stop_price = Decimal('0.0')
        st.trailing_take_profit = Decimal('0.0')

    def _P(self, price: Decimal) -> None:
        st = self.state
        target = self._get_next_topological_target("BUY", price)
        if target > Decimal('0.0') and self._will_pass_spread_in_pnl(price, target, "BUY"):
            if st.Buy != -1 and (st.A or not st.B) and (st.u or not st.v):
                if st.C:
                    st.lOrder_id = 1
                    st.has_open_long = True
                    st.trailing_stop_entry = price
                    st.trailing_stop_side = "LONG"
                    st.Buy += 1
                    logger.info(f"🟢 P(): BUY executed at {price:.5f}, target={target:.5f}")
                else:
                    self._A(price)
            logger.info("⚠️ P(): BUY rejected — projected PnL <= spread friction")

    def _Q(self, price: Decimal) -> None:
        st = self.state
        target = self._get_next_topological_target("SELL", price)
        if target > Decimal('0.0') and self._will_pass_spread_in_pnl(price, target, "SELL"):
            if st.Sell != -1 and (not st.A or st.B) and (not st.u or st.v):
                if not st.C:
                    st.kOrder_id = 1
                    st.has_open_short = True
                    st.trailing_stop_entry = price
                    st.trailing_stop_side = "SHORT"
                    st.Sell += 1
                    logger.info(f"🔴 Q(): SELL executed at {price:.5f}, target={target:.5f}")
                else:
                    self._B(price)
            logger.info("⚠️ Q(): SELL rejected — projected PnL <= spread friction")

    def _S(self) -> None:
        st = self.state
        if STOP_LOSS != Decimal('0.0'):
            self._sSL = st.price + STOP_LOSS - COMMISSION
            self._bSL = st.price - STOP_LOSS + COMMISSION
        if TAKE_PROFIT != Decimal('0.0'):
            self._sTP = st.price - TAKE_PROFIT
            self._bTP = st.price + TAKE_PROFIT

    def _execute_trailing_stop(self) -> None:
        st = self.state
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
        idx = st.Z - (st.y + 1)
        if 0 <= idx < len(st.Regime):
            regime = st.Regime[idx]
            if regime in ("tStable", "tCoherent", "sStable", "sCoherent", "Stable"):
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
            logger.info(f"⚡ Trailing stop ACTIVATED at {st.trailing_stop_price:.5f}, TP={st.trailing_take_profit:.5f}, direction={st.trailing_stop_side}")
            return
        if len(self.price_history) > 0:
            last = self.price_history[-1]
            current_spread = last.ask - last.bid
        else:
            current_spread = Decimal('0.0')
        commission_abs = abs(COMMISSION)
        point_size = self._point_size if self._point_size > Decimal('0.0') else Decimal('0.00001')
        friction_points = (current_spread + commission_abs) / point_size
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
            slDistance = max(trail_step, SLIPPAGE * point_size)
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
            slDistance = max(trail_step, SLIPPAGE * point_size)
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
            logger.info(f"📈 Trailing stop updated to {st.trailing_stop_price:.5f} (PnL={pnl_points:.1f}pts, friction={friction_points:.1f}pts)")
        if has_long and st.price >= st.trailing_take_profit:
            logger.info(f"✅ TP hit (LONG) at {st.price:.5f} / TP={st.trailing_take_profit:.5f}")
            st.trailing_stop_active = False
            st.trailing_stop_price = Decimal('0.0')
            st.trailing_take_profit = Decimal('0.0')
            st.trailing_stop_entry = Decimal('0.0')
            st.trailing_stop_side = ""
            st.has_open_long = False
            st.lOrder_id = -1
        elif has_short and st.price <= st.trailing_take_profit:
            logger.info(f"✅ TP hit (SHORT) at {st.price:.5f} / TP={st.trailing_take_profit:.5f}")
            st.trailing_stop_active = False
            st.trailing_stop_price = Decimal('0.0')
            st.trailing_take_profit = Decimal('0.0')
            st.trailing_stop_entry = Decimal('0.0')
            st.trailing_stop_side = ""
            st.has_open_short = False
            st.kOrder_id = -1

    def _get_next_topological_target(self, side: str, current_price: Decimal) -> Decimal:
        st = self.state
        for ji in range(st.y + 1, X_PERIOD):
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
        friction_points = (current_spread + abs(COMMISSION)) / point_size
        projected_distance = abs(target_price - entry_price)
        projected_pnl_points = projected_distance / point_size
        safety_buffer = Decimal('1.0')
        if side == "BUY":
            if target_price <= entry_price:
                return False
            return projected_pnl_points > (friction_points + safety_buffer)
        elif side == "SELL":
            if target_price >= entry_price:
                return False
            return projected_pnl_points > (friction_points + safety_buffer)
        return False

    def _Top(self) -> None:
        st = self.state
        price_str = f"{st.price:.5f}"
        if not any(abs(p - st.price) < Decimal('0.00001') for p in st.BL):
            st.BL.append(st.price)
            st.FVG += 1
            st.bL = price_str
            logger.info(f"▲ Top(): Blue FVG line at {price_str}, FVG={st.FVG}")
            if self._bridge_publish_callback:
                try:
                    self._bridge_publish_callback("top", price_str)
                except Exception as e:
                    logger.warning(f"_bridge_publish_callback failed: {e}")

    def _Bott(self) -> None:
        st = self.state
        price_str = f"{st.price:.5f}"
        if not any(abs(p - st.price) < Decimal('0.00001') for p in st.BL):
            st.BL.append(st.price)
            st.FVG += 1
            st.bL = price_str
            logger.info(f"▼ Bott(): Red FVG line at {price_str}, FVG={st.FVG}")
            if self._bridge_publish_callback:
                try:
                    self._bridge_publish_callback("bott", price_str)
                except Exception as e:
                    logger.warning(f"_bridge_publish_callback failed: {e}")

    def _send_signal_alert(self) -> None:
        st = self.state
        target_chat = st.chat_id
        if target_chat is None and st.webapp_user_id is not None:
            target_chat = st.webapp_user_id
        if not target_chat or not self.application:
            return
        if self._last_signal_time:
            elapsed = (datetime.now() - self._last_signal_time).seconds
            if elapsed < self._signal_cooldown:
                return
        direction = "📈 BUY" if st.price > st.signal else "📉 SELL"
        m_local = st.last_kronecker_m
        n_local = st.last_kronecker_n
        h_idx = st.h - (st.y + 1)
        m_at_h = 1 if (0 <= h_idx < len(st.k) and st.k[h_idx]) else 0
        n_at_h = 1 if (0 <= h_idx < len(st.l) and st.l[h_idx]) else 0
        condition_met = (m_local >= 3) or (n_local >= 3) or (st.h > 0)
        idx = st.Z - (st.y + 1)
        regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "Unknown"
        info = self._verify_arc_length_coherence()
        if info["coherent"]:
            coherence_str = "✅ COHERENT"
        else:
            coherence_str = f"⚠️ DEVIATION: {info['deviation_float']:.6f}"
        msg = (
            f"🎯 *ÆEA SIGNAL ALERT*\n"
            f"🧭 *Direction:* {direction}\n"
            f"🎯 *Signal Level:* {st.signal:.5f}\n"
            f"💰 *Current Price:* {st.price:.5f}\n"
            f"📊 *Regime:* {regime}\n"
            f"⚖️ *Imbalance @ h={st.h}:* m={m_at_h}, n={n_at_h}\n"
            f"⚖️ *Local m/n:* {m_local}/{n_local}\n"
            f"✅ *δ(m-n-2)=1 (MQL4 gate):* {'✅ MET' if condition_met else '❌ NOT MET'}\n"
            f"🧠 *Arc-Length Coherence:* {coherence_str}\n"
            f"🔄 *Tick Count:* {st.tick}\n"
            f"💎 Natalia Tanyatia"
        )
        try:
            self.application.bot.send_message(chat_id=target_chat, text=msg, parse_mode="Markdown")
            logger.info(f"📡 Signal alert sent to {target_chat}")
            self._last_signal_time = datetime.now()
        except Exception as e:
            logger.error(f"❌ Failed to send signal alert: {e}")

    def get_signal_status(self) -> Dict[str, Any]:
        st = self.state
        h_idx = st.h - (st.y + 1)
        m_at_h = 1 if (0 <= h_idx < len(st.k) and st.k[h_idx]) else 0
        n_at_h = 1 if (0 <= h_idx < len(st.l) and st.l[h_idx]) else 0
        m_local = self._M(st.h) if st.h > 0 else 0
        n_local = self._N(st.h) if st.h > 0 else 0
        condition_met = (m_local >= 3) or (n_local >= 3) or (st.h > 0)
        info = self._verify_arc_length_coherence()
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
            "m_count": m_local,
            "n_count": n_local,
            "m_at_h": m_at_h,
            "n_at_h": n_at_h,
            "h_bar": int(st.h),
            "condition_met": condition_met,
            "regime": regime,
            "coherence": self._check_coherence(),
            "symbol": SYMBOL,
            "tick": st.tick,
            "timestamp": datetime.now().isoformat(),
            "engine_initialized": st.FG,
            "dbz_branch": info["dbz_branch"],
            "arc_sq": info["arc_sq"],
            "radius_sq": info["radius_sq"],
            "deviation": info["deviation"],
            "re_psi": info["re_psi"],
            "quat_tick_count": int(self._quat_tick_count),
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
            "X_scan": int(st.X_scan),
            "Y_scan": int(st.Y_scan),
            "q_field": {"a": str(st.q_field.a), "b": str(st.q_field.b), "c": str(st.q_field.c), "d": str(st.q_field.d)} if st.q_field else None,
            "s_squared_exact": str(st.s_squared_exact),
            "r_squared_exact": str(st.r_squared_exact),
            "deviation_exact": str(st.deviation_exact),
            "re_psi_exact": str(st.re_psi_exact),
            "market_m": int(st.last_kronecker_m),
            "market_n": int(st.last_kronecker_n),
            "market_imbalance": int(st.last_kronecker_m) - int(st.last_kronecker_n) - 2,
            "market_regime": "BULLISH" if (int(st.last_kronecker_m) - int(st.last_kronecker_n) - 2) > 2 else ("BEARISH" if (int(st.last_kronecker_m) - int(st.last_kronecker_n) - 2) < -2 else "NEUTRAL")
        }

    def _record_entry(self, side: str, price: Decimal) -> None:
        if side == "LONG":
            self.state.has_open_long = True
            self.state.trailing_stop_entry = price
            self.state.trailing_stop_side = "LONG"
        elif side == "SHORT":
            self.state.has_open_short = True
            self.state.trailing_stop_entry = price
            self.state.trailing_stop_side = "SHORT"

    def _record_exit(self, side: str) -> None:
        if side == "LONG":
            self.state.has_open_long = False
            self.state.lOrder_id = -1
        elif side == "SHORT":
            self.state.has_open_short = False
            self.state.kOrder_id = -1

    def _step_quaternion_field(self, price: Decimal, prev_price: Optional[Decimal]) -> None:
        st = self.state
        st.time_fraction = st.time_fraction + Fraction(1, 100)
        self._quat_tick_count += 1
        price_frac = Fraction.from_decimal_string(str(price))
        prev_price_frac = (
            Fraction.from_decimal_string(str(prev_price))
            if prev_price is not None and prev_price > 0
            else price_frac
        )
        delta_price = (price_frac - prev_price_frac).abs()
        price_magnitude = prev_price_frac if not prev_price_frac.is_zero() else Fraction(1)
        normalized_delta = delta_price / price_magnitude
        s_param_time = st.time_fraction * Fraction(4, 10)
        s_param = s_param_time + normalized_delta
        theta_base = s_param * Fraction(7, 10)
        theta_perturb = Fraction.sin_rational(s_param * Fraction(3, 10), 8) * Fraction(2, 10)
        theta = theta_base + theta_perturb
        phi_base = s_param * Fraction(3, 10) + Fraction(5, 10)
        phi_perturb = Fraction.cos_rational(s_param * Fraction(5, 10), 8) * Fraction(1, 10)
        phi = phi_base + phi_perturb
        half_theta = theta / Fraction(2, 1)
        half_phi = phi / Fraction(2, 1)
        q0 = Fraction.cos_rational(half_theta, 8) * Fraction.cos_rational(half_phi, 8)
        q1 = Fraction.sin_rational(half_theta, 8) * Fraction.cos_rational(half_phi, 8)
        q2 = Fraction.cos_rational(half_theta, 8) * Fraction.sin_rational(half_phi, 8)
        q3 = Fraction.sin_rational(half_theta, 8) * Fraction.sin_rational(half_phi, 8)
        base = Quat(q0, q1, q2, q3)
        q_new = base.apply_natalia_fibration(s_param, self._eps, st.time_fraction).normalize()
        if q_new.norm_sq().is_zero():
            q_new = Quat(Fraction(1, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1))
        prev_q = st.quat_history[-1]
        dq = q_new - prev_q
        dq_norm = dq.norm()
        self._s_acc_exact = self._s_acc_exact + dq_norm
        st.quat_history.append(q_new.clone())
        if len(st.quat_history) > 2000:
            tail = st.quat_history[-1500:]
            st.quat_history = [Quat(Fraction(1, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1))] + tail
        st.s_squared_exact = self._s_acc_exact * self._s_acc_exact
        st.r_squared_exact = q_new.norm_sq()
        st.deviation_exact = st.s_squared_exact - st.r_squared_exact
        st.re_psi_exact = q_new.a
        st.dbz_branch = self._apply_dbz_branch(st.deviation_exact, st.re_psi_exact)
        dev_float = st.deviation_exact.to_float()
        st.arc_coherent = (abs(dev_float) < ARC_COHERENCE_TOLERANCE)
        if self._quat_tick_count % 100 == 0:
            logger.info(f"🌀 Quat tick #{self._quat_tick_count} | s²={st.s_squared_exact} r²={st.r_squared_exact} Δ={st.deviation_exact} Re[Ψ]={st.re_psi_exact} dbz={st.dbz_branch} coherent={st.arc_coherent}")

    def _apply_dbz_branch(self, dev: Fraction, re_psi: Fraction) -> int:
        try:
            if dev.abs().to_float() < ARC_COHERENCE_TOLERANCE:
                target = Fraction(1, 100)
                diff = target - self._eps
                self._eps = self._eps + diff * Fraction(2, 1000)
                return 0
            if re_psi.sign() > 0:
                self._eps = self._eps * Fraction(97, 100)
                if self._eps.abs().to_float() < 1e-6:
                    self._eps = Fraction(1, 100)
                return 1
            else:
                delta = (
                    Fraction.sin_rational(
                        self.state.time_fraction * Fraction(5, 10) + Fraction(1, 1), 8
                    ) * Fraction(8, 10000)
                )
                self._eps = self._eps + delta
                if self._eps.to_float() > 0.05:
                    self._eps = Fraction(5, 100)
                if self._eps.to_float() < 0.001:
                    self._eps = Fraction(1, 1000)
                return 2
        except Exception as e:
            logger.exception(f"_apply_dbz_branch failed: {e}")
            return 0

    def _verify_arc_length_coherence(self) -> Dict[str, Any]:
        st = self.state
        dev_float = st.deviation_exact.to_float()
        coherent = abs(dev_float) < ARC_COHERENCE_TOLERANCE
        return {
            "coherent": bool(coherent),
            "arc_sq": str(st.s_squared_exact),
            "radius_sq": str(st.r_squared_exact),
            "deviation": str(st.deviation_exact),
            "deviation_float": dev_float,
            "dbz_branch": int(st.dbz_branch),
            "re_psi": str(st.re_psi_exact),
            "initialized": bool(st._initialized),
            "quat_tick_count": int(self._quat_tick_count),
        }

    def _check_coherence(self) -> str:
        info = self._verify_arc_length_coherence()
        if info["coherent"]:
            return "✅ COHERENT"
        else:
            return f"⚠️ DEVIATION: {info['deviation_float']:.6f}"

    def _populate_indicator_matrix(self) -> None:
        st = self.state
        if len(self.ohlcv_history) < MIN_HISTORY_WINDOW:
            return
        size = X_PERIOD - Y_START
        if size <= 0:
            return
        end = len(self.ohlcv_history)
        for j in range(Y_START + 1, X_PERIOD + 1):
            idx = j - (Y_START + 1)
            if idx < 0 or idx >= size:
                continue
            bars_back = X_PERIOD - j
            bar_end = end - bars_back
            if bar_end < MIN_HISTORY_WINDOW:
                for i in range(13):
                    if i < len(st.iA) and idx < len(st.iA[i]):
                        st.iA[i][idx] = Decimal('50.0')
                        st.cA[i][idx] = Decimal('50.0')
                        st.kA[i][idx] = Decimal('50.0')
                        st.lA[i][idx] = Decimal('50.0')
                continue
            self._normalize(j)
            self._unify(j)
            self._indicator_populate_count += 1
            if self._indicator_populate_count % 20 == 0:
                sample = [str(st.iA[i][0]) for i in range(13)]
                logger.info(f"📊 Indicator matrix populated (pass #{self._indicator_populate_count}) | col0={sample}")

    def _force_initialization(self) -> None:
        st = self.state
        if st.FG:
            return
        if st.price <= Decimal('0.0'):
            logger.warning("⏳ Cannot force-init: price not yet available")
            return
        logger.info("🚀 First valid tick detected. Forcing engine initialization...")
        if st.h <= 0:
            st.h = st.y + 1
            logger.info(f"📌 Initialized h={st.h} (anchor bar)")
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
        if len(st.l) != size:
            st.l = [False] * size
        if len(st.Premium) < X_PERIOD:
            st.Premium = [st.price] * X_PERIOD
        if len(st.Discount) < X_PERIOD:
            st.Discount = [st.price] * X_PERIOD
        if len(st.HH) < X_PERIOD:
            st.HH = [st.price] * X_PERIOD
        if len(st.LL) < X_PERIOD:
            st.LL = [st.price] * X_PERIOD
        if len(st.Regime) < X_PERIOD:
            st.Regime = ["sRange"] * X_PERIOD
        for j in range(st.y + 1, X_PERIOD):
            self._F(j, st.price, st.price)
        st.FG = True
        st._initialized = True
        logger.info(f"✅ Engine initialized on first tick at price={st.price:.5f}, h={st.h}")

    def _find_extrema_fallback(self) -> None:
        st = self.state
        if st.h > 0:
            return
        lookback = min(20, len(self.ohlcv_history))
        if lookback < 3:
            return
        max_price = Decimal('0.0')
        min_price = Decimal('999999999.0')
        max_idx = 0
        min_idx = 0
        for i in range(1, lookback + 1):
            if i > len(self.ohlcv_history):
                break
            bar = self.ohlcv_history[-i]
            high = Decimal(str(bar['high']))
            low = Decimal(str(bar['low']))
            if high > max_price:
                max_price = high
                max_idx = i
            if low < min_price:
                min_price = low
                min_idx = i
        if max_idx > 0:
            st.h = max_idx + st.y
            logger.info(f"📌 Fallback h set to {st.h} (max_price={max_price}, min_price={min_price})")

    def _on_tick(self, price_data: PriceData) -> None:
        st = self.state
        st.tick += 1
        self._tick_log_counter += 1
        if self._tick_log_counter >= 100:
            self._tick_log_counter = 0
            idx = st.Z - (st.y + 1)
            regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "?"
            logger.info(f"⚡ Tick #{st.tick}: Price={st.price:.5f}, Signal={st.signal:.5f}, FG={st.FG}, Regime={regime}, X_scan={st.X_scan}, Y_scan={st.Y_scan}, h={st.h}")
        st.price = price_data.bid
        st.Price = price_data.close
        if len(self.ohlcv_history) >= 2:
            st.iPrice = self.ohlcv_history[-2]["close"]
            st.open = self.ohlcv_history[-2]["open"]
            st.iH = self.ohlcv_history[-2]["high"]
            st.iL = self.ohlcv_history[-2]["low"]
        else:
            st.iPrice = st.price
            st.open = st.price
            st.iH = st.price
            st.iL = st.price
        if st.price <= Decimal('0.0'):
            logger.warning(f"⚠️ Tick #{st.tick} with non-positive price. Skipping state machine.")
            return
        prev_price = self._last_price_for_quat
        self._step_quaternion_field(st.price, prev_price)
        self._last_price_for_quat = st.price
        if not st.FG:
            self._force_initialization()
        if st.h <= 0:
            self._find_extrema_fallback()
        if not st.FG:
            logger.warning(f"⏳ Engine not yet initialized (FG=false) on tick #{st.tick}")
            return
        self._execute_trailing_stop()
        self._on_point()
        self._O(st.iO, st.O, st.J, "C")
        self._O(st.io, st.o, st.iJ, "c")
        self._on_call()
        self._J()
        is_now = self.ohlcv_history[-1]["timestamp"] if self.ohlcv_history else datetime.now()
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
                    j = 2
                    st.O = j
                    idx_j = j - (st.y + 1)
                    if 0 <= idx_j < len(st.Regime):
                        if is_now != st.t:
                            if self._on_fire(j, "Stable", "tRange"):
                                self._F(j, st.iH, st.iL)
                                st.Regime[idx_j] = "tRange"
                        else:
                            st.Regime[idx_j] = "sRange"
                if st.io != 2:
                    if st.iJ >= st.io:
                        j = MIN_PERIOD
                        st.o = j
                    else:
                        j = MIN_PERIOD + 1
                        st.o = j
                else:
                    j = 2
                    st.o = j
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
                    j = X_PERIOD - 1
                    st.O = j
                    idx_j = j - (st.y + 1)
                    if 0 <= idx_j < len(st.Regime):
                        if is_now != st.t:
                            if self._on_fire(j, "Stable", "tRange"):
                                self._F(j, st.iH, st.iL)
                                st.Regime[idx_j] = "tRange"
                        else:
                            st.Regime[idx_j] = "sRange"
                if st.io != 4 * MAX_PERIOD:
                    if st.iJ >= st.io:
                        j = MAX_PERIOD - 1
                        st.o = j
                    else:
                        j = MAX_PERIOD
                        st.o = j
                else:
                    j = X_PERIOD - 1
                    st.o = j
        st.t = is_now
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
        if st.signature and st.chat_id:
            self._send_signal_alert()
        if st.ab != st.ba:
            st.ab = st.ba
            st.tick_tock = False

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
        self._consecutive_zero_prices = 0
        self.update_price(bid, ask, volume, timestamp)

    def update_price(self, bid: Decimal, ask: Decimal, volume: Decimal = Decimal('0.0'), timestamp: Optional[datetime] = None) -> None:
        if timestamp is None:
            timestamp = datetime.now()
        if bid <= Decimal('0.0'):
            logger.warning(f"update_price rejected non-positive bid: {bid}")
            return
        self.state.price = bid
        self.state.Price = (bid + ask) / Decimal('2.0')
        self._price_update_counter += 1
        price_data = PriceData(
            bid=bid, ask=ask, close=(bid + ask) / Decimal('2.0'),
            open=bid, high=max(bid, ask), low=min(bid, ask),
            volume=volume, timestamp=timestamp,
        )
        self.price_history.append(price_data)
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]
        if self._last_price_update is None or (timestamp - self._last_price_update).seconds >= 60:
            self._bar_open = True
            self._last_price_update = timestamp
            self._bar_index += 1
            self.ohlcv_history.append({
                "open": price_data.open, "high": price_data.high,
                "low": price_data.low, "close": price_data.close,
                "volume": price_data.volume, "timestamp": timestamp,
            })
            if len(self.ohlcv_history) > 200:
                self.ohlcv_history = self.ohlcv_history[-200:]
        else:
            self._bar_open = False
            if self.ohlcv_history:
                self.ohlcv_history[-1]["high"] = max(self.ohlcv_history[-1]["high"], price_data.high)
                self.ohlcv_history[-1]["low"] = min(self.ohlcv_history[-1]["low"], price_data.low)
                self.ohlcv_history[-1]["close"] = price_data.close
                self.ohlcv_history[-1]["volume"] += price_data.volume
        if self._bar_open and len(self.ohlcv_history) >= MIN_HISTORY_WINDOW:
            self._populate_indicator_matrix()
        self._on_tick(price_data)

# ============================================================================
# BRIDGE STATE
# ============================================================================
class BridgeState:
    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot: Dict[str, Any] = {
            "symbol": SYMBOL, "price": "0.0", "ask": "0.0", "bid": "0.0",
            "signal": "0.0", "regime": "Unknown", "tick": 0,
            "m_count": 0, "n_count": 0, "coherent": False,
            "arc_sq": "0", "radius_sq": "0", "deviation": "0",
            "timestamp": datetime.now().isoformat(), "endpoint": None,
            "webapp_user_id": None, "webapp_username": None,
            "last_price_update": None, "engine_initialized": False,
            "consecutive_zero_prices": 0, "dbz_branch": 0, "re_psi": "0",
            "relay_url": RELAY_URL, "relay_healthy": True,
            "indicator_populate_count": 0, "imbalance_fire_count": 0,
            "trailing_stop_active": False, "trailing_stop_price": "0.0",
            "trailing_take_profit": "0.0", "trailing_stop_entry": "0.0",
            "trailing_stop_side": "", "has_open_long": False, "has_open_short": False,
            "lOrder_id": -1, "kOrder_id": -1, "KC": True, "prime": -1,
            "dime": -1, "mem": -1, "tag": -1, "invert": True,
            "m_at_h": 0, "n_at_h": 0, "h_bar": 0,
            "on_track_runs": 0, "on_stand_runs": 0,
            "last_kronecker_bar": -1, "last_kronecker_m": 0,
            "last_kronecker_n": 0, "last_kronecker_h": -1,
            "X_scan": Y_START, "Y_scan": Y_START, "quat_tick_count": 0,
            "q_field": None, "s_squared_exact": "0", "r_squared_exact": "1",
            "deviation_exact": "0", "re_psi_exact": "1",
            "quat_history_sample": [],
            "market_m": 0, "market_n": 0, "market_imbalance": -2, "market_regime": "NEUTRAL"
        }
        self._fvgs: Dict[int, Dict[str, Any]] = {}
        self._next_fvg_idx = 0
        self._webapp_sessions: Dict[int, Dict[str, Any]] = {}
        self._handshake_lock = threading.Lock()

    def publish(self, snapshot: Dict[str, Any]) -> None:
        with self._lock:
            if "price" in snapshot and snapshot["price"] != "0.0":
                snapshot["last_price_update"] = datetime.now().isoformat()
            self._snapshot = dict(snapshot)
            if snapshot.get("tick", 0) % 50 == 0:
                logger.info(f"🌉 BRIDGE_SNAPSHOT: price={snapshot.get('price')} tick={snapshot.get('tick')} "
                            f"quat_a={snapshot.get('q_field', {}).get('a', 'N/A') if isinstance(snapshot.get('q_field'), dict) else 'N/A'} "
                            f"s2={snapshot.get('s_squared_exact')} r2={snapshot.get('r_squared_exact')} "
                            f"dev={snapshot.get('deviation_exact')} dbz={snapshot.get('dbz_branch')} "
                            f"relay_healthy={snapshot.get('relay_healthy')}")

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    def register_webapp_session(self, user_id: int, username: Optional[str], chat_id: Optional[int] = None) -> bool:
        with self._handshake_lock:
            self._webapp_sessions[user_id] = {
                "user_id": user_id, "username": username, "chat_id": chat_id,
                "first_seen": self._webapp_sessions.get(user_id, {}).get("first_seen", datetime.now().isoformat()),
                "last_seen": datetime.now().isoformat(),
            }
        with self._lock:
            self._snapshot["webapp_user_id"] = user_id
            self._snapshot["webapp_username"] = username
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
        logger.info(f"🤝 Web App session registered: user_id={user_id}, username={username}")
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
                idx = self._next_fvg_idx
                self._next_fvg_idx += 1
            self._fvgs[idx] = {
                "type": fvg_type, "price": str(price_dec), "idx": idx,
                "created": datetime.now().isoformat(), "user_id": user_id,
            }
        engine = BRIDGE_ENGINE_REF.get("engine")
        if engine is not None:
            st = engine.state
            target_len = len(st.Premium)
            if target_len > 0:
                target_idx = idx % target_len
                if fvg_type == "top":
                    st.Premium[target_idx] = price_dec
                else:
                    st.Discount[target_idx] = price_dec
            st.fvg_anchor_map[idx] = {
                "idx": idx, "type": fvg_type, "price": str(price_dec),
                "created": datetime.now().isoformat(),
            }
        return idx

    def remove_fvg(self, idx: int) -> bool:
        with self._lock:
            if idx in self._fvgs:
                del self._fvgs[idx]
        engine = BRIDGE_ENGINE_REF.get("engine")
        if engine is not None:
            engine.state.fvg_anchor_map.pop(idx, None)
        return True

    def list_fvgs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._fvgs.values())

BRIDGE_STATE = BridgeState()
BRIDGE_ENGINE_REF: Dict[str, Any] = {"engine": None, "bot": None, "public_url": None}

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
    server_version = "AEI-Bridge/2.3"

    def log_message(self, fmt, *args):
        return

    def _set_cors(self) -> None:
        origin = CORS_ORIGIN
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Telegram-Init-Data, X-Relay-Key")
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

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            snap = BRIDGE_STATE.get_snapshot()
            last = snap.get("last_price_update")
            stale = True
            age_seconds = None
            if last:
                try:
                    last_dt = datetime.fromisoformat(last)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                    age_seconds = (datetime.now().astimezone() - last_dt).total_seconds()
                    stale = age_seconds > 60
                except Exception:
                    pass
            self._send_json(200, {
                "ok": not stale, "service": "aei-bridge", "last_price_update": last,
                "age_seconds": age_seconds, "stale": stale,
                "engine_initialized": snap.get("engine_initialized", False),
                "coherent": snap.get("coherent", False),
                "dbz_branch": snap.get("dbz_branch", 0),
                "indicator_populate_count": snap.get("indicator_populate_count", 0),
                "imbalance_fire_count": snap.get("imbalance_fire_count", 0),
                "trailing_stop_active": snap.get("trailing_stop_active", False),
                "trailing_stop_price": snap.get("trailing_stop_price", "0.0"),
                "trailing_take_profit": snap.get("trailing_take_profit", "0.0"),
                "trailing_stop_entry": snap.get("trailing_stop_entry", "0.0"),
                "trailing_stop_side": snap.get("trailing_stop_side", ""),
                "has_open_long": snap.get("has_open_long", False),
                "has_open_short": snap.get("has_open_short", False),
                "KC": snap.get("KC", True), "prime": snap.get("prime", -1),
                "dime": snap.get("dime", -1), "mem": snap.get("mem", -1),
                "tag": snap.get("tag", -1), "on_track_runs": snap.get("on_track_runs", 0),
                "on_stand_runs": snap.get("on_stand_runs", 0),
                "last_kronecker_bar": snap.get("last_kronecker_bar", -1),
                "last_kronecker_m": snap.get("last_kronecker_m", 0),
                "last_kronecker_n": snap.get("last_kronecker_n", 0),
                "last_kronecker_h": snap.get("last_kronecker_h", -1),
                "X_scan": snap.get("X_scan", Y_START), "Y_scan": snap.get("Y_scan", Y_START),
                "relay_healthy": snap.get("relay_healthy", True),
            })
            return
        if path == "/config":
            self._send_json(200, {
                "public_url": BRIDGE_ENGINE_REF.get("public_url"), "tls": BRIDGE_USE_TLS,
                "port": BRIDGE_PORT, "host": BRIDGE_HOST, "symbol": SYMBOL,
                "webapp_enabled": True, "cors_origin": CORS_ORIGIN,
                "relay_url": RELAY_URL, "relay_gated": bool(RELAY_KEY),
                "x_period_constant": X_PERIOD, "y_start_constant": Y_START,
            })
            return
        if path == "/state":
            snap = BRIDGE_STATE.get_snapshot()
            public = BRIDGE_ENGINE_REF.get("public_url")
            if public:
                snap["endpoint"] = public
            else:
                host = self.headers.get("Host", f"{BRIDGE_HOST}:{BRIDGE_PORT}")
                scheme = "https" if BRIDGE_USE_TLS else "http"
                snap["endpoint"] = f"{scheme}://{host}"
            snap["relay_url"] = RELAY_URL
            self._send_json(200, snap)
            return
        if path == "/miniapp-state":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            st = engine.state
            q = st.q_field
            quat_history_sample = []
            for qh in st.quat_history[-64:]:
                quat_history_sample.append({
                    "a": str(qh.a), "b": str(qh.b), "c": str(qh.c), "d": str(qh.d)
                })
            idx = st.Z - (st.y + 1)
            regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "Unknown"
            payload = {
                "symbol": SYMBOL,
                "price": str(st.price),
                "regime": regime,
                "coherence": "COHERENT" if st.arc_coherent else "EVOLVING",
                "dbz_branch": int(st.dbz_branch),
                "q_field": {"a": str(q.a), "b": str(q.b), "c": str(q.c), "d": str(q.d)} if q else None,
                "s_squared_exact": str(st.s_squared_exact),
                "r_squared_exact": str(st.r_squared_exact),
                "deviation_exact": str(st.deviation_exact),
                "re_psi_exact": str(st.re_psi_exact),
                "quat_history": quat_history_sample,
                "tick": int(st.tick),
                "generation": 0,
                "market_m": int(st.last_kronecker_m),
                "market_n": int(st.last_kronecker_n),
                "market_imbalance": int(st.last_kronecker_m) - int(st.last_kronecker_n) - 2,
                "market_regime": "BULLISH" if (int(st.last_kronecker_m) - int(st.last_kronecker_n) - 2) > 2 else ("BEARISH" if (int(st.last_kronecker_m) - int(st.last_kronecker_n) - 2) < -2 else "NEUTRAL"),
                "last_price_update": datetime.now().isoformat(),
                "relay_healthy": (engine.feed._failure_count < 3),
                "X_PERIOD": X_PERIOD,
                "Y_START": Y_START,
                "fvg_anchors": [
                    {"idx": idx, "type": "top", "price": str(p)}
                    for idx, p in enumerate(st.Premium) if p > Decimal('0.0')
                ] + [
                    {"idx": idx, "type": "bottom", "price": str(p)}
                    for idx, p in enumerate(st.Discount) if p > Decimal('0.0')
                ],
                "recent_signals": st.signal_history[-20:],
                "ohlcv_count": len(engine.ohlcv_history) if engine else 0,
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
                limit = int(self.headers.get("X-Limit", "200"))
            except Exception:
                pass
            bars = engine.ohlcv_history[-limit:]
            ohlcv_data = []
            for bar in bars:
                ts = bar["timestamp"]
                if isinstance(ts, datetime):
                    ts_str = ts.isoformat()
                else:
                    ts_str = str(ts)
                ohlcv_data.append({
                    "timestamp": ts_str,
                    "open": float(bar["open"]),
                    "high": float(bar["high"]),
                    "low": float(bar["low"]),
                    "close": float(bar["close"]),
                    "volume": float(bar.get("volume", 0)),
                })
            self._send_json(200, {"symbol": SYMBOL, "bars": ohlcv_data, "count": len(ohlcv_data)})
            return
        if path == "/signals":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            limit = 50
            try:
                limit = int(self.headers.get("X-Limit", "50"))
            except Exception:
                pass
            signals = engine.state.signal_history[-limit:]
            self._send_json(200, {"symbol": SYMBOL, "signals": signals, "count": len(signals)})
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
                probe_data["arc_length"] = engine._verify_arc_length_coherence()
                probe_data["signal_status"] = engine.get_signal_status()
                probe_data["relay_healthy"] = (engine.feed._failure_count < 3)
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
                diag["arc_length"] = engine._verify_arc_length_coherence()
                diag["quat_history_depth"] = len(engine.state.quat_history)
                diag["ohlcv_history_depth"] = len(engine.ohlcv_history)
                diag["indicator_sample_col0"] = [str(engine.state.iA[i][0]) for i in range(13)]
                diag["indicator_sample_col1"] = [str(engine.state.iA[i][1]) for i in range(13)] if len(engine.state.iA[0]) > 1 else []
                diag["x_period_constant"] = X_PERIOD
                diag["y_start_constant"] = Y_START
                diag["consecutive_zero_prices"] = engine._consecutive_zero_prices
                diag["relay_healthy"] = (engine.feed._failure_count < 3)
                self._send_json(200, diag)
            except Exception as e:
                self._send_json(500, {"error": "diagnostics_failed", "detail": str(e)})
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
                raw = self._read_body()
                data = json.loads(raw.decode("utf-8")) if raw else {}
                init_data = data.get("initData", "").strip()
                chat_id = data.get("chat_id")
                if not init_data:
                    self._send_json(400, {"error": "missing_init_data"})
                    return
                verified = verify_telegram_init_data(init_data, TELEGRAM_BOT_TOKEN_ENV)
                if not verified or not verified.get("user"):
                    logger.warning("🚫 Handshake rejected: initData verification failed")
                    self._send_json(403, {"error": "invalid_init_data"})
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
        if path == "/fvg":
            user_id, username, verified = _extract_auth_headers(self)
            try:
                raw = self._read_body()
                data = json.loads(raw.decode("utf-8")) if raw else {}
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
                logger.info(f"📌 FVG committed: type={fvg_type} price={price_label} idx={idx} verified={verified} user={username}")
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
                logger.info("🔄 Manual reset requested via /reset")
                self._send_json(200, {"ok": True, "active_symbol": engine.feed.active_symbol()})
            except Exception as e:
                logger.error(f"/reset error: {e}")
                self._send_json(500, {"error": "internal", "detail": str(e)})
            return
        self._send_json(404, {"error": "not_found", "path": path})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
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
    original_on_tick = engine._on_tick

    def wrapped_on_tick(price_data: PriceData) -> None:
        original_on_tick(price_data)
        try:
            st = engine.state
            idx = st.Z - (st.y + 1)
            regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "Unknown"
            info = engine._verify_arc_length_coherence()
            h_idx = st.h - (st.y + 1)
            m_at_h = 1 if (0 <= h_idx < len(st.k) and st.k[h_idx]) else 0
            n_at_h = 1 if (0 <= h_idx < len(st.l) and st.l[h_idx]) else 0
            q = st.q_field
            q_dict = None
            if q:
                q_dict = {"a": str(q.a), "b": str(q.b), "c": str(q.c), "d": str(q.d)}
            quat_sample = []
            for qh in st.quat_history[-16:]:
                quat_sample.append({"a": str(qh.a), "b": str(qh.b), "c": str(qh.c), "d": str(qh.d)})
            market_m = int(st.last_kronecker_m)
            market_n = int(st.last_kronecker_n)
            market_imbalance = market_m - market_n - 2
            if market_imbalance > 2:
                market_regime = "BULLISH"
            elif market_imbalance < -2:
                market_regime = "BEARISH"
            else:
                market_regime = "NEUTRAL"
            snapshot = {
                "symbol": SYMBOL, "price": str(st.price),
                "bid": str(price_data.bid), "ask": str(price_data.ask),
                "signal": str(st.signal), "regime": regime,
                "tick": int(st.tick),
                "m_count": market_m, "n_count": market_n,
                "m_at_h": int(m_at_h), "n_at_h": int(n_at_h), "h_bar": int(st.h),
                "coherent": bool(info["coherent"]),
                "arc_sq": str(info["arc_sq"]), "radius_sq": str(info["radius_sq"]),
                "deviation": str(info["deviation"]),
                "dbz_branch": int(info["dbz_branch"]), "re_psi": str(info["re_psi"]),
                "timestamp": datetime.now().isoformat(),
                "endpoint": BRIDGE_ENGINE_REF.get("public_url"),
                "webapp_user_id": st.webapp_user_id, "webapp_username": st.webapp_username,
                "last_price_update": datetime.now().isoformat(),
                "engine_initialized": bool(st.FG),
                "consecutive_zero_prices": int(getattr(engine, "_consecutive_zero_prices", 0)),
                "relay_url": RELAY_URL,
                "relay_healthy": (engine.feed._failure_count < 3),
                "indicator_populate_count": int(engine._indicator_populate_count),
                "imbalance_fire_count": int(engine._imbalance_fire_count),
                "quat_tick_count": int(engine._quat_tick_count),
                "trailing_stop_active": bool(st.trailing_stop_active),
                "trailing_stop_price": str(st.trailing_stop_price),
                "trailing_take_profit": str(st.trailing_take_profit),
                "trailing_stop_entry": str(st.trailing_stop_entry),
                "trailing_stop_side": st.trailing_stop_side,
                "has_open_long": bool(st.has_open_long),
                "has_open_short": bool(st.has_open_short),
                "lOrder_id": int(st.lOrder_id), "kOrder_id": int(st.kOrder_id),
                "KC": bool(st.KC), "prime": int(st.prime),
                "dime": int(st.dime), "mem": int(st.mem), "tag": int(st.tag),
                "invert": bool(st.invert),
                "on_track_runs": int(st.on_track_runs),
                "on_stand_runs": int(st.on_stand_runs),
                "last_kronecker_bar": int(engine._last_kronecker_bar),
                "last_kronecker_m": int(st.last_kronecker_m),
                "last_kronecker_n": int(st.last_kronecker_n),
                "last_kronecker_h": int(st.last_kronecker_h),
                "X_scan": int(st.X_scan), "Y_scan": int(st.Y_scan),
                "q_field": q_dict,
                "s_squared_exact": str(st.s_squared_exact),
                "r_squared_exact": str(st.r_squared_exact),
                "deviation_exact": str(st.deviation_exact),
                "re_psi_exact": str(st.re_psi_exact),
                "quat_history_sample": quat_sample,
                "market_m": market_m,
                "market_n": market_n,
                "market_imbalance": market_imbalance,
                "market_regime": market_regime
            }
            BRIDGE_STATE.publish(snapshot)
        except Exception as e:
            logger.warning(f"Bridge publish failed: {e}")

    engine._on_tick = wrapped_on_tick
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

    def _resolve_webapp_url(self) -> Optional[str]:
        return TELEGRAM_WEBAPP_URL or BRIDGE_ENGINE_REF.get("public_url")

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
                logger.info(f"📊 itr#{iteration} price={st.price} tick={st.tick} FG={st.FG} regime={regime} X_scan={st.X_scan} Y_scan={st.Y_scan} OnTrack={st.on_track_runs} OnStand={st.on_stand_runs} m/n={st.last_kronecker_m}/{st.last_kronecker_n} ind_pass={self.engine._indicator_populate_count} sig_fire={self.engine._imbalance_fire_count} h={st.h}")
            except Exception:
                logger.exception(f"❌ Feed iteration #{iteration} failed")
            await asyncio.sleep(UPDATE_INTERVAL)
        logger.info("🔄 Price feed loop exited")

    def _build_main_keyboard(self) -> InlineKeyboardMarkup:
        webapp_url = self._resolve_webapp_url()
        rows = [
            [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("🎯 Signal", callback_data="signal")],
            [InlineKeyboardButton("📊 Regime", callback_data="regime"), InlineKeyboardButton("🔬 Indicators", callback_data="indicators")],
            [InlineKeyboardButton("🔄 Start Feed", callback_data="start_feed"), InlineKeyboardButton("⏹️ Stop Feed", callback_data="stop_feed")],
            [InlineKeyboardButton("📈 Info", callback_data="info"), InlineKeyboardButton("🔄 Reset", callback_data="reset")],
            [InlineKeyboardButton("🔬 Probe Relay", callback_data="probe"), InlineKeyboardButton("♻️ Rebuild Relay", callback_data="rebuild_yf")],
            [InlineKeyboardButton("🧬 Arc-Length", callback_data="arclen"), InlineKeyboardButton("🌿 DbZ", callback_data="dbz")],
            [InlineKeyboardButton("🔍 Diagnostics", callback_data="diagnostics")],
            [InlineKeyboardButton("📊 Chart", callback_data="chart")],
        ]
        if webapp_url:
            rows.append([InlineKeyboardButton("⚡ Open ÆEA Mini App", web_app=WebAppInfo(url=webapp_url))])
        else:
            rows.append([InlineKeyboardButton("⏳ Mini App (tunnel pending…)", callback_data="webapp_pending")])
        return InlineKeyboardMarkup(rows)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        self.engine.state.chat_id = chat_id
        self.engine.application = self.application
        engine_status = "✅ Initialized" if self.engine.state.FG else "⏳ Waiting for data"
        feed_status = "Active" if self._running else "Inactive"
        arclen_info = self.engine._verify_arc_length_coherence()
        coherent_mark = "✅" if arclen_info["coherent"] else "⚠️"
        welcome = (
            "🔷 *ÆEA Quantum-Financial Topology Bot*\n"
            "Welcome to @UpscaleTradeBot. This bot implements the Non-Hermitian\n"
            "Stochastic Geometry of Supply-Demand Imbalance.\n"
            "📊 *Available Commands:*\n"
            "`/status` - Current market state & regime\n"
            "`/regime` - Detailed regime classification\n"
            "`/signal` - Current trading signal\n"
            "`/indicators` - 13D Hilbert Space projection\n"
            "`/fvg` - Fair Value Gap tracking\n"
            "`/chart` - Recent signals summary\n"
            "`/arclen` - Arc-length & DbZ state\n"
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
            "`/help` - Show this message\n"
            f"*Current Symbol:* `{SYMBOL}`\n"
            f"🔄 *Feed Status:* {feed_status}\n"
            f"🧠 *Engine Status:* {engine_status}\n"
            f"🌿 *DbZ Branch:* {arclen_info['dbz_branch']}  |  *Coherent:* {coherent_mark}\n"
            "💎 Natalia Tanyatia"
        )
        await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=self._build_main_keyboard())

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.start(update, context)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            logger.info("⚠️ Engine not initialized, attempting to force...")
            self.engine._force_initialization()
            if self.engine.state.h <= 0:
                self.engine._find_extrema_fallback()
            if not self.engine.state.FG:
                await update.message.reply_text("⏳ *Engine not initialized*\nThe engine will initialize on the first price tick after starting the feed.\nPlease use `/start_feed` to start the price feed.\nIf the feed is already running, try `/reset` to reinitialize.", parse_mode="Markdown")
                return
        state = self.engine.state
        idx = state.Z - (state.y + 1)
        regime = state.Regime[idx] if 0 <= idx < len(state.Regime) and state.Regime[idx] else "Unknown"
        bid, ask = self.engine.feed.get_current_price()
        price_display = f"{bid:.5f}" if bid > Decimal('0.0') else f"{state.price:.5f}"
        info = self.engine._verify_arc_length_coherence()
        coherence_line = "✅ COHERENT" if info["coherent"] else f"⚠️ DEV: {info['deviation_float']:.6f}"
        feed_mark = "✅" if self._running else "⏹️"
        init_mark = "✅ Initialized" if state.FG else "⏳ Initializing"
        m_local = state.last_kronecker_m if state.last_kronecker_m else 0
        n_local = state.last_kronecker_n if state.last_kronecker_n else 0
        h_idx = state.h - (state.y + 1)
        m_at_h = 1 if (0 <= h_idx < len(state.k) and state.k[h_idx]) else 0
        n_at_h = 1 if (0 <= h_idx < len(state.l) and state.l[h_idx]) else 0
        trail_status = "🟢 Active" if state.trailing_stop_active else "⚪ Inactive"
        order_presence = []
        if state.has_open_long:
            order_presence.append(f"LONG(id={state.lOrder_id})")
        if state.has_open_short:
            order_presence.append(f"SHORT(id={state.kOrder_id})")
        order_str = ", ".join(order_presence) if order_presence else "none"
        response = (
            "🔷 *ÆEA STATUS*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"💰 *Price:* {price_display}\n"
            f"📊 *Regime:* {regime}\n"
            f"🧠 *Coherence:* {coherence_line}\n"
            f"🌿 *DbZ Branch:* {info['dbz_branch']}\n"
            f"🎯 *Signal Level:* {state.signal:.5f}\n"
            f"📋 *Signature:* {'Active' if state.signature else 'Idle'}\n"
            f"🔄 *Tick:* {state.tick}\n"
            f"🧠 *Engine State:* {init_mark}\n"
            f"⚖️ *Imbalance @ h={state.h}:* m={m_at_h}, n={n_at_h}\n"
            f"⚖️ *Local m/n:* {m_local}/{n_local}\n"
            f"📈 *Indicator Passes:* {self.engine._indicator_populate_count}\n"
            f"📡 *Signal Fires:* {self.engine._imbalance_fire_count}\n"
            f"📡 *Feed Active:* {feed_mark}\n"
            f"🔀 *KC:* {state.KC}  |  *Prime:* {state.prime}  |  *Dime:* {state.dime}\n"
            f"🔀 *Invert:* {state.invert}  |  *Mem:* {state.mem}  |  *Tag:* {state.tag}\n"
            f"📊 *Orders:* {order_str}\n"
            f"🛑 *Trailing Stop:* {trail_status} ({state.trailing_stop_price:.5f} / {state.trailing_take_profit:.5f})\n"
            f"🎯 *Trailing Side:* {state.trailing_stop_side or '—'}  |  *Entry:* {state.trailing_stop_entry:.5f}\n"
            f"🔍 *OnTrack Runs:* {state.on_track_runs}  |  *OnStand Runs:* {state.on_stand_runs}\n"
            f"🎯 *Last Kronecker Bar:* {self.engine._last_kronecker_bar}\n"
            f"🔢 *X_scan:* {state.X_scan}  |  *Y_scan:* {state.Y_scan}  |  *X_PERIOD:* {X_PERIOD}"
        )
        reply_markup = self._build_main_keyboard()
        if update.callback_query:
            await update.callback_query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)

    async def arclen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        state = self.engine.state
        info = self.engine._verify_arc_length_coherence()
        q = state.q_field
        qstr = f"({q.a}, {q.b}, {q.c}, {q.d})" if q is not None else "—"
        response = (
            "🧮 *EXACT ARC-LENGTH STATE*\n"
            f"🧮 *s² (ℚ-exact)* = `{info['arc_sq']}`\n"
            f"🧮 *r² (ℚ-exact)* = `{info['radius_sq']}`\n"
            f"🧮 *Δ = s² − r²* = `{info['deviation']}`\n"
            f"🧮 *Δ (float)* = {info['deviation_float']:.10e}\n"
            f"🌿 *DbZ Branch:* {info['dbz_branch']}\n"
            f"   • 0 = coherent (no action)\n"
            f"   • 1 = critical-line projection (Re[Ψ] > 0)\n"
            f"   • 2 = Natalia fibration (Re[Ψ] ≤ 0)\n"
            f"🌀 *Re[Ψ]* = `{info['re_psi']}`\n"
            f"🌀 *Current Φ* = `{qstr}`\n"
            f"🔷 *FVG anchors:* {len(state.fvg_anchor_map)}"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(response, parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")

    async def dbz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        state = self.engine.state
        info = self.engine._verify_arc_length_coherence()
        eps = self.engine._eps
        branch_names = {0: "COHERENT", 1: "CRITICAL-LINE (Branch A)", 2: "NATALIA (Branch B)"}
        response = (
            "🌿 *DECIDING-BY-ZERO (DbZ) STATE*\n"
            f"🌿 *Current Branch:* {info['dbz_branch']} — {branch_names.get(info['dbz_branch'], 'UNKNOWN')}\n"
            f"🌀 *ε (fibration parameter):* `{eps}`\n"
            f"💠 *ε as float:* {eps.to_float():.10f}\n"
            f"🌀 *Re[Ψ] =* `{info['re_psi']}`\n"
            f"🌀 *Δ (deviation) =* `{info['deviation']}`\n"
            "*Branch semantics:*\n"
            "• Re[Ψ] > 0 → project to critical line Re(s)=½\n"
            "• Re[Ψ] ≤ 0 → apply Natalia fibration ε perturbation\n"
            "• Δ ≈ 0 → relax ε toward baseline 1/100"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(response, parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")

    async def diagnostics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status = self.engine.get_signal_status()
        response = (
            "🔬 *ENGINE DIAGNOSTICS*\n"
            f"🔄 *Tick:* {status.get('tick')}\n"
            f"🧮 *Indicator Populates:* {status.get('indicator_populate_count')}\n"
            f"📡 *Signal Fires:* {status.get('imbalance_fire_count')}\n"
            f"⚖️ *Local m / n:* {status.get('m_count')} / {status.get('n_count')}\n"
            f"⚖️ *m / n (@h={status.get('h_bar')}):* {status.get('m_at_h')} / {status.get('n_at_h')}\n"
            f"🧮 *Arc s² =* `{status.get('arc_sq')}`\n"
            f"🧮 *Rad r² =* `{status.get('radius_sq')}`\n"
            f"🧮 *Δ =* `{status.get('deviation')}`\n"
            f"🌀 *Re[Ψ] =* `{status.get('re_psi')}`\n"
            f"🎯 *Signal:* {status.get('signal'):.5f}\n"
            f"📊 *Regime:* {status.get('regime')}\n"
            f"🔀 *KC:* {status.get('KC')}  |  *Prime:* {status.get('prime')}  |  *Dime:* {status.get('dime')}\n"
            f"🔀 *Invert:* {status.get('invert')}  |  *Mem:* {status.get('mem')}  |  *Tag:* {status.get('tag')}\n"
            f"📈 *Trailing Stop Active:* {status.get('trailing_stop_active')}\n"
            f"📈 *Trailing Stop Price:* {status.get('trailing_stop_price')}\n"
            f"📈 *Trailing Take Profit:* {status.get('trailing_take_profit')}\n"
            f"📍 *Trailing Entry:* {status.get('trailing_stop_entry')}  |  *Side:* {status.get('trailing_stop_side')}\n"
            f"📊 *Has Long:* {status.get('has_open_long')}  |  *Has Short:* {status.get('has_open_short')}\n"
            f"📊 *lOrder_id:* {status.get('lOrder_id')}  |  *kOrder_id:* {status.get('kOrder_id')}\n"
            f"🔍 *OnTrack Runs:* {status.get('on_track_runs')}  |  *OnStand Runs:* {status.get('on_stand_runs')}\n"
            f"🎯 *Last Kronecker Bar:* {status.get('last_kronecker_bar')}\n"
            f"🔢 *Last Kronecker m/n/h:* {status.get('last_kronecker_m')}/{status.get('last_kronecker_n')}/{status.get('last_kronecker_h')}\n"
            f"🔢 *X_PERIOD (const):* {X_PERIOD}  |  *Y_START (const):* {Y_START}"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(response, parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")

    async def regime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            self.engine._force_initialization()
            if self.engine.state.h <= 0:
                self.engine._find_extrema_fallback()
            if not self.engine.state.FG:
                await update.message.reply_text("⏳ *Engine not initialized*\nPlease use `/start_feed`.", parse_mode="Markdown")
                return
        state = self.engine.state
        y = state.y
        idx = state.Z - y - 1
        current = state.Regime[idx] if 0 <= idx < len(state.Regime) and state.Regime[idx] else "Unknown"
        premium = state.Premium[idx] if 0 <= idx < len(state.Premium) else Decimal('0.0')
        discount = state.Discount[idx] if 0 <= idx < len(state.Discount) else Decimal('0.0')
        hh = state.HH[idx] if 0 <= idx < len(state.HH) else Decimal('0.0')
        ll = state.LL[idx] if 0 <= idx < len(state.LL) else Decimal('0.0')
        m_local = state.last_kronecker_m if state.last_kronecker_m else 0
        n_local = state.last_kronecker_n if state.last_kronecker_n else 0
        imbalance_status = "✅ TRIGGER" if (m_local >= 12 or n_local >= 12) else "⏳ WAITING"
        response = (
            "📊 *REGIME CLASSIFICATION*\n"
            f"🔹 *Current Regime:* {current}\n"
            f"🔹 *Premium:* {premium:.5f}\n"
            f"🔸 *Discount:* {discount:.5f}\n"
            f"📈 *HH:* {hh:.5f}\n"
            f"📉 *LL:* {ll:.5f}\n"
            f"🟢 *Local m:* {m_local}\n"
            f"🔴 *Local n:* {n_local}\n"
            f"⚖️ *Imbalance Condition:* {imbalance_status}"
        )
        reply_markup = self._build_main_keyboard()
        if update.callback_query:
            await update.callback_query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)

    async def signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            self.engine._force_initialization()
            if self.engine.state.h <= 0:
                self.engine._find_extrema_fallback()
            if not self.engine.state.FG:
                await update.message.reply_text("⏳ *Engine not initialized*\nPlease use `/start_feed`.", parse_mode="Markdown")
                return
        state = self.engine.state
        if state.signal == Decimal('0.0'):
            direction = "⚪ NEUTRAL"
            confidence = "N/A"
        elif state.price > state.signal:
            direction = "📈 BUY"
            confidence = f"{((state.price - state.signal) / state.signal * Decimal('100')):.2f}%" if state.signal != Decimal('0.0') else "0%"
        else:
            direction = "🔴 SELL"
            confidence = f"{((state.signal - state.price) / state.signal * Decimal('100')):.2f}%" if state.signal != Decimal('0.0') else "0%"
        m_local = state.last_kronecker_m if state.last_kronecker_m else 0
        n_local = state.last_kronecker_n if state.last_kronecker_n else 0
        h_idx = state.h - (state.y + 1)
        m_at_h = 1 if (0 <= h_idx < len(state.k) and state.k[h_idx]) else 0
        n_at_h = 1 if (0 <= h_idx < len(state.l) and state.l[h_idx]) else 0
        condition_met = (m_local >= 12) or (n_local >= 12)
        info = self.engine._verify_arc_length_coherence()
        condition_mark = "✅ MET" if condition_met else "❌ NOT MET"
        response = (
            "🎯 *TRADING SIGNAL*\n"
            f"📊 *Direction:* {direction}\n"
            f"📈 *Confidence:* {confidence}\n"
            f"🎯 *Signal Level:* {state.signal:.5f}\n"
            f"💰 *Current Price:* {state.price:.5f}\n"
            f"⚖️ *Imbalance @ h={state.h}:* m={m_at_h}, n={n_at_h}\n"
            f"⚖️ *Local m/n:* {m_local}/{n_local}\n"
            f"✅ *δ(m-n-2)=1 (MQL4 gate):* {condition_mark}\n"
            f"🌿 *DbZ Branch:* {info['dbz_branch']}\n"
            f"🔀 *KC State:* {state.KC}\n"
            f"🔢 *Prime:* {state.prime}\n"
            f"🔢 *Dime:* {state.dime}\n"
            f"🔄 *Tick Count:* {state.tick}\n"
            f"📈 *Trailing Stop:* {'Active' if state.trailing_stop_active else 'Inactive'}\n"
            f"🎯 *Last Kronecker Bar:* {self.engine._last_kronecker_bar}"
        )
        reply_markup = self._build_main_keyboard()
        if update.callback_query:
            await update.callback_query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)

    async def indicators(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            self.engine._force_initialization()
            if self.engine.state.h <= 0:
                self.engine._find_extrema_fallback()
            if not self.engine.state.FG:
                await update.message.reply_text("⏳ *Engine not initialized*\nPlease use `/start_feed`.", parse_mode="Markdown")
                return
        state = self.engine.state
        y = state.y
        idx = state.Z - y - 1
        if idx < 0 or idx >= len(state.iA[0]):
            await update.message.reply_text("❌ Insufficient data for indicator projection.")
            return
        names = ["ADX", "Stochastic", "RVI", "AC", "Force", "OBV", "AD", "MFI", "Momentum", "DeM", "WPR", "CCI", "RSI"]
        indicator_str = "📊 *13D HILBERT SPACE PROJECTION*\n"
        for i, name in enumerate(names):
            val = state.iA[i][idx] if idx < len(state.iA[i]) else Decimal('50.0')
            val_int = int(float(val))
            bar_len = min(max(val_int // 10, 0), 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            indicator_str += f"`{name:8}` {val:6.1f} [{bar}]\n"
        indicator_str += "\n*Thresholds:*\n"
        indicator_str += f"  Overbought: 66.6 (f={F_THRESHOLD_D:.1f})\n"
        indicator_str += f"  Oversold:   33.3 (g={G_THRESHOLD_D:.1f})"
        reply_markup = self._build_main_keyboard()
        if update.callback_query:
            await update.callback_query.edit_message_text(indicator_str, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(indicator_str, parse_mode="Markdown", reply_markup=reply_markup)

    async def fvg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            await update.message.reply_text("⏳ *Engine not initialized*\nPlease use `/start_feed`.", parse_mode="Markdown")
            return
        state = self.engine.state
        idx = state.Z - state.y - 1
        bridge_fvgs = BRIDGE_STATE.list_fvgs()
        bridge_str = ""
        if bridge_fvgs:
            bridge_str = "\n*Web App FVGs:*\n"
            for f in bridge_fvgs[-8:]:
                mark = "▲" if f["type"] == "top" else "▼"
                who = f" (user {f['user_id']})" if f.get("user_id") else ""
                bridge_str += f"  {mark} {f['price']} idx={f['idx']}{who}\n"
        premium_val = state.Premium[idx] if 0 <= idx < len(state.Premium) else Decimal('0.0')
        discount_val = state.Discount[idx] if 0 <= idx < len(state.Discount) else Decimal('0.0')
        hh_val = state.HH[idx] if 0 <= idx < len(state.HH) else Decimal('0.0')
        ll_val = state.LL[idx] if 0 <= idx < len(state.LL) else Decimal('0.0')
        response = (
            "📐 *FAIR VALUE GAP TRACKING*\n"
            f"📊 *FVG Count:* {state.FVG + 1}\n"
            f"💰 *Current Price:* {state.price:.5f}\n"
            f"📉 *Last FVG:* {state.bL if state.bL else 'None'}\n"
            "*Topological Anchors:*\n"
            f"  🔷 *Premium:* {premium_val:.5f}\n"
            f"  🔶 *Discount:* {discount_val:.5f}\n"
            f"  📈 *HH:* {hh_val:.5f}\n"
            f"  📉 *LL:* {ll_val:.5f}"
            f"{bridge_str}"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    async def chart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        webapp_url = self._resolve_webapp_url()
        response = (
            "📊 *RECENT SIGNALS*\n"
            f"{signal_summary}\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"🎯 *Total Signals Recorded:* {len(state.signal_history)}\n"
            "Open the ÆEA Mini App for the full interactive candlestick chart "
            "with FVG drawings and signal overlays."
        )
        reply_markup = self._build_main_keyboard()
        if update.callback_query:
            await update.callback_query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        prev_on_track = self.engine.state.on_track_runs
        prev_on_stand = self.engine.state.on_stand_runs
        self.engine.OnReInit()
        reset_msg = (
            "🔄 *TOPOLOGICAL BRANCH RESET*\n"
            "The Hilbert space projection has been re-anchored to the current\n"
            "topological branch with historical preservation.\n"
            "🧠 *State Reset:*\n"
            "• All 13 indicator arrays reset\n"
            "• Regime classification seeded to 'sRange'\n"
            "• Premium/Discount/HH/LL reset to current bar data\n"
            "• k/l signal flags cleared\n"
            "• Quaternion field Φ reset to identity\n"
            "• DbZ branch history cleared\n"
            "• FVG anchor map cleared\n"
            "• ✨ Historical price data preserved\n"
            f"• 🔄 Tick count preserved: {self.engine.state.tick}\n"
            f"• 🔍 OnTrack runs preserved: {prev_on_track}\n"
            f"• 📉 OnStand runs preserved: {prev_on_stand}\n"
            "📊 *Ready for new regime classification...*"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(reset_msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(reset_msg, parse_mode="Markdown")

    async def start_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self._running:
            await update.message.reply_text("⚠️ Price feed is already running.")
            return
        self._running = True
        self.engine._running = True
        self.engine._consecutive_zero_prices = 0
        historical = []
        try:
            historical = self.engine.feed.get_historical_klines(limit=200)
            if historical and len(historical) >= MIN_HISTORY_WINDOW:
                self.engine.ohlcv_history = historical
                logger.info(f"✅ Loaded {len(historical)} historical bars from relay for {self.engine.feed.active_symbol()}")
                self.engine._populate_indicator_matrix()
            else:
                logger.info("⏳ No historical data from relay. Engine will initialize organically.")
        except Exception as e:
            logger.warning(f"⚠️ Historical data fetch failed: {e}")
        try:
            self.engine.update_price_from_feed()
        except Exception:
            logger.exception("update_price_from_feed crashed during start_feed")
        if not self.engine.state.FG:
            self.engine._force_initialization()
        if self.engine.state.h <= 0:
            self.engine._find_extrema_fallback()
        if self._price_task is None or self._price_task.done():
            self._price_task = asyncio.create_task(self.price_feed_loop())
        hist_count = len(self.engine.ohlcv_history)
        init_mode = "Pre-seeded with history" if hist_count >= MIN_HISTORY_WINDOW else "Organic first-tick"
        reply_text = (
            f"✅ *Price feed started*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"🔄 *Update Interval:* {UPDATE_INTERVAL}s\n"
            f"📊 *Historical Data:* {hist_count} bars loaded\n"
            f"🧠 *Initialization Mode:* {init_mode}\n"
            f"📈 *Indicator Passes:* {self.engine._indicator_populate_count}\n"
            f"📌 *Extrema Anchor h:* {self.engine.state.h}\n"
            f"🔮 *Status:* Monitoring for signals..."
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(reply_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(reply_text, parse_mode="Markdown")

    async def stop_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._running = False
        self.engine._running = False
        if self._price_task and not self._price_task.done():
            self._price_task.cancel()
        if update.callback_query:
            await update.callback_query.edit_message_text("⏹️ *Price feed stopped*", parse_mode="Markdown")
        else:
            await update.message.reply_text("⏹️ *Price feed stopped*", parse_mode="Markdown")

    async def probe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        info = self.engine.feed.probe()
        status = "✅ OK" if not info.get("empty") else "❌ EMPTY"
        lines = [
            "🔬 *RELAY PROBE*", "",
            f"*Status:* {status}",
            f"*Relay URL:* `{RELAY_URL or 'UNSET'}`",
            f"*Relay Gated:* {'🔒 yes' if RELAY_KEY else '🔓 no'}",
            f"*Primary symbol:* `{info.get('primary_symbol')}`",
            f"*Active symbol:* `{info.get('active_symbol')}`",
            f"*Chain index:* {info.get('chain_index')}",
            f"*Failure count:* {info.get('failure_count')}",
            f"*Fallback count:* {info.get('fallback_count')}",
            f"*Last update:* {info.get('last_update') or 'never'}",
        ]
        text = "\n".join(lines)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")

    async def rebuild_yf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")

    async def symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        global SYMBOL
        args = context.args
        if not args:
            supported = ", ".join(list(SYMBOL_MAP.keys())[:10])
            await update.message.reply_text(
                f"📈 *Current Symbol:* `{SYMBOL}`\n"
                "Use `/symbol <PAIR>` to change.\n"
                "Example: `/symbol BTC-USD` or `/symbol BTCUSDT`\n"
                f"*Supported Symbols:*\n{supported}\n(and {len(SYMBOL_MAP) - 10} more)",
                parse_mode="Markdown",
            )
            return
        new_symbol = args[0].upper()
        yahoo_symbol = SYMBOL_MAP.get(new_symbol, new_symbol)
        try:
            test_feed = FeedClient(yahoo_symbol)
            bid, _ = test_feed.get_current_price()
            if bid > Decimal('0.0'):
                SYMBOL = yahoo_symbol
                prev_chat = self.engine.state.chat_id
                prev_on_track = self.engine.state.on_track_runs
                prev_on_stand = self.engine.state.on_stand_runs
                self.engine = AEEA_Engine()
                self.engine.feed = FeedClient(yahoo_symbol)
                self.engine.state.chat_id = prev_chat
                self.engine.application = self.application
                self.engine.state.on_track_runs = prev_on_track
                self.engine.state.on_stand_runs = prev_on_stand
                self.engine._point_size = symbol_point(yahoo_symbol)
                BRIDGE_ENGINE_REF["engine"] = self.engine
                _bridge_attach_to_engine(self.engine)
                historical = self.engine.feed.get_historical_klines(limit=200)
                if historical:
                    self.engine.ohlcv_history = historical
                    self.engine._populate_indicator_matrix()
                self.engine._force_initialization()
                if self.engine.state.h <= 0:
                    self.engine._find_extrema_fallback()
                init_status = "✅ Initialized" if self.engine.state.FG else "⏳ Initializing..."
                await update.message.reply_text(
                    f"✅ *Symbol changed*\n"
                    f"📈 *New Symbol:* `{yahoo_symbol}`\n"
                    f"💰 *Current Price:* {bid}\n"
                    f"🧠 *Engine State:* {init_status}\n"
                    f"🔍 *OnTrack Runs:* {prev_on_track}  |  *OnStand Runs:* {prev_on_stand}",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(f"❌ Invalid symbol or no data: {yahoo_symbol}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        info = self.engine.feed.get_info()
        response = (
            "📊 *TICKER INFORMATION*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"📛 *Name:* {info.get('name', 'Unknown')}\n"
            f"💵 *Currency:* {info.get('currency', 'USD')}\n"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(response, parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")

    async def webapp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = self._resolve_webapp_url()
        if not url:
            await update.message.reply_text(
                "⏳ *Mini App URL not yet available*\n"
                "The bridge is starting a public HTTPS tunnel. "
                "Please try again in ~30–45 seconds.\n"
                "Alternatively, set `TELEGRAM_WEBAPP_URL` in the environment.",
                parse_mode="Markdown",
            )
            return
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Open ÆEA Mini App", web_app=WebAppInfo(url=url))]])
        await update.message.reply_text(
            "🌐 *ÆEA Telegram Mini App*\n"
            "Tap the button below to launch the full Codex Symbolica visualization.\n"
            "*Features inside the Mini App:*\n"
            "  ▲ Draw premium FVG\n"
            "  ▼ Draw discount FVG\n"
            "  ✖ Delete FVG\n"
            "  🔄 Live state polling every 2s\n"
            "  🧬 Engine-authoritative coherence panel\n"
            "  🔀 KC / Prime / Dime visible in HUD\n"
            "  🔍 OnTrack / OnStand counters in engine panel\n"
            "  📈 Trailing stop state mirrored from engine T()\n"
            "  📊 Candlestick chart with signal overlays",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    async def webgui(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        scheme = "https" if BRIDGE_USE_TLS else "http"
        local_url = f"{scheme}://{BRIDGE_HOST}:{BRIDGE_PORT}/"
        public_url = self._resolve_webapp_url() or "⏳ (tunnel pending)"
        await update.message.reply_text(
            f"🌐 *ÆEA Bridge Endpoints*\n"
            f"*Local URL:* `{local_url}`\n"
            f"*Public URL:* `{public_url}`\n"
            f"*State endpoint:* `{public_url.rstrip('/')}/state`\n"
            f"*Mini App State:* `{public_url.rstrip('/')}/miniapp-state`\n"
            f"*Health endpoint:* `{public_url.rstrip('/')}/health`\n"
            f"*Probe endpoint:* `{public_url.rstrip('/')}/probe`\n"
            f"*Diagnostics endpoint:* `{public_url.rstrip('/')}/diagnostics`\n"
            f"*OHLCV endpoint:* `{public_url.rstrip('/')}/ohlcv`\n"
            f"*Signals endpoint:* `{public_url.rstrip('/')}/signals`\n"
            f"*Handshake endpoint:* `POST {public_url.rstrip('/')}/handshake`",
            parse_mode="Markdown",
        )

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
        elif action == "arclen":
            await self.arclen(update, context)
        elif action == "dbz":
            await self.dbz(update, context)
        elif action == "diagnostics":
            await self.diagnostics(update, context)
        elif action == "webapp_pending":
            await query.edit_message_text("⏳ *Mini App tunnel is starting…*\nPlease retry `/webapp` in ~30–45 seconds.", parse_mode="Markdown")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Update {update} caused error {context.error}")

    async def _post_init(self, application) -> None:
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
        self.application.add_handler(CommandHandler("arclen", self.arclen))
        self.application.add_handler(CommandHandler("dbz", self.dbz))
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
        logger.info("📊 Quantum-Financial Topology Engine (MQL4-parity port).")
        logger.info(f"🧠 X_PERIOD (const) = {X_PERIOD}, Y_START (const) = {Y_START}")
        logger.info("🌿 DbZ branching: Re[Ψ] quaternion component (parallel symbolic layer).")
        logger.info("🧬 Leech lattice anchor: parallel symbolic layer.")
        logger.info("⚡ 13D Hilbert-space projection populated per bar.")
        logger.info("⚡ Telegram Mini App enabled.")
        logger.info("🛑 Trailing stop: real Ask−Bid spread + symbol-adaptive point size.")
        logger.info("🎯 Kronecker gate: LOCAL m/n at h-bar with fallback extrema anchor.")
        logger.info("🔄 O() regime mutation restored.")
        logger.info("📊 OnBar per-j HH/LL anchoring.")
        logger.info("🔬 OnTrack/OnStand MQL4 loop bounds restored (x-1 to 4*max).")
        logger.info("🔒 Relay shared-secret gate available.")
        logger.info("📊 Chart endpoint & signal history tracking enabled.")
        logger.info("✅ Ready. Use /start to begin.")
        self.application.run_polling()

_bridge_attach_to_bot(AEI_Bot)

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
# Q.E.D.
# ============================================================================