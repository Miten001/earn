"""
================================================================================
  EARN SCALPER - HFT-style MT5 Scalping Bot (many trades/min, quick profit)
                          made by @codex_here
================================================================================

Strategy: Multi-pair M1 EMA crossover + RSI momentum scalper
  * Scans 15+ pairs every 1 second
  * EMA(5) crossing EMA(15) + RSI bias filter
  * Spread filter (only trades tight-spread pairs)
  * Tight SL (4 pips), tight TP (5 pips), greedy 60% TP exit
  * Up to 30 concurrent trades, multiple per pair allowed
  * Dashboard with live trades, scanner, win-rate, next setup
  * Auto-attaches to logged-in MT5 (no AutoTrading disable)

Expected: 3-10 trades per minute during volatile sessions
WARNING: Higher trade count = higher spread cost. Use ONLY on tight-spread brokers.

================================================================================
SETUP:
  pip install MetaTrader5 pandas numpy matplotlib
  Login MT5 manually first, AutoTrading ON (Ctrl+E)
  Run: python earn_scalper.py   (or double-click run_scalper.bat)
================================================================================
"""

import sys, os, time, json, threading, queue, argparse
from datetime import datetime, timedelta, timezone
from typing import Optional

# ============================================================================
# >>>>>>>>>>>>>>>>>>>>>>>>>>  CONFIG  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ============================================================================
MT5_LOGIN    = 0      # 0 = use already-logged-in MT5 account (recommended)
MT5_PASSWORD = ""
MT5_SERVER   = ""
MT5_PATH     = ""

# Pairs (high-liquidity, tight-spread)
SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY",
    "USDCHF", "EURAUD", "GBPAUD", "XAUUSD",
    "BTCUSD", "ETHUSD",
]

# Risk per trade
RISK_PERCENT = 1.0          # 1% per trade (HFT = many trades, keep risk low!)
SL_PIPS_FX   = 5            # fx SL in pips
TP_PIPS_FX   = 6            # fx TP in pips (slight RR>1)
SL_USD_GOLD  = 2.0          # gold SL = $2
TP_USD_GOLD  = 2.5          # gold TP = $2.5
SL_USD_BTC   = 100          # BTC SL = $100
TP_USD_BTC   = 130          # BTC TP = $130
SL_USD_ETH   = 8            # ETH SL = $8
TP_USD_ETH   = 10           # ETH TP

# Trade caps
MAX_OPEN_TRADES     = 30    # high cap (HFT style)
MAX_TRADES_PER_PAIR = 3     # multiple per pair allowed
MAGIC_NUMBER        = 555001

# Greedy exit: close trade early at this fraction of TP distance
# e.g. 0.6 = take profit when 60% of TP reached (faster cycle)
GREEDY_EXIT_FRAC = 0.6

# EMA + RSI strategy params
EMA_FAST = 5
EMA_SLOW = 15
RSI_PERIOD = 7
RSI_LONG_FLOOR = 45         # for BUY: RSI must be > this
RSI_SHORT_CEIL = 55         # for SELL: RSI must be < this

# Spread filter (in points; reject if broker spread > this)
MAX_SPREAD_FX     = 20
MAX_SPREAD_GOLD   = 50
MAX_SPREAD_CRYPTO = 5000

# Loop & state
SCAN_INTERVAL_SEC = 1.0     # scan every 1 second (HFT)
STATE_FILE        = "earn_scalper_state.json"
TRADES_LOG_FILE   = "earn_scalper_trades.json"

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


# ----- Indicators -----
def ema(s, p):
    return s.ewm(span=p, adjust=False).mean()


def rsi(s, p=14):
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/p, adjust=False).mean()
    rs = g / l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ----- MT5 helpers -----
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


def get_rates(sym, n=60):
    """Get last N M1 candles."""
    bars = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, n)
    if bars is None or len(bars) < 30:
        return None
    return pd.DataFrame(bars)


def is_crypto(s):
    return any(c in s.upper() for c in ["BTC", "ETH", "XRP", "LTC", "DOGE", "SOL"])


def is_gold(s):
    return "XAU" in s.upper() or "GOLD" in s.upper()


def spread_points(sym):
    info = mt5.symbol_info(sym)
    return info.spread if info else 9999


