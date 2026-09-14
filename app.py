#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ÆEA TELEGRAM BOT - HEROKU DEPLOYMENT + LOCAL WEB GUI BRIDGE
Complete Quantum-Financial Topology Implementation
Data Feed: Cloudflare Worker Relay (Yahoo Finance upstream)
Platform: Heroku + Telegram Bot + Local HTTPS Bridge (index.html)
Author: Natalia Tanyatia
Version: 4.16 (MQL4 PARITY: ORGANIC FIRST-TICK INITIALIZATION)
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qsl
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal, getcontext

# ============================================================================
# EXACT ARITHMETIC: Decimal precision for financial calculations
# ============================================================================
getcontext().prec = 28

# ============================================================================
# TELEGRAM BOT IMPORTS
# ============================================================================
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
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================
# --- AETHERIC INPUT PARAMETERS (Exact Decimal Representation) ---
COMMISSION: Decimal = Decimal('0.0')
STOP_LOSS: Decimal = Decimal('0.0')
TAKE_PROFIT: Decimal = Decimal('0.0')
LOT_SIZE: Decimal = Decimal('0.01')
SLIPPAGE: int = 100
MAX_PERIOD: int = 60
MIN_PERIOD: int = 3
X_PERIOD: int = MAX_PERIOD + 2

# --- IMBALANCE OPERATOR THRESHOLDS (Exact Decimal) ---
F_THRESHOLD: Decimal = Decimal('66.6666666666666667')
G_THRESHOLD: Decimal = Decimal('33.3333333333333333')
GF_TOLERANCE: Decimal = Decimal('2.6666666666666667')

# --- THEORETICAL CONSTANTS ---
PHI_SYMBOLIC = "(1 + sqrt(5)) / 2"
PI_SYMBOLIC = "PI"
ARC_LENGTH_AXIOM = "s=r"

# --- TELEGRAM WEB APP / TUNNEL ENVIRONMENT ---
TELEGRAM_WEBAPP_URL: str = os.getenv("TELEGRAM_WEBAPP_URL", "").strip()
BRIDGE_HOST: str = os.getenv("BRIDGE_HOST", "0.0.0.0").strip()
BRIDGE_PORT: int = int(os.getenv("PORT", os.getenv("BRIDGE_PORT", "8765")))
BRIDGE_USE_TLS: bool = os.getenv("BRIDGE_USE_TLS", "0").strip() in ("1", "true", "yes")
BRIDGE_TLS_CERT: str = os.getenv("BRIDGE_TLS_CERT", "").strip()
BRIDGE_TLS_KEY: str = os.getenv("BRIDGE_TLS_KEY", "").strip()
BRIDGE_TUNNEL: str = os.getenv("BRIDGE_TUNNEL", "cloudflared").strip().lower()
BRIDGE_PUBLIC_TIMEOUT: int = int(os.getenv("BRIDGE_PUBLIC_TIMEOUT", "45"))
TELEGRAM_BOT_TOKEN_ENV: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# --- CLOUDFLARE WORKER RELAY ---
RELAY_URL: str = os.getenv("RELAY_URL", "").strip().rstrip("/")

# --- CORS CONFIGURATION ---
CORS_ORIGIN: str = os.getenv("CORS_ORIGIN", "*").strip()

# --- SYMBOL MAPPING (Yahoo Finance Format) ---
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

# --- SYMBOL FALLBACK CHAIN ---
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

SYMBOL: str = "BTC-USD"
INTERVAL: str = "1m"
UPDATE_INTERVAL: int = 30

# ============================================================================
# STATE MANAGEMENT
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
    y: int = MIN_PERIOD - 2
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
    Buy_ticket: int = -1
    Sell_ticket: int = -1
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
    Z: int = MIN_PERIOD - 1
    z: int = MIN_PERIOD - 1
    O: int = MIN_PERIOD - 1
    o: int = MIN_PERIOD - 1
    r: int = 0
    W: int = MIN_PERIOD - 1
    w: int = MIN_PERIOD - 1
    I: int = 0
    iI: int = 0
    J: int = 0
    iJ: int = 0
    ij: int = 0
    h: int = 0
    iZ: int = MIN_PERIOD - 1
    iz: int = MIN_PERIOD - 1
    iW: int = MIN_PERIOD - 1
    iw: int = MIN_PERIOD - 1
    iO: int = MIN_PERIOD - 1
    io: int = MIN_PERIOD - 1
    ir: int = 0
    count: int = 0
    toll: int = 0
    tally: str = "   "
    Premium: List[Decimal] = field(default_factory=lambda: [Decimal('0.0')] * (X_PERIOD - (MIN_PERIOD - 1)))
    Discount: List[Decimal] = field(default_factory=lambda: [Decimal('0.0')] * (X_PERIOD - (MIN_PERIOD - 1)))
    HH: List[Decimal] = field(default_factory=lambda: [Decimal('0.0')] * (X_PERIOD - (MIN_PERIOD - 1)))
    LL: List[Decimal] = field(default_factory=lambda: [Decimal('0.0')] * (X_PERIOD - (MIN_PERIOD - 1)))
    k: List[bool] = field(default_factory=lambda: [False] * (X_PERIOD - (MIN_PERIOD - 1)))
    l: List[bool] = field(default_factory=lambda: [False] * (X_PERIOD - (MIN_PERIOD - 1)))
    U: List[bool] = field(default_factory=list)
    R: bool = True
    iA: List[List[Decimal]] = field(default_factory=lambda: [[Decimal('0.0')] * ((X_PERIOD + 1) - (MIN_PERIOD - 1)) for _ in range(13)])
    cA: List[List[Decimal]] = field(default_factory=lambda: [[Decimal('0.0')] * ((X_PERIOD + 1) - (MIN_PERIOD - 1)) for _ in range(13)])
    kA: List[List[Decimal]] = field(default_factory=lambda: [[Decimal('0.0')] * ((X_PERIOD + 1) - (MIN_PERIOD - 1)) for _ in range(13)])
    lA: List[List[Decimal]] = field(default_factory=lambda: [[Decimal('0.0')] * ((X_PERIOD + 1) - (MIN_PERIOD - 1)) for _ in range(13)])
    Regime: List[str] = field(default_factory=lambda: [""] * (X_PERIOD - (MIN_PERIOD - 1)))
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
    iStdDev: Decimal = Decimal('0.0')
    iATR: Decimal = Decimal('0.0')
    iIHKk: Decimal = Decimal('50.0')
    iIHKt: Decimal = Decimal('50.0')
    FVG: int = -1
    BL: List[Decimal] = field(default_factory=list)
    bottomLine: str = "   "
    bL: str = "   "
    S: int = X_PERIOD
    T: int = X_PERIOD
    X: int = MIN_PERIOD - 1
    Y: int = MIN_PERIOD - 1
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

# ============================================================================
# INDICATOR CALCULATIONS (Decimal Precision)
# ============================================================================
def sma(data: List[Decimal], period: int) -> Decimal:
    if len(data) < period: return Decimal('0.0')
    total = sum(data[-period:], Decimal('0.0'))
    return total / Decimal(period)

def ema(data: List[Decimal], period: int) -> Decimal:
    if len(data) < period: return sma(data, period)
    alpha = Decimal('2.0') / Decimal(period + 1)
    if len(data) > 1: return alpha * data[-1] + (Decimal('1.0') - alpha) * ema(data[:-1], period)
    return data[-1]

def rsi(data: List[Decimal], period: int = 14) -> Decimal:
    if len(data) < period + 1: return Decimal('50.0')
    gains = Decimal('0.0')
    losses = Decimal('0.0')
    for i in range(1, period + 1):
        diff = data[-i] - data[-i - 1]
        if diff >= Decimal('0.0'): gains += diff
        else: losses -= diff
    avg_gain = gains / Decimal(period) if period > 0 else Decimal('0.0')
    avg_loss = losses / Decimal(period) if period > 0 else Decimal('0.0')
    if avg_loss == Decimal('0.0'): return Decimal('100.0')
    rs = avg_gain / avg_loss
    return Decimal('100.0') - (Decimal('100.0') / (Decimal('1.0') + rs))

def stochastic(high, low, close, k_period=14, d_period=3):
    if len(close) < k_period: return Decimal('50.0'), Decimal('50.0')
    highest = max(high[-k_period:])
    lowest = min(low[-k_period:])
    range_val = highest - lowest
    if range_val == Decimal('0.0'): return Decimal('50.0'), Decimal('50.0')
    k = Decimal('100.0') * (close[-1] - lowest) / range_val
    return k, k

def bollinger_bands(close, period=20, dev=Decimal('2.0')):
    if len(close) < period: return Decimal('0.0'), Decimal('0.0'), Decimal('0.0')
    mid = sma(close, period)
    variance = sum((x - mid) ** 2 for x in close[-period:]) / Decimal(period)
    std = Decimal(str(math.sqrt(float(variance)))) if variance > Decimal('0.0') else Decimal('0.0')
    upper = mid + dev * std
    lower = mid - dev * std
    return upper, mid, lower

def atr(high, low, close, period=14):
    if len(close) < period + 1: return Decimal('0.0')
    tr_values = []
    for i in range(1, period + 1):
        tr1 = high[-i] - low[-i]
        tr2 = abs(high[-i] - close[-i - 1])
        tr3 = abs(low[-i] - close[-i - 1])
        tr_values.append(max(tr1, tr2, tr3))
    return sum(tr_values) / Decimal(period)

def stddev(data, period):
    if len(data) < period: return Decimal('0.0')
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
        if isinstance(value, Decimal): return value
        return Decimal(str(value))
    except Exception:
        return Decimal('0.0')

# ============================================================================
# TELEGRAM WEB APP AUTHENTICATION (HMAC-SHA256)
# ============================================================================
def verify_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> Optional[Dict[str, Any]]:
    if not init_data or not bot_token: return None
    try: parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception: return None
    received_hash = parsed.pop("hash", None)
    if not received_hash: return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash): return None
    auth_date_raw = parsed.get("auth_date")
    if auth_date_raw is not None:
        try:
            auth_age = time.time() - int(auth_date_raw)
            if auth_age > max_age_seconds or auth_age < -300: return None
        except (ValueError, TypeError): return None
    user_json = parsed.get("user")
    user_obj: Optional[Dict[str, Any]] = None
    if user_json:
        try: user_obj = json.loads(user_json)
        except Exception: user_obj = None
    return {"user": user_obj, "auth_date": int(auth_date_raw) if auth_date_raw else None, "raw": parsed}

