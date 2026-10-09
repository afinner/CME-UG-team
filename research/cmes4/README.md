# CMES4 research code

Backtest and upper-limit tools behind `report/cmes4-upper-limit.md`.

```
pip install -r requirements.txt          # numpy, pandas, openpyxl, pytest (+ yfinance for real data)
python -m pytest -q                      # 15 tests, about 5 s
python backtest.py --source yahoo        # ES=F 5-min bars, last ~60 days (needs internet)
python backtest.py --source csv --csv es_5m.csv --tz Europe/Dublin   # e.g. a CQG export
python backtest.py --source synthetic --days 500                      # no-edge baseline
python upper_limit.py                    # ceilings and Monte Carlo tables -> results/upper_limit.md
python upper_limit.py --margin 14300 --v2-trades results/trades_yahoo_v2.csv
python make_ticket.py                    # rebuilds playbook/CMES4_v2_ticket.xlsx
python make_trader_sheet.py              # rebuilds playbook/CMES4_v2_trader_sheet.pdf (needs reportlab)
```

| File | What it does |
|---|---|
| `cmes4_rules.py` | CMES4 rules engine. `CMES4Params()` is v1 as reconstructed from the Trading Book; `v2_params()` is the proposed version. |
| `marketdata.py` | Loads 5-minute bars (Yahoo, CSV) or simulates a no-edge random walk with exact bar highs and lows. |
| `ceiling.py` | Per-trade and perfect-foresight ceilings, margin caps, Kelly, Monte Carlo, and best-possible odds for a finish. |
| `backtest.py` | Runs eight variants (v1/v2, 3- and 4-bar, worst-case fills, all-day) and writes trades and a summary. |
| `upper_limit.py` | Prints and saves the report's tables. |
| `make_ticket.py` | Builds the order-ticket workbook in the Trading Book's colours. |
| `make_trader_sheet.py` | Builds the one-page trader's sheet PDF from the same rules. |
| `test_cmes4.py` | Replays logged situations (D001, D002, D005, T004-style entry) and checks the maths. |

## How the engine decides

- **Trend:** N completed 15-min bars, each with a higher high and higher low (N = 3 by default; `trend_bars=4` is the other wording from D001).
- **Pullback and confirmation:** within 3 five-minute bars of the setup, a bar breaks the previous bar's low (long); the next bar closes above the pullback bar's close.
- **Exits inside a bar:** bars hide the order of moves, so the engine walks open → low → high → close for an up bar and open → high → low → close for a down bar. `intrabar="worst"` assumes the adverse extreme first.
- **Costs:** $2.50 per contract per side and one tick of slippage on market entries, stops and time exits. Limit exits (targets) have no slippage.

## Validation

On a random walk the 2R target must come first one time in three and the average R before costs must be zero. With 500 simulated sessions the engine gives 32% and +0.005R (v1), so all of the measured −0.17R is costs. An earlier generator with only 10 steps per bar let stop entries "fill" at prices the path jumped over and showed a false +0.19R edge for v2; the generator now draws each bar's high and low from the exact distribution for a continuous path.

## Limits

- The v1 rules are reconstructed from trades T002–T004 and decisions D001–D005; the original CMES4 text was not available.
- `results/` holds the no-edge baseline only. Real ES data could not be downloaded from the environment these files were built in; run `backtest.py --source yahoo` on a laptop.
- ES margin defaults to $28,600 (TradeZero, 16 Sep 2026). Pass `--margin` with CQG's figure.
