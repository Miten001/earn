"""
results.py - Backtest Results Analysis

Provides comprehensive analysis and reporting of backtest results including:
- Overall statistics (win rate, profit factor, etc.)
- Per-pair and per-session breakdown
- Drawdown analysis
- Monthly returns
- Text-based equity curve
- Consecutive wins/losses tracking

Uses only Python standard library.
"""

from datetime import datetime


def analyze_results(trades, initial_balance=10000.0, equity_curve=None):
    """
    Analyze backtest results and print comprehensive report.
    
    Args:
        trades: List of trade dicts from backtester
        initial_balance: Starting account balance
        equity_curve: List of equity curve data points
    """
    if not trades:
        print("No trades to analyze.")
        return

    print("\n" + "=" * 70)
    print("                    BACKTEST RESULTS REPORT")
    print("                 Smart Liquidity Reversal Strategy")
    print("=" * 70)

    # ---- Overall Statistics ----
    total_trades = len(trades)
    winning_trades = [t for t in trades if t["pnl"] > 0]
    losing_trades = [t for t in trades if t["pnl"] < 0]
    breakeven_trades = [t for t in trades if t["pnl"] == 0]

    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    total_profit = sum(t["pnl"] for t in winning_trades)
    total_loss = abs(sum(t["pnl"] for t in losing_trades))
    net_pnl = total_profit - total_loss
    profit_factor = (total_profit / total_loss) if total_loss > 0 else float("inf")

    avg_win = (total_profit / win_count) if win_count > 0 else 0
    avg_loss = (total_loss / loss_count) if loss_count > 0 else 0
    avg_rr = sum(t["rr_achieved"] for t in trades) / total_trades

    # Final balance
    final_balance = initial_balance + net_pnl
    total_return_pct = ((final_balance - initial_balance) / initial_balance) * 100

    print("\n--- OVERALL STATISTICS ---")
    print(f"  Total Trades:          {total_trades}")
    print(f"  Winning Trades:        {win_count}")
    print(f"  Losing Trades:         {loss_count}")
    print(f"  Breakeven Trades:      {len(breakeven_trades)}")
    print(f"  Win Rate:              {win_rate:.1f}%")
    print(f"  Profit Factor:         {profit_factor:.2f}")
    print(f"  Average R:R Achieved:  {avg_rr:.2f}")
    print(f"  Average Win:           ${avg_win:.2f}")
    print(f"  Average Loss:          ${avg_loss:.2f}")
    print(f"  Net P/L:               ${net_pnl:.2f}")
    print(f"  Total Return:          {total_return_pct:.1f}%")
    print(f"  Initial Balance:       ${initial_balance:.2f}")
    print(f"  Final Balance:         ${final_balance:.2f}")

    # ---- Win Rate Per Pair ----
    print("\n--- WIN RATE PER PAIR ---")
    pairs = sorted(set(t["pair"] for t in trades))
    print(f"  {'Pair':<10} {'Trades':<8} {'Wins':<6} {'Losses':<8} {'Win%':<8} {'Net P/L':<12} {'Avg RR':<8}")
    print(f"  {'-' * 60}")
    for pair in pairs:
        pair_trades = [t for t in trades if t["pair"] == pair]
        pair_wins = [t for t in pair_trades if t["pnl"] > 0]
        pair_losses = [t for t in pair_trades if t["pnl"] < 0]
        pair_wr = (len(pair_wins) / len(pair_trades) * 100) if pair_trades else 0
        pair_pnl = sum(t["pnl"] for t in pair_trades)
        pair_avg_rr = sum(t["rr_achieved"] for t in pair_trades) / len(pair_trades)
        print(f"  {pair:<10} {len(pair_trades):<8} {len(pair_wins):<6} "
              f"{len(pair_losses):<8} {pair_wr:<8.1f} ${pair_pnl:<11.2f} {pair_avg_rr:<8.2f}")

    # ---- Win Rate Per Session ----
    print("\n--- WIN RATE PER SESSION ---")
    sessions = sorted(set(t["session"] for t in trades))
    print(f"  {'Session':<12} {'Trades':<8} {'Wins':<6} {'Losses':<8} {'Win%':<8} {'Net P/L':<12} {'Avg RR':<8}")
    print(f"  {'-' * 62}")
    for session in sessions:
        sess_trades = [t for t in trades if t["session"] == session]
        sess_wins = [t for t in sess_trades if t["pnl"] > 0]
        sess_losses = [t for t in sess_trades if t["pnl"] < 0]
        sess_wr = (len(sess_wins) / len(sess_trades) * 100) if sess_trades else 0
        sess_pnl = sum(t["pnl"] for t in sess_trades)
        sess_avg_rr = sum(t["rr_achieved"] for t in sess_trades) / len(sess_trades)
        print(f"  {session:<12} {len(sess_trades):<8} {len(sess_wins):<6} "
              f"{len(sess_losses):<8} {sess_wr:<8.1f} ${sess_pnl:<11.2f} {sess_avg_rr:<8.2f}")

    # ---- Direction Analysis ----
    print("\n--- DIRECTION ANALYSIS ---")
    for direction in ["BUY", "SELL"]:
        dir_trades = [t for t in trades if t["direction"] == direction]
        dir_wins = [t for t in dir_trades if t["pnl"] > 0]
        dir_wr = (len(dir_wins) / len(dir_trades) * 100) if dir_trades else 0
        dir_pnl = sum(t["pnl"] for t in dir_trades)
        print(f"  {direction}: {len(dir_trades)} trades, {dir_wr:.1f}% win rate, "
              f"Net P/L: ${dir_pnl:.2f}")

    # ---- Pattern Analysis ----
    print("\n--- PATTERN ANALYSIS ---")
    patterns = sorted(set(t["pattern"] for t in trades if t["pattern"]))
    print(f"  {'Pattern':<22} {'Trades':<8} {'Win%':<8} {'Avg RR':<8}")
    print(f"  {'-' * 46}")
    for pattern in patterns:
        pat_trades = [t for t in trades if t["pattern"] == pattern]
        pat_wins = [t for t in pat_trades if t["pnl"] > 0]
        pat_wr = (len(pat_wins) / len(pat_trades) * 100) if pat_trades else 0
        pat_avg_rr = sum(t["rr_achieved"] for t in pat_trades) / len(pat_trades)
        print(f"  {pattern:<22} {len(pat_trades):<8} {pat_wr:<8.1f} {pat_avg_rr:<8.2f}")

    # ---- Consecutive Wins/Losses ----
    max_consec_wins, max_consec_losses = _calculate_consecutive(trades)
    print("\n--- STREAK ANALYSIS ---")
    print(f"  Max Consecutive Wins:   {max_consec_wins}")
    print(f"  Max Consecutive Losses: {max_consec_losses}")

    # ---- Max Drawdown ----
    max_dd, max_dd_pct = _calculate_max_drawdown(trades, initial_balance)
    print(f"\n--- DRAWDOWN ANALYSIS ---")
    print(f"  Max Drawdown:           ${max_dd:.2f}")
    print(f"  Max Drawdown %:         {max_dd_pct:.2f}%")

    # ---- Monthly Returns ----
    _print_monthly_returns(trades, initial_balance)

    # ---- Equity Curve (Text-based) ----
    _print_equity_curve(trades, initial_balance)

    # ---- Trade Duration Analysis ----
    _print_duration_analysis(trades)

    print("\n" + "=" * 70)
    print("                       END OF REPORT")
    print("=" * 70)


