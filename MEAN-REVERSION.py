"""
   anony_v5  -   MEAN-REVERSION  +  PROFIT-DIRECTION TRAILING  - @codex_here
   Forex - BTC - ETH - Gold - Silver
   Auto-Detect MT5  |  Auto Trade  |  Rule-based Exit  |  Live GUI

   DECISION (data-driven):
     Entry  : RSI(2) mean-reversion
     Exit   : SMA(5) cross  OR  max-hold bars   (pure mean-reversion exit)
     Safety : ATR(14) * ATR_SL_MULT protective stop  (caps the rare big loss)
     NEW    : profit-direction TRAILING SL + TRAILING TP
              - SL only moves TOWARD profit (never toward loss)
              - once in profit, SL is pulled to break-even then trails
              - TP is pushed further in the profit direction so winners run

   v5 CHANGES vs v4
     - AUDJPY removed (worst pair in live history: -$79, ~24% win rate)
     - RISK_PERCENT raised 2.0 -> 3.0
     - added manage_trailing(): SL/TP trail in the PROFIT direction only

   ENTRY RULES
     Trend filter : Close > SMA(200) -> only BUY ; Close < SMA(200) -> only SELL
     BUY  entry   : RSI(2) < 10
     SELL entry   : RSI(2) > 90
     Exit (BUY)   : last close > SMA(5)  OR  max-hold  OR  ATR/trailing SL
     Exit (SELL)  : last close < SMA(5)  OR  max-hold  OR  ATR/trailing SL

   NOTE: High win rate => small per-trade edge. USE A LOW-SPREAD BROKER; spread/
         commission can erase the edge. Test on DEMO first. H1/H4 are safest.

HOW TO USE:
  1.  pip install MetaTrader5 pandas numpy colorama pywin32
  2.  Open MT5 terminal, log in, enable Algo Trading
  3.  python rsi2_meanreversion_bot.py            <- GUI mode
      python rsi2_meanreversion_bot.py --console  <- text mode
"""

# ---------------------------------------------------------------------------
#  DEFENSIVE IMPORTS
# ---------------------------------------------------------------------------
import sys as _sys, time as _time

def _critical(msg, hint=""):
    print("\n" + "=" * 64)
    print(" [CRITICAL ERROR] " + msg)
    print("=" * 64)
    if hint:
        for line in hint.splitlines():
            print("  " + line)
    print("\n  Window stays open 180s...")
    try:    _time.sleep(180)
    except: pass
    _sys.exit(1)

try:
    import MetaTrader5 as mt5
except Exception as _e:
    _critical(
        f"MetaTrader5 load failed: {_e}",
        "Run:  pip install MetaTrader5 pandas numpy colorama pywin32\n"
        "MT5 terminal must be installed and running on this machine."
    )

try:
    import pandas as pd
    import numpy as np
except Exception as _e:
    _critical(f"pandas/numpy missing: {_e}", "Run:  pip install pandas numpy")

try:
    import time, csv, os, sys, threading
    from datetime import datetime
    from concurrent.futures import ThreadPoolExecutor, as_completed
except Exception as _e:
    _critical(f"Standard library error: {_e}")

# ---------------------------------------------------------------------------
#  THREADING & SHARED STATE
# ---------------------------------------------------------------------------
_STATE_LOCK = threading.Lock()
_STOP_EVENT = threading.Event()

SESSION = {
    "start_time": time.time(), "scans": 0, "last_scan_sec": 0.0,
    "total_scan_sec": 0.0, "trades_placed": 0, "connected": False,
    "account_info": None, "watchlist": [], "open_positions": [],
    "log_lines": [], "scan_num": 0,
}

def _push_log(line):
    with _STATE_LOCK:
        SESSION["log_lines"].append(
            f"{datetime.now().strftime('%H:%M:%S')}  {line}")
        if len(SESSION["log_lines"]) > 300:
            SESSION["log_lines"] = SESSION["log_lines"][-300:]

# ---------------------------------------------------------------------------
#  COLORAMA (optional)
# ---------------------------------------------------------------------------
try:
    from colorama import init as _cinit, Fore, Style
    _cinit(autoreset=True)
except Exception:
    class _NC:
        def __getattr__(self, _): return ""
    Fore = Style = _NC()

C = {
    "reset": Style.RESET_ALL, "bold": Style.BRIGHT,
    "green": Fore.GREEN + Style.BRIGHT, "red": Fore.RED + Style.BRIGHT,
    "yellow": Fore.YELLOW + Style.BRIGHT, "cyan": Fore.CYAN + Style.BRIGHT,
    "blue": Fore.BLUE + Style.BRIGHT, "magenta": Fore.MAGENTA + Style.BRIGHT,
    "white": Fore.WHITE + Style.BRIGHT, "gray": Fore.WHITE,
    "gold": Fore.YELLOW, "dim": Style.DIM,
}
def clr(text, color): return C.get(color, "") + str(text) + Style.RESET_ALL

try:
    import winreg
    WINDOWS = True
except ImportError:
    WINDOWS = False

# ---------------------------------------------------------------------------
#  *  SETTINGS
# ---------------------------------------------------------------------------
RISK_PERCENT       = 3.0      # % balance risked per trade (was 2.0 in v4)
SCAN_INTERVAL      = 5        # seconds between scans
DAILY_MAX_LOSS_PC  = 5.0      # daily max loss % -> stop trading
MAX_OPEN_POSITIONS = 999

MAGIC          = 202540
JOURNAL_FILE   = "trade_journal_rsi2.csv"
SCAN_WORKERS   = 12

# ---- RSI(2) mean-reversion parameters ----
RSI_PERIOD    = 2
RSI_BUY       = 10        # BUY when RSI2 < this
RSI_SELL      = 90        # SELL when RSI2 > this
SMA_TREND     = 200       # trend filter
SMA_EXIT      = 5         # mean-reversion exit line
ATR_PERIOD    = 14
ATR_SL_MULT   = 3.0       # protective SL = ATR * this
MAX_HOLD_BARS = 12        # force-exit after this many bars
RSI_NEAR      = 5         # watchlist: RSI within this of a threshold

# ---- Trailing SL / TP  (PROFIT DIRECTION ONLY) ----
TRAIL_ENABLED      = True
TRAIL_START_ATR    = 1.0   # start trailing after price moved this many ATR in profit
TRAIL_SL_ATR_MULT  = 2.0   # trailing SL distance = ATR * this (behind price)
TRAIL_TP_ATR_MULT  = 4.0   # trailing TP distance = ATR * this (ahead of price)
TRAIL_MIN_STEP_ATR = 0.10  # only modify if improvement > this * ATR (anti-spam)
TRAIL_BREAKEVEN    = True  # snap SL to >= entry once trailing activates

TIMEFRAMES = {
    "M15": mt5.TIMEFRAME_M15,
    "H1" : mt5.TIMEFRAME_H1,
    "H4" : mt5.TIMEFRAME_H4,
}
TF_MINUTES = {"M15": 15, "H1": 60, "H4": 240}

# Profitable pairs only (based on live trade history analysis).
# AUDJPY removed in v5: it was the single worst pair (-$79, ~24% win rate).
PREFERRED = {"USDJPY", "USDCAD", "AUDUSD", "CADJPY"}

