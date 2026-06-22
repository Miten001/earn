"""
================================================================================
  EARN BOT FUNDED - MT5 SMC/ICT Bot for Prop Firm / Funded Accounts
                          made by @codex_here
================================================================================

Designed for: FTMO, MyForexFunds, FundedNext, The5ers, etc.

FUNDED FIRM SAFETY GUARDS:
  * 1% risk per trade (conservative - survives drawdowns)
  * Daily loss circuit breaker: stops trading at -3% daily
  * Max drawdown protection: stops bot at -8% from peak balance
  * No weekend holding (closes all trades Friday 21:00 UTC)
  * Higher quality setups (MIN_RR = 2.0, A+ setups only)
  * Stricter killzone (London-NY overlap focus)
  * Max 3 concurrent trades (controlled exposure)
  * Larger SL buffer (avoid news spike stop-outs)

Strategy: Same SMC/ICT (sweep + CHoCH + FVG) as earn_bot.py
================================================================================
"""

import sys, os, time, json, threading, queue, argparse
from datetime import datetime, timedelta, timezone
from typing import Optional

# ============================================================================
# >>>>>>>>>>>>>>>>>>>>>>>>>>  CONFIG  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ============================================================================
# Recommended: keep MT5_LOGIN = 0 and login manually in MT5 (avoids AutoTrading off)
MT5_LOGIN    = 0
MT5_PASSWORD = ""
MT5_SERVER   = ""
MT5_PATH     = ""

# Symbols (top 4 highest win-rate for prop firms)
SYMBOLS_FOREX  = ["XAUUSD", "GBPJPY", "EURUSD", "GBPUSD"]
SYMBOLS_CRYPTO = []   # most prop firms don't allow crypto

# ----- FUNDED FIRM RISK GUARDS -----
RISK_PERCENT          = 1.0     # 1% per trade (conservative)
DAILY_LOSS_LIMIT_PCT  = 3.0     # stop trading for the day at -3% daily loss
MAX_DRAWDOWN_PCT      = 8.0     # stop bot permanently at -8% from peak
MAX_OPEN_TRADES       = 3       # max 3 concurrent (vs 999 in normal bot)
MAX_TRADES_PER_PAIR   = 1
MIN_RR_TO_TARGET      = 2.0     # only A+ setups (was 1.5)
MAGIC_NUMBER          = 888888  # different from regular bot

# Killzones (UTC) - focus on overlap for highest probability
LONDON_KZ  = (8, 11)            # narrower window
NEWYORK_KZ = (13, 16)           # NY morning + overlap

# No weekend holding (close all trades before market close)
WEEKEND_CLOSE_HOUR_UTC = 20     # close all positions Friday 20:00 UTC
NO_FRIDAY_NEW_TRADES_HOUR = 18  # no new trades after Friday 18:00 UTC

# Strategy params (slightly stricter than regular bot)
PIVOT_LOOKBACK_H1  = 5
PIVOT_LOOKBACK_M15 = 3
SWEEP_LOOKBACK_M15 = 40         # bigger swings only (cleaner sweeps)
ATR_PERIOD         = 14
SL_BUFFER_ATR      = 0.5        # bigger SL buffer (avoid news spikes)

# Trailing
BREAKEVEN_AT_R = 1.0
LOCK_HALF_AT_R = 1.5
TRAIL_START_R  = 2.0
ATR_TRAIL_MULT = 1.5

# Order params
PENDING_ORDER_EXPIRY_HOURS = 2     # tighter expiry (was 4)
MAX_SPREAD_FX     = 15             # tighter spread cap (was 25)

# Loop
SCAN_INTERVAL_SEC = 10
STATE_FILE        = "earn_funded_state.json"
TRADES_LOG_FILE   = "earn_funded_trades.json"
DAILY_FILE        = "earn_funded_daily.json"

# ============================================================================

try:
    import numpy as np
    import pandas as pd
except ImportError:
    print("[!] pip install numpy pandas")
    sys.exit(1)

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[!] pip install MetaTrader5")
    sys.exit(1)

try:
    import tkinter as tk
    from tkinter import ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.patches import Rectangle
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ----- Indicators -----
def atr(df, p=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/p, adjust=False).mean()


# ----- MT5 helpers -----
TF_MAP = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
          "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}


