from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math


class Trader:
    """
    IMC Prosperity 4 - Round 2 submission v3.
    Platform score: 5,072. Best in cross-day backtest (avg 55,333).

    Changes vs v2:
      - Take at fair +/-1 instead of +/-2 (every mispricing is pure edge).
      - LAYERED quotes: tight layer (9999/10001) + wide layer (9997/10003).
      - Tighter inventory skew kicks in at +/-15 instead of +/-25.
      - Pepper unchanged (already optimal at +50 max long).
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

        # Take anything mispriced (below fair for buy, above fair for sell)
        for ask_price in sorted(depth.sell_orders.keys()):
            if ask_price < fair and buy_capacity > 0:
                vol = -depth.sell_orders[ask_price]
                qty = min(vol, buy_capacity)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    buy_capacity -= qty
            else:
                break

        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if bid_price > fair and sell_capacity > 0:
                vol = depth.buy_orders[bid_price]
                qty = min(vol, sell_capacity)
                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    sell_capacity -= qty
            else:
                break

        # Layered quotes
        tight_buy = min(buy_capacity, 30)
        tight_sell = min(sell_capacity, 30)

        tight_bid_px = 9999
        tight_ask_px = 10001
        wide_bid_px = 9997
        wide_ask_px = 10003

        if pos > 25:
            tight_bid_px = 9998
            tight_buy = min(buy_capacity, 15)
            tight_sell = min(sell_capacity, 35)
        elif pos < -25:
            tight_ask_px = 10002
            tight_buy = min(buy_capacity, 35)
            tight_sell = min(sell_capacity, 15)
        elif pos > 15:
            tight_buy = min(buy_capacity, 20)
            tight_sell = min(sell_capacity, 30)
        elif pos < -15:
            tight_buy = min(buy_capacity, 30)
            tight_sell = min(sell_capacity, 20)

        wide_buy = max(0, buy_capacity - tight_buy)
        wide_sell = max(0, sell_capacity - tight_sell)

        if tight_buy > 0:
            orders.append(Order(product, tight_bid_px, tight_buy))
        if tight_sell > 0:
            orders.append(Order(product, tight_ask_px, -tight_sell))
        if wide_buy > 0:
            orders.append(Order(product, wide_bid_px, wide_buy))
        if wide_sell > 0:
            orders.append(Order(product, wide_ask_px, -wide_sell))

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
