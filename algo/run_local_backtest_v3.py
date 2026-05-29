#!/usr/bin/env python3
"""
Pure-stdlib CRT + TBS backtester  --  V3 (only the TP fix from v2)

V3 changes vs v1:
  1) TP is RISK-BASED (true 1:2 RR)            <-- KEEP this fix
  2) min_body_pct stays at 50                  <-- v2 set 60 (too strict)
  3) PDH/PDL filter stays OFF                  <-- v2 set ON (killed sample size)

Hypothesis: the structural TP bug was the real problem; the other "fixes"
in v2 just over-restricted entries.
"""
import csv
import gzip
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Optional, Tuple

# ====================== CONFIG ======================
@dataclass
class Config:
    tbs_start: int       = 9 * 60 + 15     # 09:15
    tbs_end: int         = 9 * 60 + 45     # 09:45
    london_start: int    = 2 * 60          # 02:00
    london_end: int      = 5 * 60          # 05:00
    ny_start: int        = 8 * 60          # 08:00
    ny_end: int          = 11 * 60         # 11:00
    htf_minutes: int     = 60              # 1H trend
    htf_ema_len: int     = 50
    atr_len: int         = 14
    sl_mult: float       = 1.0
    tp_mult: float       = 2.0
    min_body_pct: float  = 50.0          # v3: keep at 50 like v1
    use_pdl_filter: bool = False         # v3: turn OFF (was killing sample size)
    pd_proximity: float  = 1.5           # ATR multiples
    max_trades_day: int  = 1
    initial_capital: float = 100_000.0
    qty_pct: float       = 10.0
    commission_pct: float = 0.02


@dataclass
class Bar:
    __slots__ = ("ts", "o", "h", "l", "c")
    ts: datetime
    o: float
    h: float
    l: float
    c: float


# ============== HELPERS ==============
def in_session(ts: datetime, start: int, end: int) -> bool:
    m = ts.hour * 60 + ts.minute
    if start <= end:
        return start <= m < end
    return m >= start or m < end


def true_range(b: Bar, prev_close: float) -> float:
    return max(b.h - b.l, abs(b.h - prev_close), abs(b.l - prev_close))


# ============== DATA LOADERS ==============
def load_forex_m15(path: str) -> List[Bar]:
    """ejtraderLabs format: Date,open,high,low,close,tick_volume (15 min)."""
    bars: List[Bar] = []
    with open(path, "r") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            try:
                ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                bars.append(Bar(ts, float(row[1]), float(row[2]),
                                float(row[3]), float(row[4])))
            except (ValueError, IndexError):
                continue
    return bars


def load_btc_1min(path: str) -> List[Bar]:
    """ff137 format: timestamp(epoch s),open,high,low,close,volume."""
    bars: List[Bar] = []
    f = gzip.open(path, "rt") if path.endswith(".gz") else open(path)
    with f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            try:
                ts = datetime.utcfromtimestamp(int(row[0]))
                bars.append(Bar(ts, float(row[1]), float(row[2]),
                                float(row[3]), float(row[4])))
            except (ValueError, IndexError):
                continue
    return bars


def load_eth_chunks(directory: str) -> List[Bar]:
    """Bitfinex format split across many TSV files: MTS,OPEN,CLOSE,HIGH,LOW,VOLUME."""
    raw: List[Bar] = []
    files = sorted(os.listdir(directory))
    for fn in files:
        if not fn.endswith(".csv"):
            continue
        with open(os.path.join(directory, fn)) as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader, None)
            for row in reader:
                try:
                    ts = datetime.utcfromtimestamp(int(row[0]) / 1000)
                    o, c, h, l = float(row[1]), float(row[2]), float(row[3]), float(row[4])
                    raw.append(Bar(ts, o, h, l, c))
                except (ValueError, IndexError):
                    continue
    raw.sort(key=lambda b: b.ts)
    # Deduplicate by timestamp
    out: List[Bar] = []
    last_ts = None
    for b in raw:
        if b.ts != last_ts:
            out.append(b)
            last_ts = b.ts
    return out