def mt5_connect():
    kw = {}
    if MT5_PATH:
        kw["path"] = MT5_PATH
    if not mt5.initialize(**kw):
        return None, f"init failed: {mt5.last_error()}"
    acc = mt5.account_info()
    if (acc is None or (MT5_LOGIN and acc.login != MT5_LOGIN)) and MT5_LOGIN:
        if not mt5.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            return None, f"login failed: {mt5.last_error()}"
        acc = mt5.account_info()
    if acc is None:
        return None, f"no account info: {mt5.last_error()}"
    term = mt5.terminal_info()
    if term and not term.trade_allowed:
        print("\n" + "=" * 70)
        print("  (!) AUTOTRADING IS OFF IN MT5 TERMINAL")
        print("=" * 70)
        print("  MT5 me top-right 'AutoTrading' button (Ctrl+E) click karein.")
        print("  Button GREEN hote hi bot continue ho jayega.")
        print("=" * 70)
        print("  Waiting", end="", flush=True)
        while True:
            time.sleep(2)
            term = mt5.terminal_info()
            if term and term.trade_allowed:
                print("\n[+] AutoTrading ON. Continuing...")
                break
            print(".", end="", flush=True)
    return acc, "ok"


def find_symbol(base):
    for cand in [base, base + "m", base + ".r", base + "_", base + "!", base + ".s"]:
        if mt5.symbol_info(cand) is not None:
            mt5.symbol_select(cand, True)
            return cand
    matches = mt5.symbols_get(f"*{base}*")
    if matches:
        mt5.symbol_select(matches[0].name, True)
        return matches[0].name
    return None


def get_rates(sym, tf, n=300):
    bars = mt5.copy_rates_from_pos(sym, TF_MAP[tf], 0, n)
    if bars is None or len(bars) < 50:
        return None
    df = pd.DataFrame(bars)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def is_crypto(s):
    return any(c in s.upper() for c in ["BTC", "ETH", "XRP", "LTC", "DOGE", "SOL"])


def in_killzone():
    h = datetime.now(timezone.utc).hour
    return (LONDON_KZ[0] <= h < LONDON_KZ[1]) or (NEWYORK_KZ[0] <= h < NEWYORK_KZ[1])


def is_friday_eod():
    now = datetime.now(timezone.utc)
    return now.weekday() == 4 and now.hour >= NO_FRIDAY_NEW_TRADES_HOUR


def should_close_all_friday():
    now = datetime.now(timezone.utc)
    return now.weekday() == 4 and now.hour >= WEEKEND_CLOSE_HOUR_UTC


def spread_points(sym):
    info = mt5.symbol_info(sym)
    return info.spread if info else 9999


def open_count(sym=None):
    pos = mt5.positions_get(symbol=sym) if sym else mt5.positions_get()
    if pos is None:
        return 0
    return sum(1 for p in pos if p.magic == MAGIC_NUMBER)


def pending_count(sym=None):
    orders = mt5.orders_get(symbol=sym) if sym else mt5.orders_get()
    if orders is None:
        return 0
    return sum(1 for o in orders if o.magic == MAGIC_NUMBER)


# ----- SMC analysis (same as earn_bot.py) -----
def mark_pivots(df, lb):
    df = df.copy()
    df["ph"] = False
    df["pl"] = False
    for i in range(lb, len(df) - lb):
        wh = df["high"].iloc[i - lb:i + lb + 1]
        wl = df["low"].iloc[i - lb:i + lb + 1]
        if df["high"].iloc[i] == wh.max() and (wh == df["high"].iloc[i]).sum() == 1:
            df.iat[i, df.columns.get_loc("ph")] = True
        if df["low"].iloc[i] == wl.min() and (wl == df["low"].iloc[i]).sum() == 1:
            df.iat[i, df.columns.get_loc("pl")] = True
    return df


def htf_bias(sym):
    df = get_rates(sym, "H1", 250)
    if df is None:
        return None
    df = mark_pivots(df, PIVOT_LOOKBACK_H1)
    phs = df[df["ph"]].tail(3)["high"].values
    pls = df[df["pl"]].tail(3)["low"].values
    if len(phs) < 2 or len(pls) < 2:
        return None
    if phs[-1] > phs[-2] and pls[-1] > pls[-2]:
        return "UP"
    if phs[-1] < phs[-2] and pls[-1] < pls[-2]:
        return "DOWN"
    return None


def detect_sweep(df, direction):
    last = df.iloc[-2]
    window = df.iloc[-(SWEEP_LOOKBACK_M15 + 2):-2]
    if len(window) < 10:
        return None
    if direction == "UP":
        prior_low = window["low"].min()
        if last["low"] < prior_low and last["close"] > prior_low:
            return {"swept_level": prior_low, "sweep_low": last["low"]}
    else:
        prior_high = window["high"].max()
        if last["high"] > prior_high and last["close"] < prior_high:
            return {"swept_level": prior_high, "sweep_high": last["high"]}
    return None


