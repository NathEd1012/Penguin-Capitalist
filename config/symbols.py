"""Expanded trading symbol universe organized by category."""

SYMBOLS = {
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

# Flatten all symbols into a single list for convenient access
ALL_SYMBOLS = []
for category in SYMBOLS.values():
    ALL_SYMBOLS.extend(category)

# Remove duplicates while preserving order
ALL_SYMBOLS = list(dict.fromkeys(ALL_SYMBOLS))

# Category-specific lists for selective backtesting
US_EQUITIES = SYMBOLS["tech"] + SYMBOLS["defense"] + SYMBOLS["alt_assets"]
INTERNATIONAL_EQUITIES = SYMBOLS["international"]
ETFS = SYMBOLS["miners"] + SYMBOLS["commodities"] + SYMBOLS["macro_etfs"]

__all__ = [
    "SYMBOLS",
    "ALL_SYMBOLS",
    "US_EQUITIES",
    "INTERNATIONAL_EQUITIES",
    "ETFS",
]
