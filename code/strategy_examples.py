import numpy as np
import sys
import os

sys.path.append(os.getcwd())

from strategy_evaluation import calculate_strategy_pnl, plot_strategy_payoff
from get_asset_option_t_quote import get_option_quotes
from fetch_market_data import get_paradex_futures_data


def _choose_by_target_delta(df, option_prefix, target_abs_delta):
    """Select strike row whose absolute delta is closest to target_abs_delta."""
    delta_col = f"{option_prefix}_Delta"
    working = df[["Strike", delta_col, f"{option_prefix}_Bid", f"{option_prefix}_Ask"]].copy()
    working = working.dropna(subset=[delta_col, f"{option_prefix}_Bid", f"{option_prefix}_Ask"])

    if working.empty:
        return None

    working["abs_delta_diff"] = (working[delta_col].abs() - target_abs_delta).abs()
    return working.sort_values("abs_delta_diff").iloc[0]


def example_iron_condor(symbol="ETH", expiry_date=None):
    """
    基于实时市场数据构建 Iron Condor，并用 Paradex 进行 Delta 对冲后 PnL 评估。

    Args:
        symbol: 资产符号，例如 "ETH" 或 "BTC"
        expiry_date: 到期日，格式 "YYYY-MM-DD"。为空时自动选择可用到期日中的第一个。
    """
    print("\n" + "=" * 80)
    print("Example: Iron Condor (Live Quotes + Delta Hedge)")
    print("=" * 80)

    options_symbol = f"{symbol.upper()}USDT"
    futures_symbol = f"{symbol.upper()}-USD-PERP"

    # 1) 获取 Paradex 永续实时价格（用于 spot 和对冲）
    futures_data = get_paradex_futures_data(futures_symbol)
    if not futures_data:
        print(f"Error: failed to fetch Paradex futures data for {futures_symbol}")
        return

    spot = futures_data["mid_price"]
    print(f"Paradex {futures_symbol} mid: {spot:.2f}")

    # 2) 获取 Binance 期权链（包含 delta、bid/ask）
    option_data_by_expiry = get_option_quotes(options_symbol, expiry_date)
    if not option_data_by_expiry:
        print(f"Error: failed to fetch option quotes for {options_symbol}")
        return

    chosen_expiry = sorted(option_data_by_expiry.keys())[0]
    chain = option_data_by_expiry[chosen_expiry].copy()

    print(f"Using expiry: {chosen_expiry}, contracts: {len(chain)}")

    # 目标 Delta
    short_target = 0.20
    wing_target = 0.05

    # 3) 选择各腿：
    # - Short Call abs(delta) ~= 0.20
    # - Long  Call abs(delta) ~= 0.05
    # - Short Put  abs(delta) ~= 0.20
    # - Long  Put  abs(delta) ~= 0.05
    short_call = _choose_by_target_delta(chain, "C", short_target)
    long_call = _choose_by_target_delta(chain, "C", wing_target)
    short_put = _choose_by_target_delta(chain, "P", short_target)
    long_put = _choose_by_target_delta(chain, "P", wing_target)

    legs_data = [short_call, long_call, short_put, long_put]
    if any(x is None for x in legs_data):
        print("Error: insufficient valid option data to build iron condor legs.")
        return

    # 基本结构修正：Call wing 在更高执行价；Put wing 在更低执行价
    if long_call["Strike"] <= short_call["Strike"]:
        higher_calls = chain[chain["Strike"] > short_call["Strike"]].copy()
        if not higher_calls.empty:
            long_call = _choose_by_target_delta(higher_calls, "C", wing_target)

    if long_put["Strike"] >= short_put["Strike"]:
        lower_puts = chain[chain["Strike"] < short_put["Strike"]].copy()
        if not lower_puts.empty:
            long_put = _choose_by_target_delta(lower_puts, "P", wing_target)

    # 4) 用 bid/ask 估算成交：卖出按 bid，买入按 ask
    sc_strike, sc_bid = float(short_call["Strike"]), float(short_call["C_Bid"])
    lc_strike, lc_ask = float(long_call["Strike"]), float(long_call["C_Ask"])
    sp_strike, sp_bid = float(short_put["Strike"]), float(short_put["P_Bid"])
    lp_strike, lp_ask = float(long_put["Strike"]), float(long_put["P_Ask"])

    sc_delta = float(short_call["C_Delta"])
    lc_delta = float(long_call["C_Delta"])
    sp_delta = float(short_put["P_Delta"])
    lp_delta = float(long_put["P_Delta"])

    option_legs = [
        {"type": "put", "action": "buy", "strike": lp_strike, "premium": lp_ask, "quantity": 1.0},
        {"type": "put", "action": "sell", "strike": sp_strike, "premium": sp_bid, "quantity": 1.0},
        {"type": "call", "action": "sell", "strike": sc_strike, "premium": sc_bid, "quantity": 1.0},
        {"type": "call", "action": "buy", "strike": lc_strike, "premium": lc_ask, "quantity": 1.0},
    ]

    # 5) 计算组合净 Delta，并加入永续对冲腿
    # 方向：buy +delta, sell -delta
    net_option_delta = (+lp_delta) + (-sp_delta) + (-sc_delta) + (+lc_delta)
    hedge_qty = -net_option_delta

    hedge_action = "buy" if hedge_qty >= 0 else "sell"
    hedge_leg = {
        "type": "futures",
        "action": hedge_action,
        "premium": spot,
        "quantity": abs(hedge_qty),
    }

    legs = option_legs + [hedge_leg]

    print("\nSelected legs:")
    print(f"  Short Put : K={sp_strike:.0f}, delta={sp_delta:.4f}, bid={sp_bid:.4f}")
    print(f"  Long  Put : K={lp_strike:.0f}, delta={lp_delta:.4f}, ask={lp_ask:.4f}")
    print(f"  Short Call: K={sc_strike:.0f}, delta={sc_delta:.4f}, bid={sc_bid:.4f}")
    print(f"  Long  Call: K={lc_strike:.0f}, delta={lc_delta:.4f}, ask={lc_ask:.4f}")
    print(f"Net option delta: {net_option_delta:.4f}")
    print(f"Hedge leg: {hedge_action} {abs(hedge_qty):.4f} {futures_symbol} @ {spot:.2f}")

    # 6) PnL 评估（包含 Delta 对冲腿）
    price_range = np.linspace(spot * 0.7, spot * 1.3, 300)
    pnl_data = calculate_strategy_pnl(legs, spot_price=spot, price_range=price_range)

    plot_strategy_payoff(
        pnl_data=pnl_data,
        spot_price=spot,
        symbol=symbol.upper(),
        expiry_date=chosen_expiry,
        output_html="iron_condor_delta_hedged_payoff.html",
        output_png="iron_condor_delta_hedged_payoff.png",
        strategy_name="Iron Condor (Delta Hedged via Paradex)"
    )


if __name__ == "__main__":
    # 示例：请按需修改 symbol/expiry_date
    # 例如：example_iron_condor("ETH", "2026-03-27")
    example_iron_condor("ETH", "2026-02-13")