SYMBOLS = [
    "USDJPY", "USDCAD", "AUDUSD", "CADJPY",
]

FILLING_MODES = [
    mt5.ORDER_FILLING_IOC,
    mt5.ORDER_FILLING_FOK,
    mt5.ORDER_FILLING_RETURN,
]

_SESSION_START_BALANCE = None


# ---------------------------------------------------------------------------
#  MT5 CONNECTION
# ---------------------------------------------------------------------------
def load_settings():
    return (RISK_PERCENT, SCAN_INTERVAL)

def wait_for_mt5_and_connect(max_retries=10, wait_sec=10):
    for attempt in range(1, max_retries + 1):
        print(clr(f"\r  Detecting MT5... #{attempt}/{max_retries}", "cyan"),
              end="", flush=True)
        if mt5.initialize():
            acc = mt5.account_info()
            if acc is not None and acc.login:
                print()
                with _STATE_LOCK:
                    SESSION["connected"] = True
                _push_log(f"[CONNECT] MT5 found - account={acc.login} server={acc.server}")
                return True
            try: mt5.shutdown()
            except: pass
            print()
            print(clr("  [WARN] MT5 open but not logged in - log in to MT5...", "yellow"))
        else:
            _, err_msg = mt5.last_error()
            print(clr(f"\r  MT5 not found ({err_msg}) - retry in {wait_sec}s...",
                      "yellow"), end="", flush=True)
        time.sleep(wait_sec)
    print()
    print(clr(f"  [ERROR] MT5 not found after {max_retries} tries.", "red"))
    return False

def _ensure_connected():
    try:
        if mt5.terminal_info() is None:
            _push_log("[RECONNECT] MT5 disconnected - retrying...")
            mt5.shutdown()
            if mt5.initialize():
                acc = mt5.account_info()
                if acc:
                    with _STATE_LOCK:
                        SESSION["connected"] = True
                        SESSION["account_info"] = acc
                    _push_log(f"[RECONNECT] OK - {acc.login}")
                    return True
            with _STATE_LOCK:
                SESSION["connected"] = False
            _push_log("[RECONNECT] FAIL - will retry next scan")
            return False
        return True
    except Exception as e:
        _push_log(f"[RECONNECT ERR] {e}")
        return False


# ---------------------------------------------------------------------------
#  WINDOWS STARTUP
# ---------------------------------------------------------------------------
def register_startup():
    if not WINDOWS:
        return
    try:
        script_path = os.path.abspath(sys.argv[0])
        cmd = f'"{sys.executable}" "{script_path}"'
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AnonyRSI2Bot", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print(clr("  [OK] Registered in Windows Startup!", "green"))
    except Exception as e:
        print(clr(f"  [WARN] Startup register failed: {e}", "yellow"))


# ---------------------------------------------------------------------------
#  BANNER
# ---------------------------------------------------------------------------
def print_banner():
    w = 62
    lines = [
        ("anony_v5  -  RSI(2) MEAN-REVERSION + TRAILING", "gold"),
        ("Forex - Crypto - Gold - Silver", "cyan"),
        ("Auto-Detect MT5 | Auto Trade | Trailing Exit | GUI", "gray"),
        ("", ""),
        ("*  HIGHEST WIN RATE config (~66% backtest)  *", "green"),
        ("BUY: RSI2<10 & price>SMA200  |  SELL: RSI2>90 & price<SMA200", "yellow"),
        ("Exit: SMA5 / max-hold / ATR SL  +  profit-only trailing", "yellow"),
        ("", ""),
        ("Made by  @codex_here", "magenta"),
    ]
    print()
    print(clr("+" + "=" * w + "+", "cyan"))
    for text, color in lines:
        if not text:
            print(clr("|" + " " * w + "|", "cyan"))
        else:
            pad = (w - len(text)) // 2
            print(clr("|", "cyan") + " " * pad + clr(text, color)
                  + " " * (w - pad - len(text)) + clr("|", "cyan"))
    print(clr("+" + "=" * w + "+", "cyan"))

def _fmt_uptime(secs):
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h: return f"{h}h {m:02d}m {s:02d}s"
    if m: return f"{m}m {s:02d}s"
    return f"{s}s"


# ---------------------------------------------------------------------------
#  JOURNAL
# ---------------------------------------------------------------------------
def _read_today_journal_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    n = wins = losses = 0
    pnl_total = 0.0
    if not os.path.exists(JOURNAL_FILE): return n, wins, losses, pnl_total
    try:
        with open(JOURNAL_FILE, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("Date") != today: continue
                n += 1
                try:    pnl = float(row.get("Profit_Loss", 0) or 0)
                except: pnl = 0.0
                pnl_total += pnl
                if pnl > 0:   wins += 1
                elif pnl < 0: losses += 1
    except Exception: pass
    return n, wins, losses, pnl_total

def _read_all_journal_stats():
    n = wins = losses = be = 0
    pnl_total = 0.0
    if not os.path.exists(JOURNAL_FILE): return n, wins, losses, be, pnl_total
    try:
        with open(JOURNAL_FILE, newline="") as f:
            for row in csv.DictReader(f):
                n += 1
                try:    pnl = float(row.get("Profit_Loss", 0) or 0)
                except: pnl = 0.0
                pnl_total += pnl
                if pnl > 0:   wins += 1
                elif pnl < 0: losses += 1
                else:         be += 1
    except Exception: pass
    return n, wins, losses, be, pnl_total

def _read_recent_journal_rows(limit=20):
    if not os.path.exists(JOURNAL_FILE): return []
    rows = []
    try:
        with open(JOURNAL_FILE, newline="") as f:
            rows = list(csv.DictReader(f))
    except Exception: pass
    return rows[-limit:]

def setup_journal():
    if not os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, "w", newline="") as f:
            csv.writer(f).writerow([
                "Date", "Time", "Symbol", "Timeframe", "Direction",
                "Entry", "SL", "Lot", "RSI2", "ATR",
                "Status", "Profit_Loss", "Notes"
            ])

def log_trade(symbol, tf, direction, entry, sl, lot, rsi_val, atr,
              status="OPEN", pnl=0, notes=""):
    now = datetime.now()
    with open(JOURNAL_FILE, "a", newline="") as f:
        csv.writer(f).writerow([
            now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
            symbol, tf, direction, round(entry, 5), round(sl, 5),
            lot, round(rsi_val, 1), round(atr, 5),
            status, round(pnl, 2), notes
        ])


# ---------------------------------------------------------------------------
#  DAILY LOSS GUARD
# ---------------------------------------------------------------------------
def _daily_loss_hit():
    global _SESSION_START_BALANCE
    try:
        acc = mt5.account_info()
        if acc is None: return False
        if _SESSION_START_BALANCE is None:
            _SESSION_START_BALANCE = acc.balance
            return False
        loss_pc = (_SESSION_START_BALANCE - acc.balance) / _SESSION_START_BALANCE * 100
        if loss_pc >= DAILY_MAX_LOSS_PC:
            _push_log(f"[DAILY LIMIT] -{loss_pc:.1f}% - trading stopped "
                      f"(limit={DAILY_MAX_LOSS_PC}%)")
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
#  CANDLE FETCH + INDICATORS
# ---------------------------------------------------------------------------
def get_candles(symbol, timeframe, count=300):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