def _extract_auth_headers(handler: "BridgeHandler") -> Tuple[Optional[int], Optional[str], bool]:
    raw_init = handler.headers.get("X-Telegram-Init-Data", "").strip()
    if not raw_init:
        auth_hdr = handler.headers.get("Authorization", "").strip()
        if auth_hdr.lower().startswith("tma "): raw_init = auth_hdr[4:].strip()
    if not raw_init: return (None, None, False)
    verified = verify_telegram_init_data(raw_init, TELEGRAM_BOT_TOKEN_ENV)
    if not verified or not verified.get("user"): return (None, None, False)
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
            else: chain = [symbol]
        self._chain: List[str] = list(chain)
        self._chain_index: int = 0
        self._last_update: Optional[datetime] = None
        self._failure_count: int = 0
        self._fallback_count: int = 0

    def active_symbol(self) -> str: return self._chain[self._chain_index]

    def _advance_symbol_chain(self) -> None:
        if len(self._chain) <= 1: return
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
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                payload = json.loads(r.read().decode("utf-8"))
                self._failure_count = 0
                return payload
        except Exception as e:
            logger.warning(f"Relay error ({kind}) for {self.active_symbol()}: {e}")
            self._failure_count += 1
            self._fallback_count += 1
            if self._fallback_count >= 5: self._advance_symbol_chain()
            return None

    def get_current_price(self) -> Tuple[Decimal, Decimal]:
        d = self._get("price")
        if not d or "close" not in d or d.get("close") is None: return Decimal('0.0'), Decimal('0.0')
        try:
            c = Decimal(str(d["close"]))
            bid = Decimal(str(d.get("bid", d["close"])))
            ask = Decimal(str(d.get("ask", d["close"])))
            return bid, ask
        except Exception: return Decimal('0.0'), Decimal('0.0')

    def get_historical_klines(self, limit: int = 200, interval: str = "1m") -> List[Dict[str, Any]]:
        d = self._get("history", limit=limit, interval=interval)
        if not d or not isinstance(d, list): return []
        out = []
        for row in d:
            try:
                if row.get("close") is None: continue
                out.append({
                    "open": Decimal(str(row["open"])), "high": Decimal(str(row["high"])),
                    "low": Decimal(str(row["low"])), "close": Decimal(str(row["close"])),
                    "volume": Decimal(str(row.get("volume") or 0)),
                    "timestamp": datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None),
                })
            except Exception: continue
        return out

    def get_intraday(self, interval: str = "1m") -> Dict[str, Any]:
        d = self._get("intraday", interval=interval)
        if not d or d.get("close") is None: return {}
        try:
            return {
                "open": Decimal(str(d["open"])), "high": Decimal(str(d["high"])),
                "low": Decimal(str(d["low"])), "close": Decimal(str(d["close"])),
                "volume": Decimal(str(d.get("volume") or 0)), "timestamp": datetime.now(),
            }
        except Exception: return {}

    def get_info(self) -> Dict[str, Any]: return {"name": self.active_symbol(), "currency": "USD"}

    def probe(self) -> Dict[str, Any]:
        d = self._get("price")
        return {
            "active_symbol": self.active_symbol(), "primary_symbol": self.symbol,
            "chain": list(self._chain), "chain_index": self._chain_index,
            "empty": (d is None or d.get("close") is None), "relay_url": RELAY_URL,
            "failure_count": self._failure_count, "fallback_count": self._fallback_count,
            "raw_response": d,
        }