def open_count(sym=None):
    pos = mt5.positions_get(symbol=sym) if sym else mt5.positions_get()
    if pos is None:
        return 0
    return sum(1 for p in pos if p.magic == MAGIC_NUMBER)


# ----- SL/TP calculation -----
def compute_sl_tp(sym, side, entry):
    """Return (sl, tp) absolute prices for given side."""
    info = mt5.symbol_info(sym)
    if info is None:
        return None, None

    if is_gold(sym):
        sl_dist = SL_USD_GOLD
        tp_dist = TP_USD_GOLD
    elif "BTC" in sym.upper():
        sl_dist = SL_USD_BTC
        tp_dist = TP_USD_BTC
    elif "ETH" in sym.upper():
        sl_dist = SL_USD_ETH
        tp_dist = TP_USD_ETH
    else:
        # forex pip = 0.0001 for non-JPY, 0.01 for JPY
        pip = 0.01 if "JPY" in sym.upper() else 0.0001
        sl_dist = SL_PIPS_FX * pip
        tp_dist = TP_PIPS_FX * pip

    if side == "BUY":
        sl = entry - sl_dist
        tp = entry + tp_dist
    else:
        sl = entry + sl_dist
        tp = entry - tp_dist

    return sl, tp


def calc_lot(sym, entry, sl, risk_pct):
    acc = mt5.account_info()
    info = mt5.symbol_info(sym)
    if acc is None or info is None:
        return 0.0
    risk_money = acc.balance * (risk_pct / 100.0)
    sl_dist = abs(entry - sl)
    if sl_dist <= 0:
        return 0.0
    ts = info.trade_tick_size or info.point
    tv = info.trade_tick_value
    if not ts or not tv:
        return 0.0
    money_per_lot = (sl_dist / ts) * tv
    if money_per_lot <= 0:
        return 0.0
    lot = risk_money / money_per_lot
    step = info.volume_step or 0.01
    lot = round(lot / step) * step
    lot = max(info.volume_min, min(info.volume_max, lot))
    return round(lot, 2)


def place_market_order(sym, side, lot, sl, tp, comment):
    info = mt5.symbol_info(sym)
    tick = mt5.symbol_info_tick(sym)
    if info is None or tick is None or lot <= 0:
        return None
    digits = info.digits
    if side == "BUY":
        price, otype = tick.ask, mt5.ORDER_TYPE_BUY
    else:
        price, otype = tick.bid, mt5.ORDER_TYPE_SELL
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym, "volume": lot, "type": otype,
        "price": round(price, digits),
        "sl": round(sl, digits), "tp": round(tp, digits),
        "deviation": 30, "magic": MAGIC_NUMBER, "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(req)
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        return None
    return r.order


def close_position(pos):
    info = mt5.symbol_info(pos.symbol)
    tick = mt5.symbol_info_tick(pos.symbol)
    if info is None or tick is None:
        return False
    side_close = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": pos.ticket, "symbol": pos.symbol,
        "volume": pos.volume, "type": side_close,
        "price": round(price, info.digits), "deviation": 30,
        "magic": MAGIC_NUMBER, "comment": "GREEDY_TP",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


# ----- State / log -----
def load_json(p, d):
    if os.path.exists(p):
        try:
            with open(p) as f: return json.load(f)
        except Exception: pass
    return d


def save_json(p, o):
    try:
        with open(p, "w") as f: json.dump(o, f)
    except Exception: pass


def load_state(): return load_json(STATE_FILE, {})
def save_state(s): save_json(STATE_FILE, s)


def append_trade_log(e):
    log = load_json(TRADES_LOG_FILE, [])
    log.append(e)
    save_json(TRADES_LOG_FILE, log)


def load_trade_log(): return load_json(TRADES_LOG_FILE, [])


def calc_winrate():
    log = load_trade_log()
    if not log: return 0.0, 0, 0
    wins = sum(1 for t in log if (t.get("pnl") or 0) > 0)
    losses = sum(1 for t in log if (t.get("pnl") or 0) <= 0)
    total = wins + losses
    return ((wins / total * 100) if total else 0.0), wins, losses


def calc_total_pnl():
    return sum((t.get("pnl") or 0) for t in load_trade_log())


