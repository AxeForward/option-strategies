
import pandas as pd
import numpy as np
import scipy.stats as si
import matplotlib.pyplot as plt
from datetime import datetime
import sys
import os

# Import local modules
# Ensure current directory is in path
sys.path.append(os.getcwd())
from get_asset_option_t_quote import get_option_quotes
from fetch_market_data import get_paradex_futures_data, get_fred_risk_free_rate

# Try importing optionlab, fallback if not installed/configured
try:
    from optionlab import run_strategy, plot_pl, get_pl
    print_pl = None # Handle missing function if code relies on it (we don't use it yet)
except ImportError as e:
    print(f"Warning: optionlab import failed: {e}. Visualization will be skipped.")
    run_strategy = None

def calculate_bs_delta(S, K, T, r, sigma, option_type='call'):
    """
    Calculate Black-Scholes Delta.
    """
    if T <= 0:
        # Expired or expiring today
        if S > K:
            return 1.0 if option_type == 'call' else 0.0
        elif S < K:
            return 0.0 if option_type == 'call' else -1.0
        else:
            return 0.5 if option_type == 'call' else -0.5

    d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    if option_type == 'call':
        return si.norm.cdf(d1, 0.0, 1.0)
    else:
        return si.norm.cdf(d1, 0.0, 1.0) - 1.0

