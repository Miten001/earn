"""
MT5 Multi-Pair Scalping + Triangular Arbitrage Bot
==================================================
Strategy:
  1) SCALPING per pair on M1:
       - EMA(9) > EMA(21) trending up + RSI between 30-70 -> BUY
       - EMA(9) < EMA(21) trending down + RSI between 30-70 -> SELL
       - Spread filter to avoid bad fills
       - Tight SL / TP for quick scalps
  2) TRIANGULAR ARBITRAGE:
       - For triplet (A/B, B/C, A/C): theoretical = ask(A/B) * ask(B/C)
       - If |theoretical - ask(A/C)| / ask(A/C) > threshold -> 3-leg trade

Runs every SCAN_INTERVAL_SEC, can place multiple trades per minute.

USAGE:
    1. pip install -r requirements.txt
    2. Fill credentials in config.py (DEMO ACCOUNT FIRST!)
    3. python mt5_bot.py

WARNING: Forex trading involves substantial risk. Test on demo before live.
"""

import time
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[!] MetaTrader5 package nahi mila. Run: pip install MetaTrader5")
    sys.exit(1)

import config as cfg


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# --------------------------------------------------------------------------- #
# MT5 helpers
# --------------------------------------------------------------------------- #
TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
}


def init_mt5() -> bool:
    kwargs = {}
    if cfg.MT5_PATH:
        kwargs["path"] = cfg.MT5_PATH
    if cfg.MT5_LOGIN:
        kwargs.update(
            login=cfg.MT5_LOGIN,
            password=cfg.MT5_PASSWORD,
            server=cfg.MT5_SERVER,
        )

    if not mt5.initialize(**kwargs):
        print(f"[!] MT5 init failed: {mt5.last_error()}")
        return False

    acc = mt5.account_info()
    if acc is None:
        print(f"[!] Account info nahi mila: {mt5.last_error()}")
        return False
    print(f"[+] Connected: {acc.login} | Balance: {acc.balance} {acc.currency}")
    return True


def get_rates(symbol: str, tf: str, n: int = 100) -> pd.DataFrame | None:
    bars = mt5.copy_rates_from_pos(symbol, TF_MAP[tf], 0, n)
    if bars is None or len(bars) < 30:
        return None
    df = pd.DataFrame(bars)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def get_tick(symbol: str):
    if not mt5.symbol_select(symbol, True):
        return None
    return mt5.symbol_info_tick(symbol)


def pip_size(symbol: str) -> float:
    info = mt5.symbol_info(symbol)
    if info is None:
        return 0.0001
    # JPY pairs use 0.01 as a pip; everything else 0.0001
    return 0.01 if "JPY" in symbol else 0.0001


