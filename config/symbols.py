"""Trading symbol configuration for backtesting.

This module contains:
1. ACTIVE_SYMBOLS - The current list of symbols used for backtesting
2. SYMBOL_CATEGORIES - Organized categorization of available symbols
3. Helper lists for different market segments
"""

# ========== ACTIVE SYMBOLS FOR BACKTESTING ==========
# This is the primary list used by the backtest engine
# Choose active list by changing just this variable:
# "LIST_1" | "LIST_2" | "LIST_3" | "LIST_4"
ACTIVE_SYMBOL_LIST = "LIST_2"

# List 1: 5 large-cap stocks
SYMBOL_LIST_1 = [
    "NVDA",   # Nvidia
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "AMZN",   # Amazon
    "TSLA",   # Tesla
    "SPY",    # S&P 500 ETF benchmark
]

# List 2: current full ticker set (previous ACTIVE_SYMBOLS)
SYMBOL_LIST_2 = [
    # Tech giants & growth
    "SPY",    # S&P 500 ETF benchmark
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

# List 3: intentionally empty for custom manual additions
SYMBOL_LIST_3 = [
    # ===== MEGA / LARGE CAP TECH =====
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AVGO","ORCL","ADBE",
    "CRM","INTC","CSCO","AMD","QCOM","TXN","NOW","INTU","AMAT","MU",

    # ===== COMMUNICATION / INTERNET =====
    "NFLX","DIS","CMCSA","TMUS","T","VZ","SNAP","PINS","MTCH","EA",

    # ===== FINANCIALS =====
    "JPM","BAC","WFC","C","GS","MS","BLK","SCHW","AXP","SPGI",
    "CME","ICE","CB","PGR","AON","MMC","USB","PNC","TFC","BK",

    # ===== HEALTHCARE =====
    "LLY","JNJ","UNH","PFE","ABBV","MRK","TMO","DHR","ABT","BMY",
    "AMGN","GILD","ISRG","VRTX","REGN","MDT","SYK","CI","ZTS","HCA",

    # ===== INDUSTRIALS =====
    "BA","CAT","DE","GE","HON","UPS","FDX","RTX","LMT","NOC",
    "EMR","ETN","PH","ITW","GD","WM","RSG","OTIS","ROK","FAST",

    # ===== CONSUMER DISCRETIONARY =====
    "HD","MCD","SBUX","NKE","LOW","TJX","BKNG","MAR","HLT","GM",
    "F","RIVN","EBAY","ETSY","ROST","LULU","ULTA","DPZ","YUM","CMG",

    # ===== CONSUMER STAPLES =====
    "PG","KO","PEP","WMT","COST","PM","MO","MDLZ","CL","KMB",
    "GIS","HSY","KHC","KR","SYY","ADM","EL","STZ","MNST","DG",

    # ===== ENERGY =====
    "XOM","CVX","COP","EOG","SLB","PXD","MPC","VLO","PSX","OXY",
    "DVN","HAL","BKR","KMI","WMB","OKE","FANG","HES","APA","CTRA",

    # ===== MATERIALS =====
    "LIN","APD","ECL","SHW","FCX","NEM","DOW","DD","PPG","NUE",
    "STLD","MLM","VMC","ALB","IFF","LYB","MOS","CF","BALL","PKG",

    # ===== UTILITIES =====
    "NEE","DUK","SO","D","AEP","EXC","SRE","PEG","XEL","ED",

    # ===== REAL ESTATE (REITs) =====
    "AMT","PLD","CCI","EQIX","PSA","O","WELL","SPG","DLR","VTR",

    # ===== MID-CAP / HIGH LIQUIDITY GROWTH =====
    "SQ","SHOP","SNOW","CRWD","NET","DDOG","ZS","OKTA","UBER","LYFT",
    "ABNB","COIN","AFRM","SOFI","RBLX","PATH","PLTR","AI","UPST","HOOD",

    # ===== SEMICONDUCTOR ECOSYSTEM =====
    "LRCX","KLAC","ASML","MCHP","ON","NXPI","MPWR","TER","SWKS","QRVO",

    # ===== TRANSPORT / LOGISTICS =====
    "CSX","NSC","UNP","JBHT","CHRW","ODFL","LSTR","EXPD","UAL","DAL",

    # ===== ADDITIONAL DIVERSIFIERS =====
    "SPY","QQQ","IWM","DIA","XLK","XLF","XLE","XLV","XLI","XLP"
]

SYMBOL_LIST_4 = [
    # ===== CORE MEGA / INDEX =====
    "SPY","QQQ","IWM","DIA",
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO",

    # ===== LARGE CAP TECH =====
    "ORCL","ADBE","CRM","CSCO","AMD","QCOM","TXN","INTU","NOW","AMAT","MU","INTC",

    # ===== COMMUNICATION =====
    "NFLX","DIS","CMCSA","TMUS","T","VZ","EA",

    # ===== FINANCIALS =====
    "JPM","BAC","WFC","C","GS","MS","BLK","SCHW","AXP","SPGI",
    "CME","ICE","CB","PGR","AON","MMC","USB","PNC","TFC","BK",

    # ===== HEALTHCARE =====
    "LLY","JNJ","UNH","PFE","ABBV","MRK","TMO","DHR","ABT","BMY",
    "AMGN","GILD","ISRG","VRTX","REGN","MDT","SYK","CI","ZTS","HCA",

    # ===== INDUSTRIALS =====
    "BA","CAT","DE","GE","HON","UPS","FDX","RTX","LMT","NOC",
    "EMR","ETN","PH","ITW","GD","WM","RSG","OTIS","ROK","FAST",

    # ===== CONSUMER =====
    "HD","MCD","SBUX","NKE","LOW","TJX","BKNG","MAR","HLT","GM",
    "F","ROST","LULU","ULTA","DPZ","YUM","CMG",

    # ===== STAPLES =====
    "PG","KO","PEP","WMT","COST","PM","MO","MDLZ","CL","KMB",
    "GIS","HSY","KHC","KR","SYY","ADM","EL","STZ","MNST","DG",

    # ===== ENERGY =====
    "XOM","CVX","COP","EOG","SLB","MPC","VLO","PSX","OXY",
    "DVN","HAL","BKR","KMI","WMB","OKE","FANG","HES","APA","CTRA",

    # ===== MATERIALS =====
    "LIN","APD","ECL","SHW","FCX","NEM","DOW","DD","PPG","NUE",
    "STLD","MLM","VMC","ALB","IFF","LYB","MOS","CF","BALL","PKG",

    # ===== UTILITIES =====
    "NEE","DUK","SO","D","AEP","EXC","SRE","PEG","XEL","ED",

    # ===== REITS =====
    "AMT","PLD","CCI","EQIX","PSA","O","WELL","SPG","DLR","VTR",

    # ===== MID CAP GROWTH =====
    "SNOW","CRWD","DDOG","NET","ZS","OKTA","PLTR","SQ","SHOP","UBER",
    "ABNB","RBLX",

    # ===== SEMICONDUCTOR ECOSYSTEM =====
    "LRCX","KLAC","ASML","MCHP","ON","NXPI","MPWR","TER","SWKS","QRVO",

    # ===== TRANSPORT =====
    "CSX","NSC","UNP","JBHT","CHRW","ODFL","LSTR","EXPD","UAL","DAL",

    # ===== SMALL / HIGH VOL (CONTROLLED) =====
    "COIN","SOFI","AFRM","UPST","AI","HOOD","PATH",
    "RIVN","LCID","NIO","XPEV","LI",

    # ===== ADDITIONAL LIQUID MID CAPS =====
    "DOCU","ZM","TWLO","ROKU","ETSY","PINS","SNAP",
    "BILL","HUBS","TEAM","MDB","FSLY","U","APP",

    # ===== BIOTECH / VOLATILE BUT LIQUID =====
    "MRNA","BNTX","DNA","BEAM","CRSP","EDIT","NTLA",

    # ===== CLEAN ENERGY / THEMATIC =====
    "ENPH","SEDG","RUN","PLUG","FCEL","BLDP",

    # ===== DEFENSE + SPECIALTY =====
    "KTOS","AVAV","HII",

    # ===== COMMODITY / MINING SMALLER =====
    "MP","SQM","LAC","VALE","RIO","BHP",

    # ===== FINTECH / PAYMENTS =====
    "PYPL","SQ","ADYEY","FIS","FISV","GPN",

    # ===== RANDOM LIQUID ADDITIONS =====
    "CVNA","DKNG","PENN","CHWY","W","BBY","TGT","KSS","M","GPS"
]
SYMBOL_LIST_5 = [
# ===== INDEX / MACRO =====
"SPY","SSO","QQQ","IWM","DIA","XLK","XLF","XLE","XLV","XLI","XLP",

# ===== BIG TECH / PLATFORMS =====
"AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","ORCL","ADBE",
"CRM","CSCO","AMD","QCOM","TXN","INTU","NOW","AMAT","MU","INTC",

# ===== SEMICONDUCTORS =====
"LRCX","KLAC","ASML","MCHP","ON","NXPI","MPWR","TER","SWKS","QRVO",

# ===== CLOUD / SOFTWARE =====
"SNOW","CRWD","DDOG","NET","ZS","OKTA","PLTR","MDB","TEAM","HUBS",
"BILL","DOCU","ZM","TWLO","FSLY","U","APP","ESTC","SPLK","WDAY",

# ===== INTERNET / PLATFORMS =====
"SHOP","UBER","ABNB","RBLX","NFLX","DIS","CMCSA","ROKU","PINS","SNAP",
"ETSY","MTCH","EA",

# ===== FINTECH / PAYMENTS =====
"SQ","PYPL","COIN","SOFI","AFRM","HOOD","UPST","FIS","FISV","GPN",
"ADYEY","NU","MELI",

# ===== BANKS / FINANCIALS =====
"JPM","BAC","WFC","C","GS","MS","BLK","SCHW","AXP","SPGI",
"CME","ICE","CB","PGR","AON","MMC","USB","PNC","TFC","BK",

# ===== HEALTHCARE / PHARMA =====
"LLY","JNJ","UNH","PFE","ABBV","MRK","TMO","DHR","ABT","BMY",
"AMGN","GILD","ISRG","VRTX","REGN","MDT","SYK","CI","ZTS","HCA",

# ===== BIOTECH / GENETICS =====
"MRNA","BNTX","DNA","CRSP","EDIT","NTLA","BEAM","BLUE","ARCT","SGEN",

# ===== INDUSTRIALS =====
"BA","CAT","DE","GE","HON","UPS","FDX","RTX","LMT","NOC",
"EMR","ETN","PH","ITW","GD","WM","RSG","OTIS","ROK","FAST",

# ===== TRANSPORT =====
"CSX","NSC","UNP","JBHT","CHRW","ODFL","LSTR","EXPD","UAL","DAL",

# ===== CONSUMER DISCRETIONARY =====
"HD","MCD","SBUX","NKE","LOW","TJX","BKNG","MAR","HLT","GM",
"F","ROST","LULU","ULTA","DPZ","YUM","CMG",

# ===== RETAIL / E-COMMERCE =====
"TGT","WMT","COST","BBY","KSS","M","GPS","CHWY","W","CVNA",

# ===== CONSUMER STAPLES =====
"PG","KO","PEP","PM","MO","MDLZ","CL","KMB","GIS","HSY",
"KHC","KR","SYY","ADM","EL","STZ","MNST","DG",

# ===== ENERGY =====
"XOM","CVX","COP","EOG","SLB","MPC","VLO","PSX","OXY",
"DVN","HAL","BKR","KMI","WMB","OKE","FANG","HES","APA","CTRA",

# ===== CLEAN ENERGY =====
"ENPH","SEDG","RUN","PLUG","FCEL","BLDP","BE","NEE","AES","ORA",

# ===== EV / MOBILITY =====
"RIVN","LCID","NIO","XPEV","LI","TSLA","F","GM",

# ===== MATERIALS / MINING =====
"LIN","APD","ECL","SHW","FCX","NEM","DOW","DD","PPG","NUE",
"STLD","MLM","VMC","ALB","IFF","LYB","MOS","CF","BALL","PKG",
"VALE","RIO","BHP","SQM","LAC","MP",

# ===== UTILITIES =====
"DUK","SO","D","AEP","EXC","SRE","PEG","XEL","ED",

# ===== REITS =====
"AMT","PLD","CCI","EQIX","PSA","O","WELL","SPG","DLR","VTR",

# ===== SPACE / DEFENSE TECH =====
"RKLB","SPCE","KTOS","AVAV","HII",

# ===== AI / EMERGING TECH =====
"AI","BBAI","SOUN","PATH","VERI",

# ===== CRYPTO / INFRA =====
"COIN","MSTR","RIOT","MARA","CAN","GREE",

# ===== HOUSING / REAL ESTATE TECH =====
"OPEN","RDFN","Z","ZG",

# ===== GAMING / BETTING =====
"DKNG","PENN","RSI",

# ===== INTERNATIONAL LARGE CAPS (US LISTED) =====
"TSM","NVO","ASML","BABA","JD","PDD"
]

SYMBOL_LISTS = {
    "LIST_1": SYMBOL_LIST_1,
    "LIST_2": SYMBOL_LIST_2,
    "LIST_3": SYMBOL_LIST_3,
    "LIST_4": SYMBOL_LIST_4,
    "LIST_5": SYMBOL_LIST_5,
    }

if ACTIVE_SYMBOL_LIST not in SYMBOL_LISTS:
    raise ValueError(
        f"Unknown ACTIVE_SYMBOL_LIST='{ACTIVE_SYMBOL_LIST}'. "
        f"Use one of: {', '.join(SYMBOL_LISTS.keys())}."
    )

ACTIVE_SYMBOLS = SYMBOL_LISTS[ACTIVE_SYMBOL_LIST]

# Legacy alias for compatibility
SYMBOLS_LIST = ACTIVE_SYMBOLS

# Backwards compatibility alias: keep SYMBOLS as active trading list.
SYMBOLS = ACTIVE_SYMBOLS

__all__ = [
    "ACTIVE_SYMBOL_LIST",
    "SYMBOL_LIST_1",
    "SYMBOL_LIST_2",
    "SYMBOL_LIST_3",
    "SYMBOL_LIST_4",
    "SYMBOL_LISTS",
    "ACTIVE_SYMBOLS",
    "SYMBOLS_LIST",
    "SYMBOLS",  # Alias for backwards compatibility
]
