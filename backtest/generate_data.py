"""
generate_data.py - Synthetic Forex OHLC Data Generator

Generates realistic 1-minute OHLC data for 6 major forex pairs covering
approximately 2 years of trading data. Uses random walk with realistic
volatility, spreads, and session-based volume patterns.

Uses only Python standard library (random, math, csv, datetime).
"""

import random
import math
import csv
import os
from datetime import datetime, timedelta

# Seed for reproducibility
random.seed(42)

# Forex pair configurations
# pip_size: value of 1 pip
# avg_daily_range: average daily range in pips
# spread: typical spread in pips
# base_price: starting price for synthetic data
PAIR_CONFIGS = {
    "EURUSD": {
        "pip_size": 0.0001,
        "avg_daily_range": 80,
        "spread": 1.2,
        "base_price": 1.1000,
    },
    "GBPUSD": {
        "pip_size": 0.0001,
        "avg_daily_range": 110,
        "spread": 1.5,
        "base_price": 1.2700,
    },
    "GBPJPY": {
        "pip_size": 0.01,
        "avg_daily_range": 150,
        "spread": 3.0,
        "base_price": 165.00,
    },
    "USDJPY": {
        "pip_size": 0.01,
        "avg_daily_range": 85,
        "spread": 1.3,
        "base_price": 130.00,
    },
    "AUDUSD": {
        "pip_size": 0.0001,
        "avg_daily_range": 70,
        "spread": 1.4,
        "base_price": 0.6800,
    },
    "USDCAD": {
        "pip_size": 0.0001,
        "avg_daily_range": 75,
        "spread": 1.8,
        "base_price": 1.3500,
    },
}

# Session definitions (GMT hours)
# Each session has different volatility characteristics
SESSIONS = {
    "asian": {"start": 0, "end": 8, "volatility_factor": 0.6},
    "london": {"start": 7, "end": 16, "volatility_factor": 1.3},
    "newyork": {"start": 12, "end": 21, "volatility_factor": 1.2},
}


def get_session_volatility_factor(hour):
    """
    Returns a volatility multiplier based on the trading session.
    Overlapping sessions (London/NY) get higher volatility.
    """
    factor = 0.4  # Off-hours base volatility

    if 0 <= hour < 8:
        # Asian session
        factor = 0.6
    if 7 <= hour < 10:
        # London open - highest volatility
        factor = 1.4
    if 10 <= hour < 12:
        # London mid-session
        factor = 1.1
    if 12 <= hour < 16:
        # London/NY overlap - very high volatility
        factor = 1.5
    if 16 <= hour < 17:
        # NY session alone
        factor = 1.0
    if 17 <= hour < 21:
        # NY afternoon - declining volatility
        factor = 0.8
    if 21 <= hour < 24:
        # Quiet period
        factor = 0.4

    return factor


def get_volume_pattern(hour):
    """
    Returns a relative volume multiplier based on hour of day.
    Simulates realistic trading volume patterns.
    """
    # Volume follows session activity
    volume_map = {
        0: 30, 1: 25, 2: 35, 3: 40, 4: 45, 5: 40,
        6: 50, 7: 80, 8: 120, 9: 140, 10: 130, 11: 120,
        12: 150, 13: 160, 14: 155, 15: 140, 16: 110,
        17: 80, 18: 60, 19: 50, 20: 40, 21: 30, 22: 25, 23: 25,
    }
    return volume_map.get(hour, 50)


def generate_minute_candle(prev_close, pip_size, avg_daily_range, hour, trend_bias=0.0):
    """
    Generate a single 1-minute OHLC candle using random walk.

    Args:
        prev_close: Previous candle's close price
        pip_size: Value of 1 pip for this pair
        avg_daily_range: Average daily range in pips
        hour: Current hour (GMT) for session-based volatility
        trend_bias: Slight directional bias (-1 to 1) for trend simulation

    Returns:
        tuple: (open, high, low, close, volume)
    """
    # Calculate per-minute volatility from daily range
    # ~1440 minutes in a day, but sqrt scaling for random walk
    minute_vol = (avg_daily_range * pip_size) / math.sqrt(1440)

    # Apply session volatility factor
    session_factor = get_session_volatility_factor(hour)
    minute_vol *= session_factor

    # Generate price movement using normal distribution approximation
    # Box-Muller transform for normal distribution
    u1 = random.random()
    u2 = random.random()
    if u1 == 0:
        u1 = 0.0001
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    # Apply trend bias
    move = z * minute_vol + (trend_bias * minute_vol * 0.1)

    # Generate OHLC from the movement
    open_price = prev_close

    # Determine close
    close_price = open_price + move

    # Generate high and low with realistic wicks
    wick_factor = abs(z) * 0.3 + 0.1
    if close_price >= open_price:
        # Bullish candle
        high_price = close_price + abs(random.gauss(0, minute_vol * wick_factor))
        low_price = open_price - abs(random.gauss(0, minute_vol * wick_factor))
    else:
        # Bearish candle
        high_price = open_price + abs(random.gauss(0, minute_vol * wick_factor))
        low_price = close_price - abs(random.gauss(0, minute_vol * wick_factor))

    # Ensure OHLC consistency
    high_price = max(high_price, open_price, close_price)
    low_price = min(low_price, open_price, close_price)

    # Generate volume based on session
    base_volume = get_volume_pattern(hour)
    volume = int(base_volume * (0.7 + random.random() * 0.6))

    return (open_price, high_price, low_price, close_price, volume)


