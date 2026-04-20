"""
Local backtester for IMC Prosperity 4 Round 2 algorithms.

Runs a Trader class against the historical CSV data for one or all days.
Useful for cross-day validation to avoid overfitting to a single day.

Usage:
    python backtest_r2.py <path_to_trader.py> [day]
    day = -1, 0, 1, or 'all' (default: all)

Examples:
    python backtest_r2.py trader_round2_v3.py
    python backtest_r2.py trader_round2_v3.py 1

IMPORTANT: This backtester is approximate - it assumes we can take any
resting liquidity, so PnL numbers are inflated compared to the real
platform. Use it for COMPARING versions, not for absolute PnL estimates.

Requires: the 3 price CSVs (prices_round_2_day_-1.csv, _0.csv, _1.csv)
to be in the same directory as this script.
"""

import sys
import json
import csv
import importlib.util
from collections import defaultdict


# ---------------------------------------------------------------------------
# Minimal datamodel shim (matches IMC's interface)
# ---------------------------------------------------------------------------

class OrderDepth:
    def __init__(self):
        self.buy_orders = {}   # price -> volume (positive)
        self.sell_orders = {}  # price -> volume (negative, per IMC convention)


class Order:
    def __init__(self, symbol, price, quantity):
        self.symbol = symbol
        self.price = int(price)
        self.quantity = int(quantity)

    def __repr__(self):
        return f"Order({self.symbol}, p={self.price}, q={self.quantity})"


class TradingState:
    def __init__(self, timestamp, order_depths, position, traderData=""):
        self.timestamp = timestamp
        self.order_depths = order_depths
        self.position = position
        self.own_trades = {}
        self.market_trades = {}
        self.observations = {}
        self.traderData = traderData
        self.listings = {}


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

POSITION_LIMITS = {
    "ASH_COATED_OSMIUM": 50,
    "INTARIAN_PEPPER_ROOT": 50,
}


def load_prices(csv_path):
    """Return dict of {timestamp: {product: OrderDepth}}."""
    snapshots = defaultdict(dict)
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            ts = int(row['timestamp'])
            product = row['product']
            depth = OrderDepth()
            for i in (1, 2, 3):
                bp = row.get(f'bid_price_{i}', '')
                bv = row.get(f'bid_volume_{i}', '')
                if bp and bv:
                    depth.buy_orders[int(float(bp))] = int(float(bv))
                ap = row.get(f'ask_price_{i}', '')
                av = row.get(f'ask_volume_{i}', '')
                if ap and av:
                    depth.sell_orders[int(float(ap))] = -int(float(av))
            snapshots[ts][product] = depth
    return snapshots


def simulate_fill(order, depth, pos, limit, cash):
    """
    Approximate fill simulation against a static order book.
    Returns (filled_qty, cash_delta, pos_delta).

    Simplifications (vs real platform):
      - Assumes we can sweep any resting liquidity (no queue priority).
      - No latency or partial fills.
      - Result: optimistic PnL vs platform, but useful for RELATIVE comparison.
    """
    filled = 0
    cash_delta = 0
    pos_delta = 0

    if order.quantity > 0:  # BUY
        capacity = limit - pos
        if capacity <= 0:
            return 0, 0, 0
        want = min(order.quantity, capacity)
        for ask_px in sorted(depth.sell_orders.keys()):
            if ask_px > order.price:
                break
            avail = -depth.sell_orders[ask_px]
            take = min(want - filled, avail)
            if take <= 0:
                continue
            filled += take
            cash_delta -= take * ask_px
            pos_delta += take
            if filled >= want:
                break
    else:  # SELL
        capacity = limit + pos
        if capacity <= 0:
            return 0, 0, 0
        want = min(-order.quantity, capacity)
        for bid_px in sorted(depth.buy_orders.keys(), reverse=True):
            if bid_px < order.price:
                break
            avail = depth.buy_orders[bid_px]
            take = min(want - filled, avail)
            if take <= 0:
                continue
            filled += take
            cash_delta += take * bid_px
            pos_delta -= take
            if filled >= want:
                break

    return filled, cash_delta, pos_delta