def _rsi(series, period):
    delta = series.diff()
    up = delta.clip(lower=0)
    dn = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_dn = dn.ewm(alpha=1 / period, adjust=False).mean()
    rs = roll_up / roll_dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)

def _atr(df, period):
    h = df["high"]; l = df["low"]; c = df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def analyze(df_closed):
    """Latest indicator values on the last CLOSED candle."""
    if df_closed is None or len(df_closed) < SMA_TREND + 5:
        return None
    close = df_closed["close"]
    rsi = _rsi(close, RSI_PERIOD)
    sma_trend = close.rolling(SMA_TREND).mean()
    sma_exit = close.rolling(SMA_EXIT).mean()
    atr = _atr(df_closed, ATR_PERIOD)
    return {
        "close": float(close.iloc[-1]),
        "rsi": float(rsi.iloc[-1]),
        "sma_tr": float(sma_trend.iloc[-1]),
        "sma_ex": float(sma_exit.iloc[-1]),
        "atr": float(atr.iloc[-1]),
    }


def generate_signal(ind):
    """RSI(2) mean-reversion entry. Returns BUY / SELL / None."""
    if ind is None or np.isnan(ind["sma_tr"]) or ind["atr"] <= 0:
        return None
    up_trend = ind["close"] > ind["sma_tr"]
    if up_trend and ind["rsi"] < RSI_BUY:
        return "BUY"
    if (not up_trend) and ind["rsi"] > RSI_SELL:
        return "SELL"
    return None


# ---------------------------------------------------------------------------
#  ORDER MANAGEMENT
# ---------------------------------------------------------------------------
def _round_price(info, price):
    return round(float(price), int(info.digits))

def _enforce_stops(info, direction, price, sl):
    stops_level = int(getattr(info, "trade_stops_level", 0) or 0)
    spread = int(getattr(info, "spread", 0) or 0)
    min_pts = max(stops_level, spread + 20, 20)
    min_dist = min_pts * info.point
    if direction == "BUY":
        if (price - sl) < min_dist:
            sl = price - min_dist
    else:
        if (sl - price) < min_dist:
            sl = price + min_dist
    return sl

def calculate_lot(symbol, entry, sl, risk_percent, already_risked_money=0.0):
    acc = mt5.account_info()
    info = mt5.symbol_info(symbol)
    if acc is None or info is None:
        return 0.01
    available = max(0.0, acc.equity - already_risked_money)
    risk_money = available * (risk_percent / 100)
    if risk_money <= 0:
        return info.volume_min
    tick_value = info.trade_tick_value
    tick_size = info.trade_tick_size or info.point
    if not tick_value or not tick_size:
        return info.volume_min
    sl_distance = abs(entry - sl)
    if sl_distance <= 0:
        return info.volume_min
    loss_per_lot = (sl_distance / tick_size) * tick_value
    if loss_per_lot <= 0:
        return info.volume_min
    step = info.volume_step or 0.01
    lot = round(round((risk_money / loss_per_lot) / step) * step, 2)
    return max(info.volume_min, min(lot, info.volume_max))

def place_order(symbol, direction, sl, lot, tf_name):
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None:
        _push_log(f"[ORDER ERR] {symbol} - info/tick None")
        return None, "no_info_or_tick"
    price = tick.ask if direction == "BUY" else tick.bid
    if price <= 0:
        return None, "invalid_price"
    sl = _enforce_stops(info, direction, price, sl)
    price = _round_price(info, price)
    sl = _round_price(info, sl)
    step = info.volume_step or 0.01
    lot = round(round(max(info.volume_min,
                          min(float(lot), info.volume_max)) / step) * step, 2)
    otype = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    _push_log(f"[ORDER TRY] {symbol} {direction} price={price} sl={sl} lot={lot}")
    last_result = None
    last_err = "no attempt"
    for fmode in FILLING_MODES:
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
            "volume": float(lot), "type": otype, "price": price,
            "sl": sl, "tp": 0.0, "deviation": 30, "magic": MAGIC,
            "comment": f"RSI2_{tf_name}", "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": fmode,
        }
        result = mt5.order_send(req)
        last_result = result
        if result is None:
            last_err = f"fmode={fmode} -> None err={mt5.last_error()}"
            continue
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return result, "ok"
        last_err = (f"fmode={fmode} rc={result.retcode} "
                    f"'{getattr(result, 'comment', '')}'")
        _push_log(f"[ORDER WARN] {symbol} fmode={fmode} rc={result.retcode} - next...")
    _push_log(f"[ORDER FAIL] {symbol} all modes failed. Last: {last_err}")
    return last_result, last_err

def _our_positions():
    all_pos = mt5.positions_get()
    if not all_pos: return []
    return [p for p in all_pos if p.magic == MAGIC]

def is_already_open(symbol):
    pos = mt5.positions_get(symbol=symbol)
    if not pos: return False
    return any(p.magic == MAGIC for p in pos)

def close_position(pos, reason=""):
    info = mt5.symbol_info(pos.symbol)
    tick = mt5.symbol_info_tick(pos.symbol)
    if info is None or tick is None:
        return False
    price = tick.bid if pos.type == 0 else tick.ask
    otype = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
    for fmode in FILLING_MODES:
        cr = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol,
            "volume": pos.volume, "type": otype, "position": pos.ticket,
            "price": _round_price(info, price), "deviation": 30,
            "magic": MAGIC, "comment": f"exit_{reason}"[:30],
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": fmode,
        })
        if cr and cr.retcode == mt5.TRADE_RETCODE_DONE:
            _push_log(f"[EXIT] {pos.symbol} closed ({reason}) pnl={pos.profit:+.2f}")
            return True
    _push_log(f"[EXIT FAIL] {pos.symbol} could not close ({reason})")
    return False


def _modify_sltp(pos, new_sl, new_tp):
    """Send an SLTP modification for an open position."""
    info = mt5.symbol_info(pos.symbol)
    if info is None:
        return False
    r = mt5.order_send({
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   pos.symbol,
        "position": pos.ticket,
        "sl":       _round_price(info, new_sl),
        "tp":       _round_price(info, new_tp),
        "magic":    MAGIC,
    })
    return bool(r and r.retcode == mt5.TRADE_RETCODE_DONE)


def _tf_of_position(pos):
    """Recover the timeframe a position was opened on, from its comment."""
    comment = getattr(pos, "comment", "") or ""
    for t in TIMEFRAMES:
        if comment.endswith(t):
            return t
    return "H1"


