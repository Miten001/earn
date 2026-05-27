# Forex Backtesting Bot - Smart Liquidity Reversal Strategy

A comprehensive backtesting system for the Smart Liquidity Reversal (SLR) strategy, written in pure Python with no external dependencies.

## Overview

This backtester evaluates a 5-confluence-condition trading strategy across 6 major forex pairs over approximately 2 years of synthetic (but realistic) 1-minute OHLC data.

### Strategy Conditions (All Must Align)

1. **Killzone Timing** - Trade only during high-probability sessions:
   - Asian: 2-5 AM GMT
   - London: 7-10 AM GMT
   - New York: 12-3 PM GMT

2. **Higher Timeframe Bias** - 4H trend using 200-candle lookback with SMA crossover and swing structure analysis

3. **Supply/Demand Zones** - 1H zones identified by strong rejection candles with continuation

4. **Liquidity Sweep** - 15m price action sweeping beyond recent swing highs/lows then reversing

5. **Price Action Confirmation** - 5m engulfing patterns or pin bars confirming the reversal

### Risk Management

- 1% account risk per trade
- Maximum 3% daily exposure
- Maximum 2 correlated pair trades simultaneously
- TP1: 1:2 Risk-Reward (close 50%)
- TP2: 1:3 Risk-Reward (remaining 50%)
- Stop loss moves to breakeven after TP1 is hit

## Quick Start

```bash
# Run from the project root directory
python backtest/main.py
```

This will:
1. Generate synthetic data if not already present (first run takes a few minutes)
2. Run the backtest across all pairs and sessions
3. Print a comprehensive results report

## File Structure

```
backtest/
  main.py          - Entry point, orchestrates the full pipeline
  generate_data.py - Synthetic 1-minute OHLC data generator
  strategy.py      - Smart Liquidity Reversal strategy logic
  backtester.py    - Main backtesting engine with trade management
  results.py       - Results analysis and reporting
  data/            - Generated CSV data (created on first run)
    EURUSD_1m.csv
    GBPUSD_1m.csv
    GBPJPY_1m.csv
    USDJPY_1m.csv
    AUDUSD_1m.csv
    USDCAD_1m.csv
```

## Using Real Data

To replace synthetic data with real market data:

1. **Prepare your CSV files** with the following format:
   ```
   datetime,open,high,low,close,volume
   2022-01-03 00:00:00,1.13745,1.13750,1.13738,1.13742,45
   2022-01-03 00:01:00,1.13742,1.13748,1.13735,1.13740,38
   ...
   ```

2. **Requirements for the CSV:**
   - Column headers: `datetime`, `open`, `high`, `low`, `close`, `volume`
   - Datetime format: `YYYY-MM-DD HH:MM:SS` (GMT/UTC timezone)
   - 1-minute timeframe (the backtester resamples to higher TFs internally)
   - No gaps during market hours (weekends excluded is fine)
   - Decimal precision: 5 digits for pairs like EURUSD, 3 digits for JPY pairs

3. **Place files in the data directory:**
   ```
   backtest/data/EURUSD_1m.csv
   backtest/data/GBPUSD_1m.csv
   ...
   ```

4. **File naming convention:** `{PAIR}_1m.csv` (e.g., `EURUSD_1m.csv`)

5. **Run the backtest** - it will detect existing data and skip generation:
   ```bash
   python backtest/main.py
   ```

### Data Sources for Real Data

You can obtain historical 1-minute forex data from:
- MetaTrader 4/5 (export from History Center)
- Dukascopy Historical Data (free download)
- TrueFX (tick data that can be aggregated to 1-minute)
- FXCM/Forex.com data feeds

## Customization

### Adjusting Strategy Parameters

Edit `strategy.py` to modify:
- Killzone hours (function `is_killzone`)
- HTF bias lookback period (function `get_htf_bias`)
- Zone detection sensitivity (function `detect_supply_demand_zones`)
- Sweep detection window (function `detect_liquidity_sweep`)
- Confirmation patterns (function `detect_price_action_confirmation`)

### Adjusting Risk Parameters

Edit the `RiskManager` class in `backtester.py`:
- `max_risk_per_trade`: Risk per trade (default 1%)
- `max_daily_risk`: Maximum daily exposure (default 3%)
- `max_correlated`: Max correlated trades (default 2)

### Adding New Pairs

1. Add pair config to `PAIR_CONFIGS` in `generate_data.py`
2. Add to `PAIRS` and `PIP_SIZES` in `backtester.py`
3. Add correlation group in `RiskManager.CORRELATION_GROUPS`

## Output

The results report includes:
- Total trades and overall win rate
- Win rate per pair
- Win rate per session (Asian/London/NY)
- Direction analysis (Buy vs Sell)
- Pattern analysis (which confirmations perform best)
- Average R:R achieved
- Max consecutive wins/losses
- Max drawdown ($ and %)
- Monthly returns breakdown
- Text-based equity curve
- Trade duration analysis

## Requirements

- Python 3.6+
- No external packages needed (uses only standard library)
- Approximately 2-3 GB disk space for generated data
- First run takes 1-2 minutes depending on hardware

## Notes

- The synthetic data uses a seeded random walk (`random.seed(42)`) for reproducibility
- Session volatility patterns mimic real market behavior
- The target is approximately 5000 trades across all pairs over the 2-year period
- Trade results depend on market structure, so synthetic data will produce different statistics than real data
- The strategy is designed to be realistic but past (synthetic) performance is not indicative of real results
