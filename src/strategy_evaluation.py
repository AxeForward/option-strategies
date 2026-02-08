import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import os
import QuantLib as ql

def calculate_quantlib_greeks(S, K, expiry_date_str, r, sigma, option_type='call'):
    """
    Calculate Greeks using QuantLib.
    S: Spot Price
    K: Strike Price
    expiry_date_str: 'YYYY-MM-DD'
    r: Risk-free rate (decimal, e.g. 0.05)
    sigma: Volatility (decimal, e.g. 0.5)
    option_type: 'call' or 'put'
    """
    # 1. Date Setup
    today = datetime.now()
    ql_today = ql.Date(today.day, today.month, today.year)
    ql.Settings.instance().evaluationDate = ql_today

    # Parse Expiry (YYYY-MM-DD)
    try:
        exp_dt = datetime.strptime(expiry_date_str, "%Y-%m-%d")
        ql_expiry = ql.Date(exp_dt.day, exp_dt.month, exp_dt.year)
    except Exception as e:
        print(f"Error parsing date {expiry_date_str}: {e}")
        return None

    # Option Details
    opt_type = ql.Option.Call if option_type == 'call' else ql.Option.Put
    payoff = ql.PlainVanillaPayoff(opt_type, K)
    exercise = ql.EuropeanExercise(ql_expiry)
    european_option = ql.VanillaOption(payoff, exercise)

    # Market Data
    # Spot
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(S))
    
    # Rate (Risk Free)
    # Using Actual/365 for crypto/standard
    day_counter = ql.Actual365Fixed()
    flat_rate = ql.SimpleQuote(r)
    rate_handle = ql.YieldTermStructureHandle(ql.FlatForward(ql_today, ql.QuoteHandle(flat_rate), day_counter))
    
    # Dividend (Assume 0 for now)
    flat_div = ql.SimpleQuote(0.0)
    div_handle = ql.YieldTermStructureHandle(ql.FlatForward(ql_today, ql.QuoteHandle(flat_div), day_counter))
    
    # Volatility
    flat_vol = ql.SimpleQuote(sigma)
    vol_handle = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(ql_today, ql.NullCalendar(), ql.QuoteHandle(flat_vol), day_counter))

    # Process & Engine
    bsm_process = ql.BlackScholesMertonProcess(spot_handle, div_handle, rate_handle, vol_handle)
    engine = ql.AnalyticEuropeanEngine(bsm_process)
    european_option.setPricingEngine(engine)

    # Calculate
    try:
        price = european_option.NPV()
        delta = european_option.delta()
        gamma = european_option.gamma()
        theta = european_option.theta() / 365.0 # Per day approximation
        vega = european_option.vega() / 100.0   # For 1% vol change
        
        return {
            'price': price,
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega
        }
    except Exception as e:
        print(f"QuantLib Error: {e}")
        return None

def calculate_strategy_pnl(legs, spot_price, price_range=None):
    """
    Calculate PnL for a multi-leg option strategy.
    
    Parameters:
    -----------
    legs : list of dict
        Each dict represents a leg with structure:
        {
            'type': 'call' or 'put' or 'stock' or 'futures',
            'action': 'buy' or 'sell',
            'strike': float (for options),
            'premium': float (cost paid/received),
            'quantity': float (default 1.0)
        }
    spot_price : float
        Current spot/futures price (S0)
    price_range : np.array, optional
        Array of prices to evaluate. If None, defaults to +/- 20% around spot.
    
    Returns:
    --------
    dict with keys:
        'price_range': np.array of underlying prices
        'leg_pnls': list of np.array, PnL for each leg
        'total_pnl': np.array, total strategy PnL
        'legs': original legs configuration
    """
    if price_range is None:
        price_range = np.linspace(spot_price * 0.8, spot_price * 1.2, 200)
    
    leg_pnls = []
    
    for leg in legs:
        leg_type = leg.get('type', 'call').lower()
        action = leg.get('action', 'buy').lower()
        strike = leg.get('strike', spot_price)
        premium = leg.get('premium', 0.0)
        quantity = leg.get('quantity', 1.0)
        
        pnl = np.zeros(len(price_range))
        
        for i, S_T in enumerate(price_range):
            if leg_type == 'call':
                # Call option value at expiry
                intrinsic_value = max(S_T - strike, 0)
                if action == 'buy':
                    pnl[i] = (intrinsic_value - premium) * quantity
                else:  # sell
                    pnl[i] = (premium - intrinsic_value) * quantity
                    
            elif leg_type == 'put':
                # Put option value at expiry
                intrinsic_value = max(strike - S_T, 0)
                if action == 'buy':
                    pnl[i] = (intrinsic_value - premium) * quantity
                else:  # sell
                    pnl[i] = (premium - intrinsic_value) * quantity
                    
            elif leg_type in ['stock', 'futures']:
                # Stock/Futures position
                # Premium here represents entry price
                entry_price = premium if premium > 0 else spot_price
                if action == 'buy':
                    pnl[i] = (S_T - entry_price) * quantity
                else:  # sell/short
                    pnl[i] = (entry_price - S_T) * quantity
        
        leg_pnls.append(pnl)
    
    # Calculate total PnL
    total_pnl = np.sum(leg_pnls, axis=0)
    
    return {
        'price_range': price_range,
        'leg_pnls': leg_pnls,
        'total_pnl': total_pnl,
        'legs': legs
    }