def find_fvg(df, direction, min_idx=0):
    fvgs = []
    for i in range(max(2, min_idx), len(df)):
        c1, c3 = df.iloc[i - 2], df.iloc[i]
        if direction == "UP" and c1["high"] < c3["low"]:
            fvgs.append({"top": c3["low"], "bot": c1["high"],
                         "mid": (c3["low"] + c1["high"]) / 2, "idx": i})
        if direction == "DOWN" and c1["low"] > c3["high"]:
            fvgs.append({"top": c1["low"], "bot": c3["high"],
                         "mid": (c1["low"] + c3["high"]) / 2, "idx": i})
    if not fvgs:
        return None
    last_close = df.iloc[-1]["close"]
    for f in reversed(fvgs):
        if direction == "UP" and last_close > f["top"]:
            return f
        if direction == "DOWN" and last_close < f["bot"]:
            return f
    return None


def detect_choch_m5(df, direction, sweep_idx):
    pdf = mark_pivots(df, PIVOT_LOOKBACK_M15)
    after = pdf.iloc[sweep_idx:]
    if direction == "UP":
        recent = after[after["ph"]].tail(1)
        if recent.empty: return False
        return df.iloc[-1]["close"] > recent["high"].iloc[0]
    else:
        recent = after[after["pl"]].tail(1)
        if recent.empty: return False
        return df.iloc[-1]["close"] < recent["low"].iloc[0]


def find_target_liquidity(df_h1, direction, entry):
    pdf = mark_pivots(df_h1, PIVOT_LOOKBACK_H1)
    if direction == "UP":
        future = pdf[pdf["ph"] & (pdf["high"] > entry)]["high"]
        return float(future.min()) if not future.empty else float(pdf["high"].tail(50).max())
    else:
        future = pdf[pdf["pl"] & (pdf["low"] < entry)]["low"]
        return float(future.max()) if not future.empty else float(pdf["low"].tail(50).min())


# ----- Lot calc -----
def calc_lot(sym, entry, sl, risk_pct):
    acc = mt5.account_info()
    info = mt5.symbol_info(sym)
    if acc is None or info is None: return 0.0
    risk_money = acc.balance * (risk_pct / 100.0)
    sl_dist = abs(entry - sl)
    if sl_dist <= 0: return 0.0
    ts = info.trade_tick_size or info.point
    tv = info.trade_tick_value
    if not ts or not tv: return 0.0
    money_per_lot = (sl_dist / ts) * tv
    if money_per_lot <= 0: return 0.0
    lot = risk_money / money_per_lot
    step = info.volume_step or 0.01
    lot = round(lot / step) * step
    lot = max(info.volume_min, min(info.volume_max, lot))
    return round(lot, 2)


def place_pending_limit(sym, side, lot, price, sl, tp, comment):
    info = mt5.symbol_info(sym)
    if info is None or lot <= 0: return None
    digits = info.digits
    otype = mt5.ORDER_TYPE_BUY_LIMIT if side == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
    expiry = int((datetime.now() + timedelta(hours=PENDING_ORDER_EXPIRY_HOURS)).timestamp())
    req = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": sym, "volume": lot, "type": otype,
        "price": round(price, digits), "sl": round(sl, digits), "tp": round(tp, digits),
        "deviation": 30, "magic": MAGIC_NUMBER, "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_SPECIFIED, "expiration": expiry,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    r = mt5.order_send(req)
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        return None
    return r.order


