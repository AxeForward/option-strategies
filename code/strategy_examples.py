import numpy as np
import sys
import os

sys.path.append(os.getcwd())
from code.strategy_evaluation import calculate_strategy_pnl, plot_strategy_payoff

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