def plot_strategy_payoff(pnl_data, spot_price, symbol="Asset", expiry_date=None, 
                         strike=None, output_html="strategy_payoff.html", 
                         output_png="strategy_payoff.png", strategy_name="Strategy"):
    """
    Plot the payoff diagram for a multi-leg option strategy.
    
    Parameters:
    -----------
    pnl_data : dict
        Output from calculate_strategy_pnl() function
    spot_price : float
        Current spot price
    symbol : str
        Underlying symbol name
    expiry_date : str, optional
        Expiration date string
    strike : float, optional
        Reference strike (for display purposes)
    output_html : str
        Output filename for interactive HTML chart
    output_png : str
        Output filename for static PNG image
    strategy_name : str
        Name of the strategy for the title
    """
    print(f"\n--- Generating Payoff Chart for {strategy_name} ---")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "imgs")
    os.makedirs(output_dir, exist_ok=True)
    output_html_path = os.path.join(output_dir, os.path.basename(output_html))
    output_png_path = os.path.join(output_dir, os.path.basename(output_png))
    
    price_range = pnl_data['price_range']
    leg_pnls = pnl_data['leg_pnls']
    total_pnl = pnl_data['total_pnl']
    legs = pnl_data['legs']
    
    fig = go.Figure()
    
    # Color palette for legs
    colors = ['cyan', 'magenta', 'yellow', 'orange', 'pink', 'lightblue', 'lightgreen']
    dash_styles = ['dash', 'dot', 'dashdot']
    
    # Plot each leg
    for i, (leg, leg_pnl) in enumerate(zip(legs, leg_pnls)):
        leg_type = leg.get('type', 'option').capitalize()
        action = leg.get('action', 'buy').capitalize()
        strike_val = leg.get('strike', 'N/A')
        quantity = leg.get('quantity', 1.0)
        
        # Build legend label
        if leg['type'].lower() in ['call', 'put']:
            label = f"{action} {quantity:.1f}x {leg_type} (K={strike_val})"
        else:
            label = f"{action} {quantity:.2f}x {leg_type}"
        
        color = colors[i % len(colors)]
        dash = dash_styles[i % len(dash_styles)]
        
        fig.add_trace(go.Scatter(
            x=price_range, y=leg_pnl,
            mode='lines', name=label,
            line=dict(color=color, width=1, dash=dash)
        ))
    
    # Plot total PnL
    fig.add_trace(go.Scatter(
        x=price_range, y=total_pnl,
        mode='lines', name=f'Total {strategy_name} P&L',
        line=dict(color='lime', width=3)
    ))
    
    # Build title
    title_parts = [f"{strategy_name} Payoff (Expiry Analysis)<br>"]
    subtitle_parts = [f"Underlying: {symbol}, Spot: {spot_price:.2f}"]
    if strike:
        subtitle_parts.append(f"Strike: {strike}")
    if expiry_date:
        subtitle_parts.append(f"Expiry: {expiry_date}")
    
    title_text = title_parts[0] + f"<sup>{', '.join(subtitle_parts)}</sup>"
    
    # Layout
    fig.update_layout(
        title=title_text,
        xaxis_title="Underlying Price at Expiry (USD)",
        yaxis_title="Profit / Loss (USD)",
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        shapes=[
            # Vertical line at current spot
            dict(
                type="line",
                xref="x", yref="paper",
                x0=spot_price, y0=0, x1=spot_price, y1=1,
                line=dict(color="white", width=1, dash="dashdot"),
            )
        ]
    )
    
    # Add annotation for Spot
    fig.add_annotation(
        x=spot_price, y=min(total_pnl) * 0.1,
        text=f"Spot: {spot_price:.0f}",
        showarrow=False,
        yshift=10
    )
    
    # Save outputs
    print(f"   Saving interactive plot to {output_html_path}...")
    fig.write_html(output_html_path)
    
    # Try creating PNG if kaleido is available
    try:
        fig.write_image(output_png_path)
        print(f"   Saved static image to {output_png_path}")
    except Exception as e:
        print(f"   Warning: Could not save PNG (Kaleido missing?): {e}")
        print(f"   Please open the HTML file for the chart: {output_html_path}")
    
    print(f"   Chart generation complete!\n")