def modify_sl(pos, new_sl):
    info = mt5.symbol_info(pos.symbol)
    digits = info.digits if info else 5
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": pos.ticket, "symbol": pos.symbol,
        "sl": round(new_sl, digits), "tp": round(pos.tp, digits),
    }
    r = mt5.order_send(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


def close_position(pos):
    """Force-close a position at market price (used for Friday EOD)."""
    info = mt5.symbol_info(pos.symbol)
    tick = mt5.symbol_info_tick(pos.symbol)
    if info is None or tick is None: return False
    side_close = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": pos.ticket, "symbol": pos.symbol,
        "volume": pos.volume, "type": side_close,
        "price": round(price, info.digits), "deviation": 30,
        "magic": MAGIC_NUMBER, "comment": "EOD_CLOSE",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


# ----- State persistence -----
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f: return json.load(f)
        except Exception: pass
    return default


def save_json(path, obj):
    try:
        with open(path, "w") as f: json.dump(obj, f)
    except Exception: pass


def load_state(): return load_json(STATE_FILE, {})
def save_state(s): save_json(STATE_FILE, s)


def append_trade_log(entry):
    log = load_json(TRADES_LOG_FILE, [])
    log.append(entry)
    save_json(TRADES_LOG_FILE, log)


def load_trade_log(): return load_json(TRADES_LOG_FILE, [])


# ----- Funded firm guards -----
def get_today_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_daily_state():
    """Track daily PnL + peak balance for circuit breaker logic."""
    daily = load_json(DAILY_FILE, {})
    today = get_today_key()
    acc = mt5.account_info()
    if acc is None:
        return daily, today, 0.0, 0.0
    if today not in daily:
        # New trading day - record starting balance
        daily[today] = {"start_balance": acc.balance, "trades": 0}
        # Update peak
        peak = max(daily.get("peak_balance", 0), acc.balance)
        daily["peak_balance"] = peak
        save_json(DAILY_FILE, daily)
    start_bal = daily[today]["start_balance"]
    peak_bal = daily.get("peak_balance", acc.balance)
    return daily, today, start_bal, peak_bal


def check_circuit_breakers(log_func=print):
    """Return (can_trade, reason)."""
    daily, today, start_bal, peak_bal = get_daily_state()
    acc = mt5.account_info()
    if acc is None:
        return False, "no account info"

    # Daily loss limit
    daily_pnl_pct = ((acc.equity - start_bal) / start_bal) * 100 if start_bal > 0 else 0
    if daily_pnl_pct <= -DAILY_LOSS_LIMIT_PCT:
        return False, f"DAILY LOSS LIMIT HIT ({daily_pnl_pct:.2f}%) - no new trades today"

    # Max drawdown from peak
    dd_pct = ((acc.equity - peak_bal) / peak_bal) * 100 if peak_bal > 0 else 0
    if dd_pct <= -MAX_DRAWDOWN_PCT:
        return False, f"MAX DRAWDOWN HIT ({dd_pct:.2f}% from peak ${peak_bal:.2f}) - bot stopped"

    return True, "ok"


# ----- Bot Engine -----
class BotEngine:
    def __init__(self, log_callback=None):
        self.symbols = []
        self.state = load_state()
        self.log_callback = log_callback or (lambda m: print(m))
        self.running = False
        self.thread = None
        self.last_scan_info = {}
        self.circuit_status = "ok"

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_callback(f"[{ts}] {msg}")

    def resolve_symbols(self):
        self.symbols = []
        for s in SYMBOLS_FOREX + SYMBOLS_CRYPTO:
            actual = find_symbol(s)
            if actual:
                self.symbols.append(actual)
                self.log(f"  + {s} -> {actual}")
            else:
                self.log(f"  - {s} not available")

    def try_setup(self, sym):
        info_state = {"symbol": sym, "bias": None, "sweep": False,
                      "choch": False, "fvg": False, "rr": None}
        try:
            # Funded firm guards
            can_trade, reason = check_circuit_breakers()
            if not can_trade:
                self.circuit_status = reason
                return info_state
            self.circuit_status = "ok"

            # No new trades on Friday EOD
            if is_friday_eod():
                return info_state

            if open_count() + pending_count() >= MAX_OPEN_TRADES:
                return info_state
            if open_count(sym) + pending_count(sym) >= MAX_TRADES_PER_PAIR:
                return info_state
            if not is_crypto(sym) and not in_killzone():
                return info_state
            if spread_points(sym) > MAX_SPREAD_FX:
                return info_state

            direction = htf_bias(sym)
            info_state["bias"] = direction
            if direction is None: return info_state

            df_m15 = get_rates(sym, "M15", 200)
            if df_m15 is None: return info_state
            sweep = detect_sweep(df_m15, direction)
            info_state["sweep"] = sweep is not None
            if sweep is None: return info_state

            df_m5 = get_rates(sym, "M5", 200)
            if df_m5 is None: return info_state
            sweep_idx = max(0, len(df_m5) - 30)
            choch = detect_choch_m5(df_m5, direction, sweep_idx)
            info_state["choch"] = choch
            if not choch: return info_state

            fvg = find_fvg(df_m5, direction, sweep_idx)
            info_state["fvg"] = fvg is not None
            if fvg is None: return info_state

            atr_v = atr(df_m15, ATR_PERIOD).iloc[-1]
            if pd.isna(atr_v): return info_state

            entry = fvg["mid"]
            if direction == "UP":
                sl = sweep["sweep_low"] - SL_BUFFER_ATR * atr_v
            else:
                sl = sweep["sweep_high"] + SL_BUFFER_ATR * atr_v
            risk_dist = abs(entry - sl)
            if risk_dist <= 0: return info_state

            df_h1 = get_rates(sym, "H1", 200)
            target = find_target_liquidity(df_h1, direction, entry) if df_h1 is not None else None
            if target is None:
                target = entry + 2 * risk_dist if direction == "UP" else entry - 2 * risk_dist

            rr = abs(target - entry) / risk_dist
            info_state["rr"] = round(rr, 2)
            if rr < MIN_RR_TO_TARGET: return info_state

            side = "BUY" if direction == "UP" else "SELL"
            lot = calc_lot(sym, entry, sl, RISK_PERCENT)
            if lot <= 0: return info_state

            ticket = place_pending_limit(sym, side, lot, entry, sl, target,
                                         f"FUND_{direction}_RR{rr:.1f}")
            if ticket is None: return info_state

            self.state[str(ticket)] = {
                "type": "pending", "symbol": sym, "side": side,
                "entry": entry, "initial_sl": sl, "tp": target,
                "r_distance": risk_dist, "stage": 0,
                "opened_at": datetime.now().isoformat(),
            }
            save_state(self.state)
            self.log(f"[+] {sym} {side} LIMIT lot={lot} @ {entry:.5f} SL={sl:.5f} TP={target:.5f} RR={rr:.2f}")
        except Exception as e:
            self.log(f"[!] {sym} error: {e}")
        return info_state

    def manage_open(self):
        # Friday EOD: close all positions
        if should_close_all_friday():
            positions = mt5.positions_get() or []
            for pos in positions:
                if pos.magic == MAGIC_NUMBER:
                    if close_position(pos):
                        self.log(f"[~] Friday EOD: closed {pos.symbol} #{pos.ticket}")
            # Cancel pending orders too
            orders = mt5.orders_get() or []
            for o in orders:
                if o.magic == MAGIC_NUMBER:
                    mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})

        positions = mt5.positions_get() or []
        pos_tickets = {str(p.ticket): p for p in positions if p.magic == MAGIC_NUMBER}

        for tk, st in list(self.state.items()):
            if st.get("type") == "pending" and tk in pos_tickets:
                st["type"] = "position"
                self.log(f"[*] Pending #{tk} ({st['symbol']}) FILLED")
                save_state(self.state)

        for pos in positions:
            if pos.magic != MAGIC_NUMBER: continue
            st = self.state.get(str(pos.ticket))
            if st is None: continue
            rd = st.get("r_distance", 0)
            if rd <= 0: continue
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None: continue
            cur = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            entry = st["entry"]
            profit_r = (cur - entry) / rd if pos.type == mt5.ORDER_TYPE_BUY else (entry - cur) / rd
            if profit_r <= 0: continue
            new_sl = pos.sl
            stage = st.get("stage", 0)
            if profit_r >= BREAKEVEN_AT_R and stage < 1:
                new_sl = entry; st["stage"] = 1
            if profit_r >= LOCK_HALF_AT_R and stage < 2:
                new_sl = entry + 0.5 * rd if pos.type == mt5.ORDER_TYPE_BUY else entry - 0.5 * rd
                st["stage"] = 2
            if profit_r >= TRAIL_START_R:
                df = get_rates(pos.symbol, "M15", 50)
                if df is not None:
                    a = atr(df, ATR_PERIOD).iloc[-1]
                    if pos.type == mt5.ORDER_TYPE_BUY:
                        chand = cur - ATR_TRAIL_MULT * a
                        if chand > new_sl: new_sl = chand
                    else:
                        chand = cur + ATR_TRAIL_MULT * a
                        if new_sl == 0 or chand < new_sl: new_sl = chand
                    st["stage"] = max(stage, 3)
            improve = ((pos.type == mt5.ORDER_TYPE_BUY and new_sl > pos.sl) or
                       (pos.type == mt5.ORDER_TYPE_SELL and (pos.sl == 0 or new_sl < pos.sl)))
            if improve and modify_sl(pos, new_sl):
                self.log(f"    {pos.symbol} #{pos.ticket} SL trail: {pos.sl:.5f}->{new_sl:.5f} R={profit_r:.2f}")

        pending_tickets = {str(o.ticket) for o in (mt5.orders_get() or []) if o.magic == MAGIC_NUMBER}
        alive = set(pos_tickets.keys()) | pending_tickets
        for tk in list(self.state.keys()):
            if tk not in alive:
                st = self.state[tk]
                deals = mt5.history_deals_get(position=int(tk))
                pnl = sum(d.profit + d.swap + d.commission for d in deals) if deals else 0.0
                append_trade_log({
                    "ticket": tk, "symbol": st.get("symbol"), "side": st.get("side"),
                    "entry": st.get("entry"), "sl": st.get("initial_sl"),
                    "tp": st.get("tp"), "r_distance": st.get("r_distance"),
                    "pnl": pnl, "closed_at": datetime.now().isoformat(),
                })
                self.state.pop(tk, None)
        save_state(self.state)

    def run(self):
        self.running = True
        while self.running:
            try:
                scan = {}
                for sym in self.symbols:
                    scan[sym] = self.try_setup(sym)
                self.last_scan_info = scan
                self.manage_open()
            except Exception as e:
                self.log(f"[!] loop error: {e}")
            time.sleep(SCAN_INTERVAL_SEC)

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False