# ============================================================================
# CORE ÆEA ENGINE
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

    def _verify_arc_length_coherence(self, price: Decimal, signal: Decimal) -> Dict[str, Any]:
        state = self.state
        arc_sq = Decimal(str(state.tick if state.tick > 0 else 0))
        radius_sq = abs(price - signal) * Decimal('1000') if signal != Decimal('0.0') else arc_sq
        diff = abs(arc_sq - radius_sq)
        return {"coherent": diff < Decimal('0.01'), "arc_sq": arc_sq, "radius_sq": radius_sq, "deviation": diff}

    def initialize_engine(self) -> None:
        state = self.state
        if state._initialized and state.FG:
            logger.info("⏳ Engine already initialized, skipping...")
            return
        state._initialized = True
        logger.info("🚀 Engine initialization started (MQL4 style)...")
        if self.ohlcv_history:
            latest = self.ohlcv_history[-1]
            state.price = latest["close"]
            state.Price = latest["close"]
            state.iH = latest["high"]
            state.iL = latest["low"]
            state.t = datetime.now()
        else:
            bid, ask = self.feed.get_current_price()
            if bid > Decimal('0.0'):
                state.price = bid
                state.Price = bid
                state.t = datetime.now()
        if state.X <= state.y:
            state.X = state.y + MAX_PERIOD
        size = state.X - state.y
        if size <= 0: size = MAX_PERIOD
        state.X = state.y + size
        state.k = [False] * size
        state.l = [False] * size
        state.HH = [Decimal('0.0')] * size
        state.LL = [Decimal('0.0')] * size
        state.Premium = [Decimal('0.0')] * size
        state.Discount = [Decimal('0.0')] * size
        state.Regime = [""] * size
        state.U = []
        for i in range(13):
            if i < len(state.cA):
                state.cA[i] = [Decimal('0.0')] * size
                state.iA[i] = [Decimal('0.0')] * size
                state.kA[i] = [Decimal('0.0')] * size
                state.lA[i] = [Decimal('0.0')] * size
        state.D = Decimal('0.0')
        state.E = Decimal('0.0')
        state.Z = state.y + 1
        state.z = state.y + 1
        state.O = state.y + 1
        state.o = state.y + 1
        state.W = state.y + 1
        state.w = state.y + 1
        state.iZ = state.y + 1
        state.iz = state.y + 1
        state.iW = state.y + 1
        state.iw = state.y + 1
        state.iO = state.y + 1
        state.io = state.y + 1
        state.S = state.X
        state.T = state.X
        state.X = state.y
        state.Y = state.y
        if len(self.ohlcv_history) >= 2:
            state.iH = self.ohlcv_history[-2]["high"]
            state.iL = self.ohlcv_history[-2]["low"]
        for j in range(state.y + 1, state.X + 1):
            self._F(j, state.iH, state.iL)
        state.FG = False
        state.tick = 0
        state.R = True
        state.signature = False
        state.signal = Decimal('0.0')
        if len(self.ohlcv_history) >= state.y + 1:
            norm_vals = self._normalize(state.y)
            for i in range(min(13, len(norm_vals))):
                if i < len(state.iA) and len(state.iA[i]) > 0:
                    state.iA[i][0] = norm_vals[i]
                    state.cA[i][0] = norm_vals[i]
        if len(self.ohlcv_history) >= state.y + 1:
            state.iATR, state.iStdDev = self._unify_volatility(state.y)
        arc_check = self._verify_arc_length_coherence(state.price, state.signal)
        self._arc_length_verified = arc_check["coherent"]
        logger.info(f"✅ Arc-Length Axiom verification: {'COHERENT' if arc_check['coherent'] else 'DEVIATION'}")
        logger.info("✅ Engine state prepared (FG=false - waiting for OnTick initialization)")

    def _force_initialization(self) -> None:
        state = self.state
        if state.FG: return
        logger.info("🚀 First tick detected. Forcing engine initialization (MQL4 style)...")
        
        # MQL4 Parity: Set D and E to current price if signature is false
        if not state.signature:
            state.D = state.price
            state.E = state.price
            
        if state.X <= state.y:
            state.X = state.y + MAX_PERIOD
        size = state.X - state.y
        if size <= 0: size = MAX_PERIOD
        state.X = state.y + size
        if len(state.k) != size:
            state.k = [False] * size
            state.l = [False] * size
            state.HH = [Decimal('0.0')] * size
            state.LL = [Decimal('0.0')] * size
            state.Premium = [Decimal('0.0')] * size
            state.Discount = [Decimal('0.0')] * size
            state.Regime = [""] * size
        if len(self.ohlcv_history) >= 2:
            iH = self.ohlcv_history[-2]["high"]
            iL = self.ohlcv_history[-2]["low"]
        else:
            iH = state.price
            iL = state.price
        for j in range(state.y + 1, state.X + 1):
            idx = j - state.y - 1
            if 0 <= idx < len(state.k):
                norm_vals = self._normalize(j)
                for i in range(min(13, len(norm_vals))):
                    if i < len(state.cA) and idx < len(state.cA[i]):
                        state.cA[i][idx] = norm_vals[i] if i < len(norm_vals) else Decimal('50.0')
                state.k[idx] = False
                state.l[idx] = False
                state.HH[idx] = iH
                state.LL[idx] = iL
                state.Premium[idx] = iH
                state.Discount[idx] = iL
                for i in range(13):
                    if i < len(state.kA) and idx < len(state.kA[i]) and i < len(state.cA) and idx < len(state.cA[i]):
                        state.kA[i][idx] = state.cA[i][idx]
                        state.lA[i][idx] = state.cA[i][idx]
        if state.R and state.FG:
            state.U.append(True)
            if all(state.U): state.R = False
        state.FG = True
        state._initialized = True
        logger.info("✅ Engine initialized on first tick (MQL4 style)")

    def update_price_from_feed(self) -> None:
        data = self.feed.get_intraday()
        if not data:
            logger.warning(f"⚠️ No data from relay for {self.engine.feed.active_symbol()}")
            return
        bid = data["close"]
        ask = data["close"]
        volume = data.get("volume", Decimal('0.0'))
        timestamp = data.get("timestamp", datetime.now())
        self.update_price(bid, ask, volume, timestamp)

    def update_price(self, bid, ask, volume=Decimal('0.0'), timestamp=None) -> None:
        if timestamp is None: timestamp = datetime.now()
        price_data = PriceData(
            bid=bid, ask=ask, close=(bid + ask) / Decimal('2.0'),
            open=bid, high=max(bid, ask), low=min(bid, ask),
            volume=volume, timestamp=timestamp
        )
        self.price_history.append(price_data)
        if len(self.price_history) > 1000: self.price_history = self.price_history[-1000:]
        if self._last_price_update is None or (timestamp - self._last_price_update).seconds >= 60:
            self._bar_open = True
            self._last_price_update = timestamp
            self._bar_index += 1
            self.ohlcv_history.append({
                "open": price_data.open, "high": price_data.high, "low": price_data.low,
                "close": price_data.close, "volume": price_data.volume, "timestamp": timestamp
            })
            if len(self.ohlcv_history) > 200: self.ohlcv_history = self.ohlcv_history[-200:]
        else:
            self._bar_open = False
            if self.ohlcv_history:
                self.ohlcv_history[-1]["high"] = max(self.ohlcv_history[-1]["high"], price_data.high)
                self.ohlcv_history[-1]["low"] = min(self.ohlcv_history[-1]["low"], price_data.low)
                self.ohlcv_history[-1]["close"] = price_data.close
                self.ohlcv_history[-1]["volume"] += price_data.volume
        if self._bar_open and len(self.ohlcv_history) >= 2: self._on_bar()
        self._on_tick(price_data)

    def _normalize(self, j):
        if len(self.ohlcv_history) < j + 1: return (Decimal('50.0'),) * 13
        close_prices = [d["close"] for d in self.ohlcv_history]
        high_prices = [d["high"] for d in self.ohlcv_history]
        low_prices = [d["low"] for d in self.ohlcv_history]
        k, d = stochastic(high_prices, low_prices, close_prices)
        stoch_val = (k + d) / Decimal('2.0')
        rsi_val = rsi(close_prices, 14)
        return (Decimal('50.0'), stoch_val, Decimal('50.0'), Decimal('50.0'), Decimal('50.0'),
                Decimal('50.0'), Decimal('50.0'), Decimal('50.0'), Decimal('50.0'), Decimal('50.0'),
                Decimal('50.0'), Decimal('50.0'), rsi_val)

    def _unify_volatility(self, j):
        if len(self.ohlcv_history) < j + 1: return Decimal('50.0'), Decimal('50.0')
        close_prices = [d["close"] for d in self.ohlcv_history]
        high_prices = [d["high"] for d in self.ohlcv_history]
        low_prices = [d["low"] for d in self.ohlcv_history]
        atr_val = atr(high_prices, low_prices, close_prices, j)
        std_val = stddev(close_prices, j)
        atr_list, std_list = [], []
        for i in range(len(self.ohlcv_history) - j):
            if i + j <= len(high_prices):
                sub_high, sub_low, sub_close = high_prices[i:i + j], low_prices[i:i + j], close_prices[i:i + j]
                if len(sub_high) == j:
                    atr_list.append(atr(sub_high, sub_low, sub_close, j))
                    std_list.append(stddev(sub_close, j))
        atr_norm, std_norm = Decimal('50.0'), Decimal('50.0')
        if atr_list:
            min_atr, max_atr = min(atr_list), max(atr_list)
            if max_atr - min_atr > Decimal('0.0'): atr_norm = Decimal('100.0') * (atr_val - min_atr) / (max_atr - min_atr)
        if std_list:
            min_std, max_std = min(std_list), max(std_list)
            if max_std - min_std > Decimal('0.0'): std_norm = Decimal('100.0') * (std_val - min_std) / (max_std - min_std)
        return atr_norm, std_norm

    def _M(self, j, price, Price, iA, cA, kA, HH):
        m = 0
        y = self.state.y
        f = F_THRESHOLD + GF_TOLERANCE
        g_minus = G_THRESHOLD - GF_TOLERANCE
        idx = j - y - 1
        if idx < 0 or idx >= len(HH): return 0
        for i in range(13):
            if Price > HH[idx]:
                if iA[i] > f or cA[i] < kA[i]: m += 1
            elif price > HH[idx]:
                if iA[i] > f or iA[i] < kA[i]: m += 1
            elif iA[i] > f: m += 1
        if iA[0] > f or iA[0] < g_minus: m += 1
        if self.state.iIHKt > f and self.state.iIHKk > f: m += 1
        return m

    def _N(self, j, price, Price, iA, cA, lA, LL):
        n = 0
        y = self.state.y
        f = F_THRESHOLD + GF_TOLERANCE
        g_minus = G_THRESHOLD - GF_TOLERANCE
        idx = j - y - 1
        if idx < 0 or idx >= len(LL): return 0
        for i in range(13):
            if Price < LL[idx]:
                if iA[i] < g_minus or cA[i] > lA[i]: n += 1
            elif price < LL[idx]:
                if iA[i] < g_minus or iA[i] > lA[i]: n += 1
            elif iA[i] < g_minus: n += 1
        if iA[0] > f or iA[0] < g_minus: n += 1
        if self.state.iIHKt < g_minus and self.state.iIHKk < g_minus: n += 1
        return n

    def _classify_regime(self, iStdDev, iATR):
        if iStdDev < Decimal('50.0') and iATR > Decimal('50.0'): return "sVolatile"
        elif iStdDev < Decimal('50.0') and iATR < Decimal('50.0'): return "sRange"
        else: return "sTrend"

    def _on_hold(self, inp, inp0, inp1):
        idx = inp - self.state.y - 1
        if idx < 0 or idx >= len(self.state.Regime): return False
        return self.state.Regime[idx] == inp0 or self.state.Regime[idx] == inp1

    def _on_fire(self, inp, inp0, inp1):
        idx = inp - self.state.y - 1
        if idx < 0 or idx >= len(self.state.Regime): return False
        return self.state.Regime[idx] != inp0 and self.state.Regime[idx] != inp1

    def _F(self, j, iH, iL):
        state = self.state
        y = state.y
        idx = j - y - 1
        if idx < 0 or idx >= len(state.k): return
        state.k[idx] = False
        state.l[idx] = False
        state.HH[idx] = iH
        state.LL[idx] = iL
        state.Premium[idx] = iH
        state.Discount[idx] = iL
        for i in range(13):
            if idx < len(state.kA[i]):
                state.kA[i][idx] = state.cA[i][idx]
                state.lA[i][idx] = state.cA[i][idx]
        if state.R and state.FG:
            state.U.append(True)
            if all(state.U): state.R = False

    def _G(self):
        if len(self.ohlcv_history) < 2: return
        H = self.ohlcv_history[-2]["high"]
        L = self.ohlcv_history[-2]["low"]
        state = self.state
        y = state.y
        for j in range(y + 1, state.h + 1):
            if j == state.X - 1: break
            idx = j - y - 1
            if idx < 0 or idx >= len(state.k): continue
            state.k[idx] = False
            state.l[idx] = False
            state.HH[idx] = H
            state.LL[idx] = L
            state.Premium[idx] = H
            state.Discount[idx] = L
            for i in range(13):
                if idx < len(state.kA[i]):
                    state.kA[i][idx] = state.cA[i][idx]
                    state.lA[i][idx] = state.cA[i][idx]

    def _J(self):
        state = self.state
        if state.I == state.iZ: state.J = state.iW
        else: state.J = state.iZ
        if state.iI == state.iz: state.iJ = state.iw
        else: state.iJ = state.iz

    def _O(self, inp, inp0, inp1): pass

    def _R(self, j):
        state = self.state
        if j <= state.J:
            state.O = j
            state.iO = j
        if j > state.J and j < state.r:
            state.O = j
            state.iO = j
            state.r = j
        elif j > state.J: state.r = j
        if j <= state.iJ:
            state.o = j
            state.io = j
        if j > state.iJ and j < state.ir:
            state.o = j
            state.io = j
            state.ir = j
        elif j > state.iJ: state.ir = j

    def _KC(self):
        state = self.state
        if state.E != Decimal('0.0') and not state.A and not state.B and state.v and state.signal < state.E:
            state.invert = not state.KC
        if state.D != Decimal('0.0') and not state.B and not state.A and state.u and state.signal > state.D:
            state.invert = not state.KC

    def _on_call(self):
        state = self.state
        y = state.y
        for j in range(y + 1, state.X + 2):
            idx = j - y - 1
            if idx < 0 or idx >= len(state.Regime): break
            if state.Suply <= state.price or state.iSuply <= state.price or state.iSuply <= state.iH:
                i = j
                state.I = state.iW
                state.iZ = i
                state.Z = i
                state.iC = state.C
                if state.iw != 0 and state.jC == state.Cc: state.h = state.I
                state.jC = not state.C
                if self._on_hold(j, "sTrend", "tTrend"):
                    state.iz = i
                    state.z = i
                    state.iI = state.iw
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    if idx < len(state.k): state.k[idx] = m >= 12
                if state.X != state.X - 1: state.X += 1
            if state.Demand >= state.price or state.iDemand >= state.price or state.iDemand >= state.iL:
                i = j
                state.I = state.iZ
                state.iW = i
                state.W = i
                state.jC = state.C
                if state.iz != 0 and state.iC == state.Cc: state.h = state.I
                state.iC = not state.C
                if self._on_hold(j, "sTrend", "tTrend"):
                    state.iw = i
                    state.w = i
                    state.iI = state.iz
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.l): state.l[idx] = n >= 12
                if state.X != state.X - 1: state.X += 1
        state.X = y

    def _on_point(self):
        state = self.state
        y = state.y
        for j in range(y + 1, state.X):
            idx = j - y - 1
            if idx < 0 or idx >= len(state.Regime): break
            iATR_norm, iStdDev_norm = self._unify_volatility(j)
            if iStdDev_norm < Decimal('50.0') and iATR_norm > Decimal('50.0'):
                if state.Regime[idx] != "Stable":
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.k): state.k[idx] = m >= 12
                    if idx < len(state.l): state.l[idx] = n >= 12
                    if self._on_fire(j, "sVolatile", "tVolatile"): state.Regime[idx] = "sVolatile"
            elif iStdDev_norm < Decimal('50.0') and iATR_norm < Decimal('50.0'):
                if state.Regime[idx] != "Stable":
                    self._R(j)
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.k): state.k[idx] = m >= 12
                    if idx < len(state.l): state.l[idx] = n >= 12
                    if self._on_fire(j, "sRange", "tRange"): state.Regime[idx] = "sRange"
            elif self._on_fire(j, "sTrend", "tTrend"): state.Regime[idx] = "sTrend"

    def _on_bar(self):
        state = self.state
        y = state.y
        for j in range(y + 1, state.X):
            idx = j - y - 1
            if idx < 0 or idx >= len(state.Regime): break
            iATR_norm, iStdDev_norm = self._unify_volatility(j)
            if iStdDev_norm < Decimal('50.0') and iATR_norm > Decimal('50.0'):
                if state.Regime[idx] != "Stable":
                    if state.Regime[idx] != "tVolatile":
                        self._F(j, self.ohlcv_history[-1]["high"], self.ohlcv_history[-1]["low"])
                        m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                        n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                        if idx < len(state.k): state.k[idx] = m >= 12
                        if idx < len(state.l): state.l[idx] = n >= 12
                        state.Regime[idx] = "tVolatile"
            elif iStdDev_norm < Decimal('50.0') and iATR_norm < Decimal('50.0'):
                if state.Regime[idx] != "Stable":
                    self._R(j)
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.k): state.k[idx] = m >= 12
                    if idx < len(state.l): state.l[idx] = n >= 12
                    if state.Regime[idx] != "tRange":
                        self._F(j, self.ohlcv_history[-1]["high"], self.ohlcv_history[-1]["low"])
                        state.Regime[idx] = "tRange"
            elif (state.Regime[idx] != "tTrend" and state.Regime[idx] != "sTrend" and
                  idx < len(state.LL) and idx < len(state.Discount) and
                  idx < len(state.HH) and idx < len(state.Premium) and
                  state.LL[idx] < state.Discount[idx] and state.HH[idx] > state.Premium[idx]):
                state.Regime[idx] = "Stable"
            else:
                if state.Regime[idx] != "tTrend":
                    self._F(j, self.ohlcv_history[-1]["high"], self.ohlcv_history[-1]["low"])
                    state.Regime[idx] = "tTrend"
        if len(self.ohlcv_history) >= y + 1:
            close_prices = [d["close"] for d in self.ohlcv_history[-y - 1:]]
            state.Stock, _, state.Sale = bollinger_bands(close_prices, y)
            state.iStock, _, state.iSale = bollinger_bands(close_prices[:-1], y) if len(close_prices) > 1 else (Decimal('0.0'), Decimal('0.0'), Decimal('0.0'))

    def _on_tick(self, price_data):
        state = self.state
        state.tick += 1
        state.price = price_data.bid
        state.Price = price_data.close
        self._tick_log_counter += 1
        if self._tick_log_counter >= 100:
            self._tick_log_counter = 0
            logger.info(f"⚡ Tick #{state.tick}: Price={state.price:.5f}, Signal={state.signal:.5f}")
        arc_check = self._verify_arc_length_coherence(state.price, state.signal)
        if not arc_check["coherent"] and state.tick > 1:
            logger.warning(f"⚠️ Arc-Length Deviation detected at tick #{state.tick}: {arc_check['deviation']:.6f}")
            if arc_check['deviation'] > Decimal('1.0'):
                logger.info("🔧 Large deviation detected - forcing stabilization")
                self._on_reinit()
                return
        if not state.FG:
            self._force_initialization()
        if not state.FG:
            logger.error("❌ Engine initialization failed!")
            return
        if len(self.ohlcv_history) >= 2:
            state.iopen = self.ohlcv_history[-2]["open"]
            state.iPrice = self.ohlcv_history[-2]["close"]
            state.iH = self.ohlcv_history[-2]["high"]
            state.iL = self.ohlcv_history[-2]["low"]
        if len(self.ohlcv_history) >= state.y + 1:
            close_prices = [d["close"] for d in self.ohlcv_history[-state.y - 1:]]
            state.Stock, _, state.Sale = bollinger_bands(close_prices, state.y)
            state.iStock, _, state.iSale = bollinger_bands(close_prices[:-1], state.y) if len(close_prices) > 1 else (Decimal('0.0'), Decimal('0.0'), Decimal('0.0'))
        if len(self.ohlcv_history) >= state.y + 1:
            state.iATR, state.iStdDev = self._unify_volatility(state.y)
        self._on_point()
        self._O(state.iO, state.O, state.J)
        self._O(state.io, state.o, state.iJ)
        self._on_call()
        self._J()
        if len(self.ohlcv_history) > 1 and self.ohlcv_history[-1]["timestamp"] != state.t:
            self._on_bar()
            self._O(state.iO, state.O, state.J)
            self._O(state.io, state.o, state.iJ)
        if state.J == state.y + 1 and state.J != 2:
            self._on_stand()
            self._J()
            self._O(state.iO, state.O, state.J)
            self._O(state.io, state.o, state.iJ)
            if state.iO != 2:
                if state.J >= state.iO: state.O = state.y
                else: state.O = state.y + 1
            else: state.O = 2
            if state.io != 2:
                if state.iJ >= state.io: state.o = state.y
                else: state.o = state.y + 1
            else: state.o = 2
        if state.J == state.X - 1:
            self._on_track()
            self._J()
            self._O(state.iO, state.O, state.J)
            self._O(state.io, state.o, state.iJ)
            if state.iO != 4 * state.X:
                if state.J >= state.iO: state.O = state.X - 2
                else: state.O = state.X - 1
            else: state.O = state.X - 1
            if state.io != 4 * state.X:
                if state.iJ >= state.io: state.o = state.X - 2
                else: state.o = state.X - 1
            else: state.o = state.X - 1
        state.t = self.ohlcv_history[-1]["timestamp"] if self.ohlcv_history else None
        if state.Z != state.X - 1:
            if state.Z != state.y + 1 and state.k[state.iZ - state.y - 1] if 0 <= state.iZ - state.y - 1 < len(state.k) else False:
                state.h = state.iZ
                self._on_goe()
            elif state.k[state.iz - state.y - 1] if 0 <= state.iz - state.y - 1 < len(state.k) else False:
                if state.z != state.y + 1 and state.z != state.X - 1:
                    state.h = state.iz
                    self._on_goe()
            elif state.k[state.io - state.y - 1] if 0 <= state.io - state.y - 1 < len(state.k) else False:
                if state.o != state.y + 1 and state.o != state.X - 1:
                    state.h = state.io
                    self._on_goe()
            elif state.k[state.iO - state.y - 1] if 0 <= state.iO - state.y - 1 < len(state.k) else False:
                if state.O != state.y + 1 and state.O != state.X - 1:
                    state.h = state.iO
                    self._on_goe()
        if state.W != state.X - 1:
            if state.W != state.y + 1 and state.l[state.iW - state.y - 1] if 0 <= state.iW - state.y - 1 < len(state.l) else False:
                state.h = state.iW
                self._on_toe()
            elif state.l[state.iw - state.y - 1] if 0 <= state.iw - state.y - 1 < len(state.l) else False:
                if state.w != state.y + 1 and state.w != state.X - 1:
                    state.h = state.iw
                    self._on_toe()
            elif state.l[state.io - state.y - 1] if 0 <= state.io - state.y - 1 < len(state.l) else False:
                if state.o != state.y + 1 and state.o != state.X - 1:
                    state.h = state.io
                    self._on_toe()
            elif state.l[state.iO - state.y - 1] if 0 <= state.iO - state.y - 1 < len(state.l) else False:
                if state.O != state.y + 1 and state.O != state.X - 1:
                    state.h = state.iO
                    self._on_toe()
        if state.GF:
            self._on_reinit()
            state.GF = False
        if state.signature and state.chat_id:
            self._send_signal_alert()

    def _on_track(self):
        state = self.state
        y = state.y
        for s in range(state.X - 1, state.S):
            idx = s - y - 1
            if idx < 0 or idx >= len(state.Regime): break
            j = s
            if state.Suply <= state.price or state.iSuply <= state.price or state.iSuply <= state.iH:
                state.I = state.iW
                state.Z = state.X - 1
                state.iZ = s
                state.T += 1
                state.iC = state.C
                if state.iw != 0 and state.jC == state.Cc: state.h = state.I
                state.jC = not state.C
                if state.iStdDev > Decimal('50.0'):
                    state.S += 1
                    state.iz = s
                    state.iI = state.iw
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    if idx < len(state.k): state.k[idx] = m >= 12
                elif state.iATR < Decimal('50.0'):
                    state.S += 1
                    state.iO = s
                    state.io = s
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    if idx < len(state.k): state.k[idx] = m >= 12
                else:
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    if idx < len(state.k): state.k[idx] = m >= 12
                if self._on_fire(j, "Stable", "tVolatile"):
                    self._F(j, state.iH, state.iL)
                    state.Regime[idx] = "tVolatile"
                else: state.Regime[idx] = "sVolatile"
                state.S += 1
            if state.Demand >= state.price or state.iDemand >= state.price or state.iDemand >= state.iL:
                state.I = state.iZ
                state.W = state.X - 1
                state.iW = s
                state.T += 1
                state.jC = state.C
                if state.iz != 0 and state.iC == state.Cc: state.h = state.I
                state.iC = not state.C
                if state.iStdDev > Decimal('50.0'):
                    state.S += 1
                    state.iw = s
                    state.iI = state.iz
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.l): state.l[idx] = n >= 12
                elif state.iATR < Decimal('50.0'):
                    state.S += 1
                    state.iO = s
                    state.io = s
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.l): state.l[idx] = n >= 12
                else:
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.l): state.l[idx] = n >= 12
                if self._on_fire(j, "Stable", "tVolatile"):
                    self._F(j, state.iH, state.iL)
                    state.Regime[idx] = "tVolatile"
                else: state.Regime[idx] = "sVolatile"
                state.S += 1
            if s == 4 * state.X: break
        state.S = state.X
        state.T = state.X
        if state.Z != 4 * state.X:
            if state.Z >= state.z: state.z = state.X - 2
            else: state.z = state.X - 1
        else: state.z = state.X - 1
        if state.W != 4 * state.X:
            if state.W >= state.w: state.w = state.X - 2
            else: state.w = state.X - 1
        else: state.w = state.X - 1

    def _on_stand(self):
        state = self.state
        y = state.y
        for s in range(y + 1, state.Y, -1):
            if s == 1 or s < 0: break
            idx = s - y - 1
            if idx < 0 or idx >= len(state.Regime): continue
            j = s
            state.ir = 0
            state.ij = 0
            if state.Suply <= state.price or state.iSuply <= state.price or state.iSuply <= state.iH:
                state.I = state.iW
                state.Z = y + 1
                state.iZ = s
                state.T -= 1
                state.iC = state.C
                if state.iw != 0 and state.jC == state.Cc: state.h = state.I
                state.jC = not state.C
                if state.X != state.Y and state.iz == 0 and state.iStdDev > Decimal('50.0'):
                    state.ij = s
                    state.iz = s
                    state.iI = state.iw
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    if idx < len(state.k): state.k[idx] = m >= 12
                    if state.ir == 0 and state.Y != 2: state.Y -= 1
                elif state.X != state.Y and state.iO == 0 and state.iATR < Decimal('50.0'):
                    state.iO = s
                    state.ir = s
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    if idx < len(state.k): state.k[idx] = m >= 12
                    if state.ij == 0 and state.Y != 2: state.Y -= 1
                elif state.X == state.Y:
                    m = self._M(j, state.price, state.Price, state.iA, state.cA, state.kA, state.HH)
                    if idx < len(state.k): state.k[idx] = m >= 12
                    if self._on_fire(j, "Stable", "tVolatile"):
                        self._F(j, state.iH, state.iL)
                        state.Regime[idx] = "tVolatile"
                    else: state.Regime[idx] = "sVolatile"
                    if state.Y != 2 and state.X != 2:
                        state.Y -= 1
                        state.X -= 1
            if state.Demand >= state.price or state.iDemand >= state.price or state.iDemand >= state.iL:
                state.I = state.iZ
                state.W = y + 1
                state.iW = s
                state.T -= 1
                state.jC = state.C
                if state.iz != 0 and state.iC == state.Cc: state.h = state.I
                state.iC = not state.C
                if state.X != state.Y and state.iw == 0 and state.iStdDev > Decimal('50.0'):
                    state.ij = s
                    state.iw = s
                    state.iI = state.iz
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.l): state.l[idx] = n >= 12
                    if state.ir == 0 and state.Y != 2: state.Y -= 1
                elif state.X != state.Y and state.iO == 0 and state.iATR < Decimal('50.0'):
                    state.iO = s
                    state.io = s
                    state.ir = 0
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.l): state.l[idx] = n >= 12
                    if state.ij == 0 and state.Y != 2: state.Y -= 1
                elif state.X == state.Y:
                    n = self._N(j, state.price, state.Price, state.iA, state.cA, state.lA, state.LL)
                    if idx < len(state.l): state.l[idx] = n >= 12
                    if self._on_fire(j, "Stable", "tVolatile"):
                        self._F(j, state.iH, state.iL)
                        state.Regime[idx] = "tVolatile"
                    else: state.Regime[idx] = "sVolatile"
                    if state.Y != 2 and state.X != 2:
                        state.Y -= 1
                        state.X -= 1
            else:
                if state.Y != 2 and state.X != 2:
                    state.Y -= 1
                    state.X -= 1
        state.X = state.y
        state.Y = state.y
        if state.Z != 2:
            if state.Z >= state.z: state.z = state.y
            else: state.z = state.y + 1
        else: state.z = state.y + 1
        if state.W != 2:
            if state.W >= state.w: state.w = state.y
            else: state.w = state.y + 1
        else: state.w = state.y + 1

    def _on_goe(self):
        state = self.state
        if state.signal != Decimal('0.0'): return
        if self._on_gaurd(0) and state.KC:
            if ((state.h == state.io and state.z > state.o) or (state.h == state.iO and state.Z > state.O) or
                (state.h == state.iz and state.Z > state.z) or (state.h == state.iZ and state.Z < state.z)):
                state.prime = 1
                self._signal()
                state.tick_tock = True
                state.tag = 1
            elif ((state.h == state.io) or (state.h == state.iZ) or (state.h == state.iz) or (state.h == state.iO)):
                state.prime = 1
                self._signal()
                state.tick_tock = True
                state.tag = 1
        elif self._on_gaurd(0) != state.KC:
            if ((state.h == state.io and state.z > state.o) or (state.h == state.iO and state.Z > state.O) or
                (state.h == state.iz and state.Z > state.z) or (state.h == state.iZ and state.Z < state.z)):
                state.prime = 1
                self._signal()
                state.tick_tock = True
                state.tag = 1
            elif ((state.h == state.io) or (state.h == state.iZ) or (state.h == state.iz) or (state.h == state.iO)):
                state.prime = 1
                self._signal()
                state.tick_tock = True
                state.tag = 1
        self._KC()

    def _on_toe(self):
        state = self.state
        if state.signal != Decimal('0.0'): return
        if self._on_gaurd(0) and state.KC:
            if ((state.h == state.io and state.w > state.o) or (state.h == state.iO and state.W > state.O) or
                (state.h == state.iw and state.W > state.w) or (state.h == state.iW and state.W < state.w)):
                state.prime = 0
                self._signal()
                state.tick_tock = True
                state.tag = 0
            elif ((state.h == state.io) or (state.h == state.iW) or (state.h == state.iw) or (state.h == state.iO)):
                state.prime = 0
                self._signal()
                state.tick_tock = True
                state.tag = 0
        elif self._on_gaurd(0) != state.KC:
            if ((state.h == state.io and state.w > state.o) or (state.h == state.iO and state.W > state.O) or
                (state.h == state.iw and state.W > state.w) or (state.h == state.iW and state.W < state.w)):
                state.prime = 0
                self._signal()
                state.tick_tock = True
                state.tag = 0
            elif ((state.h == state.io) or (state.h == state.iW) or (state.h == state.iw) or (state.h == state.iO)):
                state.prime = 0
                self._signal()
                state.tick_tock = True
                state.tag = 0
        self._KC()

    def _signal(self):
        state = self.state
        state.ab = not state.ba
        state.count = 0
        state.toll = 0
        state.tally = " "
        state.signal = state.price
        state.signature = True
        self._last_signal_time = datetime.now()
        logger.info(f"📡 SIGNAL GENERATED: price={state.price:.5f}, tick={state.tick}")

    def _on_gaurd(self, inp):
        state = self.state
        if state.price > state.E and state.E != Decimal('0.0'):
            if state.signature and inp != -1: state.dime = 0
            return True
        elif state.price < state.D and state.D != Decimal('0.0'):
            if state.signature and inp != -1: state.dime = 1
            return True
        else:
            if state.signature and inp != -1: state.dime = 1
            return False

    def _on_reinit(self):
        state = self.state
        saved_ohlcv = self.ohlcv_history.copy()
        saved_price = state.price
        saved_Price = state.Price
        saved_iH = state.iH
        saved_iL = state.iL
        saved_tick = state.tick
        state.KC = state.invert
        if state.X <= state.y:
            state.X = state.y + MAX_PERIOD
        size = state.X - state.y
        if size <= 0: size = MAX_PERIOD
        state.X = state.y + size
        for i in range(13):
            if i < len(state.cA):
                state.cA[i] = [Decimal('0.0')] * size
                state.iA[i] = [Decimal('0.0')] * size
                state.kA[i] = [Decimal('0.0')] * size
                state.lA[i] = [Decimal('0.0')] * size
        state.IHKk = []
        state.IHKt = []
        state.RSI = []
        state.CCI = []
        state.MOM = []
        state.AD = []
        state.OBV = []
        state.Force = []
        state.MFI = []
        state.DeM = []
        state.RVIm = []
        state.AC = []
        state.StdDev = []
        state.ATR = []
        state.ADX = []
        state.Regime = [""] * size
        state.Premium = [Decimal('0.0')] * size
        state.Discount = [Decimal('0.0')] * size
        state.HH = [Decimal('0.0')] * size
        state.LL = [Decimal('0.0')] * size
        state.k = [False] * size
        state.l = [False] * size
        state.U = []
        state.R = True
        state.D = Decimal('0.0')
        state.E = Decimal('0.0')
        state.K = False
        state.Z = state.y + 1
        state.z = state.y + 1
        state.O = state.y + 1
        state.o = state.y + 1
        state.r = 0
        state.W = state.y + 1
        state.w = state.y + 1
        state.I = 0
        state.iI = 0
        state.J = 0
        state.iJ = 0
        state.ij = 0
        state.toll = 0
        state.tally = "   "
        state.tick_tock = False
        state.iZ = state.y + 1
        state.iz = state.y + 1
        state.iW = state.y + 1
        state.iw = state.y + 1
        state.iO = state.y + 1
        state.io = state.y + 1
        state.ir = 0
        state.S = state.X
        state.T = state.X
        state.X = state.y
        state.Y = state.y
        state.FG = False
        state.signature = False
        state.signal = Decimal('0.0')
        state.FVG = -1
        state.BL = []
        state.bottomLine = "   "
        state.bL = "   "
        self.ohlcv_history = saved_ohlcv
        state.price = saved_price
        state.Price = saved_Price
        state.iH = saved_iH
        state.iL = saved_iL
        state.tick = saved_tick
        logger.info(f"🔄 OnReInit() completed (MQL4 compatible) - Tick preserved: {state.tick}")

    def _send_signal_alert(self):
        state = self.state
        if not state.chat_id or not self.application: return
        if self._last_signal_time:
            elapsed = (datetime.now() - self._last_signal_time).seconds
            if elapsed < self._signal_cooldown: return
        direction = "📈 BUY" if state.price > state.signal else "📉 SELL"
        m_count = sum(1 for v in state.k if v)
        n_count = sum(1 for v in state.l if v)
        condition_met = m_count - n_count > 2
        bid, ask = self.feed.get_current_price()
        price_str = f"{bid:.5f}" if bid > Decimal('0.0') else f"{state.price:.5f}"
        idx = state.Z - state.y - 1
        regime = state.Regime[idx] if 0 <= idx < len(state.Regime) else "Unknown"
        arc_check = self._verify_arc_length_coherence(state.price, state.signal)
        coherence_str = "✅ COHERENT" if arc_check["coherent"] else f"⚠️ DEVIATION: {arc_check['deviation']:.6f}"
        msg = (
            f"🚨 *ÆEA SIGNAL ALERT*\n"
            f"📊 *Direction:* {direction}\n"
            f"💰 *Signal Level:* {state.signal:.5f}\n"
            f"💰 *Current Price:* {price_str}\n"
            f"📊 *Regime:* {regime}\n"
            f"⚖️ *Imbalance:* m={m_count}, n={n_count}\n"
            f"✅ *δ(m-n-2)=1:* {'✅ MET' if condition_met else '❌ NOT MET'}\n"
            f"🔢 *Prime:* {state.prime}\n"
            f"📋 *Dime:* {state.dime}\n"
            f"🧠 *KC State:* {state.KC}\n"
            f"🧠 *Arc-Length Coherence:* {coherence_str}\n"
            f"🔄 *Tick Count:* {state.tick}\n"
            f"💎 Natalia Tanyatia"
        )
        try:
            self.application.bot.send_message(chat_id=state.chat_id, text=msg, parse_mode="Markdown")
            logger.info(f"📤 Signal alert sent to {state.chat_id}")
            self._last_signal_time = datetime.now()
        except Exception as e:
            logger.error(f"❌ Failed to send signal alert: {e}")

    def _check_coherence(self):
        state = self.state
        arc_sq = Decimal(str(state.tick if state.tick > 0 else 0))
        radius_sq = abs(state.price - state.signal) * Decimal('1000') if state.signal != Decimal('0.0') else arc_sq
        diff = abs(arc_sq - radius_sq)
        return "✅ COHERENT" if diff < Decimal('0.01') else f"⚠️ DEVIATION: {diff:.6f}"

    def get_signal_status(self):
        state = self.state
        m_count = sum(1 for v in state.k if v)
        n_count = sum(1 for v in state.l if v)
        condition_met = m_count - n_count > 2
        return {
            "signal": float(state.signal), "price": float(state.price), "signature": state.signature,
            "KC": state.KC, "prime": state.prime, "dime": state.dime, "m_count": m_count,
            "n_count": n_count, "condition_met": condition_met,
            "regime": state.Regime[state.Z - state.y - 1] if 0 <= state.Z - state.y - 1 < len(state.Regime) else "Unknown",
            "coherence": self._check_coherence(), "symbol": SYMBOL, "tick": state.tick,
            "timestamp": datetime.now().isoformat(), "engine_initialized": state.FG
        }

