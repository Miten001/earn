"""
strategy.py - Smart Liquidity Reversal Strategy

Implements the Smart Liquidity Reversal (SLR) strategy with 5 confluence conditions:
1. Killzone timing check (Asian, London, NY sessions)
2. Higher timeframe bias (4H trend using 200 candles)
3. Supply/Demand zone detection (1H strong rejection areas)
4. Liquidity sweep detection (15m sweep beyond recent high/low)
5. Price action confirmation (5m engulfing or pin bar)

Entry: All 5 conditions must align in direction of HTF bias.
Exit: SL below/above zone, TP1 at 1:2 RR (50%), TP2 at 1:3 RR (50%).

Uses only Python standard library.
"""


# ============================================================
# CONDITION 1: Killzone Timing Check
# ============================================================

def is_killzone(hour):
    """
    Check if current hour falls within a valid trading killzone.
    
    Killzones (GMT):
    - Asian: 2-5 AM
    - London: 7-10 AM
    - New York: 12-3 PM
    
    Args:
        hour: Hour of day in GMT (0-23)
    
    Returns:
        tuple: (is_valid, session_name) or (False, None)
    """
    if 2 <= hour <= 4:
        return (True, "asian")
    elif 7 <= hour <= 9:
        return (True, "london")
    elif 12 <= hour <= 14:
        return (True, "newyork")
    return (False, None)


# ============================================================
# CONDITION 2: Higher Timeframe Bias (4H, 200 candles)
# ============================================================

def get_htf_bias(candles_4h):
    """
    Determine higher timeframe trend direction using 4H candles.
    Uses a combination of:
    - 50-period and 200-period simple moving averages
    - Price position relative to MAs
    - Recent swing structure (higher highs/lows or lower highs/lows)
    
    Args:
        candles_4h: List of 4H candles, each as dict with keys:
                    {open, high, low, close, datetime}
                    Most recent candle last.
    
    Returns:
        int: 1 for bullish bias, -1 for bearish bias, 0 for no clear bias
    """
    if len(candles_4h) < 200:
        return 0

    # Calculate 50 and 200 period SMAs using close prices
    closes = [c["close"] for c in candles_4h[-200:]]
    
    sma_200 = sum(closes) / 200
    sma_50 = sum(closes[-50:]) / 50
    current_price = closes[-1]

    # Score-based approach
    score = 0

    # MA alignment
    if sma_50 > sma_200:
        score += 1
    elif sma_50 < sma_200:
        score -= 1

    # Price vs MAs
    if current_price > sma_50:
        score += 1
    elif current_price < sma_50:
        score -= 1

    if current_price > sma_200:
        score += 1
    elif current_price < sma_200:
        score -= 1

    # Check recent swing structure (last 20 candles)
    recent = candles_4h[-20:]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]

    # Find swing highs and lows (simple pivot detection)
    swing_highs = []
    swing_lows = []
    for i in range(2, len(recent) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])

    # Check for higher highs and higher lows (bullish)
    if len(swing_highs) >= 2 and swing_highs[-1] > swing_highs[-2]:
        score += 1
    elif len(swing_highs) >= 2 and swing_highs[-1] < swing_highs[-2]:
        score -= 1

    if len(swing_lows) >= 2 and swing_lows[-1] > swing_lows[-2]:
        score += 1
    elif len(swing_lows) >= 2 and swing_lows[-1] < swing_lows[-2]:
        score -= 1

    # Determine bias - any score direction gives bias
    if score >= 1:
        return 1  # Bullish
    elif score <= -1:
        return -1  # Bearish
    return 0  # No clear bias


# ============================================================
# CONDITION 3: Supply/Demand Zone Detection (1H)
# ============================================================

def detect_supply_demand_zones(candles_1h, lookback=80):
    """
    Detect supply and demand zones on 1H timeframe.
    
    A demand zone forms when:
    - Strong bullish move away from a level (large body candle)
    - Price moved at least 1.5x the average candle size
    - The base of the move becomes the zone
    
    A supply zone forms when:
    - Strong bearish move away from a level
    - Price moved at least 1.5x the average candle size
    - The top of the move becomes the zone
    
    Args:
        candles_1h: List of 1H candles (most recent last)
        lookback: Number of candles to analyze
    
    Returns:
        dict: {
            "demand_zones": [(zone_high, zone_low), ...],
            "supply_zones": [(zone_high, zone_low), ...]
        }
    """
    if len(candles_1h) < lookback:
        return {"demand_zones": [], "supply_zones": []}

    recent = candles_1h[-lookback:]

    # Calculate average candle body size
    bodies = [abs(c["close"] - c["open"]) for c in recent]
    avg_body = sum(bodies) / len(bodies) if bodies else 0.0001

    demand_zones = []
    supply_zones = []

    for i in range(1, len(recent) - 1):
        candle = recent[i]
        body = abs(candle["close"] - candle["open"])

        # Strong bullish move (demand zone formation)
        if candle["close"] > candle["open"] and body > avg_body * 1.3:
            zone_low = min(candle["open"], candle["low"])
            zone_high = candle["open"] + body * 0.3  # Extend zone slightly
            demand_zones.append((zone_high, zone_low))

        # Strong bearish move (supply zone formation)
        elif candle["open"] > candle["close"] and body > avg_body * 1.3:
            zone_high = max(candle["open"], candle["high"])
            zone_low = candle["open"] - body * 0.3  # Extend zone slightly
            supply_zones.append((zone_high, zone_low))

    # Keep only the most recent 15 zones of each type
    demand_zones = demand_zones[-15:]
    supply_zones = supply_zones[-15:]

    return {"demand_zones": demand_zones, "supply_zones": supply_zones}


