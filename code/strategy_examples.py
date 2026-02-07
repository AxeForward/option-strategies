"""
Example: Using the modular PnL calculation and plotting functions
to evaluate different option strategies with various numbers of legs.
"""

import numpy as np
import sys
import os

sys.path.append(os.getcwd())
from code.strategy_evaluation import calculate_strategy_pnl, plot_strategy_payoff


def example_butterfly_spread():
    """
    Example: Butterfly Spread Strategy (4 legs)
    - Buy 1 Call at lower strike
    - Sell 2 Calls at middle strike
    - Buy 1 Call at higher strike
    """
    print("\n" + "="*60)
    print("Example 1: Long Call Butterfly Spread")
    print("="*60)
    
    S0 = 3000  # Current spot price
    K1 = 2900  # Lower strike
    K2 = 3000  # Middle strike (ATM)
    K3 = 3100  # Higher strike
    
    legs = [
        {'type': 'call', 'action': 'buy', 'strike': K1, 'premium': 150, 'quantity': 1.0},
        {'type': 'call', 'action': 'sell', 'strike': K2, 'premium': 100, 'quantity': 2.0},
        {'type': 'call', 'action': 'buy', 'strike': K3, 'premium': 60, 'quantity': 1.0},
    ]
    
    # Calculate PnL
    pnl_data = calculate_strategy_pnl(legs, S0)
    
    # Plot
    plot_strategy_payoff(
        pnl_data=pnl_data,
        spot_price=S0,
        symbol="ETH",
        strike=K2,
        output_html="butterfly_spread_payoff.html",
        output_png="butterfly_spread_payoff.png",
        strategy_name="Long Call Butterfly"
    )


def example_iron_condor():
    """
    Example: Iron Condor Strategy (4 legs)
    - Sell 1 Put at K1 (OTM)
    - Buy 1 Put at K2 (further OTM)
    - Sell 1 Call at K3 (OTM)
    - Buy 1 Call at K4 (further OTM)
    """
    print("\n" + "="*60)
    print("Example 2: Iron Condor")
    print("="*60)
    
    S0 = 3000
    K1 = 2800  # Sell Put
    K2 = 2700  # Buy Put
    K3 = 3200  # Sell Call
    K4 = 3300  # Buy Call
    
    legs = [
        {'type': 'put', 'action': 'buy', 'strike': K2, 'premium': 30, 'quantity': 1.0},
        {'type': 'put', 'action': 'sell', 'strike': K1, 'premium': 50, 'quantity': 1.0},
        {'type': 'call', 'action': 'sell', 'strike': K3, 'premium': 50, 'quantity': 1.0},
        {'type': 'call', 'action': 'buy', 'strike': K4, 'premium': 30, 'quantity': 1.0},
    ]
    
    pnl_data = calculate_strategy_pnl(legs, S0)
    
    plot_strategy_payoff(
        pnl_data=pnl_data,
        spot_price=S0,
        symbol="ETH",
        output_html="iron_condor_payoff.html",
        output_png="iron_condor_payoff.png",
        strategy_name="Iron Condor"
    )


def example_custom_strategy():
    """
    Example: Custom Strategy with 6 legs
    - Multiple options at different strikes
    - Plus a futures hedge
    """
    print("\n" + "="*60)
    print("Example 3: Custom 6-Leg Strategy")
    print("="*60)
    
    S0 = 3000
    
    legs = [
        {'type': 'call', 'action': 'buy', 'strike': 2900, 'premium': 150, 'quantity': 2.0},
        {'type': 'call', 'action': 'sell', 'strike': 3000, 'premium': 100, 'quantity': 3.0},
        {'type': 'call', 'action': 'buy', 'strike': 3100, 'premium': 60, 'quantity': 1.0},
        {'type': 'put', 'action': 'buy', 'strike': 2950, 'premium': 80, 'quantity': 1.0},
        {'type': 'put', 'action': 'sell', 'strike': 2850, 'premium': 40, 'quantity': 2.0},
        {'type': 'futures', 'action': 'sell', 'premium': S0, 'quantity': 0.5},
    ]
    
    pnl_data = calculate_strategy_pnl(legs, S0)
    
    plot_strategy_payoff(
        pnl_data=pnl_data,
        spot_price=S0,
        symbol="ETH",
        output_html="custom_strategy_payoff.html",
        output_png="custom_strategy_payoff.png",
        strategy_name="Custom Multi-Leg Strategy"
    )


def example_ratio_spread():
    """
    Example: Ratio Spread (3 legs with different quantities)
    - Buy 1 Call at lower strike
    - Sell 3 Calls at higher strike
    """
    print("\n" + "="*60)
    print("Example 4: Call Ratio Spread")
    print("="*60)
    
    S0 = 3000
    K1 = 2950
    K2 = 3050
    
    legs = [
        {'type': 'call', 'action': 'buy', 'strike': K1, 'premium': 120, 'quantity': 1.0},
        {'type': 'call', 'action': 'sell', 'strike': K2, 'premium': 70, 'quantity': 3.0},
    ]
    
    pnl_data = calculate_strategy_pnl(legs, S0)
    
    plot_strategy_payoff(
        pnl_data=pnl_data,
        spot_price=S0,
        symbol="ETH",
        strike=K1,
        output_html="ratio_spread_payoff.html",
        output_png="ratio_spread_payoff.png",
        strategy_name="Call Ratio Spread"
    )


if __name__ == "__main__":
    # Run all examples
    print("\n" + "="*60)
    print("Running Strategy Examples")
    print("="*60)
    
    # Uncomment the strategies you want to test:
    
    example_butterfly_spread()
    # example_iron_condor()
    # example_custom_strategy()
    # example_ratio_spread()
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60)