# ----- Strategy: EMA+RSI scalp signal -----
def scalp_signal(sym):
    """Return 'BUY' / 'SELL' / None based on EMA cross + RSI."""
    df = get_rates(sym, n=60)
    if df is None:
        return None, None
    df["ef"] = ema(df["close"], EMA_FAST)
    df["es"] = ema(df["close"], EMA_SLOW)
    df["r"] = rsi(df["close"], RSI_PERIOD)
    a, b = df.iloc[-2], df.iloc[-3]
    if pd.isna(a["r"]):
        return None, None
    # Bullish cross + RSI above floor
    if (b["ef"] <= b["es"] and a["ef"] > a["es"] and a["r"] > RSI_LONG_FLOOR):
        return "BUY", round(a["r"], 1)
    # Bearish cross + RSI below ceil
    if (b["ef"] >= b["es"] and a["ef"] < a["es"] and a["r"] < RSI_SHORT_CEIL):
        return "SELL", round(a["r"], 1)
    return None, None


def get_spread_cap(sym):
    if is_crypto(sym): return MAX_SPREAD_CRYPTO
    if is_gold(sym): return MAX_SPREAD_GOLD
    return MAX_SPREAD_FX


# ----- Bot Engine -----
class BotEngine:
    def __init__(self, log_callback=None):
        self.symbols = []
        self.state = load_state()
        self.log_callback = log_callback or (lambda m: print(m))
        self.running = False
        self.thread = None
        self.last_scan = {}     # sym -> {side, rsi, spread, status}
        self.trade_count_min = 0
        self.minute_start = time.time()

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_callback(f"[{ts}] {msg}")

    def resolve_symbols(self):
        self.symbols = []
        for s in SYMBOLS:
            actual = find_symbol(s)
            if actual:
                self.symbols.append(actual)

    def try_trade(self, sym):
        info = {"symbol": sym, "side": None, "rsi": None,
                "spread": spread_points(sym), "status": "scan"}
        try:
            if open_count() >= MAX_OPEN_TRADES:
                info["status"] = "MAX TRADES"
                return info
            if open_count(sym) >= MAX_TRADES_PER_PAIR:
                info["status"] = "PAIR FULL"
                return info
            if info["spread"] > get_spread_cap(sym):
                info["status"] = f"WIDE SPREAD"
                return info

            term = mt5.terminal_info()
            if term and not term.trade_allowed:
                info["status"] = "AUTO-TRADE OFF"
                return info

            side, rsi_val = scalp_signal(sym)
            info["side"] = side
            info["rsi"] = rsi_val
            if side is None:
                info["status"] = "no signal"
                return info

            # Got signal - place order
            tick = mt5.symbol_info_tick(sym)
            if tick is None:
                info["status"] = "no tick"
                return info
            entry = tick.ask if side == "BUY" else tick.bid
            sl, tp = compute_sl_tp(sym, side, entry)
            if sl is None or tp is None:
                info["status"] = "sl/tp err"
                return info

            lot = calc_lot(sym, entry, sl, RISK_PERCENT)
            if lot <= 0:
                info["status"] = "lot=0"
                return info

            ticket = place_market_order(sym, side, lot, sl, tp,
                                        f"SCALP_{side}_RSI{rsi_val}")
            if ticket is None:
                info["status"] = "order failed"
                return info

            info["status"] = "FIRED"
            self.state[str(ticket)] = {
                "symbol": sym, "side": side, "entry": entry,
                "sl": sl, "tp": tp, "opened_at": datetime.now().isoformat(),
            }
            save_state(self.state)
            self.trade_count_min += 1
            self.log(f"[+] {sym} {side} {lot} @ {entry:.5f} SL={sl:.5f} TP={tp:.5f} RSI={rsi_val}")
        except Exception as e:
            info["status"] = f"err: {e}"
        return info

    def manage_open(self):
        """Greedy exit + cleanup."""
        positions = mt5.positions_get() or []
        active = {str(p.ticket): p for p in positions if p.magic == MAGIC_NUMBER}

        # Greedy exit at GREEDY_EXIT_FRAC of TP
        for pos in positions:
            if pos.magic != MAGIC_NUMBER:
                continue
            st = self.state.get(str(pos.ticket))
            if st is None:
                continue
            entry = st["entry"]
            tp = st["tp"]
            tp_dist = abs(tp - entry)
            if tp_dist <= 0:
                continue
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None:
                continue
            cur = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            if pos.type == mt5.ORDER_TYPE_BUY:
                progress = (cur - entry) / tp_dist
            else:
                progress = (entry - cur) / tp_dist
            if progress >= GREEDY_EXIT_FRAC:
                if close_position(pos):
                    self.log(f"[$] {pos.symbol} #{pos.ticket} GREEDY EXIT @ {progress*100:.0f}% of TP")

        # Log closed trades
        for tk in list(self.state.keys()):
            if tk not in active:
                st = self.state[tk]
                deals = mt5.history_deals_get(position=int(tk))
                pnl = sum(d.profit + d.swap + d.commission for d in deals) if deals else 0.0
                append_trade_log({
                    "ticket": tk, "symbol": st.get("symbol"), "side": st.get("side"),
                    "entry": st.get("entry"), "sl": st.get("sl"), "tp": st.get("tp"),
                    "pnl": pnl, "closed_at": datetime.now().isoformat(),
                })
                self.state.pop(tk, None)
        save_state(self.state)

    def run(self):
        self.running = True
        while self.running:
            try:
                # Reset trade counter every 60 sec
                if time.time() - self.minute_start > 60:
                    self.trade_count_min = 0
                    self.minute_start = time.time()
                scan = {}
                for sym in self.symbols:
                    scan[sym] = self.try_trade(sym)
                self.last_scan = scan
                self.manage_open()
            except Exception as e:
                self.log(f"[!] loop err: {e}")
            time.sleep(SCAN_INTERVAL_SEC)

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False


