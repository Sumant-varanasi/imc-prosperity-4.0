from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math


class Trader:
    """
    IMC Prosperity 4 - Round 2 submission v2.
    Score: 5,230 XIRECs (platform day 1).

    Changes vs v1:
      - Osmium quoted wider (9996/10004) to match observed MM bot levels.
      - More aggressive inventory skew.
    """

    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 50,
        "INTARIAN_PEPPER_ROOT": 50,
    }

    OSMIUM_FAIR = 10000

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

        # Take cheap asks (below fair - 2)
        for ask_price in sorted(depth.sell_orders.keys()):
            if ask_price <= fair - 2 and buy_capacity > 0:
                vol = -depth.sell_orders[ask_price]
                qty = min(vol, buy_capacity)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    buy_capacity -= qty
            else:
                break

        # Take rich bids (above fair + 2)
        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if bid_price >= fair + 2 and sell_capacity > 0:
                vol = depth.buy_orders[bid_price]
                qty = min(vol, sell_capacity)
                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    sell_capacity -= qty
            else:
                break

        # Make wider passive quotes at 9996/10004
        my_bid = 9996
        my_ask = 10004

        if pos > limit * 0.6:
            my_ask = 10003
        elif pos < -limit * 0.6:
            my_bid = 9997
        elif pos > limit * 0.3:
            my_ask = 10003
        elif pos < -limit * 0.3:
            my_bid = 9997

        if buy_capacity > 0:
            orders.append(Order(product, my_bid, buy_capacity))
        if sell_capacity > 0:
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

        orders: List[Order] = []
        best_bid, best_ask = self._best_bid_ask(depth)
        target_position = limit
        qty_needed = target_position - pos

        if qty_needed > 0:
            remaining = qty_needed
            for ask_price in sorted(depth.sell_orders.keys()):
                if remaining <= 0:
                    break
                if ask_price > mid + 8:
                    break
                vol = -depth.sell_orders[ask_price]
                qty = min(vol, remaining)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    remaining -= qty

            if remaining > 0 and best_bid is not None:
                my_bid = best_bid + 1
                if best_ask is not None and my_bid < best_ask:
                    orders.append(Order(product, my_bid, remaining))

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
