#!/usr/bin/env python3
"""
Multi-timeframe backtest matrix.
Reuses v3 engine (true 1:2 RR via risk-based TP) and tests every pair
on multiple timeframes:
    Forex / Gold  : m15, m30, h1
    BTC / ETH     : m5, m15, m30, h1

The strategy's TBS window is 30 minutes long, so timeframes >= h1 are
expected to produce ~0 trades (sanity check, included in output).
"""
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_local_backtest_v3 import (
    Bar, Config, run_backtest,
    load_forex_m15, load_btc_1min, load_eth_chunks,
)


def resample_to_tf(bars: List[Bar], tf_minutes: int) -> List[Bar]:
    """Aggregate bars (any source TF) into tf_minutes OHLC bars."""
    out: List[Bar] = []
    cur = None
    o = h = l = c = 0.0
    for b in bars:
        if tf_minutes < 60:
            bucket = b.ts.replace(
                minute=(b.ts.minute // tf_minutes) * tf_minutes,
                second=0, microsecond=0)
        else:
            hpb = tf_minutes // 60
            bucket = b.ts.replace(
                hour=(b.ts.hour // hpb) * hpb,
                minute=0, second=0, microsecond=0)
        if cur is None or bucket != cur:
            if cur is not None:
                out.append(Bar(cur, o, h, l, c))
            cur = bucket
            o, h, l, c = b.o, b.h, b.l, b.c
        else:
            if b.h > h: h = b.h
            if b.l < l: l = b.l
            c = b.c
    if cur is not None:
        out.append(Bar(cur, o, h, l, c))
    return out


def summary_row(name: str, tf: str, trades, dd: float, cfg: Config) -> Optional[Dict]:
    n = len(trades)
    if n == 0:
        return {"pair": name, "tf": tf, "trades": 0, "wins": 0, "losses": 0,
                "winrate": 0.0, "pf": 0.0, "net_pct": 0.0, "maxdd": 0.0}
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gw = sum(wins) if wins else 0.0
    gl = abs(sum(losses)) if losses else 0.0
    pf = (gw / gl) if gl > 0 else float("inf")
    net = sum(pnls)
    return {"pair": name, "tf": tf, "trades": n, "wins": len(wins), "losses": len(losses),
            "winrate": len(wins) / n * 100.0, "pf": pf,
            "net_pct": net / cfg.initial_capital * 100.0, "maxdd": dd}


def main():
    cfg = Config()
    rows: List[Dict] = []

    forex_dir = "/projects/sandbox/historical-data"
    btc_path  = "/projects/sandbox/bitstamp-btcusd-minute-data/data/historical/btcusd_bitstamp_1min_2012-2025.csv"
    eth_dir   = "/projects/sandbox/Bitfinex-historical-data-AND-CryptoCompare-historical-data/fromBitFinex/ETH"

    forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "AUDUSD",
                   "USDCAD", "USDCHF", "EURJPY", "XAUUSD"]
    forex_tfs = [("m15", 15), ("m30", 30), ("h1", 60)]
    crypto_tfs = [("m5", 5), ("m15", 15), ("m30", 30), ("h1", 60)]

    # ===== FOREX / GOLD =====
    for p in forex_pairs:
        for tf_label, tf_min in forex_tfs:
            path = os.path.join(forex_dir, p, f"{p}{tf_label}.csv")
            if not os.path.exists(path):
                rows.append({"pair": p, "tf": tf_label, "trades": 0, "wins": 0,
                             "losses": 0, "winrate": 0.0, "pf": 0.0,
                             "net_pct": 0.0, "maxdd": 0.0})
                continue
            t0 = time.time()
            bars = load_forex_m15(path)
            print(f"\n[{p} {tf_label}] {len(bars)} bars  ({bars[0].ts}  ->  {bars[-1].ts})")
            trades, dd, _ = run_backtest(bars, cfg, f"{p}/{tf_label}")
            r = summary_row(p, tf_label, trades, dd, cfg)
            rows.append(r)
            print(f"  done {time.time()-t0:.1f}s  trades={r['trades']}  WR={r['winrate']:.2f}%  PF={r['pf']:.2f}  net={r['net_pct']:.2f}%")

    # ===== BTC =====
    print(f"\n\n>>> Loading BTC 1-min once, resampling to multiple TFs ...")
    t0 = time.time()
    btc_1m = load_btc_1min(btc_path)
    print(f"  loaded {len(btc_1m)} 1-min bars in {time.time()-t0:.1f}s")
    for tf_label, tf_min in crypto_tfs:
        t0 = time.time()
        bars = resample_to_tf(btc_1m, tf_min)
        print(f"\n[BTCUSD {tf_label}] {len(bars)} bars  ({bars[0].ts}  ->  {bars[-1].ts})")
        trades, dd, _ = run_backtest(bars, cfg, f"BTCUSD/{tf_label}")
        r = summary_row("BTCUSD", tf_label, trades, dd, cfg)
        rows.append(r)
        print(f"  done {time.time()-t0:.1f}s  trades={r['trades']}  WR={r['winrate']:.2f}%  PF={r['pf']:.2f}  net={r['net_pct']:.2f}%")
    del btc_1m

    # ===== ETH =====
    print(f"\n\n>>> Loading ETH 1-min once, resampling to multiple TFs ...")
    t0 = time.time()
    eth_1m = load_eth_chunks(eth_dir)
    print(f"  loaded {len(eth_1m)} 1-min bars in {time.time()-t0:.1f}s")
    for tf_label, tf_min in crypto_tfs:
        t0 = time.time()
        bars = resample_to_tf(eth_1m, tf_min)
        print(f"\n[ETHUSD {tf_label}] {len(bars)} bars  ({bars[0].ts}  ->  {bars[-1].ts})")
        trades, dd, _ = run_backtest(bars, cfg, f"ETHUSD/{tf_label}")
        r = summary_row("ETHUSD", tf_label, trades, dd, cfg)
        rows.append(r)
        print(f"  done {time.time()-t0:.1f}s  trades={r['trades']}  WR={r['winrate']:.2f}%  PF={r['pf']:.2f}  net={r['net_pct']:.2f}%")
    del eth_1m

    # ===== MATRIX OUTPUT =====
    pairs_order = forex_pairs + ["BTCUSD", "ETHUSD"]
    all_tfs = ["m5", "m15", "m30", "h1"]

    by_pair: Dict[str, Dict[str, Dict]] = {p: {} for p in pairs_order}
    for r in rows:
        by_pair[r["pair"]][r["tf"]] = r

    print()
    print("=" * 70)
    print("  MULTI-TIMEFRAME RESULTS  (v3 strategy: true 1:2 RR)")
    print("=" * 70)

    def print_table(title, key, fmt):
        print()
        print(f"  {title}")
        print(f"  {'Pair':<10}", end="")
        for tf in all_tfs:
            print(f"{tf:>10}", end="")
        print()
        print("  " + "-" * 50)
        for p in pairs_order:
            print(f"  {p:<10}", end="")
            for tf in all_tfs:
                r = by_pair[p].get(tf)
                if r and r["trades"] > 0:
                    val = r[key]
                    if key == "pf" and val == float("inf"):
                        print(f"{'inf':>10}", end="")
                    else:
                        print(fmt.format(val), end="")
                else:
                    print(f"{'-':>10}", end="")
            print()

    print_table("TRADES", "trades", "{:>10d}")
    print_table("WINRATE %", "winrate", "{:>10.2f}")
    print_table("PROFIT FACTOR", "pf", "{:>10.2f}")
    print_table("NET %", "net_pct", "{:>10.2f}")
    print_table("MAX DD %", "maxdd", "{:>10.2f}")

    # Profitable combos
    print()
    print("=" * 70)
    print("  PROFITABLE COMBOS  (PF > 1.0 and >= 30 trades)")
    print("=" * 70)
    profitable = [r for r in rows if r["trades"] >= 30 and r["pf"] > 1.0]
    if not profitable:
        print("  (none)")
    else:
        profitable.sort(key=lambda x: x["pf"], reverse=True)
        for r in profitable:
            pf_s = "inf" if r["pf"] == float("inf") else f"{r['pf']:.2f}"
            print(f"  {r['pair']:<10} {r['tf']:<5}  trades={r['trades']:>5}  "
                  f"WR={r['winrate']:>5.2f}%  PF={pf_s:>5}  net={r['net_pct']:>+6.2f}%  "
                  f"DD={r['maxdd']:>+6.2f}%")


if __name__ == "__main__":
    main()