# ============================================================================
# HTTP BRIDGE — TELEGRAM WEB APP ENABLED
# ============================================================================
class BridgeState:
    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot: Dict[str, Any] = {
            "symbol": SYMBOL, "price": "0.0", "ask": "0.0", "bid": "0.0", "signal": "0.0",
            "regime": "Unknown", "tick": 0, "m_count": 0, "n_count": 0, "coherent": True,
            "arc_sq": "0", "radius_sq": "0", "deviation": "0", "timestamp": datetime.now().isoformat(),
            "endpoint": None, "webapp_user_id": None, "webapp_username": None, "last_price_update": None,
        }
        self._fvgs: Dict[int, Dict[str, str]] = {}
        self._next_fvg_idx = 0
        self._webapp_sessions: Dict[int, Dict[str, Any]] = {}
        self._handshake_lock = threading.Lock()

    def publish(self, snapshot):
        with self._lock: self._snapshot = dict(snapshot)

    def get_snapshot(self):
        with self._lock: return dict(self._snapshot)

    def register_webapp_session(self, user_id, username, chat_id=None):
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
                    if chat_id is not None: engine.state.chat_id = chat_id
                except Exception as e: logger.warning(f"register_webapp_session → engine map failed: {e}")
            logger.info(f"🌐 Web App session registered: user_id={user_id}, username={username}")
        return True

    def add_fvg(self, fvg_type, price_str, user_id=None):
        if fvg_type not in ("top", "bott"): raise ValueError("fvg_type must be 'top' or 'bott'")
        try: price_dec = Decimal(str(price_str))
        except Exception: raise ValueError("price must be a decimal string")
        if price_dec <= Decimal('0.0'): raise ValueError("price must be > 0")
        with self._lock:
            snap = self._snapshot
            try:
                arc_sq = Decimal(str(snap.get("arc_sq", "0")))
                radius_sq = Decimal(str(snap.get("radius_sq", "0")))
                dev = abs(arc_sq - radius_sq)
                if dev > Decimal('1.0') and arc_sq > Decimal('0'):
                    raise ValueError("ARC-LENGTH DEVIATION: s²={} ≠ r²={} (dev={})".format(arc_sq, radius_sq, dev))
            except ValueError: raise
            except Exception: pass
            idx = self._next_fvg_idx
            self._next_fvg_idx += 1
            self._fvgs[idx] = {"type": fvg_type, "price": str(price_dec), "idx": idx, "created": datetime.now().isoformat(), "user_id": user_id}
            self._inject_into_engine(fvg_type, price_dec, idx)
        return idx

    def remove_fvg(self, idx):
        with self._lock:
            if idx in self._fvgs:
                del self._fvgs[idx]
                return True
        return False

    def list_fvgs(self):
        with self._lock: return list(self._fvgs.values())

    def _inject_into_engine(self, fvg_type, price, idx):
        engine = BRIDGE_ENGINE_REF.get("engine")
        if engine is None: return
        try:
            st = engine.state
            arr = st.Premium if fvg_type == "top" else st.Discount
            if len(arr) == 0: return
            slot = idx % len(arr)
            arr[slot] = price
            st.FVG = max(st.FVG, idx)
        except Exception as e: logger.warning(f"BridgeState._inject_into_engine: {e}")