def price_in_zone(price, zones, tolerance=0.0):
    """
    Check if price is within any of the given zones.
    
    Args:
        price: Current price
        zones: List of (zone_high, zone_low) tuples
        tolerance: Extra tolerance around zone boundaries
    
    Returns:
        tuple: (is_in_zone, zone) or (False, None)
    """
    for zone_high, zone_low in zones:
        zone_range = zone_high - zone_low
        tol = zone_range * 1.0 + tolerance  # 100% zone extension for proximity
        if zone_low - tol <= price <= zone_high + tol:
            return (True, (zone_high, zone_low))
    return (False, None)


# ============================================================
# CONDITION 4: Liquidity Sweep Detection (15m)
# ============================================================

def detect_liquidity_sweep(candles_15m, direction, lookback=12):
    """
    Detect liquidity sweep on 15-minute timeframe.
    
    A liquidity sweep occurs when price:
    - Goes beyond a recent swing high/low (grabbing liquidity)
    - Then reverses back (showing rejection)
    
    For bullish sweep (direction=1):
    - Price sweeps below recent swing low
    - Then closes back above it
    
    For bearish sweep (direction=-1):
    - Price sweeps above recent swing high
    - Then closes back below it
    
    Args:
        candles_15m: List of 15m candles (most recent last)
        direction: Expected trade direction (1=buy, -1=sell)
        lookback: Number of candles to look back for swings
    
    Returns:
        tuple: (sweep_detected, sweep_level)
    """
    if len(candles_15m) < lookback + 6:
        return (False, 0)

    analysis_candles = candles_15m[-(lookback + 6):-6]
    recent_candles = candles_15m[-6:]

    if direction == 1:  # Looking for bullish sweep (sweep of lows)
        # Find recent swing lows
        lows = [c["low"] for c in analysis_candles]
        if not lows:
            return (False, 0)

        # Use percentile-based targets for more opportunities
        sorted_lows = sorted(lows)
        # Target the 3 lowest levels
        targets = sorted_lows[:3]

        # Check if recent candles swept below then reversed
        for target in targets:
            for i, candle in enumerate(recent_candles):
                if candle["low"] <= target:
                    # Price went at or below target - check for reversal
                    if candle["close"] > target:
                        return (True, target)
                    # Check subsequent candles for reversal
                    for j in range(i + 1, len(recent_candles)):
                        if recent_candles[j]["close"] > target:
                            return (True, target)

    elif direction == -1:  # Looking for bearish sweep (sweep of highs)
        # Find recent swing highs
        highs = [c["high"] for c in analysis_candles]
        if not highs:
            return (False, 0)

        # Use percentile-based targets
        sorted_highs = sorted(highs, reverse=True)
        targets = sorted_highs[:3]

        # Check if recent candles swept above then reversed
        for target in targets:
            for i, candle in enumerate(recent_candles):
                if candle["high"] >= target:
                    # Price went at or above target - check for reversal
                    if candle["close"] < target:
                        return (True, target)
                    # Check subsequent candles
                    for j in range(i + 1, len(recent_candles)):
                        if recent_candles[j]["close"] < target:
                            return (True, target)

    return (False, 0)


# ============================================================
# CONDITION 5: Price Action Confirmation (5m)
# ============================================================

