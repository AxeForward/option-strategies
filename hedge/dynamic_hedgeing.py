"""Dynamic delta-hedging monitor.

This module monitors a multi-leg option position (currently Iron Condor container)
and suggests perpetual-futures hedge adjustments whenever net portfolio delta
changes beyond a configured threshold.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import pandas as pd

from hedge.positions import IronCondorPosition, OptionLegPosition
from src.fetch_market_data import get_fred_risk_free_rate
from src.get_asset_option_t_quote import get_option_quotes


@dataclass
class MonitorConfig:
    """Runtime configuration for dynamic hedge monitoring."""

    interval_seconds: int = 3600
    delta_change_threshold: float = 0.20
    fred_series_id: str = "DGS3MO"
    rf_lookback_days: int = 14
    # Useful for demo/testing; None means run forever.
    max_cycles: Optional[int] = None
    # If True, once rebalance is triggered, update local perp qty to target.
    assume_rebalance_executed: bool = True


def _safe_float(x: object) -> Optional[float]:
    try:
        val = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(val):
        return None
    return val


def _find_leg_delta(chain: pd.DataFrame, leg: OptionLegPosition) -> float:
    """Find a single leg delta from option chain by strike and option type."""
    if chain.empty:
        raise ValueError("option chain is empty")

    strike_matches = chain[chain["Strike"].astype(float) == float(leg.strike)]
    if strike_matches.empty:
        # Tolerate tiny float mismatch by nearest strike within 1e-8 relative scale.
        tol = max(abs(float(leg.strike)) * 1e-8, 1e-8)
        strike_matches = chain[(chain["Strike"].astype(float) - float(leg.strike)).abs() <= tol]

    if strike_matches.empty:
        raise ValueError(f"No quote found for strike={leg.strike}, expiry={leg.expiry}, type={leg.option_type}")

    row = strike_matches.iloc[0]
    delta_col = "C_Delta" if leg.option_type.lower() == "call" else "P_Delta"
    delta_val = _safe_float(row.get(delta_col))
    if delta_val is None:
        raise ValueError(
            f"Delta missing for strike={leg.strike}, expiry={leg.expiry}, col={delta_col}"
        )

    return delta_val


def _portfolio_option_delta(position: IronCondorPosition) -> Tuple[float, Dict[str, float], str]:
    """Fetch latest option deltas and compute signed net option delta."""
    symbol = f"{position.underlying.upper()}USDT"
    expiry = position.expiry

    data_by_expiry = get_option_quotes(symbol, expiry)
    if not data_by_expiry or expiry not in data_by_expiry:
        raise RuntimeError(f"Failed to fetch option quotes for {symbol} expiry={expiry}")

    chain = data_by_expiry[expiry]

    legs = {
        "long_put": position.long_put,
        "short_put": position.short_put,
        "short_call": position.short_call,
        "long_call": position.long_call,
    }

    leg_deltas: Dict[str, float] = {}
    net_delta = 0.0

    for name, leg in legs.items():
        raw_delta = _find_leg_delta(chain, leg)
        signed_delta = raw_delta * leg.signed_quantity
        leg_deltas[name] = signed_delta
        net_delta += signed_delta

    return net_delta, leg_deltas, expiry


def _latest_risk_free_rate(cfg: MonitorConfig) -> Optional[Tuple[datetime, float]]:
    """Fetch latest available FRED risk-free rate (decimal form)."""
    end_dt = datetime.utcnow().date()
    start_dt = end_dt - timedelta(days=cfg.rf_lookback_days)

    rf_df = get_fred_risk_free_rate(
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        series_id=cfg.fred_series_id,
    )
    if rf_df is None or rf_df.empty:
        return None

    # index is DatetimeIndex per existing implementation
    latest_ts = rf_df.index.max()
    latest_rate_pct = _safe_float(rf_df.loc[latest_ts, "rate"])
    if latest_rate_pct is None:
        return None

    return latest_ts.to_pydatetime(), latest_rate_pct / 100.0


def _calc_change_ratio(current: float, reference: float) -> float:
    if abs(reference) < 1e-12:
        return math.inf if abs(current) > 1e-12 else 0.0
    return abs(current - reference) / abs(reference)


def run_delta_hedge_monitor(position: IronCondorPosition, cfg: Optional[MonitorConfig] = None) -> None:
    """
    Dynamic delta monitor:
    1) Every interval, refresh option deltas and risk-free rate.
    2) Recompute net portfolio delta.
    3) If delta change ratio exceeds threshold, output perpetual futures rebalance size.

    Notes:
    - Delta change is measured against previous cycle.
    - Perp target qty = -net_option_delta.
    - Rebalance qty = target_perp_qty - current_perp_qty.
    """
    cfg = cfg or MonitorConfig()

    current_perp_qty = float(position.perp_futures.quantity)
    prev_option_delta: Optional[float] = None
    cycle = 0

    print("=" * 88)
    print("Dynamic Delta Hedge Monitor")
    print("=" * 88)
    print(f"Underlying: {position.underlying.upper()} | Expiry: {position.expiry}")
    print(f"Perp symbol: {position.perp_futures.symbol} | Initial perp qty: {current_perp_qty:.6f}")
    print(
        f"Interval: {cfg.interval_seconds}s | Threshold: {cfg.delta_change_threshold:.1%} | "
        f"FRED series: {cfg.fred_series_id}"
    )

    while True:
        cycle += 1
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        try:
            option_delta, leg_breakdown, used_expiry = _portfolio_option_delta(position)
        except Exception as exc:
            print(f"[{now}] Cycle {cycle}: failed to refresh option deltas: {exc}")
            if cfg.max_cycles is not None and cycle >= cfg.max_cycles:
                break
            time.sleep(cfg.interval_seconds)
            continue

        rf_info = _latest_risk_free_rate(cfg)
        if rf_info is None:
            rf_str = "N/A"
        else:
            rf_dt, rf_rate = rf_info
            rf_str = f"{rf_rate:.4%} (as of {rf_dt.date().isoformat()})"

        portfolio_delta = option_delta + current_perp_qty

        print("-" * 88)
        print(f"[{now}] Cycle {cycle} | Expiry={used_expiry} | RF={rf_str}")
        print(
            "Leg signed deltas | "
            f"LP={leg_breakdown['long_put']:.6f}, "
            f"SP={leg_breakdown['short_put']:.6f}, "
            f"SC={leg_breakdown['short_call']:.6f}, "
            f"LC={leg_breakdown['long_call']:.6f}"
        )
        print(
            f"Net option delta={option_delta:.6f}, current perp qty={current_perp_qty:.6f}, "
            f"portfolio delta={portfolio_delta:.6f}"
        )

        if prev_option_delta is None:
            print("Baseline initialized; waiting next cycle for delta change comparison.")
            prev_option_delta = option_delta
        else:
            change_ratio = _calc_change_ratio(option_delta, prev_option_delta)
            print(f"Delta change vs previous cycle: {change_ratio:.2%}")

            if change_ratio > cfg.delta_change_threshold:
                target_perp_qty = -option_delta
                rebalance_qty = target_perp_qty - current_perp_qty
                action = "BUY" if rebalance_qty > 0 else "SELL"

                print("ALERT: Delta change exceeded threshold.")
                print(
                    f"Suggested perp rebalance: {action} {abs(rebalance_qty):.6f} "
                    f"{position.perp_futures.symbol}"
                )
                print(
                    f"Post-trade target perp qty={target_perp_qty:.6f}, "
                    f"target portfolio delta¡Ö0.000000"
                )

                if cfg.assume_rebalance_executed:
                    current_perp_qty = target_perp_qty
                    print("Assumption applied: rebalance executed, local perp qty updated.")

            prev_option_delta = option_delta

        if cfg.max_cycles is not None and cycle >= cfg.max_cycles:
            print("Reached max_cycles; monitor stopped.")
            break

        time.sleep(cfg.interval_seconds)


def demo_run() -> None:
    """Small runnable example with placeholder strikes/IV; replace with real position."""
    from hedge.positions import example_manual_iron_condor_template

    pos = example_manual_iron_condor_template()
    cfg = MonitorConfig(interval_seconds=3600, delta_change_threshold=0.20)
    run_delta_hedge_monitor(pos, cfg)


if __name__ == "__main__":
    demo_run()