def _calculate_consecutive(trades):
    """Calculate maximum consecutive wins and losses."""
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for trade in trades:
        if trade["pnl"] > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif trade["pnl"] < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        else:
            current_wins = 0
            current_losses = 0

    return max_wins, max_losses


def _calculate_max_drawdown(trades, initial_balance):
    """
    Calculate maximum drawdown in dollars and percentage.
    
    Returns:
        tuple: (max_drawdown_dollars, max_drawdown_percent)
    """
    balance = initial_balance
    peak = initial_balance
    max_dd = 0
    max_dd_pct = 0

    for trade in trades:
        balance += trade["pnl"]
        if balance > peak:
            peak = balance
        drawdown = peak - balance
        dd_pct = (drawdown / peak * 100) if peak > 0 else 0
        if drawdown > max_dd:
            max_dd = drawdown
            max_dd_pct = dd_pct

    return max_dd, max_dd_pct


def _print_monthly_returns(trades, initial_balance):
    """Print monthly returns breakdown."""
    print("\n--- MONTHLY RETURNS ---")

    # Group trades by month
    monthly = {}
    for trade in trades:
        # Parse entry time
        if isinstance(trade["entry_time"], str):
            try:
                dt = datetime.strptime(trade["entry_time"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        else:
            dt = trade["entry_time"]
        
        month_key = dt.strftime("%Y-%m")
        if month_key not in monthly:
            monthly[month_key] = {"pnl": 0, "trades": 0, "wins": 0}
        monthly[month_key]["pnl"] += trade["pnl"]
        monthly[month_key]["trades"] += 1
        if trade["pnl"] > 0:
            monthly[month_key]["wins"] += 1

    if not monthly:
        print("  No monthly data available.")
        return

    print(f"  {'Month':<10} {'Trades':<8} {'Win%':<8} {'P/L ($)':<12} {'P/L (%)':<10} {'Cumulative':<12}")
    print(f"  {'-' * 60}")

    cumulative = 0
    balance = initial_balance
    for month in sorted(monthly.keys()):
        data = monthly[month]
        wr = (data["wins"] / data["trades"] * 100) if data["trades"] > 0 else 0
        pnl_pct = (data["pnl"] / balance * 100) if balance > 0 else 0
        cumulative += data["pnl"]
        balance += data["pnl"]
        cum_pct = (cumulative / initial_balance * 100)
        print(f"  {month:<10} {data['trades']:<8} {wr:<8.1f} "
              f"${data['pnl']:<11.2f} {pnl_pct:<10.2f} {cum_pct:<12.1f}%")


def _print_equity_curve(trades, initial_balance):
    """Print a text-based equity curve."""
    print("\n--- EQUITY CURVE (Text) ---")

    if not trades:
        return

    # Calculate balance at each trade
    balances = [initial_balance]
    for trade in trades:
        balances.append(balances[-1] + trade["pnl"])

    # Determine chart dimensions
    chart_width = 60
    chart_height = 20

    min_bal = min(balances)
    max_bal = max(balances)
    bal_range = max_bal - min_bal

    if bal_range == 0:
        print("  Flat equity - no change.")
        return

    # Sample points to fit chart width
    if len(balances) > chart_width:
        step = len(balances) / chart_width
        sampled = []
        for i in range(chart_width):
            idx = int(i * step)
            sampled.append(balances[idx])
        sampled.append(balances[-1])
    else:
        sampled = balances

    # Build chart rows
    chart = []
    for row in range(chart_height):
        threshold = max_bal - (row / (chart_height - 1)) * bal_range
        line = "  "
        # Y-axis label
        if row == 0:
            line += f"${max_bal:<8.0f}|"
        elif row == chart_height - 1:
            line += f"${min_bal:<8.0f}|"
        elif row == chart_height // 2:
            mid = (max_bal + min_bal) / 2
            line += f"${mid:<8.0f}|"
        else:
            line += "         |"

        for val in sampled:
            if val >= threshold:
                line += "*"
            else:
                line += " "
        chart.append(line)

    # Print chart
    for line in chart:
        print(line)

    # X-axis
    print("  " + "         |" + "-" * len(sampled))
    print(f"  {'':>9} Trade 1{' ' * (len(sampled) - 15)}Trade {len(trades)}")


def _print_duration_analysis(trades):
    """Analyze trade durations (based on entry/exit times)."""
    print("\n--- TRADE DURATION ANALYSIS ---")

    durations = []
    for trade in trades:
        if trade["entry_time"] and trade["exit_time"]:
            try:
                if isinstance(trade["entry_time"], str):
                    entry = datetime.strptime(trade["entry_time"], "%Y-%m-%d %H:%M:%S")
                else:
                    entry = trade["entry_time"]
                if isinstance(trade["exit_time"], str):
                    exit_t = datetime.strptime(trade["exit_time"], "%Y-%m-%d %H:%M:%S")
                else:
                    exit_t = trade["exit_time"]
                duration = (exit_t - entry).total_seconds() / 60  # in minutes
                if duration > 0:
                    durations.append(duration)
            except (ValueError, TypeError):
                continue

    if not durations:
        print("  No duration data available.")
        return

    avg_duration = sum(durations) / len(durations)
    min_duration = min(durations)
    max_duration = max(durations)

    # Convert to readable format
    def fmt_minutes(minutes):
        if minutes < 60:
            return f"{minutes:.0f}m"
        elif minutes < 1440:
            return f"{minutes / 60:.1f}h"
        else:
            return f"{minutes / 1440:.1f}d"

    print(f"  Average Duration: {fmt_minutes(avg_duration)}")
    print(f"  Shortest Trade:   {fmt_minutes(min_duration)}")
    print(f"  Longest Trade:    {fmt_minutes(max_duration)}")