def run_backtest(trader_class, day):
    prices_path = f'prices_round_2_day_{day}.csv'
    snapshots = load_prices(prices_path)
    timestamps = sorted(snapshots.keys())

    trader = trader_class()
    position = defaultdict(int)
    cash = 0.0
    trader_data = ""

    product_stats = defaultdict(lambda: {'trades': 0, 'buy_qty': 0, 'sell_qty': 0})

    for ts in timestamps:
        state = TradingState(
            timestamp=ts,
            order_depths=snapshots[ts],
            position=dict(position),
            traderData=trader_data,
        )
        try:
            result, conversions, trader_data = trader.run(state)
        except Exception as e:
            print(f"ERROR at ts={ts}: {e}")
            break

        if not result:
            continue

        for product, orders in result.items():
            if product not in snapshots[ts]:
                continue
            depth = snapshots[ts][product]
            limit = POSITION_LIMITS.get(product, 50)
            for order in orders:
                filled, cd, pd = simulate_fill(order, depth, position[product], limit, cash)
                if filled > 0:
                    cash += cd
                    position[product] += pd
                    product_stats[product]['trades'] += 1
                    if pd > 0:
                        product_stats[product]['buy_qty'] += pd
                    else:
                        product_stats[product]['sell_qty'] += -pd

    # Mark-to-market final positions
    last_ts = timestamps[-1]
    final_pnl = cash
    per_product_pnl = {}
    for product, pos in position.items():
        depth = snapshots[last_ts].get(product)
        if depth and depth.buy_orders and depth.sell_orders:
            mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
            mtm = pos * mid
            final_pnl += mtm
            per_product_pnl[product] = mtm

    return final_pnl, per_product_pnl, dict(position), product_stats


def load_trader(path):
    """Load a Trader class from a given .py file, stubbing out datamodel."""
    spec = importlib.util.spec_from_file_location("trader_mod", path)
    mod = importlib.util.module_from_spec(spec)

    # Stub datamodel module so the trader can import from it
    dm = type(sys)('datamodel')
    dm.OrderDepth = OrderDepth
    dm.Order = Order
    dm.TradingState = TradingState
    dm.Trade = type('Trade', (), {})
    dm.Listing = type('Listing', (), {})
    dm.ProsperityEncoder = json.JSONEncoder
    sys.modules['datamodel'] = dm

    spec.loader.exec_module(mod)
    return mod.Trader


def main():
    if len(sys.argv) < 2:
        print("Usage: python backtest_r2.py <trader.py> [day]")
        print("  day = -1, 0, 1, or 'all' (default: all)")
        return

    trader_path = sys.argv[1]
    day_arg = sys.argv[2] if len(sys.argv) > 2 else 'all'

    TraderCls = load_trader(trader_path)

    days = [-1, 0, 1] if day_arg == 'all' else [int(day_arg)]

    total = 0
    for day in days:
        pnl, per_product, final_pos, stats = run_backtest(TraderCls, day)
        total += pnl
        print(f"\n=== Day {day} ===")
        print(f"  Total PnL: {pnl:.2f}")
        for p in ('ASH_COATED_OSMIUM', 'INTARIAN_PEPPER_ROOT'):
            s = stats.get(p, {})
            print(f"  {p}:")
            print(f"    Trades: {s.get('trades', 0)}, bought {s.get('buy_qty', 0)}, sold {s.get('sell_qty', 0)}")
            print(f"    Final pos: {final_pos.get(p, 0)}")
            print(f"    MTM pnl:   {per_product.get(p, 0):.2f}")

    if len(days) > 1:
        print(f"\n=== TOTAL across {len(days)} days: {total:.2f} (avg {total/len(days):.2f}/day) ===")


if __name__ == "__main__":
    main()
