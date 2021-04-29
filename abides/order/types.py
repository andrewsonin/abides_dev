import sys
from copy import deepcopy
from typing import Optional, Any, Dict

import pandas as pd

from abides.core import Kernel
from abides.order.base import silent_mode, Order
from abides.util import dollarize

__all__ = (
    "MarketOrder",
    "BuyMarket",
    "SellMarket",
    "LimitOrder",
    "Bid",
    "Ask",
    "BasketOrder"
)


class MarketOrder(Order):
    __slots__ = ()

    if silent_mode:
        def __str__(self) -> str:
            return ''
    else:
        def __str__(self) -> str:
            return (
                f"(Agent {self.agent_id} @ {Kernel.fmtTime(self.time_placed)}) : "
                f"MKT Order {'BUY' if self.is_buy_order else 'SELL'} {self.quantity} {self.symbol}"
            )

    __repr__ = __str__

    def __copy__(self) -> 'MarketOrder':
        order = self.__class__(
            self.agent_id,
            self.time_placed,
            self.symbol,
            self.quantity,
            self.order_id,
            self.tag
        )
        order.fill_price = self.fill_price
        return order

    def __deepcopy__(self, memo: Optional[Dict[int, Any]] = None) -> 'MarketOrder':
        order = self.__class__(
            self.agent_id,
            self.time_placed,
            self.symbol,
            self.quantity,
            self.order_id,
            deepcopy(self.tag, memo)
        )
        order.fill_price = self.fill_price
        return order


class BuyMarket(MarketOrder):
    __slots__ = ()
    is_buy_order = True


class SellMarket(MarketOrder):
    __slots__ = ()
    is_buy_order = False


class LimitOrder(Order):
    """
    LimitOrder class, inherits from Order class, adds a limit price.
    These are the Orders that typically go in an Exchange's OrderBook.
    """
    __slots__ = ("limit_price",)

    def __init__(self,
                 agent_id: int,
                 time_placed: pd.Timestamp,
                 symbol: str,
                 *,
                 quantity: int,
                 limit_price: int,
                 order_id: Optional[int] = None,
                 tag: Any = None) -> None:

        super().__init__(agent_id, time_placed, symbol, quantity, order_id, tag)

        # The limit price is the minimum price the agent will accept (for a sell order) or
        # the maximum price the agent will pay (for a buy order).
        self.limit_price = limit_price

    if silent_mode:
        def __str__(self) -> str:
            return ''
    else:
        def __str__(self) -> str:
            tag = self.tag
            tag_info = f" [{tag}]" if tag is not None else ""

            # Until we make explicit market orders, we make a few assumptions that EXTREME prices on limit
            # orders are trying to represent a market order. This only affects printing - they still hit
            # the order book like limit orders, which is wrong.
            limit_price = self.limit_price
            limit_info = dollarize(limit_price) if limit_price < sys.maxsize else 'MKT'

            fill_price = self.fill_price
            filled = f" (filled @ {dollarize(fill_price)})" if fill_price else ""
            return (
                f"(Agent {self.agent_id} @ {Kernel.fmtTime(self.time_placed)}{tag_info}) : "
                f"{'BUY' if self.is_buy_order else 'SELL'} {self.quantity} {self.symbol} @ {limit_info}{filled}"
            )

    __repr__ = __str__

    def __copy__(self) -> 'LimitOrder':
        order = self.__class__(
            self.agent_id,
            self.time_placed,
            self.symbol,
            quantity=self.quantity,
            limit_price=self.limit_price,
            order_id=self.order_id,
            tag=self.tag
        )
        order.fill_price = self.fill_price
        return order

    def __deepcopy__(self, memo: Optional[Dict[int, Any]] = None) -> 'LimitOrder':
        order = self.__class__(
            self.agent_id,
            self.time_placed,
            self.symbol,
            quantity=self.quantity,
            limit_price=self.limit_price,
            order_id=self.order_id,
            tag=deepcopy(self.tag, memo)
        )
        order.fill_price = self.fill_price
        return order

    def isMatch(self, other: 'LimitOrder') -> bool:
        """Returns True if order 'other' can be matched against input 'self'"""

        is_buy_order = self.is_buy_order
        if is_buy_order is other.is_buy_order:
            print(f"WARNING: isMatch() called on limit orders of same type: {self} vs {other}")
            return False

        if is_buy_order:
            return self.limit_price >= other.limit_price
        return self.limit_price <= other.limit_price

    def hasEqPrice(self, other: 'LimitOrder') -> bool:
        return self.limit_price == other.limit_price

    def hasBetterPrice(self, other: 'LimitOrder') -> bool:
        """
        Check if ``other`` order has better price than ``self``.

        >>> f = Ask(1, pd.Timestamp('1970'), 'USD/RUB', quantity=10, limit_price=10)
        >>> s = Ask(1, pd.Timestamp('1970'), 'USD/RUB', quantity=10, limit_price=100)
        >>> f.hasBetterPrice(s)
        True

        >>> f = Bid(1, pd.Timestamp('1970'), 'USD/RUB', quantity=10, limit_price=10)
        >>> s = Bid(1, pd.Timestamp('1970'), 'USD/RUB', quantity=10, limit_price=100)
        >>> f.hasBetterPrice(s)
        False

        >>> f = Bid(1, pd.Timestamp('1970'), 'USD/RUB', quantity=10, limit_price=10)
        >>> s = Bid(1, pd.Timestamp('1970'), 'USD/RUB', quantity=10, limit_price=10)
        >>> f.hasBetterPrice(s)
        False

        >>> f = Ask(1, pd.Timestamp('1970'), 'USD/RUB', quantity=10, limit_price=10)
        >>> s = Bid(1, pd.Timestamp('1970'), 'USD/RUB', quantity=10, limit_price=100)
        >>> f.hasBetterPrice(s)
        WARNING: hasBetterPrice() called on orders of different type: Ask vs Bid
        False

        Args:
            other:  other limit order
        Returns:
            result of price comparison
        """

        self_is_buy = self.is_buy_order
        if self_is_buy is not other.is_buy_order:
            print(
                f"WARNING: hasBetterPrice() called on orders of different type: "
                f"{self.__class__.__name__} vs {other.__class__.__name__}"
            )
            return False

        if self_is_buy:
            return self.limit_price > other.limit_price
        return self.limit_price < other.limit_price


