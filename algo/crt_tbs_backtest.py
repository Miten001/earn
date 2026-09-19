#!/usr/bin/env python3
"""
CRT + TBS ULTIMATE SNIPER PRO - Python Backtester
==================================================
Pine Script v6 strategy translated to Python with full backtest engine.

Usage:
    # Single symbol
    python crt_tbs_backtest.py --symbol XAUUSD --period 60d --interval 5m

    # All default symbols (forex + metals + crypto)
    python crt_tbs_backtest.py --all --period 60d --interval 5m

    # Use your own CSV (datetime,Open,High,Low,Close[,Volume])
    python crt_tbs_backtest.py --csv mydata.csv --tz America/New_York

Supported symbol keys (auto-mapped to yfinance tickers):
    Forex   : EURUSD, GBPUSD, USDJPY, GBPJPY, USDCHF, USDCAD, AUDUSD, NZDUSD
    Metals  : XAUUSD (Gold), XAGUSD (Silver)
    Crypto  : BTCUSD, ETHUSD
"""

import argparse
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False


# ====================== CONFIG ======================
@dataclass
class Config:
    # Sessions (HH:MM in cfg.tz)
    tbs_start: str = "09:15"
    tbs_end: str = "09:45"
    london_start: str = "02:00"
    london_end: str = "05:00"
    ny_start: str = "08:00"
    ny_end: str = "11:00"
    tz: str = "America/New_York"

    # Trend filter
    htf_resample: str = "1h"
    htf_ema_len: int = 50
    use_pdl_filter: bool = False
    pd_proximity: float = 1.5  # ATR multiples

    # Strategy params
    atr_len: int = 14
    sl_mult: float = 1.0
    tp_mult: float = 2.0
    min_body_pct: float = 50.0
    max_trades_day: int = 1

    # Capital & costs
    initial_capital: float = 100_000.0
    qty_pct_equity: float = 10.0   # % of equity used as notional per trade
    commission_pct: float = 0.02   # per side, in percent


# ============== TICKER MAPPING (yfinance) ==============
SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "GBPJPY": "GBPJPY=X",
    "USDCHF": "USDCHF=X",
    "USDCAD": "USDCAD=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "XAUUSD": "GC=F",   # Gold futures (best free proxy)
    "XAGUSD": "SI=F",   # Silver futures
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
}

DEFAULT_BASKET = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "BTCUSD", "ETHUSD"]


# ====================== HELPERS ======================
def parse_hhmm(s: str) -> int:
    """Convert 'HH:MM' to minutes from midnight."""
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def in_session_mask(idx: pd.DatetimeIndex, start: str, end: str) -> pd.Series:
    """Boolean Series: True when timestamp is in [start, end)."""
    s = parse_hhmm(start)
    e = parse_hhmm(end)
    minutes = pd.Series(idx.hour * 60 + idx.minute, index=idx)
    if s <= e:
        return (minutes >= s) & (minutes < e)
    return (minutes >= s) | (minutes < e)  # overnight


