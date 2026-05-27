"""
backtester.py - Main Backtesting Engine

Loads generated 1-minute data, resamples to multiple timeframes,
runs the Smart Liquidity Reversal strategy across all pairs and sessions,
and tracks all trades with full P/L and risk management.

Risk Management:
- 1% account risk per trade
- Maximum 3% daily exposure
- Maximum 2 correlated pair trades simultaneously

Uses only Python standard library.
"""

import csv
import os
from datetime import datetime, timedelta

from strategy import (
    check_strategy_conditions,
    is_killzone,
)


# ============================================================
# DATA LOADING AND RESAMPLING
# ============================================================

def load_csv_data(filepath):
    """
    Load 1-minute OHLC data from CSV file.
    
    Args:
        filepath: Path to CSV file
    
    Returns:
        list: List of candle dicts with keys: datetime, open, high, low, close, volume
    """
    candles = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append({
                "datetime": datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S"),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            })
    return candles


def resample_candles(candles_1m, period_minutes):
    """
    Resample 1-minute candles to a higher timeframe.
    
    Args:
        candles_1m: List of 1-minute candle dicts
        period_minutes: Target timeframe in minutes (5, 15, 60, 240)
    
    Returns:
        list: Resampled candle dicts
    """
    if not candles_1m:
        return []

    resampled = []
    bucket = []

    for candle in candles_1m:
        # Determine which period bucket this candle belongs to
        dt = candle["datetime"]
        # Calculate minutes since midnight
        minutes_since_midnight = dt.hour * 60 + dt.minute
        # Determine period start
        period_start = (minutes_since_midnight // period_minutes) * period_minutes
        # Also account for date
        period_key = (dt.date(), period_start)

        if bucket and bucket[0] != period_key:
            # Flush previous bucket
            bucket_candles = bucket[1]
            if bucket_candles:
                resampled_candle = {
                    "datetime": bucket_candles[0]["datetime"],
                    "open": bucket_candles[0]["open"],
                    "high": max(c["high"] for c in bucket_candles),
                    "low": min(c["low"] for c in bucket_candles),
                    "close": bucket_candles[-1]["close"],
                    "volume": sum(c["volume"] for c in bucket_candles),
                }
                resampled.append(resampled_candle)
            bucket = [period_key, [candle]]
        elif not bucket:
            bucket = [period_key, [candle]]
        else:
            bucket[1].append(candle)

    # Flush last bucket
    if bucket and bucket[1]:
        bucket_candles = bucket[1]
        resampled_candle = {
            "datetime": bucket_candles[0]["datetime"],
            "open": bucket_candles[0]["open"],
            "high": max(c["high"] for c in bucket_candles),
            "low": min(c["low"] for c in bucket_candles),
            "close": bucket_candles[-1]["close"],
            "volume": sum(c["volume"] for c in bucket_candles),
        }
        resampled.append(resampled_candle)

    return resampled


# ============================================================
# TRADE MANAGEMENT
# ============================================================

class Trade:
    """Represents a single trade with partial TP management."""

    def __init__(self, pair, signal, account_balance, risk_percent=1.0):
        self.pair = pair
        self.direction = signal["direction"]
        self.session = signal["session"]
        self.entry_price = signal["entry_price"]
        self.stop_loss = signal["stop_loss"]
        self.tp1 = signal["tp1"]
        self.tp2 = signal["tp2"]
        self.risk_amount = signal["risk"]
        self.pattern = signal["pattern"]
        self.entry_time = signal["datetime"]
        self.zone = signal["zone"]

        # Risk management - use fixed 1% of initial 10000 = $100 per trade
        # This prevents exponential compounding and gives realistic results
        self.risk_percent = risk_percent
        self.position_risk = 100.0  # Fixed $100 risk per trade (1% of $10,000)

        # Trade state
        self.tp1_hit = False
        self.tp2_hit = False
        self.stopped_out = False
        self.closed = False
        self.exit_time = None
        self.exit_price = None
        self.pnl = 0.0
        self.rr_achieved = 0.0

    def update(self, candle):
        """
        Update trade state based on new price candle.
        
        Args:
            candle: Dict with high, low, close, datetime keys
        
        Returns:
            bool: True if trade is now closed
        """
        if self.closed:
            return True

        high = candle["high"]
        low = candle["low"]

        if self.direction == 1:  # Long trade
            # Check stop loss first (worst case)
            if low <= self.stop_loss:
                self._close_trade(self.stop_loss, candle["datetime"], "stop_loss")
                return True

            # Check TP1
            if not self.tp1_hit and high >= self.tp1:
                self.tp1_hit = True
                # Move stop to breakeven after TP1
                self.stop_loss = self.entry_price

            # Check TP2
            if self.tp1_hit and high >= self.tp2:
                self._close_trade(self.tp2, candle["datetime"], "tp2")
                return True

        else:  # Short trade
            # Check stop loss first
            if high >= self.stop_loss:
                self._close_trade(self.stop_loss, candle["datetime"], "stop_loss")
                return True

            # Check TP1
            if not self.tp1_hit and low <= self.tp1:
                self.tp1_hit = True
                # Move stop to breakeven after TP1
                self.stop_loss = self.entry_price

            # Check TP2
            if self.tp1_hit and low <= self.tp2:
                self._close_trade(self.tp2, candle["datetime"], "tp2")
                return True

        return False

    def _close_trade(self, exit_price, exit_time, reason):
        """Close the trade and calculate P/L."""
        self.closed = True
        self.exit_price = exit_price
        self.exit_time = exit_time

        if reason == "stop_loss":
            if self.tp1_hit:
                # TP1 was hit (50% at 2R) then stopped at BE on remaining
                self.pnl = self.position_risk * 1.0  # Net: +1R (50% * 2R)
                self.rr_achieved = 1.0
            else:
                # Full stop loss
                self.pnl = -self.position_risk
                self.rr_achieved = -1.0
                self.stopped_out = True
        elif reason == "tp2":
            # TP1 hit (50% at 2R) + TP2 hit (50% at 3R) = 2.5R total
            self.pnl = self.position_risk * 2.5
            self.rr_achieved = 2.5
            self.tp2_hit = True

    def to_dict(self):
        """Convert trade to dictionary for results tracking."""
        return {
            "pair": self.pair,
            "direction": "BUY" if self.direction == 1 else "SELL",
            "session": self.session,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "stop_loss": self.stop_loss,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp1_hit": self.tp1_hit,
            "tp2_hit": self.tp2_hit,
            "stopped_out": self.stopped_out,
            "pnl": self.pnl,
            "rr_achieved": self.rr_achieved,
            "pattern": self.pattern,
            "risk_percent": self.risk_percent,
        }


# ============================================================
# RISK MANAGER
# ============================================================

class RiskManager:
    """
    Manages position sizing and risk limits.
    
    Rules:
    - Max 1% risk per trade
    - Max 3% total daily exposure
    - Max 2 correlated trades simultaneously
    """

    # Correlation groups - pairs that tend to move together
    CORRELATION_GROUPS = {
        "USD_LONG": ["EURUSD", "GBPUSD", "AUDUSD"],  # These move inversely to USD
        "USD_SHORT": ["USDJPY", "USDCAD"],  # These move with USD
        "GBP": ["GBPUSD", "GBPJPY"],  # GBP pairs
    }

    def __init__(self, initial_balance=10000.0, max_risk_per_trade=1.0,
                 max_daily_risk=3.0, max_correlated=2):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_risk = max_daily_risk
        self.max_correlated = max_correlated

        self.open_trades = []
        self.daily_risk_used = 0.0
        self.current_date = None

    def reset_daily(self, date):
        """Reset daily risk counter for a new day."""
        if self.current_date != date:
            self.current_date = date
            self.daily_risk_used = 0.0

    def can_take_trade(self, pair, direction):
        """
        Check if a new trade is allowed based on risk rules.
        
        Args:
            pair: Currency pair name
            direction: Trade direction (1 or -1)
        
        Returns:
            bool: True if trade is allowed
        """
        # Check daily risk limit
        if self.daily_risk_used + self.max_risk_per_trade > self.max_daily_risk:
            return False

        # Check correlated trades
        correlated_count = 0
        for trade in self.open_trades:
            if not trade.closed:
                # Check if same pair
                if trade.pair == pair:
                    return False  # No duplicate pair trades

                # Check correlation groups
                for group_pairs in self.CORRELATION_GROUPS.values():
                    if pair in group_pairs and trade.pair in group_pairs:
                        if trade.direction == direction:
                            correlated_count += 1

        if correlated_count >= self.max_correlated:
            return False

        return True

    def open_trade(self, trade):
        """Register a new open trade."""
        self.open_trades.append(trade)
        self.daily_risk_used += trade.risk_percent

    def close_trade(self, trade):
        """Process a closed trade."""
        self.balance += trade.pnl

    def cleanup_closed(self):
        """Remove closed trades from open list."""
        self.open_trades = [t for t in self.open_trades if not t.closed]

    def get_balance(self):
        """Get current account balance."""
        return self.balance


# ============================================================
# MAIN BACKTESTER ENGINE
# ============================================================

class Backtester:
    """
    Main backtesting engine that coordinates data loading,
    strategy execution, and trade management.
    """

    PAIRS = ["EURUSD", "GBPUSD", "GBPJPY", "USDJPY", "AUDUSD", "USDCAD"]
    PIP_SIZES = {
        "EURUSD": 0.0001,
        "GBPUSD": 0.0001,
        "GBPJPY": 0.01,
        "USDJPY": 0.01,
        "AUDUSD": 0.0001,
        "USDCAD": 0.0001,
    }

    def __init__(self, data_dir="backtest/data", initial_balance=10000.0):
        self.data_dir = data_dir
        self.initial_balance = initial_balance
        self.risk_manager = RiskManager(initial_balance)
        self.all_trades = []
        self.equity_curve = []

    def load_all_data(self):
        """Load and resample data for all pairs."""
        self.pair_data = {}

        for pair in self.PAIRS:
            filepath = os.path.join(self.data_dir, f"{pair}_1m.csv")
            if not os.path.exists(filepath):
                print(f"  WARNING: Data file not found for {pair}: {filepath}")
                continue

            print(f"  Loading {pair}...")
            candles_1m = load_csv_data(filepath)
            print(f"    1m candles: {len(candles_1m)}")

            # Resample to higher timeframes
            candles_5m = resample_candles(candles_1m, 5)
            candles_15m = resample_candles(candles_1m, 15)
            candles_1h = resample_candles(candles_1m, 60)
            candles_4h = resample_candles(candles_1m, 240)

            print(f"    5m: {len(candles_5m)}, 15m: {len(candles_15m)}, "
                  f"1h: {len(candles_1h)}, 4h: {len(candles_4h)}")

            self.pair_data[pair] = {
                "1m": candles_1m,
                "5m": candles_5m,
                "15m": candles_15m,
                "1h": candles_1h,
                "4h": candles_4h,
            }

        print(f"  Loaded data for {len(self.pair_data)} pairs")

    def run(self):
        """
        Run the backtest across all pairs.
        
        Strategy is evaluated on 5-minute candle closes to balance
        signal quality with performance.
        """
        print("\n" + "=" * 60)
        print("RUNNING BACKTEST")
        print("=" * 60)

        self.load_all_data()

        if not self.pair_data:
            print("ERROR: No data loaded. Run generate_data.py first.")
            return []

        print("\nProcessing signals...")

        # Process each pair independently
        for pair in self.PAIRS:
            if pair not in self.pair_data:
                continue

            print(f"\n  Processing {pair}...")
            self._process_pair(pair)

        # Sort all trades by entry time
        self.all_trades.sort(key=lambda t: t["entry_time"])

        print(f"\n  Total trades taken: {len(self.all_trades)}")
        print("=" * 60)

        return self.all_trades

    def _process_pair(self, pair):
        """
        Process strategy signals for a single pair.
        
        Uses 5-minute candle closes as evaluation points.
        Maintains rolling windows of higher timeframe data.
        Each pair uses independent risk management (per-pair daily limits).
        """
        data = self.pair_data[pair]
        candles_5m = data["5m"]
        candles_15m = data["15m"]
        candles_1h = data["1h"]
        candles_4h = data["4h"]
        candles_1m = data["1m"]

        pip_size = self.PIP_SIZES[pair]
        pair_trades = []
        open_trades = []

        # Per-pair risk manager with 5% daily limit
        pair_risk = RiskManager(
            initial_balance=self.risk_manager.get_balance(),
            max_risk_per_trade=1.0,
            max_daily_risk=5.0,
            max_correlated=2
        )

        # Build index mappings for efficient lookback
        # For each 5m candle, find the corresponding indices in other timeframes

        # We iterate through 5m candles and use lookback windows
        # Minimum: need 200 4H candles history (checked via idx_4h >= 200)
        # and 80 1H candles (checked via idx_1h >= 80)
        # Start conservatively after enough base data exists
        # 80 1H candles = 80*12 = 960 5m candles minimum
        min_start = 1000

        if len(candles_5m) <= min_start:
            print(f"    Not enough data for {pair}")
            return

        # Create datetime index for 15m, 1h, 4h for binary search
        dt_15m = [c["datetime"] for c in candles_15m]
        dt_1h = [c["datetime"] for c in candles_1h]
        dt_4h = [c["datetime"] for c in candles_4h]

        # Track signal cooldown to avoid over-trading
        last_signal_time = None
        cooldown_minutes = 5  # Minimum 5 minutes between signals per pair

        trade_count = 0

        # Evaluate every 5m candle during killzones
        step = 1

        for i in range(min_start, len(candles_5m), step):
            current_candle = candles_5m[i]
            current_time = current_candle["datetime"]
            current_date = current_time.date()

            # Quick killzone pre-filter - skip non-killzone hours
            hour = current_time.hour
            if not (2 <= hour <= 4 or 7 <= hour <= 9 or 12 <= hour <= 14):
                # Still update open trades
                for trade_obj in open_trades[:]:
                    if not trade_obj.closed:
                        closed = trade_obj.update(current_candle)
                        if closed:
                            pair_risk.close_trade(trade_obj)
                            pair_trades.append(trade_obj.to_dict())
                open_trades = [t for t in open_trades if not t.closed]
                pair_risk.cleanup_closed()
                continue

            # Reset daily risk
            pair_risk.reset_daily(current_date)

            # Update open trades with recent 1m candles
            # Find 1m candles that correspond to this 5m period
            for trade_obj in open_trades[:]:
                if trade_obj.closed:
                    continue
                # Use 5m candle to update (approximation for speed)
                closed = trade_obj.update(current_candle)
                if closed:
                    pair_risk.close_trade(trade_obj)
                    pair_trades.append(trade_obj.to_dict())

            # Cleanup
            open_trades = [t for t in open_trades if not t.closed]
            pair_risk.cleanup_closed()

            # Check cooldown
            if last_signal_time:
                time_diff = (current_time - last_signal_time).total_seconds() / 60
                if time_diff < cooldown_minutes:
                    continue

            # Check if we can take a trade (risk management)
            # We don't know direction yet, check both
            if not pair_risk.can_take_trade(pair, 1) and \
               not pair_risk.can_take_trade(pair, -1):
                continue

            # Get lookback data for strategy conditions
            # 4H: need 200 candles
            idx_4h = self._find_index_before(dt_4h, current_time)
            if idx_4h < 200:
                continue
            window_4h = candles_4h[idx_4h - 200:idx_4h + 1]

            # 1H: need 80 candles for zone detection
            idx_1h = self._find_index_before(dt_1h, current_time)
            if idx_1h < 80:
                continue
            window_1h = candles_1h[idx_1h - 80:idx_1h + 1]

            # 15m: need 25 candles
            idx_15m = self._find_index_before(dt_15m, current_time)
            if idx_15m < 25:
                continue
            window_15m = candles_15m[idx_15m - 25:idx_15m + 1]

            # 5m: need 5 candles
            if i < 5:
                continue
            window_5m = candles_5m[i - 4:i + 1]

            # Run strategy
            signal = check_strategy_conditions(
                window_4h, window_1h, window_15m, window_5m,
                current_time, pip_size
            )

            if signal is None:
                continue

            # Verify risk management allows this specific direction
            if not pair_risk.can_take_trade(pair, signal["direction"]):
                continue

            # Create and register trade
            trade = Trade(
                pair=pair,
                signal=signal,
                account_balance=pair_risk.get_balance(),
                risk_percent=1.0,
            )

            open_trades.append(trade)
            pair_risk.open_trade(trade)
            last_signal_time = current_time
            trade_count += 1

            # Record equity point
            self.equity_curve.append({
                "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "balance": pair_risk.get_balance(),
            })

        # Close any remaining open trades at last price
        if open_trades:
            last_candle = candles_5m[-1]
            for trade_obj in open_trades:
                if not trade_obj.closed:
                    trade_obj._close_trade(
                        last_candle["close"],
                        last_candle["datetime"].strftime("%Y-%m-%d %H:%M:%S")
                        if isinstance(last_candle["datetime"], datetime)
                        else last_candle["datetime"],
                        "stop_loss"
                    )
                    pair_risk.close_trade(trade_obj)
                    pair_trades.append(trade_obj.to_dict())

        # Update main risk manager balance
        self.risk_manager.balance = pair_risk.get_balance()

        self.all_trades.extend(pair_trades)
        print(f"    {pair}: {trade_count} trades taken")

    def _find_index_before(self, dt_list, target_time):
        """
        Binary search to find the index of the last element <= target_time.
        
        Args:
            dt_list: Sorted list of datetimes
            target_time: Target datetime
        
        Returns:
            int: Index of last element before or equal to target_time
        """
        lo, hi = 0, len(dt_list) - 1
        result = -1
        while lo <= hi:
            mid = (lo + hi) // 2
            if dt_list[mid] <= target_time:
                result = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return result

    def get_equity_curve(self):
        """Return the equity curve data."""
        return self.equity_curve

    def get_final_balance(self):
        """Return final account balance."""
        return self.risk_manager.get_balance()
