import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
FRED_API_KEY = os.getenv("FRED_API_KEY")

# Paradex API Config
PARADEX_API_URL = "https://api.prod.paradex.trade"
# Using ETH-USD-PERP as default since the user was working with ETHUSDT options
DEFAULT_PARADEX_SYMBOL = "ETH-USD-PERP" 

def get_fred_risk_free_rate(start_date=None, end_date=None, series_id='DGS3MO', api_key=None):
    """
    Fetch risk-free rate (default 3-Month Treasury Constant Maturity Rate) from FRED.
    
    Args:
        start_date (str): 'YYYY-MM-DD'
        end_date (str): 'YYYY-MM-DD'
        series_id (str): FRED Series ID (e.g., 'DGS3MO', 'DTB3')
        api_key (str): FRED API Key (optional if set in env)
    
    Returns:
        pd.DataFrame: DataFrame with 'date' and 'rate' columns
    """
    api_key = api_key or FRED_API_KEY
    if not api_key:
        print("Warning: FRED_API_KEY not found. Please set it in environment or pass as argument.")
        return None

    url = "https://api.stlouisfed.org/fred/series/observations"
    
    params = {
        'series_id': series_id,
        'api_key': api_key,
        'file_type': 'json',
    }
    
    if start_date:
        params['observation_start'] = start_date
    if end_date:
        params['observation_end'] = end_date
        
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        observations = data.get('observations', [])
        if not observations:
            print("No data returned from FRED.")
            return None
            
        df = pd.DataFrame(observations)
        # FRED returns '.' for missing values
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df['date'] = pd.to_datetime(df['date'])
        
        # Renaissance format
        df = df[['date', 'value']].rename(columns={'value': 'rate'})
        df = df.dropna()
        
        # Convert percent to decimal (FRED returns 4.5 for 4.5%)
        # Usually option pricing models expect decimal (0.045), but let's keep as is or convert?
        # User asked for data, usually rate is kept in percent or converted. 
        # I'll leave it as percent but add a comment, or just return raw.
        # Let's keep it raw (percent) to match source, but user can transform.
        
        return df.set_index('date')
        
    except Exception as e:
        print(f"Error fetching FRED data: {e}")
        return None

def get_paradex_futures_data(symbol=DEFAULT_PARADEX_SYMBOL):
    """
    Fetch real-time BBO (Best Bid/Offer) data for perpetual futures from Paradex.
    
    Args:
        symbol (str): Market symbol, e.g., 'ETH-USD-PERP', 'BTC-USD-PERP'
    
    Returns:
        dict: Dictionary containing BBO data with keys:
            - 'bid': Best bid price
            - 'bid_size': Size at best bid
            - 'ask': Best ask price
            - 'ask_size': Size at best ask
            - 'spread': Ask - Bid
            - 'mid_price': (Bid + Ask) / 2
            - 'last_updated_at': Timestamp (ms)
            - 'last_updated_datetime': Human-readable datetime
            - 'market': Market symbol
            - 'seq_no': Sequence number
        Returns None if request fails.
    """
    url = f"{PARADEX_API_URL}/v1/bbo/{symbol}"
    
    try:
        response = requests.get(url, headers={'Accept': 'application/json'})
        response.raise_for_status()
        data = response.json()
        
        # Parse and enrich the data
        bid = float(data.get('bid', 0))
        ask = float(data.get('ask', 0))
        bid_size = float(data.get('bid_size', 0))
        ask_size = float(data.get('ask_size', 0))
        last_updated_at = data.get('last_updated_at')
        
        # Calculate derived fields
        spread = ask - bid
        mid_price = (bid + ask) / 2
        
        # Convert timestamp to datetime
        last_updated_datetime = datetime.fromtimestamp(last_updated_at / 1000) if last_updated_at else None
        
        return {
            'bid': bid,
            'bid_size': bid_size,
            'ask': ask,
            'ask_size': ask_size,
            'spread': spread,
            'mid_price': mid_price,
            'last_updated_at': last_updated_at,
            'last_updated_datetime': last_updated_datetime,
            'market': data.get('market'),
            'seq_no': data.get('seq_no')
        }
        
    except Exception as e:
        print(f"Error fetching BBO data for {symbol}: {e}")
        return None


# Module-level usage examples (commented out):
# 
# Example 1: Fetch Risk-Free Rate
# rf_data = get_fred_risk_free_rate(start_date='2026-01-01', end_date='2026-02-07')
# print(rf_data)
#
# Example 2: Fetch Real-time BBO Data
# bbo_data = get_paradex_futures_data('ETH-USD-PERP')
# if bbo_data:
#     print(f"Market: {bbo_data['market']}")
#     print(f"Mid Price: ${bbo_data['mid_price']:.2f}")
#     print(f"Spread: ${bbo_data['spread']:.2f}")
#     print(f"Bid: ${bbo_data['bid']:.2f} (Size: {bbo_data['bid_size']})")
#     print(f"Ask: ${bbo_data['ask']:.2f} (Size: {bbo_data['ask_size']})")
#     print(f"Last Updated: {bbo_data['last_updated_datetime']}")
