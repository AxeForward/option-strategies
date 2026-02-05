import requests
import pandas as pd
from datetime import datetime
import time

# Constants
BASE_URL = "https://eapi.binance.com"
UNDERLYING = "ETHUSDT"

import requests
import pandas as pd
from datetime import datetime
import time
import sys

# Constants
BASE_URL = "https://eapi.binance.com"
UNDERLYING = sys.argv[1] if len(sys.argv) > 1 else "ETHUSDT"

def get_json(url, params=None):
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def get_exchange_info():
    """Fetch exchange information (symbols, strikes, expirations)."""
    return get_json(f"{BASE_URL}/eapi/v1/exchangeInfo")

def get_tickers_bulk():
    """Fetch current market data (best bid/ask, volume) for ALL options."""
    # Returns list of all tickers
    return get_json(f"{BASE_URL}/eapi/v1/ticker")

def get_mark_prices_bulk():
    """Fetch mark prices and Greeks (IVs) for ALL options."""
    # Returns list of all mark prices
    return get_json(f"{BASE_URL}/eapi/v1/mark")

def format_expiry(ts):
    """Convert timestamp to readable date string."""
    return datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')

def main():
    print(f"Fetching Option Data for {UNDERLYING} from Binance...")
    
    # 1. Get Exchange Info
    exchange_info = get_exchange_info()
    if not exchange_info:
        return

    # Filter for target underlying options
    # Note: optionSymbols may include symbols for other underlyings if not filtered carefully?
    # Usually exchangeInfo returns all.
    target_options = [
        s for s in exchange_info['optionSymbols'] 
        if s['underlying'] == UNDERLYING
    ]
    
    if not target_options:
        print(f"No options found for {UNDERLYING}")
        return

    print(f"Found {len(target_options)} option contracts.")

    # Create mapping: Symbol -> Details
    # Also keep track of expiry/strike for structuring
    symbol_map = {}
    for opt in target_options:
        symbol_map[opt['symbol']] = {
            'strike': float(opt['strikePrice']),
            'expiry_ts': opt['expiryDate'],
            'expiry': format_expiry(opt['expiryDate']),
            'side': opt['side']  # 'CALL' or 'PUT'
        }

    # 2. Get Bulk Data
    tickers = get_tickers_bulk()
    marks = get_mark_prices_bulk()
    
    if not tickers or not marks:
        print("Failed to fetch market data.")
        return

    # Convert to dict for fast lookup by symbol
    # Ticker: bidPrice, askPrice, volume (24h)
    ticker_map = {t['symbol']: t for t in tickers}
    
    # Mark: bidIV, askIV, markIV
    mark_map = {m['symbol']: m for m in marks}
    
    # 3. Aggregate Data Structure
    # { Expiry: { Strike: { 'call': {...}, 'put': {...} } } }
    data_by_expiry = {}

    for symbol, details in symbol_map.items():
        expiry = details['expiry']
        strike = details['strike']
        side = details['side'] # CALL or PUT
        
        t_data = ticker_map.get(symbol, {})
        m_data = mark_map.get(symbol, {})
        
        # Extract metrics
        metrics = {
            'bid': float(t_data.get('bidPrice', 0.0)),
            'ask': float(t_data.get('askPrice', 0.0)),
            'vol': float(t_data.get('volume', 0.0)),
            'bid_iv': float(m_data.get('bidIV', 0.0)),
            'ask_iv': float(m_data.get('askIV', 0.0)),
        }
        
        if expiry not in data_by_expiry:
            data_by_expiry[expiry] = {}
        if strike not in data_by_expiry[expiry]:
            data_by_expiry[expiry][strike] = {'call': {}, 'put': {}}
            
        if side == 'CALL':
            data_by_expiry[expiry][strike]['call'] = metrics
        else:
            data_by_expiry[expiry][strike]['put'] = metrics

    # 4. Display Tables
    expiries = sorted(data_by_expiry.keys())

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.unicode.east_asian_width', True)

    for expiry in expiries:
        print(f"\n{'='*30} Expiry: {expiry} {'='*30}")
        
        strikes_data = data_by_expiry[expiry]
        rows = []
        for strike in sorted(strikes_data.keys()):
            c = strikes_data[strike]['call']
            p = strikes_data[strike]['put']
            
            # Format: C_Vol, C_BidIV, C_Bid, C_Ask, C_AskIV | Strike | ...
            row = {
                'C_Vol': c.get('vol', 0.0),
                'C_BidIV': c.get('bid_iv', 0.0),
                'C_Bid': c.get('bid', 0.0),
                'C_Ask': c.get('ask', 0.0),
                'C_AskIV': c.get('ask_iv', 0.0),
                
                'Strike': strike,
                
                'P_BidIV': p.get('bid_iv', 0.0),
                'P_Bid': p.get('bid', 0.0),
                'P_Ask': p.get('ask', 0.0),
                'P_AskIV': p.get('ask_iv', 0.0),
                'P_Vol': p.get('vol', 0.0)
            }
            rows.append(row)
            
        df = pd.DataFrame(rows)
        if df.empty:
            print("No data.")
            continue
            
        # Define column order
        cols = [
            'C_Vol', 'C_BidIV', 'C_Bid', 'C_Ask', 'C_AskIV',
            'Strike',
            'P_BidIV', 'P_Bid', 'P_Ask', 'P_AskIV', 'P_Vol'
        ]
        df = df[cols]
        
        # Optional: Rounding for cleaner display
        pd.set_option('display.max_colwidth', 20)
        
        # Define formatter for specific columns
        formatters = {
            'C_Vol': '{:,.2f}'.format,
            'C_BidIV': '{:.2f}'.format,
            'C_Bid': '{:.2f}'.format,
            'C_Ask': '{:.2f}'.format,
            'C_AskIV': '{:.2f}'.format,
            'Strike': '{:.0f}'.format,
            'P_BidIV': '{:.2f}'.format,
            'P_Bid': '{:.2f}'.format,
            'P_Ask': '{:.2f}'.format,
            'P_AskIV': '{:.2f}'.format,
            'P_Vol': '{:,.2f}'.format
        }

        # Print with formatters
        print(df.to_string(index=False, formatters=formatters))

if __name__ == "__main__":
    main()
