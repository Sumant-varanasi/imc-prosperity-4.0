# IMC Prosperity 4 — Trading Challenge 2026

My submissions for [IMC Prosperity 4](https://prosperity.imc.com/), the global algorithmic trading competition hosted by IMC Trading (April 14–30, 2026). Over five rounds, participants develop Python algorithms to trade fictional products in a simulated market and solve manual trading puzzles.

This year's theme: **a deep-space trading outpost on the planet Intara, earning XIRECs** (the in-game currency).

---

## 📂 Files

| File | Description |
|---|---|
| `trader_round2_v1.py` | Round 2 algo — initial version (4,901 XIRECs platform score) |
| `trader_round2_v2.py` | Round 2 algo — wider passive quotes (5,230 XIRECs) |
| `trader_round2_v3.py` | Round 2 algo — layered quotes, best cross-day average |
| `backtest_r2.py` | Local cross-day backtester for Round 2 |
| `.gitignore` | Excludes data CSVs, logs, and submission artifacts |

---

## 🧠 Strategy Notes

### Round 2 — Algorithmic

Two products introduced in Round 2:

| Product | Behavior | Strategy |
|---|---|---|
| **ASH_COATED_OSMIUM** | Fair value ≈ 10,000, std ~5, spread ~16 | Market-make with layered quotes + inventory skew |
| **INTARIAN_PEPPER_ROOT** | Upward drift of +1,000 XIRECs/day | Immediately go max long (+50) and hold |

Key insight from data analysis: Pepper Root's price drifts **+0.1 per timestep** with only ~1.9 std — a clear, consistent trend across all three historical days. Holding max long for the full day captures ~5,000 XIRECs purely from mark-to-market.

### Round 2 — Manual (Budget Allocation)

Allocated a 50,000 XIREC budget across three pillars: Research, Scale, and Speed. After probing the UI to map the payoff curves:
- Research was **heavily concave** (front-loaded returns)
- Scale was **roughly linear** (7× at 100%)
- Speed had **no visible forecast** (treated as 0)

Optimal split: **6% Research / 94% Scale / 0% Speed** for a forecast of **394,528 XIRECs** (~7.9× return on budget).

---

## 🛠 Running the Local Backtester

The backtester runs a Trader class against the 3 historical days of R2 data (day -1, 0, 1) for cross-day validation — critical to avoid overfitting to a single day.

```bash
# Place the R2 price CSVs (prices_round_2_day_-1.csv etc.) in this folder
python backtest_r2.py trader_round2_v3.py all
```

Options:
- `all` — run across all 3 days and report average
- `-1`, `0`, or `1` — run a single specific day

> ⚠️ The backtester uses simplified fill logic (no queue priority, no latency), so absolute PnL numbers are inflated versus the real platform. Use it for **comparing versions**, not for predicting platform scores.

---

## 📊 Results

### Round 2

| Version | Platform Day 1 | Local Avg (3 days) | Notes |
|:---:|---:|---:|:---|
| v1 | 4,901 | 54,469 | Initial — narrow passive quotes |
| v2 | 5,230 | 54,138 | Wider quotes (9996/10004) |
| **v3** | **5,072** | **55,333** | **Layered quotes, best cross-day avg** |

Final submission: **v3** (consistency across days > single-day peak)

### Cumulative Score

| Round | Algo | Manual |
|:---:|---:|---:|
| R1 | — | — | 
| R2 | ~5,600 | ~51k | 

---



## 🧾 Tech Notes

- **Language:** Python 3
- **Submission environment constraints:** stdlib only — no `numpy`, `pandas`, `scipy`, or any external imports allowed in the uploaded `trader.py`
- **Data model:** provided by IMC (`OrderDepth`, `Order`, `TradingState`)
- **State persistence:** JSON-serialized into `traderData` between ticks

---


## 📜 Disclaimer

This code is shared for educational and portfolio purposes only. It is not financial advice and reflects strategies for a simulated trading environment.

*Prosperity, XIRECs, and the game products are concepts of IMC Trading.*