def manage_trailing():
    """Trail SL and TP in the PROFIT direction ONLY.

       BUY  -> SL only moves UP (toward profit), TP pushed further UP.
       SELL -> SL only moves DOWN (toward profit), TP pushed further DOWN.
       SL never moves toward a loss. Once trailing activates, SL is also
       snapped to at least break-even (entry) if TRAIL_BREAKEVEN is on.
    """
    if not TRAIL_ENABLED:
        return
    for pos in _our_positions():
        sym  = pos.symbol
        tick = mt5.symbol_info_tick(sym)
        info = mt5.symbol_info(sym)
        if tick is None or info is None:
            continue

        tf_name = _tf_of_position(pos)
        tf_code = TIMEFRAMES.get(tf_name, mt5.TIMEFRAME_H1)
        df = get_candles(sym, tf_code, count=ATR_PERIOD + 30)
        if df is None or len(df) < ATR_PERIOD + 2:
            continue
        atr = float(_atr(df.iloc[:-1], ATR_PERIOD).iloc[-1])
        if atr <= 0:
            continue

        cur_sl = pos.sl or 0.0
        cur_tp = pos.tp or 0.0
        entry  = pos.price_open
        step   = TRAIL_MIN_STEP_ATR * atr

        if pos.type == 0:                       # BUY -> profit is UP
            price = tick.bid
            if price - entry < TRAIL_START_ATR * atr:
                continue                        # not enough profit yet
            new_sl = price - TRAIL_SL_ATR_MULT * atr
            if TRAIL_BREAKEVEN:
                new_sl = max(new_sl, entry)     # never below break-even
            new_sl = _enforce_stops(info, "BUY", price, new_sl)
            new_tp = price + TRAIL_TP_ATR_MULT * atr
            sl_ok = new_sl > cur_sl + step      # only toward profit (up)
            tp_ok = new_tp > cur_tp + step      # push target further up
            if sl_ok or tp_ok:
                final_sl = new_sl if sl_ok else cur_sl
                final_tp = new_tp if tp_ok else cur_tp
                if _modify_sltp(pos, final_sl, final_tp):
                    _push_log(f"[TRAIL] {sym} BUY  SL->{final_sl:.5f} TP->{final_tp:.5f}")

        else:                                   # SELL -> profit is DOWN
            price = tick.ask
            if entry - price < TRAIL_START_ATR * atr:
                continue
            new_sl = price + TRAIL_SL_ATR_MULT * atr
            if TRAIL_BREAKEVEN:
                new_sl = min(new_sl, entry)     # never above break-even
            new_sl = _enforce_stops(info, "SELL", price, new_sl)
            new_tp = price - TRAIL_TP_ATR_MULT * atr
            sl_ok = (cur_sl == 0.0) or (new_sl < cur_sl - step)   # only toward profit (down)
            tp_ok = (cur_tp == 0.0) or (new_tp < cur_tp - step)   # push target further down
            if sl_ok or tp_ok:
                final_sl = new_sl if sl_ok else cur_sl
                final_tp = new_tp if tp_ok else cur_tp
                if _modify_sltp(pos, final_sl, final_tp):
                    _push_log(f"[TRAIL] {sym} SELL SL->{final_sl:.5f} TP->{final_tp:.5f}")


