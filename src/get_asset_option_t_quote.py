import requests
import pandas as pd
import numpy as np
from datetime import datetime

# Constants
BASE_URL = "https://eapi.binance.com"
UNDERLYING = "ETHUSDT"

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

def get_option_quotes(underlying, expiry_date=None):
    """
    获取期权行情数据并返回 DataFrame 字典
    
    Args:
        underlying: 标的交易对，如 'ETHUSDT'
        expiry_date: 到期日期（可选），格式 'YYYY-MM-DD'，如果为 None 则返回所有到期日
    
    Returns:
        dict: {expiry_date: DataFrame} 字典，每个 DataFrame 包含该到期日的所有行权价数据
              如果失败则返回 None
    """
    print(f"Fetching Option Data for {underlying} from Binance...")
    
    # 1. Get Exchange Info
    exchange_info = get_exchange_info()
    if not exchange_info:
        return None

    # Filter for target underlying options
    target_options = [
        s for s in exchange_info['optionSymbols'] 
        if s['underlying'] == underlying
    ]
    
    if not target_options:
        print(f"No options found for {underlying}")
        return None

    print(f"Found {len(target_options)} option contracts.")

    # Create mapping: Symbol -> Details
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
        return None

    # Convert to dict for fast lookup by symbol
    ticker_map = {t['symbol']: t for t in tickers}
    mark_map = {m['symbol']: m for m in marks}
    
    # 3. Aggregate Data Structure
    # { Expiry: { Strike: { 'call': {...}, 'put': {...} } } }
    data_by_expiry = {}

    for symbol, details in symbol_map.items():
        expiry = details['expiry']
        strike = details['strike']
        side = details['side']
        
        t_data = ticker_map.get(symbol, {})
        m_data = mark_map.get(symbol, {})
        
        # Extract metrics
        metrics = {
            'bid': float(t_data.get('bidPrice', np.nan)) if t_data.get('bidPrice') else np.nan,
            'ask': float(t_data.get('askPrice', np.nan)) if t_data.get('askPrice') else np.nan,
            'vol': float(t_data.get('volume', np.nan)) if t_data.get('volume') else np.nan,
            'bid_iv': float(m_data.get('bidIV', np.nan)) if m_data.get('bidIV') else np.nan,
            'ask_iv': float(m_data.get('askIV', np.nan)) if m_data.get('askIV') else np.nan,
            'delta': float(m_data.get('delta', np.nan)) if m_data.get('delta') else np.nan,
        }
        
        if expiry not in data_by_expiry:
            data_by_expiry[expiry] = {}
        if strike not in data_by_expiry[expiry]:
            data_by_expiry[expiry][strike] = {'call': {}, 'put': {}}
            
        if side == 'CALL':
            data_by_expiry[expiry][strike]['call'] = metrics
        else:
            data_by_expiry[expiry][strike]['put'] = metrics

    # 4. Convert to DataFrame format
    result = {}
    expiries = sorted(data_by_expiry.keys())
    
    # Filter by expiry_date if provided
    if expiry_date:
        if expiry_date not in data_by_expiry:
            print(f"No data found for expiry date: {expiry_date}")
            print(f"Available expiry dates: {', '.join(expiries)}")
            return None
        expiries = [expiry_date]
    
    for expiry in expiries:
        strikes_data = data_by_expiry[expiry]
        rows = []
        for strike in sorted(strikes_data.keys()):
            c = strikes_data[strike]['call']
            p = strikes_data[strike]['put']
            
            # Format: C_Vol, C_BidIV, C_Bid, C_Ask, C_AskIV, C_Delta | Strike | ...
            row = {
                'C_Vol': c.get('vol', np.nan),
                'C_BidIV': c.get('bid_iv', np.nan),
                'C_Bid': c.get('bid', np.nan),
                'C_Ask': c.get('ask', np.nan),
                'C_AskIV': c.get('ask_iv', np.nan),
                'C_Delta': c.get('delta', np.nan),
                
                'Strike': strike,
                
                'P_Delta': p.get('delta', np.nan),
                'P_BidIV': p.get('bid_iv', np.nan),
                'P_Bid': p.get('bid', np.nan),
                'P_Ask': p.get('ask', np.nan),
                'P_AskIV': p.get('ask_iv', np.nan),
                'P_Vol': p.get('vol', np.nan)
            }
            rows.append(row)
            
        df = pd.DataFrame(rows)
        if not df.empty:
            # Define column order
            cols = [
                'C_Vol', 'C_BidIV', 'C_Bid', 'C_Ask', 'C_AskIV', 'C_Delta',
                'Strike',
                'P_Delta', 'P_BidIV', 'P_Bid', 'P_Ask', 'P_AskIV', 'P_Vol'
            ]
            df = df[cols]
            result[expiry] = df
    
    return result


def print_option_quotes(underlying, expiry_date=None):
    """
    打印格式化的期权报价表
    
    Args:
        underlying: 标的交易对，如 'ETHUSDT'
        expiry_date: 到期日期（可选），格式 'YYYY-MM-DD'，如果为 None 则打印所有到期日
    """
    # Get data
    data_dict = get_option_quotes(underlying, expiry_date)
    
    if not data_dict:
        return
    
    # Configure pandas display options
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.unicode.east_asian_width', True)
    pd.set_option('display.max_colwidth', 20)
    
    # Define formatter for specific columns
    formatters = {
        'C_Vol': '{:,.2f}'.format,
        'C_BidIV': '{:.2f}'.format,
        'C_Bid': '{:.2f}'.format,
        'C_Ask': '{:.2f}'.format,
        'C_AskIV': '{:.2f}'.format,
        'C_Delta': '{:.4f}'.format,
        'Strike': '{:.0f}'.format,
        'P_Delta': '{:.4f}'.format,
        'P_BidIV': '{:.2f}'.format,
        'P_Bid': '{:.2f}'.format,
        'P_Ask': '{:.2f}'.format,
        'P_AskIV': '{:.2f}'.format,
        'P_Vol': '{:,.2f}'.format
    }
    
    # Print tables
    for expiry in sorted(data_dict.keys()):
        print(f"\n{'='*30} Expiry: {expiry} {'='*30}")
        df = data_dict[expiry]
        print(df.to_string(index=False, formatters=formatters))


def main():
    """主函数：打印默认交易对的期权报价"""
    print_option_quotes(UNDERLYING)


if __name__ == "__main__":
    main()