def true_range(df: pd.DataFrame) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    return pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    return true_range(df).rolling(length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


# ============== DATA LOADING ==============
def fetch_yf(symbol: str, period: str, interval: str, tz: str) -> pd.DataFrame:
    if not HAS_YF:
        raise RuntimeError("yfinance not installed. Run: pip install yfinance")
    ticker = SYMBOLS.get(symbol.upper(), symbol)
    df = yf.download(ticker, period=period, interval=interval,
                     progress=False, auto_adjust=False)
    if df.empty:
        raise ValueError(f"No data returned for {symbol} ({ticker}). "
                         f"Try a different period/interval.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(tz)
    return df


def load_csv(path: str, tz: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    df.columns = [c.capitalize() for c in df.columns]
    for c in ["Open", "High", "Low", "Close"]:
        if c not in df.columns:
            raise ValueError(f"CSV missing required column: {c}")
    if "Volume" not in df.columns:
        df["Volume"] = 0
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(tz)
    return df


# ============== INDICATOR PRECOMPUTE ==============
def precompute(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    out = df.copy()

    # ATR
    out["ATR"] = atr(out, cfg.atr_len)

    # HTF trend (no look-ahead: shift by 1 to use only completed HTF bar)
    htf_close = out["Close"].resample(cfg.htf_resample).last().dropna()
    htf_ema = ema(htf_close, cfg.htf_ema_len)
    htf_trend = pd.Series(0, index=htf_close.index, dtype=int)
    htf_trend[htf_close > htf_ema] = 1
    htf_trend[htf_close < htf_ema] = -1
    htf_trend = htf_trend.shift(1).fillna(0).astype(int)
    out["HTF_Trend"] = htf_trend.reindex(out.index, method="ffill").fillna(0).astype(int)

    # PDH / PDL based on date in cfg.tz
    dates = pd.Series(out.index.date, index=out.index)
    daily_table = pd.DataFrame({
        "high": out.groupby(dates)["High"].max(),
        "low":  out.groupby(dates)["Low"].min(),
    })
    daily_table["pdh"] = daily_table["high"].shift(1)
    daily_table["pdl"] = daily_table["low"].shift(1)
    out["PDH"] = dates.map(daily_table["pdh"])
    out["PDL"] = dates.map(daily_table["pdl"])

    # Sessions
    idx = out.index
    out["inTBS"]      = in_session_mask(idx, cfg.tbs_start, cfg.tbs_end)
    out["inLondon"]   = in_session_mask(idx, cfg.london_start, cfg.london_end)
    out["inNY"]       = in_session_mask(idx, cfg.ny_start, cfg.ny_end)
    out["inKillzone"] = out["inLondon"] | out["inNY"]

    # CRT body %
    body = (out["Close"] - out["Open"]).abs()
    rng = (out["High"] - out["Low"]).replace(0, np.nan)
    out["BodyPct"] = (body / rng) * 100
    out["isBullCRT"] = (out["Close"] > out["Open"]) & (out["BodyPct"] >= cfg.min_body_pct)
    out["isBearCRT"] = (out["Close"] < out["Open"]) & (out["BodyPct"] >= cfg.min_body_pct)

    # Date label for daily reset
    out["Date"] = out.index.date
    return out


# ============== BACKTEST ENGINE ==============
@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp]
    side: str           # 'long' or 'short'
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    qty: float
    pnl: float = 0.0
    exit_reason: str = ""


def run_backtest(df: pd.DataFrame, cfg: Config) -> Tuple[List[Trade], pd.Series]:
    """Bar-by-bar simulation matching Pine Script semantics."""
    df = precompute(df, cfg)
    trades: List[Trade] = []
    equity = cfg.initial_capital

    range_high = np.nan
    range_low = np.nan
    range_ready = False
    trades_today = 0
    daily_lock = False
    current_date = None
    prev_in_tbs = False
    pos: Optional[dict] = None

    equity_curve = np.empty(len(df))

    for i, (ts, row) in enumerate(df.iterrows()):
        # ---- Daily reset ----
        if current_date is None or row["Date"] != current_date:
            current_date = row["Date"]
            range_high = np.nan
            range_low = np.nan
            range_ready = False
            trades_today = 0
            daily_lock = False
            prev_in_tbs = False

        # ---- Manage open position (intra-bar SL/TP) ----
        if pos is not None:
            hit_sl = hit_tp = False
            exit_price = None
            if pos["side"] == "long":
                if row["Low"] <= pos["sl"]:
                    hit_sl, exit_price = True, pos["sl"]
                elif row["High"] >= pos["tp"]:
                    hit_tp, exit_price = True, pos["tp"]
            else:  # short
                if row["High"] >= pos["sl"]:
                    hit_sl, exit_price = True, pos["sl"]
                elif row["Low"] <= pos["tp"]:
                    hit_tp, exit_price = True, pos["tp"]

            if hit_sl or hit_tp:
                if pos["side"] == "long":
                    pnl = (exit_price - pos["entry"]) * pos["qty"]
                else:
                    pnl = (pos["entry"] - exit_price) * pos["qty"]
                # commission both sides
                cost = (pos["entry"] + exit_price) * pos["qty"] * cfg.commission_pct / 100.0
                pnl -= cost
                equity += pnl

                trades.append(Trade(
                    entry_time=pos["entry_time"], exit_time=ts, side=pos["side"],
                    entry_price=pos["entry"], exit_price=exit_price,
                    sl=pos["sl"], tp=pos["tp"], qty=pos["qty"], pnl=pnl,
                    exit_reason="TP" if hit_tp else "SL",
                ))
                if hit_tp:
                    daily_lock = True   # lock day after a winning trade
                pos = None

        # ---- Build TBS range during session ----
        if row["inTBS"]:
            if np.isnan(range_high) or np.isnan(range_low):
                range_high, range_low = row["High"], row["Low"]
            else:
                range_high = max(range_high, row["High"])
                range_low  = min(range_low,  row["Low"])
            range_ready = False

        # Mark range READY on the bar right after TBS ends
        if (not row["inTBS"]) and prev_in_tbs and (not np.isnan(range_high)):
            range_ready = True

        # ---- Entry signals (only if flat) ----
        atr_val = row["ATR"]
        atr_valid = not np.isnan(atr_val) and atr_val > 0

        can_trade = (
            pos is None
            and trades_today < cfg.max_trades_day
            and not daily_lock
            and atr_valid
            and not row["inTBS"]
            and bool(row["inKillzone"])
            and range_ready
        )

        if can_trade:
            buy_sweep = (
                row["Low"] < range_low
                and row["Close"] > range_low
                and row["Close"] > row["Open"]
            )
            sell_sweep = (
                row["High"] > range_high
                and row["Close"] < range_high
                and row["Close"] < row["Open"]
            )

            bull_trend = row["HTF_Trend"] == 1
            bear_trend = row["HTF_Trend"] == -1

            pdh, pdl = row["PDH"], row["PDL"]
            near_pdl = (not cfg.use_pdl_filter) or (
                not pd.isna(pdl) and abs(row["Low"] - pdl) <= atr_val * cfg.pd_proximity
            )
            near_pdh = (not cfg.use_pdl_filter) or (
                not pd.isna(pdh) and abs(row["High"] - pdh) <= atr_val * cfg.pd_proximity
            )

            buy_cond  = buy_sweep  and bool(row["isBullCRT"]) and bull_trend and near_pdl
            sell_cond = sell_sweep and bool(row["isBearCRT"]) and bear_trend and near_pdh

            if buy_cond or sell_cond:
                entry_price = row["Close"]   # enter at close of signal bar
                if buy_cond:
                    sl = row["Low"]  - atr_val * cfg.sl_mult
                    tp = entry_price + atr_val * cfg.tp_mult
                    side = "long"
                else:
                    sl = row["High"] + atr_val * cfg.sl_mult
                    tp = entry_price - atr_val * cfg.tp_mult
                    side = "short"

                notional = equity * cfg.qty_pct_equity / 100.0
                qty = notional / entry_price
                pos = {
                    "side": side, "entry": entry_price,
                    "sl": sl, "tp": tp, "qty": qty,
                    "entry_time": ts,
                }
                trades_today += 1

        prev_in_tbs = bool(row["inTBS"])

        # ---- Mark-to-market equity ----
        mtm = equity
        if pos is not None:
            if pos["side"] == "long":
                mtm += (row["Close"] - pos["entry"]) * pos["qty"]
            else:
                mtm += (pos["entry"] - row["Close"]) * pos["qty"]
        equity_curve[i] = mtm

    return trades, pd.Series(equity_curve, index=df.index, name="Equity")


# ============== STATS ==============
def compute_stats(trades: List[Trade], equity: pd.Series, cfg: Config) -> dict:
    n = len(trades)
    if n == 0:
        return {
            "trades": 0, "wins": 0, "losses": 0, "winrate": 0.0,
            "profit_factor": 0.0, "net_profit": 0.0, "net_profit_pct": 0.0,
            "max_drawdown_pct": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
            "best": 0.0, "worst": 0.0,
            "tp_count": 0, "sl_count": 0,
        }
    pnls   = np.array([t.pnl for t in trades])
    wins   = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gross_w = wins.sum() if len(wins) else 0.0
    gross_l = abs(losses.sum()) if len(losses) else 0.0
    pf = (gross_w / gross_l) if gross_l > 0 else float("inf")

    eq = equity.values
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak * 100.0
    max_dd = dd.min() if len(dd) else 0.0

    return {
        "trades": n,
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "winrate": len(wins) / n * 100.0,
        "profit_factor": pf,
        "net_profit": float(pnls.sum()),
        "net_profit_pct": float(pnls.sum()) / cfg.initial_capital * 100.0,
        "max_drawdown_pct": float(max_dd),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "best": float(pnls.max()),
        "worst": float(pnls.min()),
        "tp_count": int(sum(1 for t in trades if t.exit_reason == "TP")),
        "sl_count": int(sum(1 for t in trades if t.exit_reason == "SL")),
    }


def print_report(symbol: str, stats: dict, cfg: Config):
    print()
    print("=" * 62)
    print(f"  CRT + TBS BACKTEST — {symbol}")
    print("=" * 62)
    print(f"  Initial Capital      : {cfg.initial_capital:>14,.2f}")
    print(f"  Net Profit           : {stats['net_profit']:>14,.2f}  "
          f"({stats['net_profit_pct']:.2f}%)")
    print(f"  Total Trades         : {stats['trades']:>14d}")
    print(f"  Wins / Losses        : {stats['wins']:>5d} / {stats['losses']:d}")
    print(f"  Winrate              : {stats['winrate']:>13.2f}%")
    pf = stats['profit_factor']
    pf_str = "inf" if pf == float('inf') else f"{pf:.2f}"
    print(f"  Profit Factor        : {pf_str:>14}")
    print(f"  Avg Win / Avg Loss   : {stats['avg_win']:>7.2f} / {stats['avg_loss']:.2f}")
    print(f"  Best / Worst Trade   : {stats['best']:>7.2f} / {stats['worst']:.2f}")
    print(f"  TP hits / SL hits    : {stats['tp_count']} / {stats['sl_count']}")
    print(f"  Max Drawdown         : {stats['max_drawdown_pct']:>13.2f}%")
    print("=" * 62)


# ============== MAIN ==============
def main():
    p = argparse.ArgumentParser(description="CRT + TBS Strategy Backtester")
    p.add_argument("--symbol", default="XAUUSD",
                   help="Symbol key (e.g. XAUUSD, EURUSD, BTCUSD)")
    p.add_argument("--period", default="60d",
                   help="yfinance period (e.g. 60d, 730d, 1y)")
    p.add_argument("--interval", default="5m",
                   help="yfinance interval (1m, 5m, 15m, 30m, 1h)")
    p.add_argument("--csv", default=None,
                   help="Optional CSV (datetime,Open,High,Low,Close[,Volume])")
    p.add_argument("--tz", default="America/New_York",
                   help="Strategy timezone")
    p.add_argument("--max-trades", type=int, default=1)
    p.add_argument("--sl-mult", type=float, default=1.0)
    p.add_argument("--tp-mult", type=float, default=2.0)
    p.add_argument("--min-body", type=float, default=50.0,
                   help="Min CRT body %% (default 50)")
    p.add_argument("--save-trades", default=None,
                   help="Optional CSV path to save trade log")
    p.add_argument("--all", action="store_true",
                   help="Run all default symbols and print summary table")
    args = p.parse_args()

    cfg = Config(
        tz=args.tz,
        max_trades_day=args.max_trades,
        sl_mult=args.sl_mult,
        tp_mult=args.tp_mult,
        min_body_pct=args.min_body,
    )

    if args.all:
        results = []
        for sym in DEFAULT_BASKET:
            try:
                df = fetch_yf(sym, args.period, args.interval, cfg.tz)
                trades, eq = run_backtest(df, cfg)
                stats = compute_stats(trades, eq, cfg)
                print_report(sym, stats, cfg)
                results.append({"symbol": sym, **stats})
            except Exception as e:
                print(f"[{sym}] ERROR: {e}")
        if results:
            summary = pd.DataFrame(results)[
                ["symbol", "trades", "wins", "losses",
                 "winrate", "profit_factor", "net_profit_pct", "max_drawdown_pct"]
            ]
            summary = summary.rename(columns={
                "winrate": "winrate%",
                "net_profit_pct": "net%",
                "max_drawdown_pct": "maxDD%",
            })
            print("\n" + "=" * 62)
            print("  SUMMARY — ALL SYMBOLS")
            print("=" * 62)
            print(summary.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
        return

    if args.csv:
        df = load_csv(args.csv, cfg.tz)
        label = args.csv
    else:
        df = fetch_yf(args.symbol, args.period, args.interval, cfg.tz)
        label = args.symbol

    trades, equity = run_backtest(df, cfg)
    stats = compute_stats(trades, equity, cfg)
    print_report(label, stats, cfg)

    if args.save_trades and trades:
        rows = [{
            "entry_time": t.entry_time, "exit_time": t.exit_time,
            "side": t.side, "entry": t.entry_price, "exit": t.exit_price,
            "sl": t.sl, "tp": t.tp, "qty": t.qty,
            "pnl": t.pnl, "reason": t.exit_reason,
        } for t in trades]
        pd.DataFrame(rows).to_csv(args.save_trades, index=False)
        print(f"\nTrade log saved -> {args.save_trades}")


if __name__ == "__main__":
    main()
