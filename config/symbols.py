"""Trading symbol configuration for backtesting.

This module contains:
1. ACTIVE_SYMBOLS - The current list of symbols used for backtesting
2. SYMBOL_CATEGORIES - Organized categorization of available symbols
3. Helper lists for different market segments
"""

# ========== ACTIVE SYMBOLS FOR BACKTESTING ==========
# This is the primary list used by the backtest engine
# Modify this list to change which symbols are traded

ACTIVE_SYMBOLS = [
    # Tech giants & growth
    "NVDA",   # Nvidia
    "AAPL",   # Apple
    "PLTR",   # Palantir
    "AMD",    # Advanced Micro Devices
    "MSTR",   # MicroStrategy (Bitcoin proxy)
    "MSFT",   # Microsoft
    "TSLA",   # Tesla
    
    # Materials & Mining
    "MP",     # MP Materials (rare earths)
    
    # Defense
    "NOC",    # Northrop Grumman
    "LMT",    # Lockheed Martin
    
    # International
    "NVO",    # Novo Nordisk (Denmark)
    
    # --- ETFs / Commodity ETFs ---
    "GLD",    # Gold
    "SLV",    # Silver
    "PPLT",   # Platinum
    "COPX",   # Copper miners
    "JO",     # Coffee
    "LIT",    # Lithium & Battery Tech
    "URTH",   # MSCI World
    "GDXJ",   # Junior gold miners
    "SIL",    # Silver miners
    "REMX",   # Rare earth / critical metals
    "PICK",   # Global metals & mining
]

# Legacy alias for compatibility
SYMBOLS_LIST = ACTIVE_SYMBOLS

# ========== SYMBOL CATEGORIES ==========
# Organized categorization for selective backtesting or analysis

SYMBOL_CATEGORIES = {
    "tech": [
        "NVDA",    # Nvidia
        "AAPL",    # Apple
        "MSFT",    # Microsoft
        "AMD",     # Advanced Micro Devices
        "TSLA",    # Tesla
        "GOOGL",   # Google/Alphabet
        "META",    # Meta
        "AMZN",    # Amazon
    ],
    
    "defense": [
        "NOC",     # Northrop Grumman
        "LMT",     # Lockheed Martin
        "RTX",     # Raytheon Technologies
        "GD",      # General Dynamics
    ],
    
    "alt_assets": [
        "MSTR",    # MicroStrategy (Bitcoin proxy)
        "MP",      # MP Materials (rare earths)
        "PLTR",    # Palantir
    ],
    
    "international": [
        "NVO",     # Novo Nordisk (Denmark)
        "ASML",    # ASML (Netherlands)
        "TSM",     # TSMC (Taiwan)
        "BABA",    # Alibaba (China)
    ],
    
    "miners": [
        "COPX",    # Copper miners ETF
        "PICK",    # Global metals & mining ETF
        "REMX",    # Rare earth / critical metals ETF
        "GDXJ",    # Junior gold miners ETF
        "SIL",     # Silver miners ETF
    ],
    
    "commodities": [
        "GLD",     # Gold ETF
        "SLV",     # Silver ETF
        "PPLT",    # Platinum ETF
        "JO",      # Coffee ETF
        "LIT",     # Lithium & Battery Tech ETF
    ],
    
    "macro_etfs": [
        "SPY",     # S&P 500
        "QQQ",     # Nasdaq 100
        "IWM",     # Russell 2000 (Small Cap)
        "TLT",     # Long-term Treasuries
        "DBC",     # Commodities
        "URTH",    # MSCI World (global equities)
    ],
}

# ========== DERIVED SYMBOL LISTS ==========

# Flatten all categorized symbols into a single list
ALL_SYMBOLS = []
for category in SYMBOL_CATEGORIES.values():
    ALL_SYMBOLS.extend(category)

# Remove duplicates while preserving order
ALL_SYMBOLS = list(dict.fromkeys(ALL_SYMBOLS))

# Category-specific lists for selective backtesting or analysis
US_EQUITIES = (
    SYMBOL_CATEGORIES["tech"] + 
    SYMBOL_CATEGORIES["defense"] + 
    SYMBOL_CATEGORIES["alt_assets"]
)
INTERNATIONAL_EQUITIES = SYMBOL_CATEGORIES["international"]
ETFS = (
    SYMBOL_CATEGORIES["miners"] + 
    SYMBOL_CATEGORIES["commodities"] + 
    SYMBOL_CATEGORIES["macro_etfs"]
)

# Backwards compatibility alias
SYMBOLS = SYMBOL_CATEGORIES

__all__ = [
    "ACTIVE_SYMBOLS",
    "SYMBOLS_LIST",
    "SYMBOL_CATEGORIES",
    "SYMBOLS",  # Alias for backwards compatibility
    "ALL_SYMBOLS",
    "US_EQUITIES",
    "INTERNATIONAL_EQUITIES",
    "ETFS",
]