def manage_exits():
    """Rule-based mean-reversion exit (SMA5 cross) + max-hold for each position."""
    for pos in _our_positions():
        sym = pos.symbol
        tf_name = _tf_of_position(pos)
        tf_code = TIMEFRAMES.get(tf_name, mt5.TIMEFRAME_H1)
        df = get_candles(sym, tf_code, count=SMA_TREND + 20)
        if df is None or len(df) < SMA_EXIT + 2:
            continue
        df_closed = df.iloc[:-1]
        last_close = float(df_closed["close"].iloc[-1])
        sma_ex = float(df_closed["close"].rolling(SMA_EXIT).mean().iloc[-1])

        held_bars = 0
        try:
            open_dt = datetime.fromtimestamp(pos.time)
            mins = (datetime.now() - open_dt).total_seconds() / 60.0
            held_bars = int(mins // TF_MINUTES.get(tf_name, 60))
        except Exception:
            pass

        if pos.type == 0:   # BUY
            if last_close > sma_ex:
                close_position(pos, "SMA5"); continue
        else:               # SELL
            if last_close < sma_ex:
                close_position(pos, "SMA5"); continue
        if held_bars >= MAX_HOLD_BARS:
            close_position(pos, "maxhold")


# ---------------------------------------------------------------------------
#  SCAN LOGIC
# ---------------------------------------------------------------------------
def _scan_one_pair(symbol, tf_name, tf_code):
    try:
        if not mt5.symbol_select(symbol, True):
            return None
        df = get_candles(symbol, tf_code, count=SMA_TREND + 30)
        if df is None or len(df) < SMA_TREND + 5:
            return None
        df_closed = df.iloc[:-1].reset_index(drop=True)
        ind = analyze(df_closed)
        if ind is None:
            return None
        direction = generate_signal(ind)
        if direction is None:
            up_trend = ind["close"] > ind["sma_tr"]
            near = None
            if up_trend and ind["rsi"] < RSI_BUY + RSI_NEAR:
                near = ("BUY", ind["rsi"])
            elif (not up_trend) and ind["rsi"] > RSI_SELL - RSI_NEAR:
                near = ("SELL", ind["rsi"])
            if near:
                return {"type": "watch", "symbol": symbol, "tf": tf_name,
                        "rsi": ind["rsi"], "trend": "UP" if up_trend else "DN",
                        "hint": near[0]}
            return None

        if direction == "BUY":
            sl = ind["close"] - ATR_SL_MULT * ind["atr"]
        else:
            sl = ind["close"] + ATR_SL_MULT * ind["atr"]

        return {"type": "signal", "symbol": symbol, "tf": tf_name,
                "direction": direction, "entry": ind["close"], "sl": sl,
                "rsi": ind["rsi"], "atr": ind["atr"]}
    except Exception as e:
        return {"type": "error", "symbol": symbol, "tf": tf_name, "error": str(e)}


def scan_all_symbols(scan_num, risk_percent):
    if not _ensure_connected():
        _push_log(f"[SCAN #{scan_num}] Skipped - MT5 not connected")
        return
    if _daily_loss_hit():
        _push_log(f"[SCAN #{scan_num}] Skipped - daily loss limit hit")
        return

    t0 = time.time()
    signals = watch = 0
    watch_list = []
    signal_results = []

    tasks = [(sym, tfn, tfc) for sym in SYMBOLS for tfn, tfc in TIMEFRAMES.items()]
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as ex:
        futures = {ex.submit(_scan_one_pair, s, tn, tc): None
                   for s, tn, tc in tasks}
        for fut in as_completed(futures):
            r = fut.result()
            if r is None: continue
            t = r["type"]
            if t == "watch":
                watch += 1; watch_list.append(r)
            elif t == "signal":
                signal_results.append(r)
            elif t == "error":
                _push_log(f"[WARN] {r['symbol']} [{r['tf']}] {r['error']}")

    committed_risk = 0.0
    for r in signal_results:
        symbol = r["symbol"]; tf_name = r["tf"]
        direction = r["direction"]; signals += 1
        flag = "PREFERRED" if symbol in PREFERRED else "ok"
        _push_log(f"[SIGNAL] {symbol} {tf_name} {direction} "
                  f"RSI2={r['rsi']:.1f} ({flag})")

        if is_already_open(symbol):
            _push_log(f"[SKIP] {symbol} - position already open")
            continue

        entry = r["entry"]; sl = r["sl"]
        lot = calculate_lot(symbol, entry, sl, risk_percent, committed_risk)
        result, status = place_order(symbol, direction, sl, lot, tf_name)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            _push_log(f"[ORDER OK] {symbol} ticket=#{result.order} lot={lot}")
            log_trade(symbol, tf_name, direction, entry, sl, lot,
                      r["rsi"], r["atr"], notes=f"Auto|{tf_name}|Scan#{scan_num}")
            with _STATE_LOCK:
                SESSION["trades_placed"] += 1
            info_tmp = mt5.symbol_info(symbol)
            if info_tmp:
                ts = info_tmp.trade_tick_size or info_tmp.point
                tv = info_tmp.trade_tick_value
                if ts and tv:
                    committed_risk += lot * (abs(entry - sl) / ts) * tv
        else:
            rc = result.retcode if result else "None"
            _push_log(f"[ORDER FAIL] {symbol} rc={rc} status='{status}'")

    elapsed = time.time() - t0
    with _STATE_LOCK:
        SESSION["scans"] += 1
        SESSION["last_scan_sec"] = elapsed
        SESSION["total_scan_sec"] += elapsed
        SESSION["scan_num"] = scan_num
        SESSION["watchlist"] = watch_list

        pos_snap = []
        for p in _our_positions():
            ep = p.price_open; sl_p = p.sl
            risk = abs(ep - sl_p) if sl_p else 0
            move = ((p.price_current - ep) if p.type == 0 else (ep - p.price_current))
            rr_now = (move / risk) if risk > 0 else 0
            pos_snap.append({
                "symbol": p.symbol, "side": "BUY" if p.type == 0 else "SELL",
                "entry": ep, "now": p.price_current, "sl": sl_p,
                "profit": p.profit, "rr": rr_now, "lot": p.volume,
                "comment": getattr(p, "comment", ""),
            })
        SESSION["open_positions"] = pos_snap
        SESSION["account_info"] = mt5.account_info()

    _push_log(f"[SCAN #{scan_num}] signals={signals} watch={watch} ({elapsed:.2f}s)")
    manage_exits()
    manage_trailing()


# ---------------------------------------------------------------------------
#  STARTUP TEST TRADE
# ---------------------------------------------------------------------------
def run_startup_test_trade():
    TEST_MAGIC = MAGIC + 1
    TEST_SYM = "EURUSD"
    WAIT_SEC = 10
    _push_log("[TEST] Startup test trade...")
    if not mt5.symbol_select(TEST_SYM, True):
        _push_log(f"[TEST] {TEST_SYM} select failed - skip"); return
    info = mt5.symbol_info(TEST_SYM)
    tick = mt5.symbol_info_tick(TEST_SYM)
    if info is None or tick is None:
        _push_log("[TEST] info/tick missing - skip"); return
    lot = info.volume_min
    price = tick.ask
    stops_lv = int(getattr(info, "trade_stops_level", 5) or 5)
    spread = int(getattr(info, "spread", 10) or 10)
    min_dist = max(stops_lv, spread + 20, 20) * info.point
    sl = _round_price(info, price - min_dist * 3)
    tp = _round_price(info, price + min_dist * 3)
    last_result = None
    for fmode in FILLING_MODES:
        r = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": TEST_SYM,
            "volume": float(lot), "type": mt5.ORDER_TYPE_BUY,
            "price": _round_price(info, price), "sl": sl, "tp": tp,
            "deviation": 30, "magic": TEST_MAGIC, "comment": "TEST_v5",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": fmode,
        })
        last_result = r
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            break
    if not last_result or last_result.retcode != mt5.TRADE_RETCODE_DONE:
        _push_log(f"[TEST] FAIL rc={getattr(last_result, 'retcode', 'None')} "
                  f"- AlgoTrading enabled? Err={mt5.last_error()}")
        return
    ticket = last_result.order
    _push_log(f"[TEST] OK BUY #{ticket} lot={lot} - closing in {WAIT_SEC}s...")
    for _ in range(WAIT_SEC):
        if _STOP_EVENT.is_set(): break
        time.sleep(1)
    positions = mt5.positions_get(ticket=ticket) or []
    if not positions:
        all_pos = mt5.positions_get(symbol=TEST_SYM) or []
        positions = [p for p in all_pos if p.magic == TEST_MAGIC]
    if not positions:
        _push_log(f"[TEST] #{ticket} not found to close (TP/SL hit?) - OK"); return
    for pos in positions:
        ctick = mt5.symbol_info_tick(pos.symbol)
        cinf = mt5.symbol_info(pos.symbol)
        if ctick is None: continue
        cr = None
        for fmode in FILLING_MODES:
            cr = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol,
                "volume": pos.volume, "type": mt5.ORDER_TYPE_SELL,
                "position": pos.ticket,
                "price": _round_price(cinf, ctick.bid) if cinf else ctick.bid,
                "deviation": 30, "magic": TEST_MAGIC, "comment": "TEST_close_v5",
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": fmode,
            })
            if cr and cr.retcode == mt5.TRADE_RETCODE_DONE:
                break
        if cr and cr.retcode == mt5.TRADE_RETCODE_DONE:
            _push_log(f"[TEST] OK #{pos.ticket} closed - script works!")
        else:
            rc = cr.retcode if cr else "None"
            _push_log(f"[TEST] Close FAIL #{pos.ticket} rc={rc} "
                      f"- close TEST position manually in MT5")


# ---------------------------------------------------------------------------
#  SCANNER THREAD
# ---------------------------------------------------------------------------
def scanner_worker(risk, interval):
    global _SESSION_START_BALANCE
    print(clr("\n  Scanner thread start - detecting MT5...", "cyan"))
    _push_log("[STARTUP] Looking for MT5...")
    if not wait_for_mt5_and_connect():
        _push_log("[FATAL] MT5 not found - open MT5, log in, restart")
        with _STATE_LOCK:
            SESSION["connected"] = False
        return
    acc = mt5.account_info()
    _SESSION_START_BALANCE = acc.balance
    with _STATE_LOCK:
        SESSION["account_info"] = acc
        SESSION["connected"] = True
    setup_journal()
    _push_log(f"[OK] Connected: account={acc.login} "
              f"balance=${acc.balance:.2f} server={acc.server}")
    term = mt5.terminal_info()
    if term and not term.trade_allowed:
        _push_log("[WARN] AlgoTrading DISABLED in MT5! Click 'Algo Trading'.")
    try:
        run_startup_test_trade()
    except Exception as e:
        _push_log(f"[TEST] Exception: {e}")
    scan_num = 0
    try:
        while not _STOP_EVENT.is_set():
            scan_num += 1
            try:
                scan_all_symbols(scan_num, risk)
            except Exception as e:
                _push_log(f"[ERROR] Scan crash: {e}")
            for _ in range(interval):
                if _STOP_EVENT.is_set(): break
                time.sleep(1)
    finally:
        try: mt5.shutdown()
        except: pass
        _push_log("[SHUTDOWN] Scanner stopped")


