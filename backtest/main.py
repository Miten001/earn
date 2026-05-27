"""
main.py - Entry Point for Forex Backtesting Bot

Runs the complete backtesting pipeline:
1. Generates synthetic data if not already present
2. Runs the Smart Liquidity Reversal strategy backtest
3. Prints comprehensive results report

Usage:
    python backtest/main.py

Uses only Python standard library.
"""

import os
import sys
import time

# Add backtest directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_data import generate_all_data
from backtester import Backtester
from results import analyze_results


def main():
    """Main entry point for the backtesting system."""
    start_time = time.time()

    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "   FOREX BACKTESTING BOT - Smart Liquidity Reversal Strategy".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print()

    # ---- Step 1: Data Generation ----
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    # Check if data already exists
    pairs = ["EURUSD", "GBPUSD", "GBPJPY", "USDJPY", "AUDUSD", "USDCAD"]
    data_exists = all(
        os.path.exists(os.path.join(data_dir, f"{pair}_1m.csv"))
        for pair in pairs
    )

    if not data_exists:
        print("[Step 1/3] Generating synthetic forex data...")
        print("(This may take a few minutes for 2 years of 1-minute data)")
        print()
        generate_all_data(output_dir=data_dir)
    else:
        print("[Step 1/3] Synthetic data already exists, skipping generation.")
        print(f"  Data directory: {data_dir}")
        print()

    # ---- Step 2: Run Backtest ----
    print("\n[Step 2/3] Running backtest...")
    print("  Strategy: Smart Liquidity Reversal (5 confluence conditions)")
    print("  Pairs: EURUSD, GBPUSD, GBPJPY, USDJPY, AUDUSD, USDCAD")
    print("  Sessions: Asian (2-5 GMT), London (7-10 GMT), NY (12-3 PM GMT)")
    print("  Risk: 1% per trade, 3% max daily, 2 max correlated")
    print()

    backtester = Backtester(data_dir=data_dir, initial_balance=10000.0)
    trades = backtester.run()

    # ---- Step 3: Results Analysis ----
    print("\n[Step 3/3] Analyzing results...")
    analyze_results(
        trades,
        initial_balance=10000.0,
        equity_curve=backtester.get_equity_curve()
    )

    # ---- Timing ----
    elapsed = time.time() - start_time
    print(f"\nTotal execution time: {elapsed:.1f} seconds")
    print()

    return trades


if __name__ == "__main__":
    trades = main()
