"""
MT5 Scalping + Arbitrage Bot - Configuration
Sab kuch yahan se control karein. Strategy parameters tweak karein apni risk tolerance ke hisab se.
"""

# ============== MT5 LOGIN ==============
# Apna broker account dalein. Demo se start karein!
MT5_LOGIN = 0              # e.g. 12345678
MT5_PASSWORD = ""          # e.g. "yourPassword"
MT5_SERVER = ""            # e.g. "Exness-MT5Trial"
MT5_PATH = ""              # Optional: "C:/Program Files/MetaTrader 5/terminal64.exe"

# ============== PAIRS TO TRADE ==============
# Major + minor pairs - high liquidity, low spread
SCALP_PAIRS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "EURJPY",
    "GBPJPY",
    "EURGBP",
]

# Triangular arbitrage triplets: (A/B, B/C, A/C)
# Maths: A/B * B/C should == A/C ; agar mismatch hai, arbitrage opportunity
ARB_TRIPLETS = [
    ("EURUSD", "USDJPY", "EURJPY"),
    ("GBPUSD", "USDJPY", "GBPJPY"),
    ("EURGBP", "GBPUSD", "EURUSD"),
]

# ============== STRATEGY PARAMS ==============
TIMEFRAME = "M1"           # M1 = 1 minute scalping
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
RSI_LOW = 30
RSI_HIGH = 70

# Spread filter (in points). Skip pair agar spread bahut zyada ho.
MAX_SPREAD_POINTS = 20

# Arbitrage threshold (decimal). 0.0003 = 3 pips deviation needed.
ARB_THRESHOLD = 0.0003

# ============== RISK MANAGEMENT ==============
LOT_SIZE = 0.01            # Micro lot - safe start
SL_PIPS = 8                # Stop loss in pips
TP_PIPS = 12               # Take profit in pips (1.5 R:R)
MAX_OPEN_TRADES = 5        # Total concurrent positions cap
MAX_TRADES_PER_PAIR = 1    # Ek pair pe ek hi trade
MAGIC_NUMBER = 234000      # Bot identifier

# ============== LOOP CONTROL ==============
SCAN_INTERVAL_SEC = 2      # Har 2 second me scan
RUN_MINUTES = 60           # Bot kitne minutes chalana hai (0 = infinite)
