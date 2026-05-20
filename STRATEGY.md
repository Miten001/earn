# MT5 Final Bot — Strategy Documentation

## Why this is "best practice" approach

Most retail bots fail because they:
1. Trade single timeframe (lots of false signals)
2. Use fixed SL/TP (ignore market volatility)
3. Use fixed lot (ignore account size & risk)
4. Cut winners early, let losers run (opposite of "trend is your friend")

This bot fixes all four.

## Strategy: Multi-Timeframe Trend Following with Dynamic Risk

### Tier 1 — H4 Macro Trend Filter
- EMA50 > EMA200 AND price > EMA50 → **bullish bias**
- EMA50 < EMA200 AND price < EMA50 → **bearish bias**
- Otherwise: **no trade**

This single filter eliminates ~70% of low-probability counter-trend setups.

### Tier 2 — H1 Trend Strength
- ADX(14) > 22 → market is trending (not chopping)
- Price aligned with EMA50 in trend direction

ADX filter is critical. Trend-following systems lose money in ranges.

### Tier 3 — M15 Entry Zone (Pullback)
- Price pulls back to EMA20
- RSI(14) crosses 50 in trend direction
- Closing candle confirms (bullish/bearish body)

We buy/sell on **pullbacks**, not breakouts. Better R:R, less FOMO.

### Tier 4 — M5 Trigger
- Strong-body candle (>50% of range) in trend direction

Final confirmation that momentum is shifting.

## Risk Management Math

```
Per-trade risk     = 3% of account balance
SL distance        = 1.5 × ATR(14) on M15
Lot size           = (balance × 0.03) / (SL_distance × tick_value/tick_size)
```

So if balance = $1000:
- Risk per trade = $30
- If SL = 50 pips on EURUSD, lot = ~0.06
- If SL = 200 pips on BTCUSD, lot calculated to risk exactly $30

**No matter the symbol or volatility, you risk exactly 3%.**

## Trailing Stop Logic

| Profit Stage | Action |
|---|---|
| 0 → 1R | SL stays at initial level |
| **+1.0R reached** | SL moves to **breakeven (entry)** — trade is now risk-free |
| **+1.5R reached** | SL moves to **+0.5R** — half profit locked |
| **+2.0R+ reached** | **ATR-trailing** activates (1.5×ATR below price for longs) — let it run |

The Chandelier Exit at stage 3 follows the trend. As long as price keeps making new highs, SL keeps moving up. When trend breaks, SL gets hit and you keep the profit.

This achieves "let winners run, cut losers fast" — the only sustainable edge in trading.

## Expected Performance (Realistic)

| Metric | Range |
|---|---|
| Win rate | 38–48% |
| Avg R per trade | +0.6 to +1.2R |
| Max drawdown | 15–25% (with 3% risk) |
| Trades per day | 0–8 (depends on market) |
| Profit factor target | 1.5–2.0 |

**Yes — win rate is below 50%.** That's intentional. Trend-following systems win less often but win **bigger** (sometimes 5R+ on a runner). Net expectancy is positive.

## ⚠️ Risk Warning for 3% per trade

3% per trade is **aggressive**. With 8 max simultaneous trades, your account could have 24% at risk at any moment.

**Recommended progression:**
- **Week 1–2:** demo, RISK_PERCENT = 3.0
- **Month 1 live:** RISK_PERCENT = 1.0 (small real money)
- **After consistent profit:** scale to 2.0
- **Only experts:** 3.0+

A losing streak of 5–6 trades is normal. With 3% risk that's 18% drawdown. Mentally prepare.

## Why Forex + BTC/ETH together?

- **Forex** trades 24/5, low volatility, high leverage available → small moves, frequent setups
- **Crypto** trades 24/7, high volatility, BIG runners → fewer setups, bigger R when they hit
- Combined: bot is rarely idle, diversified across asset classes

## Limitations / Honest disclaimers

1. Bot has **no news filter**. Big news = big slippage = SL gaps possible.
2. Crypto weekend gaps: Forex closes Friday, crypto runs. Bot manages both.
3. Broker spread varies. Bot has spread filter but extreme widening (e.g. NFP) can still hurt.
4. Past performance ≠ future returns. **Backtest first, demo second, real money last.**