BRIDGE_STATE = BridgeState()
BRIDGE_ENGINE_REF: Dict[str, Any] = {"engine": None, "bot": None, "public_url": None}

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

    def _which(self, name):
        from shutil import which
        return which(name)

    def _spawn(self, cmd):
        logger.info(f"🌐 Spawning tunnel: {' '.join(cmd)}")
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

    def _scan_for_url(self, proc, regex, deadline):
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            if line:
                logger.debug(f"[tunnel] {line}")
                m = regex.search(line)
                if m: return m.group(0)
            if time.time() > deadline: return None
        return None

    def _try_cloudflared(self):
        if not self._which("cloudflared"): return None
        try: proc = self._spawn(["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{self.port}", "--no-autoupdate"])
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
        try: proc.terminate()
        except Exception: pass
        return None

    def _try_ngrok(self):
        if not self._which("ngrok"): return None
        try: proc = self._spawn(["ngrok", "http", str(self.port), "--log=stdout"])
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
        try: proc.terminate()
        except Exception: pass
        return None

    def _try_serveo(self):
        if not self._which("ssh"): return None
        try: proc = self._spawn(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "-R", f"80:127.0.0.1:{self.port}", "serveo.net"])
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
        try: proc.terminate()
        except Exception: pass
        return None

    def start(self):
        if TELEGRAM_WEBAPP_URL:
            self.public_url = TELEGRAM_WEBAPP_URL
            self.provider = "explicit"
            BRIDGE_ENGINE_REF["public_url"] = self.public_url
            logger.info(f"🌐 Using explicit TELEGRAM_WEBAPP_URL: {self.public_url}")
            return self.public_url
        order = [self.prefer] + [p for p in ("cloudflared", "ngrok", "serveo") if p != self.prefer]
        for provider in order:
            method = getattr(self, f"_try_{provider}", None)
            if method is None: continue
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

    def stop(self):
        if self.process is None: return
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            try: self.process.kill()
            except Exception: pass
        self.process = None
        logger.info("🌐 Tunnel stopped")

