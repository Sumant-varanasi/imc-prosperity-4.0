from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math


class Trader:
    """
    IMC Prosperity 4 - Round 2 submission v1.
    Initial version - score: 4,901 XIRECs.

    Products (based on data analysis of prices_round_2_day_-1/0/1):
      - ASH_COATED_OSMIUM    : Mean-reverts around fair value 10,000.
                               Spread ~16, std ~5. Classic market-make target.
      - INTARIAN_PEPPER_ROOT : STRONG UPWARD TREND (+1,000 XIRECs per day).
                               Strategy: stay long at max position size.

    Strategy:
      Osmium:  Take anything below 9999 (buy) or above 10001 (sell),
               then quote +/-2 around 10000.
      Pepper:  Buy aggressively. Hold max long position.
    """

    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 50,
        "INTARIAN_PEPPER_ROOT": 50,
    }

    OSMIUM_FAIR = 10000
    PEPPER_DRIFT_PER_TICK = 0.10

    def _best_bid_ask(self, depth: OrderDepth):
        best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
        best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
        return best_bid, best_ask

    def _mid(self, depth: OrderDepth):
        b, a = self._best_bid_ask(depth)
        if b is None or a is None:
            return None
        return (a + b) / 2.0

    def _load_memory(self, state: TradingState):
        if state.traderData and state.traderData != "":
            try:
                return json.loads(state.traderData)
            except Exception:
                return {}
        return {}

    def _trade_osmium(self, state: TradingState, memory: dict) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        depth = state.order_depths.get(product)
        if not depth:
            return []

        pos = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        fair = self.OSMIUM_FAIR

        orders: List[Order] = []
        buy_capacity = limit - pos
        sell_capacity = limit + pos

        # Take mispriced asks
        for ask_price in sorted(depth.sell_orders.keys()):
            if ask_price <= fair - 1 and buy_capacity > 0:
                vol = -depth.sell_orders[ask_price]
                qty = min(vol, buy_capacity)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    buy_capacity -= qty
            else:
                break

        # Take mispriced bids
        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if bid_price >= fair + 1 and sell_capacity > 0:
                vol = depth.buy_orders[bid_price]
                qty = min(vol, sell_capacity)
                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    sell_capacity -= qty
            else:
                break

        # Make passive quotes at +/- 2
        best_bid, best_ask = self._best_bid_ask(depth)
        my_bid = fair - 2
        if best_bid is not None and best_bid + 1 <= fair - 1:
            my_bid = max(my_bid, best_bid + 1)
        my_ask = fair + 2
        if best_ask is not None and best_ask - 1 >= fair + 1:
            my_ask = min(my_ask, best_ask - 1)

        if pos > limit * 0.5:
            my_ask = max(fair + 1, my_ask - 1)
        elif pos < -limit * 0.5:
            my_bid = min(fair - 1, my_bid + 1)

        if buy_capacity > 0 and my_bid < fair:
            orders.append(Order(product, my_bid, buy_capacity))
        if sell_capacity > 0 and my_ask > fair:
            orders.append(Order(product, my_ask, -sell_capacity))

        return orders

    def _trade_pepper(self, state: TradingState, memory: dict) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        depth = state.order_depths.get(product)
        if not depth:
            return []

        pos = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]

        mid = self._mid(depth)
        if mid is None:
            return []

        ema = memory.get("pepper_ema", mid)
        alpha = 0.05
        ema = alpha * mid + (1 - alpha) * ema
        memory["pepper_ema"] = ema

        orders: List[Order] = []
        best_bid, best_ask = self._best_bid_ask(depth)

        target_position = limit
        qty_needed = target_position - pos

        if qty_needed > 0 and best_ask is not None:
            remaining = qty_needed
            for ask_price in sorted(depth.sell_orders.keys()):
                if remaining <= 0:
                    break
                if ask_price > mid + 5:
                    break
                vol = -depth.sell_orders[ask_price]
                qty = min(vol, remaining)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    remaining -= qty

            if remaining > 0 and best_bid is not None:
                my_bid = best_bid + 1
                if my_bid < (best_ask if best_ask else mid):
                    orders.append(Order(product, my_bid, remaining))

        if pos > 0 and mid > ema + 8 and best_bid is not None:
            shave_qty = min(pos // 4, depth.buy_orders[best_bid])
            if shave_qty > 0:
                orders.append(Order(product, best_bid, -shave_qty))

        return orders

    def run(self, state: TradingState):
        memory = self._load_memory(state)
        result: Dict[str, List[Order]] = {}

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self._trade_osmium(state, memory)
        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"] = self._trade_pepper(state, memory)

        conversions = 0
        trader_data = json.dumps(memory)
        return result, conversions, trader_data