# ----- Stats -----
def calc_winrate():
    log = load_trade_log()
    if not log: return 0.0, 0, 0
    wins = sum(1 for t in log if (t.get("pnl") or 0) > 0)
    losses = sum(1 for t in log if (t.get("pnl") or 0) <= 0)
    total = wins + losses
    return ((wins / total * 100) if total else 0.0), wins, losses


def calc_total_pnl():
    return sum((t.get("pnl") or 0) for t in load_trade_log())


def calc_today_pnl():
    """Today's P&L in % from start balance."""
    daily, today, start_bal, _ = get_daily_state()
    acc = mt5.account_info()
    if acc is None or start_bal <= 0:
        return 0.0, 0.0
    pnl_dollar = acc.equity - start_bal
    pnl_pct = (pnl_dollar / start_bal) * 100
    return pnl_dollar, pnl_pct


# ----- Tkinter Dashboard -----
class Dashboard:
    REFRESH_MS = 2000

    def __init__(self, root, engine):
        self.root = root
        self.engine = engine
        self.root.title("Earn Bot FUNDED - Prop Firm Edition  |  made by @codex_here")
        self.root.geometry("1200x720")
        self.root.configure(bg="#0e1117")
        self._setup_style()
        self._build_header()
        self._build_guards_bar()
        self._build_notebook()
        self.engine.log_callback = self.append_log
        self.log_q = queue.Queue()
        self.root.after(self.REFRESH_MS, self.refresh)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_style(self):
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("Treeview", background="#1a1f2b", foreground="#e6edf3",
                        fieldbackground="#1a1f2b", rowheight=24)
        style.configure("Treeview.Heading", background="#21262d", foreground="#58a6ff",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#264f78")])

    def _build_header(self):
        h = tk.Frame(self.root, bg="#161b22", pady=8)
        h.pack(fill="x")
        self.lbl_acc = tk.Label(h, text="Connecting...", fg="#58a6ff", bg="#161b22",
                                font=("Segoe UI", 11, "bold"))
        self.lbl_acc.pack(side="left", padx=15)
        self.lbl_stats = tk.Label(h, text="", fg="#7ee787", bg="#161b22",
                                  font=("Segoe UI", 10))
        self.lbl_stats.pack(side="left", padx=15)
        self.lbl_kz = tk.Label(h, text="", fg="#f0883e", bg="#161b22",
                               font=("Segoe UI", 10))
        self.lbl_kz.pack(side="right", padx=15)

    def _build_guards_bar(self):
        # Funded firm safety guards bar
        gbar = tk.Frame(self.root, bg="#3d2010", pady=6)
        gbar.pack(fill="x")
        tk.Label(gbar, text="FUNDED GUARDS:", fg="#f85149", bg="#3d2010",
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=15)
        self.lbl_guards = tk.Label(gbar, text="", fg="#e6edf3", bg="#3d2010",
                                   font=("Segoe UI", 9))
        self.lbl_guards.pack(side="left", padx=5)
        self.lbl_status = tk.Label(gbar, text="", fg="#7ee787", bg="#3d2010",
                                   font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side="right", padx=15)

    def _build_notebook(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: Active trades
        self.tab_trades = tk.Frame(self.nb, bg="#0e1117")
        self.nb.add(self.tab_trades, text="  Active Trades  ")
        cols = ("ticket", "symbol", "side", "lot", "entry", "sl", "tp", "rr", "current", "r_now", "pnl", "stage")
        self.tv_trades = ttk.Treeview(self.tab_trades, columns=cols, show="headings", height=15)
        for c in cols:
            self.tv_trades.heading(c, text=c.upper())
            self.tv_trades.column(c, width=85, anchor="center")
        self.tv_trades.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 2: Setup scanner
        self.tab_scan = tk.Frame(self.nb, bg="#0e1117")
        self.nb.add(self.tab_scan, text="  Setup Scanner  ")
        scols = ("symbol", "bias", "sweep", "choch", "fvg", "progress", "rr", "spread", "status")
        self.tv_scan = ttk.Treeview(self.tab_scan, columns=scols, show="headings", height=15)
        for c in scols:
            self.tv_scan.heading(c, text=c.upper())
            self.tv_scan.column(c, width=100, anchor="center")
        self.tv_scan.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 3: Closed trades
        self.tab_log = tk.Frame(self.nb, bg="#0e1117")
        self.nb.add(self.tab_log, text="  Closed Trades  ")
        lcols = ("closed_at", "symbol", "side", "entry", "sl", "tp", "pnl", "result")
        self.tv_log = ttk.Treeview(self.tab_log, columns=lcols, show="headings", height=15)
        for c in lcols:
            self.tv_log.heading(c, text=c.upper())
            self.tv_log.column(c, width=100, anchor="center")
        self.tv_log.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 4: Console
        self.tab_console = tk.Frame(self.nb, bg="#0e1117")
        self.nb.add(self.tab_console, text="  Console Log  ")
        self.txt = tk.Text(self.tab_console, bg="#0d1117", fg="#7ee787",
                          insertbackground="white", font=("Consolas", 9), wrap="word")
        self.txt.pack(fill="both", expand=True, padx=8, pady=8)

    def append_log(self, msg):
        self.log_q.put(msg)

    def drain_logs(self):
        while True:
            try: msg = self.log_q.get_nowait()
            except queue.Empty: break
            self.txt.insert("end", msg + "\n")
            self.txt.see("end")

    def refresh(self):
        try:
            self.drain_logs()
            self.update_header()
            self.update_guards()
            self.update_trades()
            self.update_scan()
            self.update_log()
        except Exception as e:
            print(f"refresh err: {e}")
        self.root.after(self.REFRESH_MS, self.refresh)

    def update_header(self):
        acc = mt5.account_info()
        if acc:
            self.lbl_acc.config(
                text=f"Acc {acc.login} | {acc.server} | "
                     f"Bal: {acc.balance:.2f} | Eq: {acc.equity:.2f} {acc.currency}"
            )
        rate, wins, losses = calc_winrate()
        pnl = calc_total_pnl()
        col = "#7ee787" if pnl >= 0 else "#f85149"
        self.lbl_stats.config(
            text=f"WinRate {rate:.1f}%  ({wins}W / {losses}L)  |  Total P&L: {pnl:+.2f}",
            fg=col,
        )
        now = datetime.now(timezone.utc)
        weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][now.weekday()]
        kz = "YES" if in_killzone() else "no"
        self.lbl_kz.config(text=f"UTC {now:%H:%M} {weekday}  |  Killzone: {kz}")

    def update_guards(self):
        # Show daily loss + drawdown status
        daily, today, start_bal, peak_bal = get_daily_state()
        acc = mt5.account_info()
        if acc is None: return
        today_dollar, today_pct = calc_today_pnl()
        dd_pct = ((acc.equity - peak_bal) / peak_bal) * 100 if peak_bal > 0 else 0

        # Color daily PnL
        col_today = "#7ee787" if today_pct >= 0 else (
            "#f0883e" if today_pct > -DAILY_LOSS_LIMIT_PCT * 0.6 else "#f85149"
        )
        col_dd = "#7ee787" if dd_pct >= 0 else (
            "#f0883e" if dd_pct > -MAX_DRAWDOWN_PCT * 0.6 else "#f85149"
        )

        text = (f"Today: {today_pct:+.2f}%  ({today_dollar:+.2f})  "
                f"limit -{DAILY_LOSS_LIMIT_PCT}%   |   "
                f"DD from peak: {dd_pct:+.2f}%  "
                f"limit -{MAX_DRAWDOWN_PCT}%   |   "
                f"Peak: ${peak_bal:.2f}")
        self.lbl_guards.config(text=text, fg=col_today)

        # Status
        can_trade, reason = check_circuit_breakers()
        if can_trade:
            self.lbl_status.config(text="✓ TRADING", fg="#7ee787")
        else:
            self.lbl_status.config(text=f"✗ {reason}", fg="#f85149")

    def update_trades(self):
        for r in self.tv_trades.get_children():
            self.tv_trades.delete(r)
        positions = mt5.positions_get() or []
        for pos in positions:
            if pos.magic != MAGIC_NUMBER: continue
            st = self.engine.state.get(str(pos.ticket), {})
            rd = st.get("r_distance", 0)
            tick = mt5.symbol_info_tick(pos.symbol)
            cur = (tick.bid if (tick and pos.type == mt5.ORDER_TYPE_BUY) else
                   (tick.ask if tick else 0))
            entry = st.get("entry", pos.price_open)
            r_now = ((cur - entry) / rd if pos.type == mt5.ORDER_TYPE_BUY else
                     (entry - cur) / rd) if rd > 0 and cur else 0
            rr_init = (abs(pos.tp - entry) / rd) if rd > 0 and pos.tp else 0
            stage_names = {0: "INIT", 1: "BE", 2: "+0.5R", 3: "ATR-TRAIL"}
            stg = stage_names.get(st.get("stage", 0), "?")
            side = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
            tag = "win" if pos.profit >= 0 else "loss"
            self.tv_trades.insert("", "end", values=(
                pos.ticket, pos.symbol, side, pos.volume,
                f"{entry:.5f}", f"{pos.sl:.5f}", f"{pos.tp:.5f}",
                f"{rr_init:.2f}", f"{cur:.5f}",
                f"{r_now:+.2f}R", f"{pos.profit:+.2f}", stg
            ), tags=(tag,))
        self.tv_trades.tag_configure("win", foreground="#7ee787")
        self.tv_trades.tag_configure("loss", foreground="#f85149")

    def update_scan(self):
        for r in self.tv_scan.get_children():
            self.tv_scan.delete(r)
        scan = self.engine.last_scan_info
        rows = []
        for sym in self.engine.symbols:
            info = scan.get(sym, {})
            score = sum([1 if info.get(k) else 0 for k in ("bias", "sweep", "choch", "fvg")])
            if info.get("fvg") and info.get("rr"):
                status, tag = "READY -> FIRING", "ready"
            elif info.get("choch"):
                status, tag = "3/4 - need FVG", "watch"
            elif info.get("sweep"):
                status, tag = "2/4 - need CHoCH", "watch"
            elif info.get("bias"):
                status, tag = "1/4 - need sweep", "neutral"
            else:
                status, tag = "0/4 - no bias", "idle"
            rows.append((score, sym, info, status, tag))
        rows.sort(key=lambda r: -r[0])
        for score, sym, info, status, tag in rows:
            self.tv_scan.insert("", "end", values=(
                sym, info.get("bias") or "-",
                "YES" if info.get("sweep") else "no",
                "YES" if info.get("choch") else "no",
                "YES" if info.get("fvg") else "no",
                f"{score}/4", info.get("rr") or "-",
                spread_points(sym), status,
            ), tags=(tag,))
        self.tv_scan.tag_configure("ready", foreground="#7ee787")
        self.tv_scan.tag_configure("watch", foreground="#58a6ff")
        self.tv_scan.tag_configure("neutral", foreground="#e6edf3")
        self.tv_scan.tag_configure("idle", foreground="#6e7681")

    def update_log(self):
        for r in self.tv_log.get_children():
            self.tv_log.delete(r)
        log = load_trade_log()
        for t in reversed(log[-100:]):
            pnl = t.get("pnl") or 0
            res = "WIN" if pnl > 0 else "LOSS"
            tag = "win" if pnl > 0 else "loss"
            self.tv_log.insert("", "end", values=(
                t.get("closed_at", "")[:19], t.get("symbol", ""), t.get("side", ""),
                f"{t.get('entry', 0):.5f}", f"{t.get('sl', 0):.5f}", f"{t.get('tp', 0):.5f}",
                f"{pnl:+.2f}", res
            ), tags=(tag,))
        self.tv_log.tag_configure("win", foreground="#7ee787")
        self.tv_log.tag_configure("loss", foreground="#f85149")

    def on_close(self):
        self.engine.stop()
        time.sleep(0.3)
        try: mt5.shutdown()
        except Exception: pass
        self.root.destroy()


# ----- Main -----
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-gui", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("  EARN BOT FUNDED - Prop Firm Edition")
    print("                    made by @codex_here")
    print("=" * 70)
    print(f"  Risk per trade        : {RISK_PERCENT}%")
    print(f"  Daily loss limit      : -{DAILY_LOSS_LIMIT_PCT}%")
    print(f"  Max drawdown          : -{MAX_DRAWDOWN_PCT}% from peak")
    print(f"  Max concurrent trades : {MAX_OPEN_TRADES}")
    print(f"  Min R:R               : {MIN_RR_TO_TARGET}")
    print(f"  Friday EOD close      : {WEEKEND_CLOSE_HOUR_UTC}:00 UTC")
    print("=" * 70)
    print()

    acc, status = mt5_connect()
    if acc is None:
        print(f"[!] Login failed: {status}")
        sys.exit(1)
    print(f"[+] Logged in: {acc.login} | Balance: {acc.balance:.2f} {acc.currency}")
    print(f"    Server: {acc.server} | Leverage: 1:{acc.leverage}")
    term = mt5.terminal_info()
    if term:
        print(f"    AutoTrading: {'ON' if term.trade_allowed else 'OFF'}")
    print()

    engine = BotEngine()
    engine.resolve_symbols()
    if not engine.symbols:
        print("[!] No tradable symbols.")
        mt5.shutdown()
        sys.exit(1)
    engine.start()

    if args.no_gui or not HAS_TK:
        print("[*] Headless mode. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(60)
                today_dollar, today_pct = calc_today_pnl()
                rate, w, l = calc_winrate()
                pnl = calc_total_pnl()
                print(f"[stat] Today {today_pct:+.2f}% ({today_dollar:+.2f}) | "
                      f"WinRate {rate:.1f}% ({w}W/{l}L) | Total {pnl:+.2f}")
        except KeyboardInterrupt:
            print("\n[*] Stopping...")
        finally:
            engine.stop()
            mt5.shutdown()
    else:
        root = tk.Tk()
        Dashboard(root, engine)
        root.mainloop()


if __name__ == "__main__":
    main()