class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "AEI-Bridge/4.16"

    def log_message(self, fmt, *args): return

    def _set_cors(self):
        origin = CORS_ORIGIN
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Telegram-Init-Data")
        if origin != "*": self.send_header("Vary", "Origin")

    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code, html):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0: return b""
        return self.rfile.read(length)

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            snap = BRIDGE_STATE.get_snapshot()
            last = snap.get("last_price_update")
            stale = True
            age_seconds = None
            if last:
                try:
                    age_seconds = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
                    stale = age_seconds > 60
                except Exception: pass
            self._send_json(200, {"ok": not stale, "service": "aei-bridge", "version": "4.16", "last_price_update": last, "age_seconds": age_seconds, "stale": stale, "relay_url": RELAY_URL or None})
            return
        if path == "/config":
            self._send_json(200, {"public_url": BRIDGE_ENGINE_REF.get("public_url"), "tls": BRIDGE_USE_TLS, "port": BRIDGE_PORT, "host": BRIDGE_HOST, "symbol": SYMBOL, "webapp_enabled": True, "cors_origin": CORS_ORIGIN, "relay_url": RELAY_URL or None})
            return
        if path == "/state":
            snap = BRIDGE_STATE.get_snapshot()
            public = BRIDGE_ENGINE_REF.get("public_url")
            if public: snap["endpoint"] = public
            else:
                host = self.headers.get("Host", f"{BRIDGE_HOST}:{BRIDGE_PORT}")
                scheme = "https" if BRIDGE_USE_TLS else "http"
                snap["endpoint"] = f"{scheme}://{host}"
            self._send_json(200, snap)
            return
        if path == "/fvg":
            self._send_json(200, {"fvgs": BRIDGE_STATE.list_fvgs()})
            return
        if path == "/probe":
            engine = BRIDGE_ENGINE_REF.get("engine")
            if engine is None:
                self._send_json(503, {"error": "engine_not_ready"})
                return
            self._send_json(200, engine.feed.probe())
            return
        if path == "/" or path == "/index.html":
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                html_path = os.path.join(base, "index.html")
                if os.path.isfile(html_path):
                    with open(html_path, "r", encoding="utf-8") as f: self._send_html(200, f.read())
                else:
                    self._send_html(200, "<!DOCTYPE html><html><body style='font-family:monospace;background:#050510;color:#aaccff;padding:40px;'><h2>⚡ ÆEA Mini App Bridge Online</h2><p>index.html not found in <code>" + base + "</code>.</p></body></html>")
            except Exception as e:
                self._send_json(500, {"error": "read_index_failed", "detail": str(e)})
            return
        self._send_json(404, {"error": "not_found", "path": path})

    def do_POST(self):
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
                self._send_json(200, {"ok": True, "user_id": user_id, "username": username, "public_url": BRIDGE_ENGINE_REF.get("public_url")})
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
                if fvg_type is None or price_str is None:
                    self._send_json(400, {"error": "missing_fields", "need": ["type", "price"]})
                    return
                idx = BRIDGE_STATE.add_fvg(fvg_type, price_str, user_id=user_id)
                logger.info(f"🔷 FVG committed: type={fvg_type} price={price_str} idx={idx} verified={verified} user={username}")
                self._send_json(201, {"ok": True, "idx": idx, "type": fvg_type, "price": price_str, "verified": verified})
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
                logger.info("🔄 Manual reset requested via /reset")
                self._send_json(200, {"ok": True, "active_symbol": engine.feed.active_symbol()})
            except Exception as e:
                logger.error(f"/reset error: {e}")
                self._send_json(500, {"error": "internal", "detail": str(e)})
            return
        self._send_json(404, {"error": "not_found", "path": path})

    def do_DELETE(self):
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

class BridgeServer:
    def __init__(self, host=BRIDGE_HOST, port=BRIDGE_PORT):
        self.host = host
        self.port = int(port)
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._tunnel: Optional[TunnelManager] = None
        self._ssl_context: Optional[ssl.SSLContext] = None

    def _build_ssl_context(self):
        if not BRIDGE_USE_TLS: return None
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

    def start(self):
        if self._thread is not None: return
        try:
            self._httpd = ThreadingHTTPServer((self.host, self.port), BridgeHandler)
            self._httpd.daemon_threads = True
            self._ssl_context = self._build_ssl_context()
            if self._ssl_context is not None: self._httpd.socket = self._ssl_context.wrap_socket(self._httpd.socket, server_side=True)
        except OSError as e:
            logger.error(f"❌ Bridge server bind failed on {self.host}:{self.port}: {e}")
            return
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="aei-bridge", daemon=True)
        self._thread.start()
        scheme = "https" if self._ssl_context else "http"
        logger.info(f"🌐 ÆEA Mini App Bridge listening on {scheme}://{self.host}:{self.port}")
        self._tunnel = TunnelManager(self.port, prefer=BRIDGE_TUNNEL, timeout=BRIDGE_PUBLIC_TIMEOUT)
        threading.Thread(target=self._tunnel.start, name="aei-tunnel", daemon=True).start()

    def stop(self):
        if self._tunnel is not None:
            try: self._tunnel.stop()
            except Exception: pass
            self._tunnel = None
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception: pass
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("🌐 ÆEA Mini App Bridge stopped")

def _bridge_attach_to_engine(engine: "AEEA_Engine") -> None:
    if getattr(engine, "_bridge_attached", False): return
    original_on_tick = engine._on_tick
    def wrapped_on_tick(price_data):
        original_on_tick(price_data)
        try:
            st = engine.state
            idx = st.Z - st.y - 1
            regime = st.Regime[idx] if 0 <= idx < len(st.Regime) else "Unknown"
            arc_check = engine._verify_arc_length_coherence(st.price, st.signal)
            snapshot = {
                "symbol": SYMBOL, "price": str(st.price), "bid": str(price_data.bid), "ask": str(price_data.ask),
                "signal": str(st.signal), "regime": regime, "tick": int(st.tick),
                "m_count": int(sum(1 for v in st.k if v)), "n_count": int(sum(1 for v in st.l if v)),
                "coherent": bool(arc_check["coherent"]), "arc_sq": str(arc_check["arc_sq"]),
                "radius_sq": str(arc_check["radius_sq"]), "deviation": str(arc_check["deviation"]),
                "timestamp": datetime.now().isoformat(), "endpoint": BRIDGE_ENGINE_REF.get("public_url"),
                "webapp_user_id": st.webapp_user_id, "webapp_username": st.webapp_username,
                "last_price_update": datetime.now().isoformat(),
            }
            BRIDGE_STATE.publish(snapshot)
        except Exception as e: logger.warning(f"Bridge publish failed: {e}")
    engine._on_tick = wrapped_on_tick
    engine._bridge_attached = True
    logger.info("🔗 Bridge attached to AEEA_Engine (snapshot publishing active)")

def _bridge_attach_to_bot(bot: "AEI_Bot") -> None:
    if getattr(bot, "_bridge_attached", False): return
    original_run = bot.run
    def wrapped_run(self):
        BRIDGE_ENGINE_REF["engine"] = self.engine
        BRIDGE_ENGINE_REF["bot"] = self
        _bridge_attach_to_engine(self.engine)
        server = BridgeServer()
        server.start()
        self._bridge_server = server
        try: original_run(self)
        finally: server.stop()
    bot.run = wrapped_run
    bot._bridge_attached = True
    logger.info("🔗 Bridge attached to AEI_Bot.run()")