class Bid(LimitOrder):
    __slots__ = ()
    is_buy_order = True


class Ask(LimitOrder):
    __slots__ = ()
    is_buy_order = False


class BasketOrder(Order):
    """
    BasketOrder class, inherits from Order class.  These are the
    Orders that typically go in a Primary Exchange and immediately get filled.
    A buy order translates to a creation order for an ETF share
    A sell order translates to a redemption order for shares of the underlying.
    """
    __slots__ = ("dollar",)

    def __init__(self,
                 agent_id: int,
                 time_placed: pd.Timestamp,
                 symbol: str,
                 quantity: int,
                 dollar: bool = True,
                 order_id: Optional[int] = None) -> None:
        super().__init__(agent_id, time_placed, symbol, quantity, order_id)
        self.dollar = dollar

    if silent_mode:
        def __str__(self) -> str:
            return ""
    else:
        def __str__(self) -> str:
            fill_price = self.fill_price
            if fill_price:
                filled = f" (filled @ {dollarize(fill_price) if self.dollar else fill_price})"
            else:
                filled = ""
            # Until we make explicit market orders, we make a few assumptions that EXTREME prices on limit
            # orders are trying to represent a market order.  This only affects printing - they still hit
            # the order book like limit orders, which is wrong.
            return (
                f"(Order_ID: {self.order_id} Agent {self.agent_id} @ {Kernel.fmtTime(self.time_placed)}) : "
                f"{'CREATE' if self.is_buy_order else 'REDEEM'} {self.quantity} {self.symbol} @ {filled}{fill_price}"
            )

    __repr__ = __str__

    def __copy__(self) -> 'BasketOrder':
        order = self.__class__(
            self.agent_id,
            self.time_placed,
            self.symbol,
            self.quantity,
            self.dollar,
            self.order_id
        )
        order.fill_price = self.fill_price
        return order

    def __deepcopy__(self, memo: Optional[Dict[int, Any]] = None) -> 'BasketOrder':
        return self.__copy__()