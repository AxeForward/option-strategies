"""
Position data models for hedging.

This module is intentionally "input-friendly": you can manually fill in the actual
executed fills + IV + risk-free rate for each option leg, then pass the
position into `hedge/dynamic_hedgeing.py` to compute hedge adjustments later.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


OPTION_TYPES = {"call", "put"}
ACTIONS = {"buy", "sell"}


@dataclass(frozen=True)
class OptionLegPosition:
    """
    One option leg in a multi-leg strategy.

    Notes:
    - `expiry` uses 'YYYY-MM-DD' because QuantLib helper expects that string format.
    - `fill_price` is the actual executed premium (成交价).
    - `iv` is implied volatility as decimal (e.g. 0.55 for 55%).
    - `risk_free_rate` is annualized decimal (e.g. 0.05 for 5%).
    """

    option_type: str  # 'call' / 'put'
    action: str  # 'buy' / 'sell'
    strike: float
    expiry: str  # 'YYYY-MM-DD'
    fill_price: float
    iv: float
    risk_free_rate: float
    quantity: float = 1.0

    def __post_init__(self) -> None:
        ot = self.option_type.lower()
        ac = self.action.lower()
        if ot not in OPTION_TYPES:
            raise ValueError(f"option_type must be one of {sorted(OPTION_TYPES)}; got {self.option_type!r}")
        if ac not in ACTIONS:
            raise ValueError(f"action must be one of {sorted(ACTIONS)}; got {self.action!r}")
        if self.quantity <= 0:
            raise ValueError(f"quantity must be > 0; got {self.quantity!r}")

    @property
    def signed_quantity(self) -> float:
        """Buy is positive exposure, sell is negative exposure."""
        return self.quantity if self.action.lower() == "buy" else -self.quantity


@dataclass(frozen=True)
class PerpFuturesPosition:
    """
    Perpetual futures position used for delta hedging.

    - `quantity` is SIGNED: + means long, - means short.
    - If `quantity == 0`, it can mean "initial delta is near zero" or "exchange
      minimum size prevents opening such a small hedge" (as you described).
    - `entry_price` is optional; useful if you also want PnL attribution later.
    """

    symbol: str  # e.g. "ETH-USD-PERP"
    quantity: float = 0.0
    entry_price: Optional[float] = None


@dataclass(frozen=True)
class IronCondorPosition:
    """
    Actual executed position for a standard Iron Condor:
      long_put (buy) < short_put (sell) < short_call (sell) < long_call (buy)

    This is meant to be the canonical container passed into dynamic hedging logic.
    """

    underlying: str  # e.g. "ETH" / "BTC"
    long_put: OptionLegPosition
    short_put: OptionLegPosition
    short_call: OptionLegPosition
    long_call: OptionLegPosition
    perp_futures: PerpFuturesPosition
    opened_at: Optional[str] = None  # ISO timestamp string, optional
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        # Light validation only (do not over-restrict manual input).
        if self.long_put.option_type.lower() != "put":
            raise ValueError("long_put.option_type must be 'put'")
        if self.short_put.option_type.lower() != "put":
            raise ValueError("short_put.option_type must be 'put'")
        if self.short_call.option_type.lower() != "call":
            raise ValueError("short_call.option_type must be 'call'")
        if self.long_call.option_type.lower() != "call":
            raise ValueError("long_call.option_type must be 'call'")

    @property
    def expiry(self) -> str:
        """
        Convenience expiry (assumes all legs share expiry; if they don't, use leg.expiry).
        """
        return self.short_put.expiry


def example_manual_iron_condor_template() -> IronCondorPosition:
    """
    Minimal template you can copy/paste and fill with real trades.

    For leg direction/order, see `static_strategy_examples.py` -> `example_iron_condor()`.
    """
    expiry = "2026-02-13"
    rf = 0.05

    return IronCondorPosition(
        underlying="ETH",
        long_put=OptionLegPosition(
            option_type="put",
            action="buy",
            strike=0.0,
            expiry=expiry,
            fill_price=0.0,
            iv=0.0,
            risk_free_rate=rf,
            quantity=1.0,
        ),
        short_put=OptionLegPosition(
            option_type="put",
            action="sell",
            strike=0.0,
            expiry=expiry,
            fill_price=0.0,
            iv=0.0,
            risk_free_rate=rf,
            quantity=1.0,
        ),
        short_call=OptionLegPosition(
            option_type="call",
            action="sell",
            strike=0.0,
            expiry=expiry,
            fill_price=0.0,
            iv=0.0,
            risk_free_rate=rf,
            quantity=1.0,
        ),
        long_call=OptionLegPosition(
            option_type="call",
            action="buy",
            strike=0.0,
            expiry=expiry,
            fill_price=0.0,
            iv=0.0,
            risk_free_rate=rf,
            quantity=1.0,
        ),
        perp_futures=PerpFuturesPosition(symbol="ETH-USD-PERP", quantity=0.0, entry_price=None),
        opened_at=None,
        notes="Set perp_futures.quantity=0 if initial hedge is too small / not opened.",
    )