# ============================================================================
# TELEGRAM BOT HANDLERS
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
                logger.info(f"🔄 Feed iteration #{iteration} (relay={RELAY_URL or 'unset'})")
                self.engine.update_price_from_feed()
                logger.info(f"📊 price={self.engine.state.price} tick={self.engine.state.tick} FG={self.engine.state.FG} active_sym={self.engine.feed.active_symbol()}")
            except Exception as e:
                logger.exception(f"❌ Feed iteration #{iteration} failed")
            await asyncio.sleep(UPDATE_INTERVAL)
        logger.info("🔄 Price feed loop exited")

    def _build_main_keyboard(self) -> InlineKeyboardMarkup:
        webapp_url = self._resolve_webapp_url()
        rows = [
            [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("📈 Signal", callback_data="signal")],
            [InlineKeyboardButton("📊 Regime", callback_data="regime"), InlineKeyboardButton("📐 Indicators", callback_data="indicators")],
            [InlineKeyboardButton("🔄 Start Feed", callback_data="start_feed"), InlineKeyboardButton("⏹️ Stop Feed", callback_data="stop_feed")],
            [InlineKeyboardButton("📈 Info", callback_data="info"), InlineKeyboardButton("🔄 Reset", callback_data="reset")],
            [InlineKeyboardButton("🔬 Probe Relay", callback_data="probe"), InlineKeyboardButton("♻️ Rebuild Relay", callback_data="rebuild_yf")],
        ]
        if webapp_url: rows.append([InlineKeyboardButton("⚡ Open ÆEA Mini App", web_app=WebAppInfo(url=webapp_url))])
        else: rows.append([InlineKeyboardButton("⚡ Mini App (tunnel pending…)", callback_data="webapp_pending")])
        return InlineKeyboardMarkup(rows)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        self.engine.state.chat_id = chat_id
        self.engine.application = self.application
        engine_status = "✅ Initialized" if self.engine.state.FG else "⏳ Waiting for data"
        webapp_url = self._resolve_webapp_url()
        webapp_display = webapp_url if webapp_url else "⏳ Tunnel not yet established"
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
            "`/reset` - Reset topological branch\n"
            "`/start_feed` - Start price feed\n"
            "`/stop_feed` - Stop price feed\n"
            "`/symbol <PAIR>` - Change trading symbol\n"
            "`/info` - Ticker information\n"
            "`/probe` - Relay diagnostics\n"
            "`/rebuild_yf` - Force relay reset\n"
            "`/webapp` - Launch Telegram Mini App\n"
            "`/webgui` - Show local bridge URL\n"
            "`/help` - Show this message\n\n"
            f"📈 *Current Symbol:* `{SYMBOL}`\n"
            f"🔄 *Feed Status:* {'Active' if self._running else 'Inactive'}\n"
            f"🌐 *Relay:* `{RELAY_URL or 'unset'}`\n"
            f"🌐 *Mini App URL:* `{webapp_display}`\n"
            f"🧠 *Engine Status:* {engine_status}\n\n"
            "🧠 *Theoretical Foundation:*\n"
            "• Arc-Length Coherence (s = r)\n"
            "• Kronecker-Delta Execution: δ(m-n-2)=1\n"
            "• Observer Operator O[Ψ]\n"
            "• Non-Hermitian Lindblad Dynamics\n\n"
            "💎 Natalia Tanyatia"
        )
        await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=self._build_main_keyboard())

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.start(update, context)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            logger.info("⚠️ Engine not initialized, attempting to force...")
            self.engine._force_initialization()
            if not self.engine.state.FG:
                await update.message.reply_text(
                    "⏳ *Engine not initialized*\n"
                    "The engine will initialize on the first price tick after starting the feed.\n"
                    "Please use `/start_feed` to start the price feed.\n"
                    "If the feed is already running, try `/reset` to reinitialize.",
                    parse_mode="Markdown"
                )
                return
        state = self.engine.state
        idx = state.Z - state.y - 1
        regime = state.Regime[idx] if 0 <= idx < len(state.Regime) else "Unknown"
        bid, ask = self.engine.feed.get_current_price()
        price_display = f"{bid:.5f}" if bid > Decimal('0.0') else f"{state.price:.5f}"
        coherence = self.engine._check_coherence()
        response = (
            "🔷 *ÆEA STATUS*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"🔎 *Active Relay Symbol:* `{self.engine.feed.active_symbol()}`\n"
            f"💰 *Price:* {price_display}\n"
            f"📊 *Regime:* {regime}\n"
            f"🔄 *Coherence:* {coherence}\n"
            f"🎯 *Signal Level:* {state.signal:.5f}\n"
            f"📋 *Signature:* {'Active' if state.signature else 'Idle'}\n"
            f"🧠 *KC State:* {state.KC}\n"
            f"🔄 *Tick:* {state.tick}\n"
            f"🧠 *Engine State:* {'✅ Initialized' if state.FG else '⏳ Initializing'}\n"
            f"🌐 *Mini App User:* {state.webapp_username or '—'}\n"
            f"📅 *Last Update:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📊 *Imbalance:* m={sum(1 for v in state.k if v)}, n={sum(1 for v in state.l if v)}\n"
            f"📡 *Feed Active:* {'✅' if self._running else '❌'}"
        )
        reply_markup = self._build_main_keyboard()
        if update.callback_query: await update.callback_query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        else: await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)

    async def regime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            self.engine._force_initialization()
            if not self.engine.state.FG:
                await update.message.reply_text("⏳ *Engine not initialized*\nPlease use `/start_feed`.", parse_mode="Markdown")
                return
        state = self.engine.state
        y = state.y
        idx = state.Z - y - 1
        current = state.Regime[idx] if 0 <= idx < len(state.Regime) else "Unknown"
        premium = state.Premium[idx] if 0 <= idx < len(state.Premium) else Decimal('0.0')
        discount = state.Discount[idx] if 0 <= idx < len(state.Discount) else Decimal('0.0')
        hh = state.HH[idx] if 0 <= idx < len(state.HH) else Decimal('0.0')
        ll = state.LL[idx] if 0 <= idx < len(state.LL) else Decimal('0.0')
        k_count = sum(1 for v in state.k if v)
        l_count = sum(1 for v in state.l if v)
        response = (
            "📊 *REGIME CLASSIFICATION*\n"
            f"🔹 *Current Regime:* {current}\n"
            f"🔸 *Premium:* {premium:.5f}\n"
            f"🔻 *Discount:* {discount:.5f}\n"
            f"📈 *HH:* {hh:.5f}\n"
            f"📉 *LL:* {ll:.5f}\n"
            f"🟢 *Bullish Signals (k):* {k_count}\n"
            f"🔴 *Bearish Signals (l):* {l_count}\n"
            f"📐 *Imbalance Condition:* {'✅ TRIGGER' if k_count >= 12 or l_count >= 12 else '⏳ WAITING'}"
        )
        reply_markup = self._build_main_keyboard()
        if update.callback_query: await update.callback_query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        else: await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)

    async def signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            self.engine._force_initialization()
            if not self.engine.state.FG:
                await update.message.reply_text("⏳ *Engine not initialized*\nPlease use `/start_feed`.", parse_mode="Markdown")
                return
        state = self.engine.state
        if state.signal == Decimal('0.0'):
            direction = "🟡 NEUTRAL"
            confidence = "N/A"
        elif state.price > state.signal:
            direction = "🟢 BUY"
            confidence = f"{((state.price - state.signal) / state.signal * Decimal('100')):.2f}%" if state.signal != Decimal('0.0') else "0%"
        else:
            direction = "🔴 SELL"
            confidence = f"{((state.signal - state.price) / state.signal * Decimal('100')):.2f}%" if state.signal != Decimal('0.0') else "0%"
        m_count = sum(1 for v in state.k if v)
        n_count = sum(1 for v in state.l if v)
        condition_met = m_count - n_count > 2
        response = (
            "🎯 *TRADING SIGNAL*\n"
            f"📊 *Direction:* {direction}\n"
            f"📈 *Confidence:* {confidence}\n"
            f"🎯 *Signal Level:* {state.signal:.5f}\n"
            f"💰 *Current Price:* {state.price:.5f}\n"
            f"⚖️ *Imbalance:* m={m_count}, n={n_count}\n"
            f"✅ *Condition δ(m-n-2)=1:* {'✅ MET' if condition_met else '❌ NOT MET'}\n"
            f"🧠 *KC State:* {state.KC}\n"
            f"🔢 *Prime:* {state.prime}\n"
            f"📋 *Dime:* {state.dime}\n"
            f"🔄 *Tick Count:* {state.tick}"
        )
        reply_markup = self._build_main_keyboard()
        if update.callback_query: await update.callback_query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        else: await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)

    async def indicators(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            self.engine._force_initialization()
            if not self.engine.state.FG:
                await update.message.reply_text("⏳ *Engine not initialized*\nPlease use `/start_feed`.", parse_mode="Markdown")
                return
        state = self.engine.state
        y = state.y
        idx = state.Z - y - 1
        if idx < 0 or idx >= 13:
            await update.message.reply_text("❌ Insufficient data for indicator projection.")
            return
        i_values = [state.iA[i][idx] if idx < len(state.iA[i]) else Decimal('50.0') for i in range(13)]
        names = ["ADX", "Stochastic", "RVI", "AC", "Force", "OBV", "AD", "MFI", "Momentum", "DeM", "WPR", "CCI", "RSI"]
        indicator_str = "📊 *13D HILBERT SPACE PROJECTION*\n"
        for i, (name, val) in enumerate(zip(names, i_values)):
            val_int = int(float(val))
            bar = "█" * min(max(val_int // 10, 0), 10) + "░" * (10 - min(max(val_int // 10, 0), 10))
            indicator_str += f"`{name:8}` {val:6.1f} [{bar}]\n"
        indicator_str += "\n*Thresholds:*\n"
        indicator_str += f"  Overbought: 66.6 (f={F_THRESHOLD:.1f})\n"
        indicator_str += f"  Oversold:   33.3 (g={G_THRESHOLD:.1f})"
        reply_markup = self._build_main_keyboard()
        if update.callback_query: await update.callback_query.edit_message_text(indicator_str, parse_mode="Markdown", reply_markup=reply_markup)
        else: await update.message.reply_text(indicator_str, parse_mode="Markdown", reply_markup=reply_markup)

    async def fvg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine.state.FG:
            await update.message.reply_text("⏳ *Engine not initialized*\nPlease use `/start_feed`.", parse_mode="Markdown")
            return
        state = self.engine.state
        idx = state.Z - state.y - 1
        bridge_fvgs = BRIDGE_STATE.list_fvgs()
        bridge_str = ""
        if bridge_fvgs:
            bridge_str = "\n🌐 *Web App FVGs:*\n"
            for f in bridge_fvgs[-8:]:
                mark = "▲" if f["type"] == "top" else "▼"
                who = f" (user {f['user_id']})" if f.get("user_id") else ""
                bridge_str += f"  {mark} {f['price']} (idx={f['idx']}){who}\n"
        response = (
            "📐 *FAIR VALUE GAP TRACKING*\n"
            f"📊 *FVG Count:* {state.FVG + 1}\n"
            f"📈 *Current Price:* {state.price:.5f}\n"
            f"📉 *Last FVG:* {state.bL if state.bL else 'None'}\n"
            "*Topological Anchors:*\n"
            f"  🔷 *Premium:* {state.Premium[idx] if 0 <= idx < len(state.Premium) else Decimal('0.0'):.5f}\n"
            f"  🔶 *Discount:* {state.Discount[idx] if 0 <= idx < len(state.Discount) else Decimal('0.0'):.5f}\n"
            f"  📈 *HH:* {state.HH[idx] if 0 <= idx < len(state.HH) else Decimal('0.0'):.5f}\n"
            f"  📉 *LL:* {state.LL[idx] if 0 <= idx < len(state.LL) else Decimal('0.0'):.5f}"
            f"{bridge_str}"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        state = self.engine.state
        saved_ohlcv = self.engine.ohlcv_history.copy()
        saved_price = state.price
        saved_Price = state.Price
        saved_iH = state.iH
        saved_iL = state.iL
        saved_tick = state.tick
        if state.X <= state.y:
            state.X = state.y + MAX_PERIOD
        size = state.X - state.y
        if size <= 0: size = MAX_PERIOD
        state.X = state.y + size
        for i in range(13):
            if i < len(state.cA):
                state.cA[i] = [Decimal('0.0')] * size
                state.iA[i] = [Decimal('0.0')] * size
                state.kA[i] = [Decimal('0.0')] * size
                state.lA[i] = [Decimal('0.0')] * size
        state.IHKk = []
        state.IHKt = []
        state.RSI = []
        state.CCI = []
        state.MOM = []
        state.AD = []
        state.OBV = []
        state.Force = []
        state.MFI = []
        state.DeM = []
        state.RVIm = []
        state.AC = []
        state.StdDev = []
        state.ATR = []
        state.ADX = []
        state.Regime = [""] * size
        state.Premium = [Decimal('0.0')] * size
        state.Discount = [Decimal('0.0')] * size
        state.HH = [Decimal('0.0')] * size
        state.LL = [Decimal('0.0')] * size
        state.k = [False] * size
        state.l = [False] * size
        state.U = []
        state.R = True
        state.D = Decimal('0.0')
        state.E = Decimal('0.0')
        state.K = False
        state.Z = state.y + 1
        state.z = state.y + 1
        state.O = state.y + 1
        state.o = state.y + 1
        state.r = 0
        state.W = state.y + 1
        state.w = state.y + 1
        state.I = 0
        state.iI = 0
        state.J = 0
        state.iJ = 0
        state.ij = 0
        state.toll = 0
        state.tally = "   "
        state.tick_tock = False
        state.iZ = state.y + 1
        state.iz = state.y + 1
        state.iW = state.y + 1
        state.iw = state.y + 1
        state.iO = state.y + 1
        state.io = state.y + 1
        state.ir = 0
        state.S = state.X
        state.T = state.X
        state.X = state.y
        state.Y = state.y
        state.FG = False
        state.signature = False
        state.signal = Decimal('0.0')
        state.FVG = -1
        state.BL = []
        state.bottomLine = "   "
        state.bL = "   "
        self.engine.ohlcv_history = saved_ohlcv
        state.price = saved_price
        state.Price = saved_Price
        state.iH = saved_iH
        state.iL = saved_iL
        state.tick = saved_tick
        if len(self.engine.ohlcv_history) >= 2:
            iH = self.engine.ohlcv_history[-2]["high"]
            iL = self.engine.ohlcv_history[-2]["low"]
            for j in range(state.y + 1, state.X + 1):
                idx = j - state.y - 1
                if 0 <= idx < len(state.k):
                    state.k[idx] = False
                    state.l[idx] = False
                    state.HH[idx] = iH
                    state.LL[idx] = iL
                    state.Premium[idx] = iH
                    state.Discount[idx] = iL
                    for i in range(13):
                        if idx < len(state.kA[i]) and idx < len(state.cA[i]):
                            state.kA[i][idx] = state.cA[i][idx]
                            state.lA[i][idx] = state.cA[i][idx]
            state.FG = True
        reset_msg = (
            "🔄 *TOPOLOGICAL BRANCH RESET*\n"
            "The Hilbert space projection has been re-anchored to the current\n"
            "topological branch with historical preservation (MQL4 OnReInit() compatible).\n\n"
            "🧠 *State Reset:*\n"
            "• All 13 indicator arrays reset\n"
            "• Regime classification cleared\n"
            "• Premium/Discount/HH/LL reset to current bar data\n"
            "• k/l signal flags cleared\n"
            "• Tracking variables reset to initial state\n"
            "• ✨ Historical price data preserved via F() initialization\n"
            f"• 🔄 Tick count preserved: {state.tick}\n\n"
            "📊 *Ready for new regime classification...*"
        )
        if update.callback_query: await update.callback_query.edit_message_text(reset_msg, parse_mode="Markdown")
        else: await update.message.reply_text(reset_msg, parse_mode="Markdown")

    async def start_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self._running:
            await update.message.reply_text("⚠️ Price feed is already running.")
            return
        self._running = True
        self.engine._running = True
        
        historical = []
        try:
            historical = self.engine.feed.get_historical_klines(limit=200)
            if historical and len(historical) >= 20:
                self.engine.ohlcv_history = historical
                logger.info(f"✅ Loaded {len(historical)} historical bars from relay for {self.engine.feed.active_symbol()}")
                try:
                    self.engine.initialize_engine()
                except Exception as e:
                    logger.exception("initialize_engine crashed")
            else:
                logger.info("⏳ No historical data from relay. Engine will initialize organically on first tick (MQL4 parity).")
        except Exception as e:
            logger.warning(f"⚠️ Historical data fetch failed: {e}. Engine will initialize organically on first tick.")

        try:
            self.engine.update_price_from_feed()
        except Exception as e:
            logger.exception("update_price_from_feed crashed during start_feed")

        if self._price_task is None or self._price_task.done():
            self._price_task = asyncio.create_task(self.price_feed_loop())

        hist_count = len(self.engine.ohlcv_history)
        init_mode = "Pre-seeded with history" if hist_count >= 20 else "Organic first-tick initialization (MQL4 parity)"
        
        reply_text = (
            f"✅ *Price feed started*\n"
            f"📈 *Symbol:* {SYMBOL}\n"
            f"🔎 *Active Relay Symbol:* `{self.engine.feed.active_symbol()}`\n"
            f"🔄 *Update Interval:* {UPDATE_INTERVAL}s\n"
            f"📊 *Historical Data:* {hist_count} bars loaded\n"
            f"🧠 *Initialization Mode:* {init_mode}\n"
            f"🌐 *Relay:* `{RELAY_URL or 'unset'}`\n"
            f"🔮 *Status:* Monitoring for signals...\n"
            f"_Tip: The engine builds its state in real-time as ticks arrive._"
        )
        if update.callback_query: await update.callback_query.edit_message_text(reply_text, parse_mode="Markdown")
        else: await update.message.reply_text(reply_text, parse_mode="Markdown")

    async def stop_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._running = False
        self.engine._running = False
        if self._price_task and not self._price_task.done(): self._price_task.cancel()
        if update.callback_query: await update.callback_query.edit_message_text("⏹️ *Price feed stopped*", parse_mode="Markdown")
        else: await update.message.reply_text("⏹️ *Price feed stopped*", parse_mode="Markdown")

    async def probe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        info = self.engine.feed.probe()
        status = "✅ OK" if not info.get("empty") else "❌ EMPTY"
        lines = [
            "🔬 *RELAY PROBE*", "",
            f"*Relay URL:* `{info.get('relay_url') or 'UNSET'}`",
            f"*Status:* {status}",
            f"*Primary symbol:* `{info.get('primary_symbol')}`",
            f"*Active symbol:* `{info.get('active_symbol')}`",
            f"*Chain:* `{info.get('chain')}`",
            f"*Chain index:* {info.get('chain_index')}",
            f"*Failure count:* {info.get('failure_count')}",
            f"*Fallback count:* {info.get('fallback_count')}",
        ]
        raw = info.get("raw_response")
        if raw:
            lines.append(f"*Raw keys:* `{list(raw.keys())}`")
            lines.append("")
            lines.append("_If EMPTY persists:_")
            lines.append("_1. Verify the Worker URL: `curl <relay>/?symbol=BTC-USD&kind=price`_")
            lines.append("_2. Check the Worker dashboard for errors._")
            lines.append("_3. Send `/rebuild_yf` to force a symbol rotation._")
        text = "\n".join(lines)
        if update.callback_query: await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        else: await update.message.reply_text(text, parse_mode="Markdown")

    async def rebuild_yf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.engine.feed._rebuild_ticker()
        self.engine.feed._fallback_count = 0
        if len(self.engine.feed._chain) > 1: self.engine.feed._advance_symbol_chain()
        active = self.engine.feed.active_symbol()
        text = f"♻️ *Relay client rebuilt*\n🔎 *Active symbol:* `{active}`\n_Feed will use this symbol on next iteration._"
        if update.callback_query: await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        else: await update.message.reply_text(text, parse_mode="Markdown")

    async def symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        global SYMBOL
        args = context.args
        if not args:
            await update.message.reply_text(
                f"📈 *Current Symbol:* `{SYMBOL}`\n"
                "Use `/symbol <PAIR>` to change.\n"
                "Example: `/symbol BTC-USD` or `/symbol BTCUSDT`\n"
                f"*Supported Symbols:*\n"
                f"{', '.join(list(SYMBOL_MAP.keys())[:10])}\n"
                f"(and {len(SYMBOL_MAP) - 10} more)",
                parse_mode="Markdown"
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
                self.engine = AEEA_Engine()
                self.engine.feed = FeedClient(yahoo_symbol)
                self.engine.state.chat_id = prev_chat
                self.engine.application = self.application
                BRIDGE_ENGINE_REF["engine"] = self.engine
                _bridge_attach_to_engine(self.engine)
                historical = self.engine.feed.get_historical_klines(limit=200)
                if historical:
                    self.engine.ohlcv_history = historical
                    self.engine.initialize_engine()
                    self.engine._force_initialization()
                await update.message.reply_text(
                    f"✅ *Symbol changed*\n"
                    f"📈 *New Symbol:* `{yahoo_symbol}`\n"
                    f"💰 *Current Price:* {bid}\n"
                    f"🧠 *Engine State:* {'✅ Initialized' if self.engine.state.FG else '⏳ Initializing...'}",
                    parse_mode="Markdown"
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
            f"🔎 *Active Relay Symbol:* `{self.engine.feed.active_symbol()}`\n"
            f"📛 *Name:* {info.get('name', 'Unknown')}\n"
            f"💵 *Currency:* {info.get('currency', 'USD')}\n"
            f"🌐 *Data Source:* Cloudflare Worker Relay (Yahoo Finance upstream)\n"
            f"🔗 *Relay URL:* `{RELAY_URL or 'unset'}`"
        )
        if update.callback_query: await update.callback_query.edit_message_text(response, parse_mode="Markdown")
        else: await update.message.reply_text(response, parse_mode="Markdown")

    async def webapp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = self._resolve_webapp_url()
        if not url:
            await update.message.reply_text(
                "⏳ *Mini App URL not yet available*\n"
                "The bridge is starting a public HTTPS tunnel. "
                "Please try again in ~30–45 seconds.\n"
                "Alternatively, set `TELEGRAM_WEBAPP_URL` in the environment to a "
                "pre-provisioned HTTPS endpoint.",
                parse_mode="Markdown"
            )
            return
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Open ÆEA Mini App", web_app=WebAppInfo(url=url))]])
        await update.message.reply_text(
            f"🌐 *ÆEA Telegram Mini App*\n"
            f"*Public URL:* `{url}`\n"
            f"*Provider:* {'explicit' if TELEGRAM_WEBAPP_URL else BRIDGE_TUNNEL}\n"
            f"Tap the button below to launch the full Codex Symbolica visualization "
            f"as a Telegram Web App — the same GUI served locally at "
            f"`http://127.0.0.1:{BRIDGE_PORT}`, but reachable from inside Telegram.\n\n"
            f"*Features inside the Mini App:*\n"
            f"  ▲ Draw premium FVG (Top)\n"
            f"  ▼ Draw discount FVG (Bottom)\n"
            f"  ✖ Delete FVG (Deleter)\n"
            f"  ⟳ Live state polling every 2 s\n"
            f"  🧠 Arc-Length Coherence gate enforced on every FVG commit\n\n"
            f"Your Telegram user ID is bound to `chat_id` on handshake, so bot "
            f"signal alerts route to the same account.",
            parse_mode="Markdown",
            reply_markup=keyboard
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
            f"*Health endpoint:* `{public_url.rstrip('/')}/health`\n"
            f"*Probe endpoint:* `{public_url.rstrip('/')}/probe`\n"
            f"*Handshake endpoint:* `POST {public_url.rstrip('/')}/handshake`\n"
            f"*Relay URL:* `{RELAY_URL or 'unset'}`\n"
            f"*Chart tools in Mini App:*\n"
            f"  ▲ Top → Blue premium FVG\n"
            f"  ▼ Bottom → Red discount FVG\n"
            f"  ✖ Delete → Remove FVG\n"
            f"  Esc → Pan/Rotate",
            parse_mode="Markdown"
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        action = query.data
        if action == "status": await self.status(update, context)
        elif action == "regime": await self.regime(update, context)
        elif action == "signal": await self.signal(update, context)
        elif action == "indicators": await self.indicators(update, context)
        elif action == "start_feed": await self.start_feed(update, context)
        elif action == "stop_feed": await self.stop_feed(update, context)
        elif action == "info": await self.info(update, context)
        elif action == "reset": await self.reset(update, context)
        elif action == "probe": await self.probe(update, context)
        elif action == "rebuild_yf": await self.rebuild_yf(update, context)
        elif action == "webapp_pending":
            await query.edit_message_text(
                "⏳ *Mini App tunnel is starting…*\n"
                f"Please retry `/webapp` in ~30–45 seconds.\n"
                f"Tunnel provider: `{BRIDGE_TUNNEL}`",
                parse_mode="Markdown"
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Update {update} caused error {context.error}")

    async def _post_init(self, application) -> None:
        url = self._resolve_webapp_url()
        if not url:
            logger.info("⏳ MenuButtonWebApp deferred — no public URL yet")
            return
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="ÆEA Mini App", web_app=WebAppInfo(url=url))
            )
            logger.info(f"✅ MenuButtonWebApp registered: {url}")
        except Exception as e:
            logger.warning(f"Failed to set menu button: {e}")

    def run(self):
        self.application = Application.builder().token(self.token).post_init(self._post_init).build()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("regime", self.regime))
        self.application.add_handler(CommandHandler("signal", self.signal))
        self.application.add_handler(CommandHandler("indicators", self.indicators))
        self.application.add_handler(CommandHandler("fvg", self.fvg))
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
        logger.info(f"📊 Quantum-Financial Topology Engine initialized.")
        logger.info(f"🧠 Arc-Length Axiom (s=r) enforced.")
        logger.info(f"🔄 Non-Hermitian Lindblad Dynamics active.")
        logger.info(f"🌐 Relay: {RELAY_URL or 'UNSET — set RELAY_URL env var!'}")
        logger.info(f"⚡ Telegram Mini App enabled.")
        logger.info(f"🌐 CORS origin: {CORS_ORIGIN}")
        logger.info(f"💎 Ready. Use /start to begin.")
        self.application.run_polling()

# ============================================================================
# BRIDGE BOOTSTRAP
# ============================================================================
_bridge_attach_to_bot(AEI_Bot)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
_BRIDGE_MANIFEST = r"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ ÆEA TELEGRAM BOT + WEB GUI BRIDGE · v4.16 (MQL4 PARITY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Architecture:
• Telegram bot      : app.py (python-telegram-bot)
• Data feed         : Cloudflare Worker relay (Yahoo upstream)
• HTTPS bridge      : http://0.0.0.0:8765  (auto-attached)
• Public tunnel     : cloudflared | ngrok | serveo (auto-discovered)
• Web GUI           : index.html → Telegram Web App (Mini App)
• Menu button       : MenuButtonWebApp (one tap to open Mini App)

v4.16 MQL4 Parity Update:
• Engine no longer requires historical data on initialization
• State is determined "in time" organically on the first tick
• D and E signal thresholds anchored to first tick price
• Arrays seeded dynamically as bars arrive (exact MQL4 FG==false logic)
• Historical data is optional pre-seeding, not a prerequisite

Quick start:
1. Deploy the Cloudflare Worker (see worker.js).
2. export TELEGRAM_BOT_TOKEN='YOUR_BOT_TOKEN'
3. export RELAY_URL='https://your-worker.workers.dev'
4. python3 app.py
5. In Telegram: /start → /start_feed → tap "⚡ Open ÆEA Mini App"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

def _print_manifest():
    try: print(_BRIDGE_MANIFEST)
    except Exception: pass

_AEI_Bot_run_orig = AEI_Bot.run
def _AEI_Bot_run_with_manifest(self):
    _print_manifest()
    return _AEI_Bot_run_orig(self)
AEI_Bot.run = _AEI_Bot_run_with_manifest

def main():
    """Main entry point."""
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not TOKEN:
        logger.error("❌ Error: TELEGRAM_BOT_TOKEN not set.")
        logger.error("   export TELEGRAM_BOT_TOKEN='YOUR_BOT_TOKEN'")
        sys.exit(1)
    if not RELAY_URL:
        logger.warning("⚠️ RELAY_URL not set — feed will fail.")
        logger.warning("   Deploy the Cloudflare Worker and set RELAY_URL env var.")
    bot = AEI_Bot(TOKEN, "UpscaleTradeBot")
    bot.run()

if __name__ == "__main__":
    main()

# ============================================================================
# Q.E.D.
# ============================================================================