def spread_points(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    return info.spread if info else 9999


def open_positions_count(symbol: str | None = None) -> int:
    pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if pos is None:
        return 0
    return sum(1 for p in pos if p.magic == cfg.MAGIC_NUMBER)


# --------------------------------------------------------------------------- #
# Order placement
# --------------------------------------------------------------------------- #
def place_order(symbol: str, side: str, lot: float, comment: str = "scalp") -> bool:
    tick = get_tick(symbol)
    if tick is None:
        return False

    info = mt5.symbol_info(symbol)
    if info is None or not info.visible:
        return False

    ps = pip_size(symbol)
    digits = info.digits

    if side == "BUY":
        price = tick.ask
        sl = round(price - cfg.SL_PIPS * ps, digits)
        tp = round(price + cfg.TP_PIPS * ps, digits)
        order_type = mt5.ORDER_TYPE_BUY
    else:
        price = tick.bid
        sl = round(price + cfg.SL_PIPS * ps, digits)
        tp = round(price - cfg.TP_PIPS * ps, digits)
        order_type = mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": cfg.MAGIC_NUMBER,
        "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"[!] {symbol} order_send returned None: {mt5.last_error()}")
        return False
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[!] {symbol} {side} failed retcode={result.retcode} {result.comment}")
        return False
    print(f"[+] {symbol} {side} {lot} @ {price} SL={sl} TP={tp}  ({comment})")
    return True


# --------------------------------------------------------------------------- #
# Strategy 1: EMA + RSI scalping
# --------------------------------------------------------------------------- #
def scalp_signal(symbol: str) -> str | None:
    df = get_rates(symbol, cfg.TIMEFRAME, 100)
    if df is None:
        return None

    df["ema_f"] = ema(df["close"], cfg.EMA_FAST)
    df["ema_s"] = ema(df["close"], cfg.EMA_SLOW)
    df["rsi"] = rsi(df["close"], cfg.RSI_PERIOD)

    last = df.iloc[-2]   # use closed candle, ignore forming one
    prev = df.iloc[-3]

    if pd.isna(last["rsi"]):
        return None

    # Bullish crossover with healthy RSI
    if (
        prev["ema_f"] <= prev["ema_s"]
        and last["ema_f"] > last["ema_s"]
        and cfg.RSI_LOW < last["rsi"] < cfg.RSI_HIGH
    ):
        return "BUY"

    # Bearish crossover with healthy RSI
    if (
        prev["ema_f"] >= prev["ema_s"]
        and last["ema_f"] < last["ema_s"]
        and cfg.RSI_LOW < last["rsi"] < cfg.RSI_HIGH
    ):
        return "SELL"

    return None


def run_scalper():
    placed = 0
    for symbol in cfg.SCALP_PAIRS:
        # caps
        if open_positions_count() >= cfg.MAX_OPEN_TRADES:
            break
        if open_positions_count(symbol) >= cfg.MAX_TRADES_PER_PAIR:
            continue
        if spread_points(symbol) > cfg.MAX_SPREAD_POINTS:
            continue

        sig = scalp_signal(symbol)
        if sig and place_order(symbol, sig, cfg.LOT_SIZE, comment=f"scalp_{sig}"):
            placed += 1
    return placed


# --------------------------------------------------------------------------- #
# Strategy 2: Triangular arbitrage
# --------------------------------------------------------------------------- #
def arb_signal(triplet):
    """
    For (A/B, B/C, A/C):
        synthetic A/C = (A/B) * (B/C)
        Compare with real A/C.
    Returns ("LONG_AC"|"SHORT_AC", deviation) or None.
    """
    s_ab, s_bc, s_ac = triplet
    t_ab = get_tick(s_ab)
    t_bc = get_tick(s_bc)
    t_ac = get_tick(s_ac)
    if not (t_ab and t_bc and t_ac):
        return None
    if min(t_ab.ask, t_bc.ask, t_ac.ask) <= 0:
        return None

    synthetic = t_ab.ask * t_bc.ask
    real = t_ac.ask
    dev = (synthetic - real) / real

    if abs(dev) < cfg.ARB_THRESHOLD:
        return None

    # synthetic > real => A/C undervalued => buy A/C, hedge by selling A/B and B/C
    if dev > 0:
        return ("LONG_AC", dev)
    return ("SHORT_AC", dev)


def run_arb():
    placed = 0
    for triplet in cfg.ARB_TRIPLETS:
        if open_positions_count() >= cfg.MAX_OPEN_TRADES:
            break
        sig = arb_signal(triplet)
        if not sig:
            continue
        direction, dev = sig
        s_ab, s_bc, s_ac = triplet
        print(f"[~] ARB {triplet} dev={dev:.5f} -> {direction}")
        if direction == "LONG_AC":
            ok = (
                place_order(s_ac, "BUY",  cfg.LOT_SIZE, "arb_buyAC")
                and place_order(s_ab, "SELL", cfg.LOT_SIZE, "arb_sellAB")
                and place_order(s_bc, "SELL", cfg.LOT_SIZE, "arb_sellBC")
            )
        else:
            ok = (
                place_order(s_ac, "SELL", cfg.LOT_SIZE, "arb_sellAC")
                and place_order(s_ab, "BUY",  cfg.LOT_SIZE, "arb_buyAB")
                and place_order(s_bc, "BUY",  cfg.LOT_SIZE, "arb_buyBC")
            )
        if ok:
            placed += 3
    return placed


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def main():
    if not init_mt5():
        return

    # Make sure all symbols are available in MarketWatch
    for s in set(cfg.SCALP_PAIRS) | {x for trip in cfg.ARB_TRIPLETS for x in trip}:
        mt5.symbol_select(s, True)

    end = (
        datetime.now() + timedelta(minutes=cfg.RUN_MINUTES)
        if cfg.RUN_MINUTES > 0
        else None
    )
    print(f"[*] Bot started. Scan every {cfg.SCAN_INTERVAL_SEC}s. "
          f"{'Runs forever.' if end is None else f'Ends at {end:%H:%M:%S}'}")

    try:
        while True:
            if end and datetime.now() >= end:
                print("[*] Time up, stopping.")
                break

            scalp_n = run_scalper()
            arb_n = run_arb()
            if scalp_n or arb_n:
                print(f"[i] Placed scalp={scalp_n} arb={arb_n} "
                      f"open={open_positions_count()}")
            time.sleep(cfg.SCAN_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("\n[*] Ctrl+C - stopping.")
    finally:
        mt5.shutdown()
        print("[*] MT5 disconnected.")


if __name__ == "__main__":
    main()
