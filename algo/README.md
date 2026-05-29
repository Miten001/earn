# CRT + TBS ULTIMATE SNIPER PRO — Python Backtester

Pine Script v6 strategy ka Python version. **Real data fetch karke real winrate** deta hai — Forex, Gold, Silver, BTC, ETH sab pairs ka.

---

## Setup (1 baar)

```bash
# repo clone karo (agar nahi kiya)
git clone https://github.com/Miten001/earn.git
cd earn/algo

# python 3.10+ required
pip install -r requirements.txt
```

---

## Use kaise karein

### 1. Single symbol pe backtest

```bash
python crt_tbs_backtest.py --symbol XAUUSD --period 60d --interval 5m
```

### 2. **Sab pairs ek saath** (forex + metals + crypto)

```bash
python crt_tbs_backtest.py --all --period 60d --interval 5m
```

Last me ek summary table milega:

```
SUMMARY — ALL SYMBOLS
symbol  trades  wins  losses  winrate%  profit_factor  net%  maxDD%
XAUUSD     ...   ...     ...      ...            ...   ...     ...
EURUSD     ...
GBPUSD     ...
...
```

### 3. Apna CSV use karo (lambi history ke liye)

```bash
python crt_tbs_backtest.py --csv mydata.csv --tz America/New_York
```

CSV format:
```csv
datetime,Open,High,Low,Close,Volume
2024-01-02 09:30:00,2050.5,2052.3,2049.8,2051.7,12345
...
```

### 4. Trade log save karo (har trade ka detail)

```bash
python crt_tbs_backtest.py --symbol XAUUSD --save-trades trades.csv
```

---

## Supported Symbols

| Key | yfinance Ticker | Asset |
|---|---|---|
| `EURUSD`, `GBPUSD`, `USDJPY`, `GBPJPY`, `USDCHF`, `USDCAD`, `AUDUSD`, `NZDUSD` | `*=X` | Forex |
| `XAUUSD` | `GC=F` | Gold futures |
| `XAGUSD` | `SI=F` | Silver futures |
| `BTCUSD` | `BTC-USD` | Bitcoin |
| `ETHUSD` | `ETH-USD` | Ethereum |

---

## Tunable Parameters

| Flag | Default | Matlab |
|---|---|---|
| `--period` | `60d` | History length (yfinance limit: 5m → 60d max, 1h → 730d max) |
| `--interval` | `5m` | Candle timeframe |
| `--tz` | `America/New_York` | Strategy timezone (sessions ke liye) |
| `--max-trades` | `1` | Max trades per day |
| `--sl-mult` | `1.0` | SL = ATR × is multiplier |
| `--tp-mult` | `2.0` | TP = ATR × is multiplier |
| `--min-body` | `50` | Min CRT candle body % |

---

## Strategy Logic (kya detect karta hai)

1. **TBS Range** banta hai 09:15–09:45 (NY tz) ke beech — High/Low capture
2. TBS khatam hone ke baad **Killzone** (London 02:00–05:00 ya NY 08:00–11:00) me trade dekha jata hai
3. **Liquidity Sweep:**
   - **Buy:** price TBS Low ke neeche gira but close uske upar + bullish candle
   - **Sell:** price TBS High ke upar gaya but close uske neeche + bearish candle
4. **CRT confirmation:** body ≥ 50% of total range
5. **HTF trend filter:** 1H EMA(50) — long sirf bull trend me, short sirf bear me
6. **Optional:** PDH/PDL proximity (ATR × 1.5)
7. **Risk:** SL = ATR × 1.0, TP = ATR × 2.0 (1:2 RR)
8. **Daily lock:** ek win ke baad us din aur trade nahi

---

## Important Notes ⚠️

- **yfinance ki limit:** 5m data sirf last 60 din, 1h data 730 din. Lambi backtest ke liye broker/MT5 data export karke `--csv` use karo.
- **Forex weekend gaps** normal hain — script handle kar leta hai.
- **Backtest ≠ live performance.** Real account pe slippage, spread, requote, latency hota hai. Demo pe test karo pehle.
- **Sample size** check karo — 60 din me 5–20 trades hi aayenge (max 1/day rule). Statistically meaningful sample ke liye 6+ months chahiye.
- Ye **financial advice nahi hai**. Apni risk tolerance ke hisab se decide karo.

---

## Troubleshooting

**"No data returned"** → symbol/period galat hai. `--interval 1h --period 730d` try karo.

**0 trades** → 
- `tz` symbol ke exchange ke saath match nahi kar raha
- `--max-trades 5` karke check karo  
- HTF trend filter kabhi flip nahi ho raha → `--period` badhao

**yfinance install error** → `pip install --upgrade yfinance` ya `pip install yfinance==0.2.40`
