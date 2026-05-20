# SMC / ICT Bot — Strategy Documentation

## Concepts (jaldi se samjho)

**SMC (Smart Money Concepts)** aur **ICT (Inner Circle Trader)** ye theory hai ki:
> *Banks aur institutions retail traders ke stops "grab" karke market move karte hain. Hum unhe follow karein, against nahi.*

Core building blocks:

| Term | Hindi me | Bot me |
|---|---|---|
| **Market Structure** | Trend ki direction (HH/HL ya LH/LL) | H1 pe pivots se decide |
| **BOS** (Break of Structure) | Trend continue ho raha | Implicit in HH/HL check |
| **CHoCH** (Change of Character) | Trend reverse hone ka first signal | M5 pe detect |
| **Liquidity Sweep** | Stop hunt — wick beyond swing point | M15 pe detect |
| **FVG** (Fair Value Gap) | 3-candle me imbalance / gap | M5 pe POI ke liye |
| **Order Block** | Last opposing candle before BOS | (Future enhancement) |
| **Killzone** | High-volume sessions only | London 7-10 UTC, NY 12-15 UTC |
| **Premium/Discount** | Range ka upper/lower half | Built into FVG logic |

## Setup (entry sequence)

Ye bot **classic ICT 2022 model** implement karta hai:

```
Step 1: H1 pe market direction check       (HH/HL = UP, LH/LL = DOWN)
   ↓
Step 2: M15 pe liquidity sweep wait        (price grabs stops, then reverses)
   ↓
Step 3: M5 pe CHoCH confirm                (structure shift in HTF direction)
   ↓
Step 4: M5 pe unfilled FVG identify        (POI = entry zone)
   ↓
Step 5: Killzone check                     (London ya NY hours)
   ↓
Step 6: Pending LIMIT order @ FVG midpoint  (price retrace pe fill hoga)
   ↓
Step 7: SL = beyond swept liquidity         (jahan stops grab kiye the)
   ↓
Step 8: TP = next opposing pool             (next H1 swing high/low)
```

## Example trade (LONG)

**Setup:**
- H1: Last 3 swings — HH at 1.0850, HL at 1.0820, HH at 1.0880, HL at 1.0840 → **UP bias**
- M15: Recent swing low at 1.0855. Price wicks down to 1.0848 then closes at 1.0862 → **liquidity sweep below 1.0855**
- M5: After sweep, price breaks above last M5 swing high at 1.0875 → **CHoCH confirmed UP**
- M5: Bullish FVG between 1.0865 and 1.0870 (unfilled) → **POI for entry**
- Time: 08:30 UTC → London Killzone ✓

**Entry plan:**
- Entry: 1.0867 (FVG midpoint, pending BUY LIMIT)
- SL: 1.0846 (sweep low − 0.3 ATR buffer = 21 pips)
- TP: 1.0920 (next H1 swing high) = 53 pips
- **R:R ≈ 1:2.5**
- Lot: calculated to risk exactly 3% of balance over 21 pips

## Why this is "smart money" approach

1. **Trades WITH institutions, not against** — sweep + CHoCH = institutional accumulation/distribution footprint
2. **Asymmetric R:R** — entries at FVG (deep retracement) give 2-5R potential
3. **Killzone filter** — only when actual volume is in market (London/NY)
4. **No lagging indicators** — pure price action structure

## Realistic performance expectation

| Metric | Expected range |
|---|---|
| Setups per day | 1-4 across 10 pairs |
| Win rate | **45-58%** (better than v2 because of confluence filter) |
| Avg R per trade | +1.0 to +2.0R |
| Profit factor target | 2.0-3.0 |
| Max drawdown (3% risk) | 20-30% in tough months |

⚠️ SMC bots me setups **kam** lagte hain (high quality > quantity). Kabhi kabhi pure din 0 trade. That's correct behavior — jab confluence nahi to baith jao.

## Limitations / Honest disclaimers

1. **Pivot detection bot vs visual:** Real SMC traders eyes use karte hain. Bot fractal-based hai — kabhi kabhi different swings choose karega.
2. **FVG fill detection:** Bot checks if price crossed FVG; real ICT requires "balance" achieved (specific candle close logic). Implementation simplified.
3. **Order Block:** Bot uses FVG only; OB add karna future enhancement (more complex logic).
4. **Pending limit expiry:** 4 hours. Agar price wapas FVG nahi aaya, order auto-cancel.
5. **Crypto 24/7:** Killzone skip karta hai crypto pe, but BTC pe Asia session illiquid — manually exclude kar sakte ho `SYMBOLS_CRYPTO = []`.

## Comparison: v2 (Trend Following) vs SMC bot

| Aspect | v2 Trend Bot | SMC/ICT Bot |
|---|---|---|
| Style | Pullback continuation | Stop hunt reversal |
| Entry trigger | EMA pullback + RSI cross | Sweep + CHoCH + FVG |
| Win rate | 40-48% | 45-58% |
| Avg R | 0.8-1.2R | 1.0-2.0R |
| Trades/day | 2-8 | 1-4 |
| Best market | Strong trends | Choppy + ranging + reversals |

**Pro tip:** Run **both bots** on different magic numbers — they trade complementary setups. Trend bot pakadta hai trends, SMC bot pakadta hai reversals.

## File: `smc_ict_bot.py`

Same risk infra as v2 final bot:
- 3% risk per trade (auto position size)
- Multi-pair (forex + crypto + gold)
- Smart trailing (BE @ 1R, lock @ 1.5R, ATR trail @ 2R+)
- State persistence in `smc_bot_state.json`

Run karne ka tarika same:
```bash
pip install MetaTrader5 pandas numpy
# Edit credentials at top of smc_ict_bot.py
python smc_ict_bot.py
```