def detect_price_action_confirmation(candles_5m, direction):
    """
    Detect confirmation price action patterns on 5-minute timeframe.
    
    Patterns detected:
    1. Engulfing pattern - current candle body engulfs previous candle body
    2. Pin bar - long wick showing rejection (wick > 1.5x body)
    3. Strong momentum candle - large body candle in trade direction
    
    Args:
        candles_5m: List of 5m candles (most recent last), need at least 3
        direction: Expected trade direction (1=buy, -1=sell)
    
    Returns:
        tuple: (confirmed, pattern_name)
    """
    if len(candles_5m) < 3:
        return (False, None)

    current = candles_5m[-1]
    previous = candles_5m[-2]

    curr_body = current["close"] - current["open"]
    prev_body = previous["close"] - previous["open"]
    curr_body_size = abs(curr_body)
    prev_body_size = abs(prev_body)

    # Calculate average body for context
    avg_body = sum(abs(c["close"] - c["open"]) for c in candles_5m[-3:]) / 3
    if avg_body == 0:
        avg_body = 0.00001

    if direction == 1:  # Looking for bullish confirmation
        # Bullish engulfing (current bullish engulfs previous bearish)
        if (curr_body > 0 and prev_body < 0 and
                curr_body_size > prev_body_size * 0.8 and
                current["close"] >= previous["open"]):
            return (True, "bullish_engulfing")

        # Bullish pin bar (hammer) - long lower wick
        lower_wick = min(current["open"], current["close"]) - current["low"]
        upper_wick = current["high"] - max(current["open"], current["close"])
        if curr_body_size > 0:
            if lower_wick > curr_body_size * 1.5 and upper_wick < curr_body_size:
                return (True, "bullish_pin_bar")

        # Strong bullish momentum candle
        if curr_body > 0 and curr_body_size > avg_body * 1.2:
            # Confirm previous candle was bearish or small (setup candle)
            if prev_body <= 0 or prev_body_size < curr_body_size * 0.5:
                return (True, "bullish_momentum")

        # Bullish inside bar breakout - current breaks above previous high
        if (current["close"] > previous["high"] and
                current["close"] > current["open"]):
            return (True, "bullish_breakout")

    elif direction == -1:  # Looking for bearish confirmation
        # Bearish engulfing
        if (curr_body < 0 and prev_body > 0 and
                curr_body_size > prev_body_size * 0.8 and
                current["close"] <= previous["open"]):
            return (True, "bearish_engulfing")

        # Bearish pin bar (shooting star) - long upper wick
        upper_wick = current["high"] - max(current["open"], current["close"])
        lower_wick = min(current["open"], current["close"]) - current["low"]
        if curr_body_size > 0:
            if upper_wick > curr_body_size * 1.5 and lower_wick < curr_body_size:
                return (True, "bearish_pin_bar")

        # Strong bearish momentum candle
        if curr_body < 0 and curr_body_size > avg_body * 1.2:
            if prev_body >= 0 or prev_body_size < curr_body_size * 0.5:
                return (True, "bearish_momentum")

        # Bearish inside bar breakout - current breaks below previous low
        if (current["close"] < previous["low"] and
                current["close"] < current["open"]):
            return (True, "bearish_breakout")

    return (False, None)


# ============================================================
# MAIN STRATEGY FUNCTION
# ============================================================

def check_strategy_conditions(candles_4h, candles_1h, candles_15m, candles_5m,
                               current_time, pip_size):
    """
    Check all 5 strategy conditions and generate trade signal if all align.
    
    Args:
        candles_4h: 4H candle data (list of dicts, most recent last)
        candles_1h: 1H candle data
        candles_15m: 15m candle data
        candles_5m: 5m candle data
        current_time: Current datetime
        pip_size: Pip size for the pair
    
    Returns:
        dict or None: Trade signal with entry details, or None if no setup
        {
            "direction": 1 or -1,
            "session": str,
            "entry_price": float,
            "stop_loss": float,
            "tp1": float,
            "tp2": float,
            "zone": (high, low),
            "pattern": str,
            "datetime": str
        }
    """
    # Condition 1: Killzone check
    hour = current_time.hour
    is_kz, session = is_killzone(hour)
    if not is_kz:
        return None

    # Condition 2: HTF bias
    bias = get_htf_bias(candles_4h)
    if bias == 0:
        return None

    direction = bias  # Trade in direction of bias

    # Condition 3: Supply/Demand zone
    zones = detect_supply_demand_zones(candles_1h)
    current_price = candles_5m[-1]["close"] if candles_5m else None
    if current_price is None:
        return None

    if direction == 1:
        # For buys, look for price in demand zone
        in_zone, zone = price_in_zone(current_price, zones["demand_zones"])
    else:
        # For sells, look for price in supply zone
        in_zone, zone = price_in_zone(current_price, zones["supply_zones"])

    if not in_zone:
        return None

    # Condition 4: Liquidity sweep
    sweep_detected, sweep_level = detect_liquidity_sweep(candles_15m, direction)
    if not sweep_detected:
        return None

    # Condition 5: Price action confirmation
    confirmed, pattern = detect_price_action_confirmation(candles_5m, direction)
    if not confirmed:
        return None

    # All 5 conditions met - calculate trade parameters
    entry_price = current_price

    if direction == 1:  # Buy
        stop_loss = zone[1] - (2 * pip_size)  # Below demand zone
        risk = entry_price - stop_loss
        tp1 = entry_price + (risk * 2)  # 1:2 RR
        tp2 = entry_price + (risk * 3)  # 1:3 RR
    else:  # Sell
        stop_loss = zone[0] + (2 * pip_size)  # Above supply zone
        risk = stop_loss - entry_price
        tp1 = entry_price - (risk * 2)  # 1:2 RR
        tp2 = entry_price - (risk * 3)  # 1:3 RR

    # Validate risk is positive and reasonable
    if risk <= 0 or risk > 200 * pip_size:
        return None

    return {
        "direction": direction,
        "session": session,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "risk": risk,
        "zone": zone,
        "pattern": pattern,
        "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S"),
    }