# ----- Tkinter Dashboard -----
class Dashboard:
    REFRESH_MS = 1500

    def __init__(self, root, engine):
        self.root = root
        self.engine = engine
        self.root.title("Earn Scalper - HFT Mode  |  made by @codex_here")
        self.root.geometry("1250x720")
        self.root.configure(bg="#0e1117")
        self._setup_style()
        self._build_header()
        self._build_next_bar()
        self._build_notebook()
        self.engine.log_callback = self.append_log
        self.log_q = queue.Queue()
        self.root.after(self.REFRESH_MS, self.refresh)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_style(self):
        s = ttk.Style()
        try: s.theme_use("clam")
        except Exception: pass
        s.configure("Treeview", background="#1a1f2b", foreground="#e6edf3",
                    fieldbackground="#1a1f2b", rowheight=22)
        s.configure("Treeview.Heading", background="#21262d", foreground="#58a6ff",
                    font=("Segoe UI", 9, "bold"))
        s.map("Treeview", background=[("selected", "#264f78")])

    def _build_header(self):
        h = tk.Frame(self.root, bg="#161b22", pady=8)
        h.pack(fill="x")
        self.lbl_acc = tk.Label(h, text="Connecting...", fg="#58a6ff", bg="#161b22",
                                font=("Segoe UI", 11, "bold"))
        self.lbl_acc.pack(side="left", padx=15)
        self.lbl_stats = tk.Label(h, text="", fg="#7ee787", bg="#161b22",
                                  font=("Segoe UI", 10))
        self.lbl_stats.pack(side="left", padx=15)
        self.lbl_rate = tk.Label(h, text="", fg="#f0883e", bg="#161b22",
                                 font=("Segoe UI", 10, "bold"))
        self.lbl_rate.pack(side="right", padx=15)

    def _build_next_bar(self):
        # Next setup forecast bar
        nb = tk.Frame(self.root, bg="#1a2332", pady=6)
        nb.pack(fill="x")
        tk.Label(nb, text="NEXT SETUP:", fg="#f0883e", bg="#1a2332",
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=15)
        self.lbl_next = tk.Label(nb, text="scanning...", fg="#e6edf3",
                                 bg="#1a2332", font=("Segoe UI", 10))
        self.lbl_next.pack(side="left", padx=5)
        self.lbl_next2 = tk.Label(nb, text="", fg="#58a6ff", bg="#1a2332",
                                  font=("Segoe UI", 9))
        self.lbl_next2.pack(side="left", padx=15)

    def _build_notebook(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Active trades
        self.tab_t = tk.Frame(self.nb, bg="#0e1117")
        self.nb.add(self.tab_t, text="  Active Trades  ")
        cols = ("ticket", "symbol", "side", "lot", "entry", "sl", "tp", "current", "pnl")
        self.tv_t = ttk.Treeview(self.tab_t, columns=cols, show="headings", height=12)
        for c in cols:
            self.tv_t.heading(c, text=c.upper())
            self.tv_t.column(c, width=110, anchor="center")
        self.tv_t.pack(fill="both", expand=True, padx=8, pady=8)

        # Setup scanner
        self.tab_s = tk.Frame(self.nb, bg="#0e1117")
        self.nb.add(self.tab_s, text="  Setup Scanner  ")
        scols = ("symbol", "side", "rsi", "spread", "open", "status")
        self.tv_s = ttk.Treeview(self.tab_s, columns=scols, show="headings", height=15)
        for c in scols:
            self.tv_s.heading(c, text=c.upper())
            self.tv_s.column(c, width=120, anchor="center")
        self.tv_s.pack(fill="both", expand=True, padx=8, pady=8)

        # Closed trades
        self.tab_l = tk.Frame(self.nb, bg="#0e1117")
        self.nb.add(self.tab_l, text="  Closed Trades  ")
        lcols = ("closed_at", "symbol", "side", "entry", "sl", "tp", "pnl", "result")
        self.tv_l = ttk.Treeview(self.tab_l, columns=lcols, show="headings", height=15)
        for c in lcols:
            self.tv_l.heading(c, text=c.upper())
            self.tv_l.column(c, width=110, anchor="center")
        self.tv_l.pack(fill="both", expand=True, padx=8, pady=8)

        # Console
        self.tab_c = tk.Frame(self.nb, bg="#0e1117")
        self.nb.add(self.tab_c, text="  Console Log  ")
        self.txt = tk.Text(self.tab_c, bg="#0d1117", fg="#7ee787",
                           insertbackground="white", font=("Consolas", 9), wrap="word")
        self.txt.pack(fill="both", expand=True, padx=8, pady=8)

    def append_log(self, msg):
        self.log_q.put(msg)

    def drain_logs(self):
        while True:
            try: m = self.log_q.get_nowait()
            except queue.Empty: break
            self.txt.insert("end", m + "\n")
            self.txt.see("end")
            # cap text length
            if int(self.txt.index('end-1c').split('.')[0]) > 500:
                self.txt.delete('1.0', '100.0')

    def refresh(self):
        try:
            self.drain_logs()
            self.update_header()
            self.update_trades()
            self.update_scan()
            self.update_log()
        except Exception as e:
            print("refresh err:", e)
        self.root.after(self.REFRESH_MS, self.refresh)

    def update_header(self):
        acc = mt5.account_info()
        if acc:
            self.lbl_acc.config(
                text=f"Acc {acc.login} | {acc.server} | "
                     f"Bal: {acc.balance:.2f} | Eq: {acc.equity:.2f} {acc.currency}"
            )
        rate, w, l = calc_winrate()
        pnl = calc_total_pnl()
        col = "#7ee787" if pnl >= 0 else "#f85149"
        self.lbl_stats.config(
            text=f"WinRate {rate:.1f}%  ({w}W / {l}L)  |  Total P&L: {pnl:+.2f}",
            fg=col)
        # Trades/min indicator
        self.lbl_rate.config(text=f"Trades/min: {self.engine.trade_count_min}")

    def update_trades(self):
        for r in self.tv_t.get_children():
            self.tv_t.delete(r)
        positions = mt5.positions_get() or []
        for pos in positions:
            if pos.magic != MAGIC_NUMBER: continue
            tick = mt5.symbol_info_tick(pos.symbol)
            cur = (tick.bid if (tick and pos.type == mt5.ORDER_TYPE_BUY) else
                   (tick.ask if tick else 0))
            side = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
            tag = "win" if pos.profit >= 0 else "loss"
            self.tv_t.insert("", "end", values=(
                pos.ticket, pos.symbol, side, pos.volume,
                f"{pos.price_open:.5f}", f"{pos.sl:.5f}", f"{pos.tp:.5f}",
                f"{cur:.5f}", f"{pos.profit:+.2f}",
            ), tags=(tag,))
        self.tv_t.tag_configure("win", foreground="#7ee787")
        self.tv_t.tag_configure("loss", foreground="#f85149")

    def update_scan(self):
        for r in self.tv_s.get_children():
            self.tv_s.delete(r)
        scan = self.engine.last_scan
        rows = []
        for sym in self.engine.symbols:
            info = scan.get(sym, {})
            score = 1 if info.get("side") else 0
            rows.append((score, sym, info))
        rows.sort(key=lambda r: -r[0])
        # Update next-setup label with first non-firing pair that has a side
        next_label = None
        for score, sym, info in rows:
            side = info.get("side")
            status = info.get("status", "")
            rsi_v = info.get("rsi")
            sp = info.get("spread", 0)
            opens = open_count(sym)
            tag = ("ready" if status == "FIRED" else
                   "watch" if side else
                   "neutral" if status == "no signal" else "idle")
            self.tv_s.insert("", "end", values=(
                sym, side or "-", rsi_v or "-", sp, opens, status
            ), tags=(tag,))
            if next_label is None and side and status != "FIRED":
                col = "#58a6ff"
                self.lbl_next.config(text=f"{sym} {side}  (RSI={rsi_v})", fg=col)
                self.lbl_next2.config(text=f"-> {status}")
                next_label = sym
        if next_label is None:
            # Fall back to most-recent firing
            firing = [s for s in scan.values() if s.get("status") == "FIRED"]
            if firing:
                f = firing[-1]
                self.lbl_next.config(text=f"{f['symbol']} {f['side']} just FIRED", fg="#7ee787")
                self.lbl_next2.config(text="")
            else:
                self.lbl_next.config(text="no signals - waiting for EMA cross",
                                     fg="#6e7681")
                self.lbl_next2.config(text="")
        self.tv_s.tag_configure("ready", foreground="#7ee787")
        self.tv_s.tag_configure("watch", foreground="#58a6ff")
        self.tv_s.tag_configure("neutral", foreground="#e6edf3")
        self.tv_s.tag_configure("idle", foreground="#6e7681")

    def update_log(self):
        for r in self.tv_l.get_children():
            self.tv_l.delete(r)
        log = load_trade_log()
        for t in reversed(log[-100:]):
            pnl = t.get("pnl") or 0
            res = "WIN" if pnl > 0 else "LOSS"
            tag = "win" if pnl > 0 else "loss"
            self.tv_l.insert("", "end", values=(
                t.get("closed_at", "")[:19], t.get("symbol", ""), t.get("side", ""),
                f"{t.get('entry', 0):.5f}", f"{t.get('sl', 0):.5f}", f"{t.get('tp', 0):.5f}",
                f"{pnl:+.2f}", res
            ), tags=(tag,))
        self.tv_l.tag_configure("win", foreground="#7ee787")
        self.tv_l.tag_configure("loss", foreground="#f85149")

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
    print("  EARN SCALPER - HFT-style MT5 Bot")
    print("                    made by @codex_here")
    print("=" * 70)
    print(f"  Risk per trade  : {RISK_PERCENT}%")
    print(f"  Max trades      : {MAX_OPEN_TRADES} concurrent ({MAX_TRADES_PER_PAIR}/pair)")
    print(f"  SL / TP (FX)    : {SL_PIPS_FX} / {TP_PIPS_FX} pips")
    print(f"  Greedy exit     : at {int(GREEDY_EXIT_FRAC*100)}% of TP")
    print(f"  Scan interval   : {SCAN_INTERVAL_SEC}s")
    print(f"  Strategy        : EMA({EMA_FAST}/{EMA_SLOW}) cross + RSI({RSI_PERIOD}) filter")
    print("=" * 70)

    acc, status = mt5_connect()
    if acc is None:
        print(f"[!] Login failed: {status}")
        sys.exit(1)
    print(f"[+] Logged in: {acc.login} | Balance: {acc.balance:.2f} {acc.currency}")
    term = mt5.terminal_info()
    if term:
        print(f"    AutoTrading: {'ON' if term.trade_allowed else 'OFF'}")
    print()

    engine = BotEngine()
    engine.resolve_symbols()
    print(f"[*] Symbols loaded: {len(engine.symbols)}")
    if not engine.symbols:
        print("[!] No symbols available.")
        mt5.shutdown()
        sys.exit(1)
    engine.start()

    if args.no_gui or not HAS_TK:
        print("[*] Headless. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(30)
                rate, w, l = calc_winrate()
                pnl = calc_total_pnl()
                print(f"[stat] WinRate {rate:.1f}% ({w}W/{l}L) | "
                      f"P&L {pnl:+.2f} | Open {open_count()} | "
                      f"Trades/min {engine.trade_count_min}")
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