def evaluate_gamma_scalping():
    print("\n--- Starting Gamma Scalping Strategy Evaluation ---\n")
    
    # 1. Get Futures Data (Underlying)
    print("1. Fetching Futures Data from Paradex...")
    futures_symbol = "ETH-USD-PERP"
    futures_data = get_paradex_futures_data(futures_symbol)
    
    if not futures_data:
        print("Error: Failed to fetch futures data.")
        return
        
    S0 = futures_data['mid_price']
    print(f"   Current Futures Price (S0): ${S0:.2f}")
    
    # 2. Get Risk Free Rate
    print("2. Fetching Risk-Free Rate from FRED...")
    try:
        rf_df = get_fred_risk_free_rate()
        if rf_df is not None and not rf_df.empty:
            # FRED rate is in percent, e.g. 4.5
            r_percent = rf_df.iloc[-1]['rate']
            r = r_percent / 100.0
            print(f"   Risk-Free Rate: {r_percent:.2f}% (using {r:.4f})")
        else:
            r = 0.045
            print(f"   Warning: Could not fetch rates. Using default: {r*100}%")
    except Exception as e:
        r = 0.045
        print(f"   Error fetching rates: {e}. Using default: {r*100}%")

    # 3. Get Option Quotes
    print("3. Fetching Option Quotes from Binance...")
    underlying = "ETHUSDT"
    options_dict = get_option_quotes(underlying)
    
    if not options_dict:
        print("Error: Failed to fetch option quotes.")
        return
        
    # Select Target Expiry
    # expiries = sorted(options_dict.keys())
    # target_expiry = expiries[0]
    target_expiry = "2026-02-13"
    print(f"   Target Expiry: {target_expiry}")
    
    if target_expiry not in options_dict:
        print(f"Error: Data for expiry {target_expiry} not found. Available: {sorted(options_dict.keys())}")
        return

    df = options_dict[target_expiry]
    if df.empty:
        print("Error: No data for target expiry.")
        return

    # 4. Strategy Setup: ATM Straddle with Delta Hedge
    # Find ATM Strike
    df['dist'] = abs(df['Strike'] - S0)
    atm_row = df.loc[df['dist'].idxmin()]
    
    strike = atm_row['Strike']
    print(f"   Selected ATM Strike: {strike}")
    
    # Extract Data
    c_ask = atm_row['C_Ask']
    p_ask = atm_row['P_Ask']
    c_iv = atm_row['C_AskIV']
    p_iv = atm_row['P_AskIV']
    
    if pd.isna(c_iv) or pd.isna(p_iv):
        print("   Warning: Implied Volatility (IV) missing. Using 0.5 as fallback.")
        c_iv = 0.5 if pd.isna(c_iv) else c_iv
        p_iv = 0.5 if pd.isna(p_iv) else p_iv

    print(f"   Call Ask: ${c_ask:.2f} (IV: {c_iv:.2f})")
    print(f"   Put Ask: ${p_ask:.2f} (IV: {p_iv:.2f})")

    # Calculate Time to Expiry
    expiry_date = datetime.strptime(target_expiry, "%Y-%m-%d")
    now = datetime.now()
    days_to_expiry = (expiry_date - now).days
    
    # Approximate fraction of year
    if days_to_expiry < 0:
        T = 0.001 # Expiring soon
    else:
        T = max(days_to_expiry, 1) / 365.0
    
    print(f"   Time to Expiry (T): {T:.4f} years")

    # Calculate Deltas
    delta_c = calculate_bs_delta(S0, strike, T, r, c_iv, 'call')
    delta_p = calculate_bs_delta(S0, strike, T, r, p_iv, 'put')
    
    # Straddle: Buy 1 Call, Buy 1 Put
    net_option_delta = delta_c + delta_p # Put delta is negative
    
    print(f"   Call Delta: {delta_c:.4f}")
    print(f"   Put Delta: {delta_p:.4f}")
    print(f"   Net Option Delta (Straddle): {net_option_delta:.4f}")
    
    # Initial Hedge
    # We want Total Delta = 0 => Hedge Delta = -Net Option Delta
    hedge_qty = -net_option_delta
    
    print("\n--- Strategy Execution Proposal ---")
    print(f"1. BUY 1 Call @ {strike} (Cost: ${c_ask:.2f})")
    print(f"2. BUY 1 Put @ {strike} (Cost: ${p_ask:.2f})")
    
    hedge_action = "SELL (Short)" if hedge_qty < 0 else "BUY (Long)"
    print(f"3. {hedge_action} {abs(hedge_qty):.4f} Futures @ ${S0:.2f} (Hedge)")
    
    total_cost = c_ask + p_ask
    print(f"Total Premium Paid: ${total_cost:.2f}")

    # 5. OptionLab Visualization
    if run_strategy:
        print("\n--- OptionLab Visualization ---")
        
        try:
            from optionlab import Inputs
            
            # Prepare Inputs
            start_date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Define Range for Plotting (+/- 20% of Spot)
            min_stock = S0 * 0.8
            max_stock = S0 * 1.2
            
            # Average IV if available, else 0.5
            avg_iv = (c_iv + p_iv) / 2 if (c_iv and p_iv) else 0.5
            
            # Scaling factor for simulation (to allow integer stock units)
            N_CONTRACTS = 100
            
            # Re-calculate costs and hedge for N contracts
            total_premium = (c_ask + p_ask) * N_CONTRACTS
            
            # Hedge Quantity (Stock/Futures)
            # Net Delta = (Delta_C + Delta_P) * N
            # Hedge = -Net Delta
            # We round to nearest integer because optionlab requires int for n
            raw_hedge_qty = -net_option_delta * N_CONTRACTS
            hedge_n = int(round(abs(raw_hedge_qty)))
            hedge_action = "sell" if raw_hedge_qty < 0 else "buy"
            
            print(f"\n--- Strategy Setup (Scaled to {N_CONTRACTS} contracts) ---")
            print(f"   Buy {N_CONTRACTS} Calls @ {strike}")
            print(f"   Buy {N_CONTRACTS} Puts  @ {strike}")
            print(f"   Net Delta: {net_option_delta * N_CONTRACTS:.2f}")
            print(f"   Hedge Action: {hedge_action.upper()} {hedge_n} Futures (rounded from {abs(raw_hedge_qty):.2f})")
            
            # Construct Legs (Options Only for OptionLab)
            legs = [
                {"type": "call", "strike": strike, "premium": c_ask, "n": N_CONTRACTS, "action": "buy"},
                {"type": "put", "strike": strike, "premium": p_ask, "n": N_CONTRACTS, "action": "buy"}
            ]
            
            # Print Hedge Info (Manual Calculation planned)
            if hedge_n > 0:
                print(f"   (Stock Hedge of {hedge_n} units {hedge_action.upper()} will be calculated manually)")

            print(f"Creating Inputs for OptionLab...")
            print(f"   Spot: {S0:.2f}, Range: [{min_stock:.2f}, {max_stock:.2f}]")
            print(f"   Start: {start_date_str}, Target: {target_expiry}")
            
            inputs_obj = Inputs(
                stock_price=S0,
                start_date=start_date_str,
                target_date=target_expiry,
                volatility=avg_iv,
                interest_rate=r,
                min_stock=min_stock,
                max_stock=max_stock,
                strategy=legs
            )
            
            print("Running Strategy Calculation...")
            out = run_strategy(inputs_obj)
            
            print("Inspecting OptionLab Output...")
            try:
                # Try to get data
                if get_pl:
                    # Based on source, get_pl might take 'out' or be a method
                    # Let's check what get_pl does
                    try:
                        pl_data = get_pl(out)
                        print(f"get_pl returned type: {type(pl_data)}")
                        if hasattr(pl_data, 'head'):
                            print(pl_data.head())
                        else:
                            print(pl_data[:5] if isinstance(pl_data, list) else pl_data)
                    except Exception as e:
                        print(f"get_pl(out) failed: {e}")
                
                # Check attributes
                print(f"Output attributes: {[x for x in dir(out) if not x.startswith('_')]}")
                
            except Exception as e:
                print(f"Inspection failed: {e}")

            print("Generating Payoff Plot (Options Only for now)...")
            
            # Use non-interactive backend for saving
            plt.switch_backend('Agg') 
            
            # Plot
            plot_pl(out)
            
            plt.title(f"Gamma Scalping Payoff (Options Component)\nExpiry: {target_expiry}, Spot: {S0:.2f}")
            plt.xlabel("Underlying Price at Expiry")
            plt.ylabel("Profit / Loss ($)")
            plt.grid(True, alpha=0.3)
            plt.axvline(x=S0, color='r', linestyle='--', label=f'Current Spot: {S0:.0f}')
            plt.legend()
            
            output_file = "gamma_scalping_payoff.png"
            plt.savefig(output_file)
            print(f"Payoff plot saved successfully to: {os.path.abspath(output_file)}")
            
        except Exception as e:
            print(f"OptionLab Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    evaluate_gamma_scalping()