def resample_15m(bars: List[Bar]) -> List[Bar]:
    """Aggregate 1-minute bars to 15-minute OHLC bars."""
    out: List[Bar] = []
    cur_start = None
    o = h = l = c = 0.0
    for b in bars:
        bucket = b.ts.replace(minute=(b.ts.minute // 15) * 15,
                              second=0, microsecond=0)
        if cur_start is None or bucket != cur_start:
            if cur_start is not None:
                out.append(Bar(cur_start, o, h, l, c))
            cur_start = bucket
            o, h, l, c = b.o, b.h, b.l, b.c
        else:
            if b.h > h: h = b.h
            if b.l < l: l = b.l
            c = b.c
    if cur_start is not None:
        out.append(Bar(cur_start, o, h, l, c))
    return out


# ============== INDICATORS ==============
def compute_atr_rma(bars: List[Bar], length: int) -> List[Optional[float]]:
    """Wilder's RMA — matches Pine ta.atr."""
    n = len(bars)
    atr: List[Optional[float]] = [None] * n
    if n < length + 1:
        return atr
    trs = [true_range(bars[i], bars[i - 1].c) for i in range(1, length + 1)]
    avg = sum(trs) / length
    atr[length] = avg
    for i in range(length + 1, n):
        tr = true_range(bars[i], bars[i - 1].c)
        avg = (avg * (length - 1) + tr) / length
        atr[i] = avg
    return atr


def compute_htf_signal(bars: List[Bar], htf_minutes: int, ema_len: int) -> List[int]:
    """
    HTF (default 60 min) EMA trend signal aligned to source bars.
    No look-ahead: each source bar gets the signal of the *previous*
    completed HTF bar.
    """
    if htf_minutes < 60:
        bucket_fn = lambda ts: ts.replace(minute=(ts.minute // htf_minutes) * htf_minutes,
                                          second=0, microsecond=0)
    else:
        hours_per = htf_minutes // 60
        bucket_fn = lambda ts: ts.replace(hour=(ts.hour // hours_per) * hours_per,
                                          minute=0, second=0, microsecond=0)
    htf_bars: List[Bar] = []
    cur_start = None
    o = h = l = c = 0.0
    for b in bars:
        bucket = bucket_fn(b.ts)
        if cur_start is None or bucket != cur_start:
            if cur_start is not None:
                htf_bars.append(Bar(cur_start, o, h, l, c))
            cur_start = bucket
            o, h, l, c = b.o, b.h, b.l, b.c
        else:
            if b.h > h: h = b.h
            if b.l < l: l = b.l
            c = b.c
    if cur_start is not None:
        htf_bars.append(Bar(cur_start, o, h, l, c))

    # EMA on HTF closes
    closes = [hb.c for hb in htf_bars]
    alpha = 2.0 / (ema_len + 1)
    ema_vals: List[float] = []
    for i, cl in enumerate(closes):
        ema_vals.append(cl if i == 0 else alpha * cl + (1 - alpha) * ema_vals[-1])

    # Signal per HTF bar — shifted: use previous HTF bar's (close vs ema)
    htf_sig: List[int] = [0] * len(htf_bars)
    for i in range(1, len(htf_bars)):
        if closes[i - 1] > ema_vals[i - 1]:
            htf_sig[i] = 1
        elif closes[i - 1] < ema_vals[i - 1]:
            htf_sig[i] = -1

    # Map back to original bars
    out = [0] * len(bars)
    j = 0
    for i, b in enumerate(bars):
        while j + 1 < len(htf_bars) and htf_bars[j + 1].ts <= b.ts:
            j += 1
        out[i] = htf_sig[j]
    return out


def compute_pdh_pdl(bars: List[Bar]) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    """For each bar, return previous calendar day's High and Low."""
    daily_h: Dict = {}
    daily_l: Dict = {}
    for b in bars:
        d = b.ts.date()
        if d not in daily_h:
            daily_h[d] = b.h
            daily_l[d] = b.l
        else:
            if b.h > daily_h[d]: daily_h[d] = b.h
            if b.l < daily_l[d]: daily_l[d] = b.l
    sorted_dates = sorted(daily_h.keys())
    pdh_map: Dict = {}
    pdl_map: Dict = {}
    for i, d in enumerate(sorted_dates):
        if i == 0:
            pdh_map[d] = None
            pdl_map[d] = None
        else:
            prev = sorted_dates[i - 1]
            pdh_map[d] = daily_h[prev]
            pdl_map[d] = daily_l[prev]
    pdh = [pdh_map.get(b.ts.date()) for b in bars]
    pdl = [pdl_map.get(b.ts.date()) for b in bars]
    return pdh, pdl


# ============== BACKTEST ENGINE ==============
@dataclass
class Trade:
    entry_time: datetime
    exit_time: Optional[datetime]
    side: str
    entry: float
    exit: float
    qty: float
    pnl: float
    reason: str


def run_backtest(bars: List[Bar], cfg: Config, name: str = "") -> Tuple[List[Trade], float, float]:
    n = len(bars)
    if n < cfg.atr_len + 100:
        return [], 0.0, cfg.initial_capital
    print(f"  [{name}] computing ATR + HTF trend + PDH/PDL ...", flush=True)
    atr_arr = compute_atr_rma(bars, cfg.atr_len)
    htf_sig = compute_htf_signal(bars, cfg.htf_minutes, cfg.htf_ema_len)
    pdh_arr, pdl_arr = compute_pdh_pdl(bars)

    print(f"  [{name}] running simulation on {n} bars ...", flush=True)
    trades: List[Trade] = []
    equity = cfg.initial_capital
    range_high = None
    range_low = None
    range_ready = False
    trades_today = 0
    daily_lock = False
    cur_date = None
    prev_in_tbs = False
    pos = None

    eq_peak = equity
    max_dd = 0.0

    for i in range(n):
        b = bars[i]
        atr_val = atr_arr[i]
        date = b.ts.date()

        # Daily reset
        if date != cur_date:
            cur_date = date
            range_high = None
            range_low = None
            range_ready = False
            trades_today = 0
            daily_lock = False
            prev_in_tbs = False

        in_tbs = in_session(b.ts, cfg.tbs_start, cfg.tbs_end)
        in_kz  = (in_session(b.ts, cfg.london_start, cfg.london_end) or
                  in_session(b.ts, cfg.ny_start, cfg.ny_end))

        # Manage open position (intra-bar SL/TP)
        if pos is not None:
            hit_sl = hit_tp = False
            ex = None
            if pos["side"] == "long":
                if b.l <= pos["sl"]:
                    hit_sl = True; ex = pos["sl"]
                elif b.h >= pos["tp"]:
                    hit_tp = True; ex = pos["tp"]
            else:
                if b.h >= pos["sl"]:
                    hit_sl = True; ex = pos["sl"]
                elif b.l <= pos["tp"]:
                    hit_tp = True; ex = pos["tp"]
            if hit_sl or hit_tp:
                if pos["side"] == "long":
                    pnl = (ex - pos["entry"]) * pos["qty"]
                else:
                    pnl = (pos["entry"] - ex) * pos["qty"]
                cost = (pos["entry"] + ex) * pos["qty"] * cfg.commission_pct / 100.0
                pnl -= cost
                equity += pnl
                trades.append(Trade(pos["entry_time"], b.ts, pos["side"],
                                    pos["entry"], ex, pos["qty"], pnl,
                                    "TP" if hit_tp else "SL"))
                if hit_tp:
                    daily_lock = True
                pos = None

        # Build TBS range
        if in_tbs:
            if range_high is None:
                range_high, range_low = b.h, b.l
            else:
                if b.h > range_high: range_high = b.h
                if b.l < range_low:  range_low = b.l
            range_ready = False

        if (not in_tbs) and prev_in_tbs and range_high is not None:
            range_ready = True

        # Entry logic
        atr_valid = atr_val is not None and atr_val > 0
        if (pos is None and trades_today < cfg.max_trades_day
                and not daily_lock and atr_valid
                and not in_tbs and in_kz and range_ready):
            buy_sweep  = b.l < range_low  and b.c > range_low  and b.c > b.o
            sell_sweep = b.h > range_high and b.c < range_high and b.c < b.o

            body = abs(b.c - b.o)
            rng = b.h - b.l
            body_pct = (body / rng * 100.0) if rng > 0 else 0.0
            bull_crt = b.c > b.o and body_pct >= cfg.min_body_pct
            bear_crt = b.c < b.o and body_pct >= cfg.min_body_pct

            sig = htf_sig[i]

            # FIX #3: PDH/PDL proximity filter
            pdh, pdl = pdh_arr[i], pdl_arr[i]
            near_pdl = (not cfg.use_pdl_filter) or (
                pdl is not None and abs(b.l - pdl) <= atr_val * cfg.pd_proximity
            )
            near_pdh = (not cfg.use_pdl_filter) or (
                pdh is not None and abs(b.h - pdh) <= atr_val * cfg.pd_proximity
            )

            buy_cond  = buy_sweep  and bull_crt and sig ==  1 and near_pdl
            sell_cond = sell_sweep and bear_crt and sig == -1 and near_pdh

            if buy_cond or sell_cond:
                entry_price = b.c
                if buy_cond:
                    sl = b.l - atr_val * cfg.sl_mult
                    # FIX #1: TP is now RISK-BASED (true 1:2 RR)
                    risk = entry_price - sl
                    tp = entry_price + cfg.tp_mult * risk
                    side = "long"
                else:
                    sl = b.h + atr_val * cfg.sl_mult
                    # FIX #1: TP is now RISK-BASED (true 1:2 RR)
                    risk = sl - entry_price
                    tp = entry_price - cfg.tp_mult * risk
                    side = "short"
                qty = (equity * cfg.qty_pct / 100.0) / entry_price
                pos = {"side": side, "entry": entry_price, "sl": sl, "tp": tp,
                       "qty": qty, "entry_time": b.ts}
                trades_today += 1

        prev_in_tbs = in_tbs

        # Track drawdown using mark-to-market equity
        mtm = equity
        if pos is not None:
            if pos["side"] == "long":
                mtm += (b.c - pos["entry"]) * pos["qty"]
            else:
                mtm += (pos["entry"] - b.c) * pos["qty"]
        if mtm > eq_peak:
            eq_peak = mtm
        dd = (mtm - eq_peak) / eq_peak * 100.0 if eq_peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd

    return trades, max_dd, equity


# ============== REPORT ==============
def report(name: str, trades: List[Trade], max_dd: float,
           final_eq: float, cfg: Config) -> Optional[Dict]:
    n = len(trades)
    print()
    print("=" * 64)
    print(f"  {name}")
    print("=" * 64)
    if n == 0:
        print("  No trades generated.")
        return None
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    winrate = len(wins) / n * 100.0
    gw = sum(wins) if wins else 0.0
    gl = abs(sum(losses)) if losses else 0.0
    pf = (gw / gl) if gl > 0 else float("inf")
    net = sum(pnls)
    print(f"  Total Trades         : {n}")
    print(f"  Wins / Losses        : {len(wins)} / {len(losses)}")
    print(f"  Winrate              : {winrate:.2f}%")
    print(f"  Profit Factor        : {'inf' if pf == float('inf') else f'{pf:.2f}'}")
    print(f"  Net P&L (relative)   : {net:.2f}  ({net / cfg.initial_capital * 100:.2f}%)")
    print(f"  Avg Win / Avg Loss   : {mean(wins) if wins else 0:.2f} / {mean(losses) if losses else 0:.2f}")
    print(f"  Best / Worst Trade   : {max(pnls):.2f} / {min(pnls):.2f}")
    print(f"  Max Drawdown         : {max_dd:.2f}%")
    return {"name": name, "trades": n, "wins": len(wins), "losses": len(losses),
            "winrate": winrate, "pf": pf,
            "net_pct": net / cfg.initial_capital * 100, "maxdd": max_dd}


# ============== MAIN ==============
def main():
    cfg = Config()
    results: List[Dict] = []

    forex_dir = "/projects/sandbox/historical-data"
    btc_path  = "/projects/sandbox/bitstamp-btcusd-minute-data/data/historical/btcusd_bitstamp_1min_2012-2025.csv"
    eth_dir   = "/projects/sandbox/Bitfinex-historical-data-AND-CryptoCompare-historical-data/fromBitFinex/ETH"

    pairs = ["EURUSD", "GBPUSD", "USDJPY", "GBPJPY",
             "AUDUSD", "USDCAD", "USDCHF", "EURJPY", "XAUUSD"]

    for p in pairs:
        path = os.path.join(forex_dir, p, f"{p}m15.csv")
        if not os.path.exists(path):
            continue
        t0 = time.time()
        bars = load_forex_m15(path)
        print(f"\n[{p}] {len(bars)} m15 bars  ({bars[0].ts}  ->  {bars[-1].ts})")
        trades, dd, _ = run_backtest(bars, cfg, p)
        r = report(p, trades, dd, 0, cfg)
        if r:
            results.append(r)
        print(f"  [{p}] done in {time.time()-t0:.1f}s")

    # BTC
    if os.path.exists(btc_path):
        t0 = time.time()
        print(f"\n[BTCUSD] loading 1min gz file (large) ...")
        bars_1m = load_btc_1min(btc_path)
        print(f"[BTCUSD] {len(bars_1m)} 1-min bars; resampling to 15m ...")
        bars = resample_15m(bars_1m)
        del bars_1m
        print(f"[BTCUSD] {len(bars)} 15m bars  ({bars[0].ts}  ->  {bars[-1].ts})")
        trades, dd, _ = run_backtest(bars, cfg, "BTCUSD")
        r = report("BTCUSD", trades, dd, 0, cfg)
        if r:
            results.append(r)
        print(f"  [BTCUSD] done in {time.time()-t0:.1f}s")

    # ETH
    if os.path.isdir(eth_dir):
        t0 = time.time()
        print(f"\n[ETHUSD] loading chunked 1min data ...")
        bars_1m = load_eth_chunks(eth_dir)
        print(f"[ETHUSD] {len(bars_1m)} 1-min bars; resampling to 15m ...")
        bars = resample_15m(bars_1m)
        del bars_1m
        print(f"[ETHUSD] {len(bars)} 15m bars  ({bars[0].ts}  ->  {bars[-1].ts})")
        trades, dd, _ = run_backtest(bars, cfg, "ETHUSD")
        r = report("ETHUSD", trades, dd, 0, cfg)
        if r:
            results.append(r)
        print(f"  [ETHUSD] done in {time.time()-t0:.1f}s")

    # ===== Final Summary =====
    if results:
        print()
        print("=" * 64)
        print("  FINAL SUMMARY V3  (true 1:2 RR only, body>=50%, no PDL filter)")
        print("=" * 64)
        print(f"  {'Symbol':<10} {'Trades':>6} {'Wins':>5} {'Loss':>5} "
              f"{'WinR%':>7} {'PF':>6} {'Net%':>8} {'MaxDD%':>8}")
        print("  " + "-" * 60)
        # sort by winrate desc
        for r in sorted(results, key=lambda x: x["winrate"], reverse=True):
            pf_s = "inf" if r["pf"] == float("inf") else f"{r['pf']:.2f}"
            print(f"  {r['name']:<10} {r['trades']:>6d} {r['wins']:>5d} {r['losses']:>5d} "
                  f"{r['winrate']:>7.2f} {pf_s:>6} {r['net_pct']:>8.2f} {r['maxdd']:>8.2f}")
        print()
        # Aggregate
        total_t = sum(r["trades"] for r in results)
        total_w = sum(r["wins"]   for r in results)
        if total_t > 0:
            print(f"  AGGREGATE: {total_t} trades, "
                  f"{total_w / total_t * 100:.2f}% combined winrate")
    else:
        print("\nNo results — data directories missing?")


if __name__ == "__main__":
    main()
