import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest

# Load environment variables from .env file
load_dotenv()

# Initialize client with credentials from .env
api_key = os.getenv('ALPACA_API_KEY')
secret_key = os.getenv('ALPACA_SECRET_KEY')
client = TradingClient(api_key, secret_key)

# Get all US equity assets
assets = client.get_all_assets(GetAssetsRequest(asset_class="us_equity"))

# Extract ticker symbols and company names
tickers_data = [(asset.symbol, asset.name) for asset in assets]

# Save to text file
with open("available_tickers.txt", "w") as f:
    f.write(f"Total Tickers: {len(tickers_data)}\n")
    f.write("=" * 80 + "\n\n")

    for symbol, name in sorted(tickers_data):
        f.write(f"{symbol:<10} - {name}\n")

print(f"✓ Saved {len(tickers_data)} tickers to 'available_tickers.txt'")
print(f"\nFirst 10 tickers:")
for symbol, name in sorted(tickers_data)[:10]:
    print(f"  {symbol:<10} - {name}")