def generate_trend_phases(num_days):
    """
    Generate trend phases to make data more realistic.
    Returns a list of (duration_days, direction) tuples.
    Direction: 1 = uptrend, -1 = downtrend, 0 = ranging
    """
    phases = []
    remaining_days = num_days
    while remaining_days > 0:
        # Trend duration: 5-60 days
        duration = random.randint(5, 60)
        duration = min(duration, remaining_days)
        direction = random.choice([-1, -1, 0, 1, 1])
        phases.append((duration, direction))
        remaining_days -= duration
    return phases


def generate_pair_data(pair_name, config, start_date, num_days):
    """
    Generate complete 1-minute OHLC data for a single forex pair.

    Args:
        pair_name: Name of the pair (e.g., "EURUSD")
        config: Configuration dict for the pair
        start_date: Starting datetime
        num_days: Number of trading days to generate

    Returns:
        list: List of [datetime_str, open, high, low, close, volume] rows
    """
    print(f"  Generating {pair_name} data ({num_days} days)...")

    pip_size = config["pip_size"]
    avg_daily_range = config["avg_daily_range"]
    base_price = config["base_price"]

    # Generate trend phases
    phases = generate_trend_phases(num_days)

    data = []
    current_price = base_price
    current_date = start_date
    day_count = 0

    for phase_duration, phase_direction in phases:
        # Trend strength varies
        trend_strength = random.uniform(0.3, 0.8) * phase_direction

        for day in range(phase_duration):
            # Skip weekends (Saturday=5, Sunday=6)
            while current_date.weekday() >= 5:
                current_date += timedelta(days=1)

            # Daily volatility variation (some days are more volatile)
            daily_vol_factor = random.uniform(0.7, 1.5)

            # Generate 1440 minutes of data for this day
            for minute in range(1440):
                hour = minute // 60
                minute_of_hour = minute % 60

                timestamp = current_date.replace(
                    hour=hour, minute=minute_of_hour, second=0
                )

                # Adjust trend bias slightly with some noise
                bias = trend_strength + random.uniform(-0.2, 0.2)

                open_p, high_p, low_p, close_p, volume = generate_minute_candle(
                    current_price,
                    pip_size,
                    avg_daily_range * daily_vol_factor,
                    hour,
                    bias,
                )

                # Round prices appropriately
                if pip_size == 0.0001:
                    decimals = 5
                else:
                    decimals = 3

                open_p = round(open_p, decimals)
                high_p = round(high_p, decimals)
                low_p = round(low_p, decimals)
                close_p = round(close_p, decimals)

                data.append([
                    timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    open_p,
                    high_p,
                    low_p,
                    close_p,
                    volume,
                ])

                current_price = close_p

            current_date += timedelta(days=1)
            day_count += 1

    return data


def save_to_csv(pair_name, data, output_dir):
    """Save generated data to CSV file."""
    filepath = os.path.join(output_dir, f"{pair_name}_1m.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["datetime", "open", "high", "low", "close", "volume"])
        writer.writerows(data)
    print(f"  Saved {len(data)} candles to {filepath}")
    return filepath


def generate_all_data(output_dir="backtest/data", num_days=580):
    """
    Generate synthetic forex data for all configured pairs.

    Args:
        output_dir: Directory to save CSV files
        num_days: Number of trading days (~580 = ~2.2 years accounting for weekends)

    Returns:
        dict: Mapping of pair names to file paths
    """
    os.makedirs(output_dir, exist_ok=True)

    # Start date: approximately 2 years ago
    start_date = datetime(2022, 1, 3, 0, 0, 0)  # First Monday of 2022

    print("=" * 60)
    print("FOREX SYNTHETIC DATA GENERATOR")
    print("=" * 60)
    print(f"Generating {num_days} trading days of 1-minute data")
    print(f"Start date: {start_date.strftime('%Y-%m-%d')}")
    print(f"Pairs: {', '.join(PAIR_CONFIGS.keys())}")
    print(f"Output directory: {output_dir}")
    print("-" * 60)

    file_paths = {}
    for pair_name, config in PAIR_CONFIGS.items():
        data = generate_pair_data(pair_name, config, start_date, num_days)
        filepath = save_to_csv(pair_name, data, output_dir)
        file_paths[pair_name] = filepath

    print("-" * 60)
    print("Data generation complete!")
    print("=" * 60)

    return file_paths


if __name__ == "__main__":
    generate_all_data()