# ---------------------------------------------------------------------------
#  GUI DASHBOARD
# ---------------------------------------------------------------------------
class DashboardGUI:
    # ---- v5 modern palette (deep navy + indigo/cyan accents) ----
    BG = "#0a0e17"; PANEL = "#121829"; PANEL_HI = "#1a2236"; BORDER = "#283350"
    PANEL_ALT = "#161d30"   # alternating table row
    LOG_BG = "#070a12"
    FG = "#eef1f8"; DIM = "#8893ad"; GREEN = "#34d399"; RED = "#fb7185"
    YELLOW = "#fbbf24"; BLUE = "#60a5fa"; MAGENTA = "#c084fc"; GOLD = "#fcd34d"
    ACCENT = "#6366f1"; CYAN = "#22d3ee"

    def __init__(self, risk, interval):
        self.cfg = dict(risk=risk, interval=interval)
        import tkinter as tk
        from tkinter import ttk, scrolledtext
        self.tk = tk; self.ttk = ttk; self.ST = scrolledtext.ScrolledText
        self.root = tk.Tk()
        self.root.title("anony_v5 - RSI(2) Mean-Reversion + Trailing")
        self.root.geometry("1300x800")
        self.root.minsize(1100, 700)
        self.root.configure(bg=self.BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self.worker = threading.Thread(
            target=scanner_worker, args=(risk, interval), daemon=True)
        self.worker.start()
        self.root.after(500, self._refresh)

    def _lbl(self, parent, text, fg=None, font=("Segoe UI", 10), bg=None, **kw):
        return self.tk.Label(parent, text=text, fg=fg or self.FG,
                             bg=bg or self.PANEL, font=font, **kw)

    def _section(self, parent, title, color=None):
        color = color or self.ACCENT
        wrap = self.tk.Frame(parent, bg=self.BORDER)
        inner = self.tk.Frame(wrap, bg=self.PANEL)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        hdr = self.tk.Frame(inner, bg=self.PANEL_HI)
        hdr.pack(fill="x")
        # left accent bar
        self.tk.Frame(hdr, bg=color, width=4, height=22).pack(side="left", fill="y")
        self._lbl(hdr, "  " + title.upper(), fg=color,
                  font=("Segoe UI", 10, "bold"), bg=self.PANEL_HI,
                  anchor="w").pack(side="left", pady=6)
        body = self.tk.Frame(inner, bg=self.PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        return wrap, body

    def _make_tree(self, parent, columns, headings, widths):
        ttk = self.ttk
        style = ttk.Style()
        try: style.theme_use("clam")
        except: pass
        style.configure("Tri.Treeview", background=self.PANEL, foreground=self.FG,
                        fieldbackground=self.PANEL, borderwidth=0, rowheight=25,
                        font=("Consolas", 9))
        style.configure("Tri.Treeview.Heading", background=self.PANEL_HI,
                        foreground=self.CYAN, font=("Segoe UI", 9, "bold"),
                        borderwidth=0, relief="flat", padding=(4, 5))
        style.map("Tri.Treeview", background=[("selected", self.ACCENT)],
                  foreground=[("selected", "#ffffff")])
        style.map("Tri.Treeview.Heading", background=[("active", self.BORDER)])
        tree = ttk.Treeview(parent, columns=columns, show="headings",
                            style="Tri.Treeview", height=8)
        for c in columns:
            tree.heading(c, text=headings.get(c, c))
            tree.column(c, width=widths.get(c, 80), anchor="center", stretch=True)
        tree.pack(fill="both", expand=True, side="left")
        vs = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        tree.tag_configure("buy", foreground=self.GREEN)
        tree.tag_configure("sell", foreground=self.RED)
        tree.tag_configure("win", foreground=self.GREEN)
        tree.tag_configure("loss", foreground=self.RED)
        tree.tag_configure("neutral", foreground=self.FG)
        # zebra striping (background only -> coexists with colour tags)
        tree.tag_configure("odd", background=self.PANEL_ALT)
        tree.tag_configure("even", background=self.PANEL)
        return tree

    @staticmethod
    def _stripe(i):
        return "odd" if i % 2 else "even"

    def _build_ui(self):
        tk = self.tk
        # thin accent strip on top
        tk.Frame(self.root, bg=self.ACCENT, height=3).pack(fill="x")
        topbar = tk.Frame(self.root, bg=self.PANEL_HI, height=64)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        # logo block
        logo = tk.Frame(topbar, bg=self.PANEL_HI)
        logo.pack(side="left", padx=(18, 6))
        tk.Label(logo, text="anony", bg=self.PANEL_HI, fg=self.FG,
                 font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(logo, text="v5", bg=self.PANEL_HI, fg=self.ACCENT,
                 font=("Segoe UI", 17, "bold")).pack(side="left", padx=(2, 0))
        tk.Label(topbar, text="RSI(2) MEAN-REVERSION  +  PROFIT TRAILING",
                 bg=self.PANEL_HI, fg=self.DIM,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=6)
        # connection status pill
        pill = tk.Frame(topbar, bg=self.BORDER)
        pill.pack(side="left", padx=16)
        self.lbl_conn = tk.Label(pill, text="  \u25cf  CONNECTING  ",
                                 bg=self.BORDER, fg=self.YELLOW,
                                 font=("Segoe UI", 9, "bold"))
        self.lbl_conn.pack(padx=2, pady=4)
        # right side: clock + account chip
        self.lbl_clock = tk.Label(topbar, text="", bg=self.PANEL_HI, fg=self.DIM,
                                  font=("Consolas", 11, "bold"))
        self.lbl_clock.pack(side="right", padx=16)
        self.lbl_acc = tk.Label(topbar, text="", bg=self.PANEL_HI, fg=self.CYAN,
                                font=("Consolas", 10, "bold"))
        self.lbl_acc.pack(side="right", padx=8)

        main = tk.Frame(self.root, bg=self.BG)
        main.pack(fill="both", expand=True, padx=10, pady=8)
        for col in range(3):
            main.columnconfigure(col, weight=1, uniform="col")
        for row in range(3):
            main.rowconfigure(row, weight=1)

        sw, sb = self._section(main, "STRATEGY LOGIC", color=self.BLUE)
        sw.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        rows = [
            ("Type", "RSI(2) Mean-Reversion"),
            ("Trend", f"Close vs SMA({SMA_TREND})"),
            ("BUY", f"RSI2 < {RSI_BUY} & price > SMA{SMA_TREND}"),
            ("SELL", f"RSI2 > {RSI_SELL} & price < SMA{SMA_TREND}"),
            ("Exit", f"cross SMA({SMA_EXIT}) / {MAX_HOLD_BARS} bars"),
            ("SL", f"ATR({ATR_PERIOD}) x {ATR_SL_MULT} protective"),
            ("Trail", f"SL x{TRAIL_SL_ATR_MULT} / TP x{TRAIL_TP_ATR_MULT} ATR (profit only)"),
            ("Risk", f"{RISK_PERCENT}% balance / trade"),
            ("DailyLim", f"-{DAILY_MAX_LOSS_PC}% balance -> stop"),
            ("Symbols", f"{len(SYMBOLS)} x {', '.join(TIMEFRAMES.keys())}"),
            ("Scan", f"every {SCAN_INTERVAL}s, {SCAN_WORKERS} workers"),
            ("Pairs", "USDJPY USDCAD AUDUSD CADJPY"),
        ]
        for i, (k, v) in enumerate(rows):
            tk.Label(sb, text=k + ":", fg=self.DIM, bg=self.PANEL,
                     font=("Segoe UI", 9), anchor="w", width=9
                     ).grid(row=i, column=0, sticky="w")
            tk.Label(sb, text=v, fg=self.FG, bg=self.PANEL, font=("Segoe UI", 9),
                     anchor="w", justify="left", wraplength=310
                     ).grid(row=i, column=1, sticky="w", padx=4)

        stw, stb = self._section(main, "WIN RATE & P&L", color=self.GREEN)
        stw.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self.stats_labels = {}
        stat_rows = [
            ("All-time trades", "all_n", self.FG),
            ("Win rate", "all_wr", self.GREEN),
            ("Wins / Losses", "all_wl", self.FG),
            ("All-time P&L", "all_pnl", self.GREEN),
            ("", "", self.FG),
            ("Today trades", "today_n", self.FG),
            ("Today win rate", "today_wr", self.GREEN),
            ("Today P&L", "today_pnl", self.GREEN),
            ("Unrealized P&L", "unreal", self.GREEN),
        ]
        for i, (k, key, color) in enumerate(stat_rows):
            if not k:
                tk.Frame(stb, bg=self.PANEL, height=8).grid(row=i, column=0, columnspan=2)
                continue
            tk.Label(stb, text=k + ":", fg=self.DIM, bg=self.PANEL,
                     font=("Segoe UI", 9), anchor="w", width=18
                     ).grid(row=i, column=0, sticky="w", pady=1)
            lbl = tk.Label(stb, text="-", fg=color, bg=self.PANEL,
                           font=("Consolas", 11, "bold"), anchor="w")
            lbl.grid(row=i, column=1, sticky="w", padx=4)
            self.stats_labels[key] = lbl

        aw, ab = self._section(main, "ACCOUNT / SESSION", color=self.GOLD)
        aw.grid(row=0, column=2, sticky="nsew", padx=4, pady=4)
        self.acc_labels = {}
        acc_rows = [
            ("Login", "login", self.FG), ("Server", "server", self.FG),
            ("Balance", "balance", self.FG), ("Equity", "equity", self.FG),
            ("Free margin", "free", self.FG), ("Currency", "currency", self.DIM),
            ("", "", self.FG), ("Uptime", "uptime", self.DIM),
            ("Scans", "scans", self.DIM), ("Last scan", "last_scan", self.DIM),
            ("Avg scan", "avg_scan", self.DIM),
        ]
        for i, (k, key, color) in enumerate(acc_rows):
            if not k:
                tk.Frame(ab, bg=self.PANEL, height=8).grid(row=i, column=0, columnspan=2)
                continue
            tk.Label(ab, text=k + ":", fg=self.DIM, bg=self.PANEL,
                     font=("Segoe UI", 9), anchor="w", width=12
                     ).grid(row=i, column=0, sticky="w", pady=1)
            lbl = tk.Label(ab, text="-", fg=color, bg=self.PANEL,
                           font=("Consolas", 10), anchor="w")
            lbl.grid(row=i, column=1, sticky="w", padx=4)
            self.acc_labels[key] = lbl

        nw, nb = self._section(main, "WATCHLIST - RSI nearing trigger",
                               color=self.YELLOW)
        nw.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.watch_tree = self._make_tree(nb,
            columns=("pair", "tf", "trend", "rsi", "hint"),
            headings={"pair": "Pair", "tf": "TF", "trend": "Trend",
                      "rsi": "RSI2", "hint": "Side"},
            widths={"pair": 80, "tf": 45, "trend": 60, "rsi": 70, "hint": 70})

        pw, pb = self._section(main, "OPEN POSITIONS - live RR / SL / P&L",
                               color=self.GREEN)
        pw.grid(row=1, column=1, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.pos_tree = self._make_tree(pb,
            columns=("pair", "side", "lot", "entry", "now", "sl", "rr", "pnl"),
            headings={"pair": "Pair", "side": "Side", "lot": "Lot",
                      "entry": "Entry", "now": "Price", "sl": "SL",
                      "rr": "RR", "pnl": "P&L"},
            widths={"pair": 82, "side": 52, "lot": 52, "entry": 90, "now": 90,
                    "sl": 90, "rr": 60, "pnl": 82})

        jw, jb = self._section(main, "TRADE JOURNAL - last 20", color=self.MAGENTA)
        jw.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.journal_tree = self._make_tree(jb,
            columns=("date", "time", "pair", "tf", "dir", "entry", "sl",
                     "rsi", "lot", "pnl", "status"),
            headings={"date": "Date", "time": "Time", "pair": "Pair", "tf": "TF",
                      "dir": "Dir", "entry": "Entry", "sl": "SL", "rsi": "RSI2",
                      "lot": "Lot", "pnl": "P&L", "status": "Status"},
            widths={"date": 80, "time": 60, "pair": 70, "tf": 40, "dir": 45,
                    "entry": 80, "sl": 80, "rsi": 50, "lot": 50, "pnl": 65,
                    "status": 60})

        lw, lb = self._section(main, "ACTIVITY LOG", color=self.CYAN)
        lw.grid(row=2, column=2, sticky="nsew", padx=4, pady=4)
        self.log_text = self.ST(lb, bg=self.LOG_BG, fg=self.DIM,
                                font=("Consolas", 9), wrap="word",
                                insertbackground=self.FG, relief="flat",
                                borderwidth=0, highlightthickness=0)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        foot = tk.Frame(self.root, bg=self.PANEL_HI)
        foot.pack(fill="x")
        tk.Label(foot, text="  Made by @codex_here   \u2022   v5 RSI(2) + profit-only trailing"
                            "   \u2022   auto-detects MT5   \u2022   no credentials stored",
                 bg=self.PANEL_HI, fg=self.DIM,
                 font=("Segoe UI", 8)).pack(side="left", pady=4)

    def _refresh(self):
        try: self._refresh_once()
        except Exception as e: _push_log(f"[GUI] refresh err: {e}")
        if not _STOP_EVENT.is_set():
            self.root.after(1000, self._refresh)

    def _refresh_once(self):
        self.lbl_clock.config(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        with _STATE_LOCK:
            connected = SESSION["connected"]
            acc = SESSION["account_info"]
            watch = list(SESSION["watchlist"])
            positions = list(SESSION["open_positions"])
            scans = SESSION["scans"]
            last_scan = SESSION["last_scan_sec"]
            total_scan = SESSION["total_scan_sec"]
            log_lines = list(SESSION["log_lines"])

        self.lbl_conn.config(
            text="  \u25cf  CONNECTED  " if connected else "  \u25cf  CONNECTING  ",
            fg=self.GREEN if connected else self.YELLOW)
        if acc:
            self.lbl_acc.config(
                text=f"#{acc.login}  \u2022  ${acc.balance:,.2f}  \u2022  {acc.server}")
            self.acc_labels["login"].config(text=str(acc.login))
            self.acc_labels["server"].config(text=acc.server)
            self.acc_labels["balance"].config(text=f"${acc.balance:,.2f}")
            self.acc_labels["equity"].config(text=f"${acc.equity:,.2f}")
            self.acc_labels["free"].config(text=f"${acc.margin_free:,.2f}")
            self.acc_labels["currency"].config(text=acc.currency)
        avg = (total_scan / scans) if scans else 0.0
        self.acc_labels["uptime"].config(
            text=_fmt_uptime(time.time() - SESSION["start_time"]))
        self.acc_labels["scans"].config(text=str(scans))
        self.acc_labels["last_scan"].config(text=f"{last_scan:.2f}s")
        self.acc_labels["avg_scan"].config(text=f"{avg:.2f}s")

        n_t, w_t, l_t, pnl_t = _read_today_journal_stats()
        n_a, w_a, l_a, _, pnl_a = _read_all_journal_stats()
        wr_a = (w_a / max(1, w_a + l_a)) * 100 if (w_a + l_a) else 0
        wr_t = (w_t / max(1, w_t + l_t)) * 100 if (w_t + l_t) else 0
        unreal = sum(p["profit"] for p in positions)
        self.stats_labels["all_n"].config(text=str(n_a))
        self.stats_labels["all_wr"].config(text=f"{wr_a:.1f}%",
            fg=self.GREEN if wr_a >= 50 else (self.YELLOW if wr_a >= 35 else self.RED))
        self.stats_labels["all_wl"].config(text=f"{w_a} W  /  {l_a} L")
        self.stats_labels["all_pnl"].config(text=self._money(pnl_a),
            fg=self.GREEN if pnl_a >= 0 else self.RED)
        self.stats_labels["today_n"].config(text=str(n_t))
        self.stats_labels["today_wr"].config(text=f"{wr_t:.1f}%",
            fg=self.GREEN if wr_t >= 50 else (self.YELLOW if wr_t >= 35 else self.RED))
        self.stats_labels["today_pnl"].config(text=self._money(pnl_t),
            fg=self.GREEN if pnl_t >= 0 else self.RED)
        self.stats_labels["unreal"].config(text=self._money(unreal),
            fg=self.GREEN if unreal >= 0 else self.RED)

        self.watch_tree.delete(*self.watch_tree.get_children())
        for i, a in enumerate(sorted(watch, key=lambda x: abs(x["rsi"] - 50), reverse=True)[:30]):
            tag = "buy" if a["hint"] == "BUY" else "sell"
            self.watch_tree.insert("", "end", tags=(tag, self._stripe(i)), values=(
                a["symbol"], a["tf"], a["trend"], f"{a['rsi']:.1f}", a["hint"]))

        self.pos_tree.delete(*self.pos_tree.get_children())
        for i, p in enumerate(positions):
            tag = "win" if p["profit"] >= 0 else "loss"
            self.pos_tree.insert("", "end", tags=(tag, self._stripe(i)), values=(
                p["symbol"], p["side"], f"{p['lot']:.2f}", f"{p['entry']:.5f}",
                f"{p['now']:.5f}", f"{p['sl']:.5f}", f"{p['rr']:+.2f}",
                self._money(p["profit"])))

        rows = _read_recent_journal_rows(20)
        self.journal_tree.delete(*self.journal_tree.get_children())
        for i, row in enumerate(rows[::-1]):
            try: pnl_v = float(row.get("Profit_Loss", 0) or 0)
            except: pnl_v = 0
            tag = "win" if pnl_v > 0 else ("loss" if pnl_v < 0 else "neutral")
            self.journal_tree.insert("", "end", tags=(tag, self._stripe(i)), values=(
                row.get("Date", ""), row.get("Time", ""), row.get("Symbol", ""),
                row.get("Timeframe", ""), row.get("Direction", ""),
                row.get("Entry", ""), row.get("SL", ""), row.get("RSI2", ""),
                row.get("Lot", ""),
                self._money(pnl_v) if pnl_v else "-", row.get("Status", "")))

        new_text = "\n".join(log_lines[-200:])
        cur_text = self.log_text.get("1.0", "end-1c")
        if new_text != cur_text:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.insert("1.0", new_text)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

    @staticmethod
    def _money(x):
        try: x = float(x)
        except: return str(x)
        sign = "+" if x >= 0 else "-"
        return f"{sign}${abs(x):,.2f}"

    def _on_close(self):
        from tkinter import messagebox
        if messagebox.askyesno("Stop Bot?",
                "Stopping disconnects MT5.\n\nOpen positions stay on the broker "
                "(not auto-closed).\n\nStop now?"):
            _STOP_EVENT.set()
            self.root.after(500, self.root.destroy)

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
#  CONSOLE MODE
# ---------------------------------------------------------------------------
def run_console_mode(risk, interval):
    global _SESSION_START_BALANCE
    print(clr("\n  Detecting MT5...", "cyan"))
    if not wait_for_mt5_and_connect():
        print(clr("\n  [ERROR] MT5 not found!", "red"))
        time.sleep(15); return
    acc = mt5.account_info()
    _SESSION_START_BALANCE = acc.balance
    print(clr(f"\n  Account: {acc.login}  Bal: ${acc.balance:,.2f}  "
              f"Server: {acc.server}", "green"))
    term = mt5.terminal_info()
    if term and not term.trade_allowed:
        print(clr("  [WARN] AlgoTrading DISABLED in MT5!", "red"))
    setup_journal()
    try:
        run_startup_test_trade()
    except Exception as e:
        _push_log(f"[TEST] Exception: {e}")
    print(clr("\n  Bot running (console mode). Ctrl+C to stop.\n", "green"))
    scan_num = 0
    try:
        while True:
            scan_num += 1
            scan_all_symbols(scan_num, risk)
            with _STATE_LOCK:
                lines = list(SESSION["log_lines"])
            for line in lines[-10:]:
                print(clr("  " + line, "gray"))
            time.sleep(interval)
    except KeyboardInterrupt:
        print(clr("\n  Stopping...", "yellow"))
        try: mt5.shutdown()
        except: pass


# ---------------------------------------------------------------------------
#  MAIN
# ---------------------------------------------------------------------------
def main():
    print_banner()
    use_console = "--console" in sys.argv
    risk, interval = load_settings()
    if WINDOWS:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "AnonyRSI2Bot")
            winreg.CloseKey(key)
        except FileNotFoundError:
            print(clr("\n  First run - registering in Windows Startup...", "yellow"))
            register_startup()
        except Exception:
            pass
    if use_console:
        run_console_mode(risk, interval)
        return
    try:
        import tkinter
        p = tkinter.Tk(); p.withdraw(); p.destroy()
    except Exception as e:
        print(clr(f"\n  [WARN] tkinter missing ({e}) - using console mode.", "yellow"))
        run_console_mode(risk, interval)
        return
    print(clr("\n  Launching GUI window...", "cyan"))
    print(clr("  (MT5 must be open and logged in. Console: --console)\n", "dim"))
    gui = DashboardGUI(risk, interval)
    gui.run()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        _STOP_EVENT.set()
    except Exception as e:
        import traceback
        print()
        print(clr("=" * 60, "red"))
        print(clr(" [CRASH] Script crashed", "red"))
        print(clr("=" * 60, "red"))
        print(clr(f"\n  {type(e).__name__}: {e}\n", "yellow"))
        traceback.print_exc()
        print(clr("\n  Closing in 60s...", "dim"))
        try: time.sleep(60)
        except: pass
        sys.exit(1)
