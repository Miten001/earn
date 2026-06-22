# MT5 Multi-Pair Scalping + Arbitrage Bot

Python bot for MetaTrader 5 jo multiple forex pairs pe ek saath scalp karta hai aur triangular arbitrage opportunities pe trade lagata hai.

## Features

- **Scalping** on M1 timeframe — EMA(9/21) crossover + RSI(14) filter + spread filter
- **Triangular arbitrage** on triplets like (EURUSD, USDJPY, EURJPY)
- **Risk controls** — fixed SL/TP, lot size, max open trades, per-pair cap
- **Multi-trade in minutes** — har 2 second scan, parallel pairs
- Magic number isolation — bot ke trades alag se identify hote hain

## Setup

1. **Install MT5 terminal** (Windows / Wine on Mac/Linux). Login with broker (demo recommended).
2. **Install Python deps:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Edit `config.py`:**
   - `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` dalein
   - Pairs / risk params adjust karein
4. **Run:**
   ```bash
   python mt5_bot.py
   ```

## Config Knobs (in `config.py`)

| Param | Default | Kya karta hai |
|---|---|---|
| `SCALP_PAIRS` | 8 majors/minors | Scalping ke liye pairs |
| `ARB_TRIPLETS` | 3 triplets | Arbitrage check ke liye |
| `LOT_SIZE` | 0.01 | Micro lot — start small |
| `SL_PIPS` / `TP_PIPS` | 8 / 12 | Tight scalp SL/TP |
| `MAX_OPEN_TRADES` | 5 | Concurrent positions cap |
| `MAX_SPREAD_POINTS` | 20 | Skip pair if spread > this |
| `ARB_THRESHOLD` | 0.0003 | Arb deviation needed |
| `SCAN_INTERVAL_SEC` | 2 | Loop sleep |
| `RUN_MINUTES` | 60 | 0 = infinite |

## Strategy Logic

### 1. Scalping
- Fetch last 100 M1 candles
- Compute EMA9, EMA21, RSI14 on closed candles
- **BUY** if EMA9 crosses *above* EMA21 and 30 < RSI < 70
- **SELL** if EMA9 crosses *below* EMA21 and 30 < RSI < 70
- Spread filter rejects bad-quote moments

### 2. Triangular Arbitrage
For triplet (A/B, B/C, A/C):
```
synthetic = ask(A/B) * ask(B/C)
real      = ask(A/C)
dev       = (synthetic - real) / real
```
Agar `|dev| > ARB_THRESHOLD` to 3-leg trade lagao (long undervalued, short overvalued).

> **Note:** Real arbitrage is hard — most retail brokers ka spread + execution delay ROI kha jata hai. Threshold realistic rakhein.

## Important Warnings

- **DEMO account pe pehle test karein.** Forex me capital loss ka real risk hai.
- Broker ka algo trading allow hona chahiye (most do).
- VPS pe 24/7 chalana practical hai — local laptop sleep me bot band ho jata hai.
- Backtest before scaling lot size. Past performance != future returns.

## Stop the bot
Ctrl+C — clean shutdown, MT5 disconnect ho jata hai. Open trades automatically close nahi hote, manually close karein ya broker ka stop level handle karega.
