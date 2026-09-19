# CRT + TBS Strategy — Complete Backtest Results

Strategy: "CRT + TBS ULTIMATE SNIPER PRO" (Pine Script v6) ported to Python.
Engine: `run_local_backtest_v3.py` (true 1:2 RR via risk-based TP).
Data: 10+ years historical OHLC from public GitHub repos.
Cost model: 0.02% commission per side. **No spread/slippage modeled.**

> NOTE on timezone: forex/gold data is in the source broker's time
> (≈GMT+2). Sessions (TBS 09:15-09:45, London, NY) are applied in that
> time. On TradingView with a different chart timezone, numbers will shift.

---

## Winrate by Symbol & Timeframe

| Symbol | m5 | m15 | m30 | h1 | h4 |
|--------|----:|----:|----:|----:|----:|
| EURUSD | – | 33.33% | 29.78% | 0 trades | 0 trades |
| GBPUSD | – | 33.69% | 34.98% | 0 trades | 0 trades |
| USDJPY | – | 35.12% | 36.23% | 0 trades | 0 trades |
| GBPJPY | – | 34.17% | 33.17% | 0 trades | 0 trades |
| AUDUSD | – | 30.44% | 31.67% | 0 trades | 0 trades |
| USDCAD | – | 32.83% | 26.70% | 0 trades | 0 trades |
| USDCHF | – | 37.68% | 32.75% | 0 trades | 0 trades |
| EURJPY | – | 34.82% | 37.66% | 0 trades | 0 trades |
| **XAUUSD (Gold)** | – | 33.41% | 32.17% | 0 trades | 0 trades |
| **BTCUSD** | 29.89% | 33.85% | 35.60% | 0 trades | – |
| **ETHUSD** | 34.47% | 37.32% | 35.47% | 0 trades | – |
| **XAGUSD (Silver)** | NO PUBLIC DATA FOUND | | | | |

## Profit Factor by Symbol & Timeframe (>1.0 = profitable)

| Symbol | m5 | m15 | m30 |
|--------|----:|----:|----:|
| EURUSD | – | 0.74 | 0.79 |
| GBPUSD | – | 0.65 | 0.87 |
| USDJPY | – | 0.75 | 0.84 |
| GBPJPY | – | 0.82 | 0.86 |
| AUDUSD | – | 0.62 | 0.75 |
| USDCAD | – | 0.60 | 0.51 |
| USDCHF | – | 0.90 | 0.86 |
| EURJPY | – | 0.81 | 0.96 |
| **XAUUSD (Gold)** | – | 0.75 | 0.77 |
| **BTCUSD** | 0.88 | 0.96 | **1.06** ✅ |
| **ETHUSD** | 0.86 | **1.10** ✅ | **1.18** ✅ |

---

## Key Findings

1. **h1 / h4 timeframes = 0 trades for everyone.** The TBS range session
   is a 30-minute window; it cannot form inside a 1-hour or 4-hour candle.
   The strategy is intraday-only (m5–m30).

2. **Forex + Gold: NOT profitable on any timeframe.** All 9 forex pairs
   and gold show PF < 1.0 (best = EURJPY m30 at 0.96). Winrate ~30-38%,
   which is around the break-even rate for 1:2 RR with no edge.

3. **Crypto m30 is the only profitable zone:**
   - ETHUSD m30: PF 1.18, +4.00%, 172 trades
   - ETHUSD m15: PF 1.10, +2.24%, 276 trades
   - BTCUSD m30: PF 1.06, +2.48%, 455 trades

4. **m5 too noisy** (more false sweeps); **m30 better than m15** on most
   instruments (less noise, smaller average loss).

---

## Caveats / Honest Warnings

- **No spread/slippage** in model — only 0.02% commission. Real crypto
  exchange round-trip fees + slippage could push PF 1.06 below 1.0.
- **Sample sizes borderline** for the profitable crypto cells (172-455).
- **Silver (XAGUSD) untested** — no committed public dataset located.
  Provide a CSV (`datetime,Open,High,Low,Close,Volume`) to include it.
- **Backtest ≠ live performance.** Forward-test on demo before risking
  real capital.
- This is **not financial advice.**

---

## Data Sources (public GitHub)

- Forex + Gold (m15/m30/h1/h4): `ejtraderLabs/historical-data`
- BTC (1-min, 2012-2025): `ff137/bitstamp-btcusd-minute-data`
- ETH (1-min, 2016-2021): `Vitaly007/Bitfinex-historical-data-AND-CryptoCompare-historical-data`
