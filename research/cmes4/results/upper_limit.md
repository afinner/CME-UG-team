### A. Most one perfect trade can add, at the margin limit (35 ES on $1,001,395)

| Trade | Points | Most it can add (full margin) |
| --- | --- | --- |
| CMES4 v1 target: 2R x 4.0 pts | 8 | 1.4% |
| v2 runner on a trend leg (25 pts) | 25 | 4.4% |
| Whole trend day, 1% of ES (78 pts) | 78 | 13.6% |

### B. Perfect foresight: every setup wins 2R, compounded to 30 Oct

| Size | 1 setup a day: 16 trades | Every setup, full session (2.3 a day): 37 trades |
| --- | --- | --- |
| 5 ES (as on 6 Oct) | +3.2% | +7.3% |
| 0.5% risk per trade | +16.3% | +41.7% |
| Full margin | +24.2% | +65.2% |

### C. CMES4 v1 by 30 Oct, Monte Carlo (20,000 runs)

| Hit rate | Size | Setups/day | Median | 1 in 10 best | 1 in 100 best | P(>= +30%) | P(<= -10%) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 33% (no edge) | 5 ES | 1.0 | -0.2% | +0.6% | +1.4% | 0.0% | 0.0% |
| 33% (no edge) | 5 ES | 2.3 | -0.5% | +0.8% | +1.9% | 0.0% | 0.0% |
| 33% (no edge) | Full margin | 1.0 | -1.6% | +4.3% | +9.9% | 0.0% | 1.8% |
| 33% (no edge) | Full margin | 2.3 | -3.6% | +5.3% | +14.0% | 0.0% | 15.0% |
| 38% (breakeven after costs) | 5 ES | 1.0 | +0.0% | +0.9% | +1.7% | 0.0% | 0.0% |
| 38% (breakeven after costs) | 5 ES | 2.3 | +0.1% | +1.4% | +2.5% | 0.0% | 0.0% |
| 38% (breakeven after costs) | Full margin | 1.0 | +0.0% | +6.2% | +12.2% | 0.0% | 0.7% |
| 38% (breakeven after costs) | Full margin | 2.3 | +0.1% | +9.8% | +18.8% | 0.0% | 5.8% |
| 45% (strong edge) | 5 ES | 1.0 | +0.4% | +1.3% | +2.1% | 0.0% | 0.0% |
| 45% (strong edge) | 5 ES | 2.3 | +0.9% | +2.3% | +3.5% | 0.0% | 0.0% |
| 45% (strong edge) | Full margin | 1.0 | +2.5% | +9.3% | +15.8% | 0.0% | 0.1% |
| 45% (strong edge) | Full margin | 2.3 | +6.1% | +16.7% | +26.9% | 0.5% | 1.0% |

### D. CMES4 v2 by 30 Oct, 1.25 trades a day, trade shape from no-edge synthetic backtest, 1,000 sessions

| Average R per trade | Size | Median | 1 in 10 best | 1 in 100 best | P(>= +30%) | P(<= -10%) |
| --- | --- | --- | --- | --- | --- | --- |
| as backtested (-0.07) | 0.5% risk | -0.9% | +3.5% | +8.2% | 0.0% | 0.0% |
| as backtested (-0.07) | 1% risk (margin-capped) | -1.8% | +6.2% | +13.9% | 0.0% | 4.6% |
| as backtested (-0.07) | Full margin | -2.4% | +9.1% | +20.4% | 0.1% | 15.0% |
| +0.10 | 0.5% risk | +0.5% | +5.7% | +11.8% | 0.0% | 0.0% |
| +0.10 | 1% risk (margin-capped) | +0.8% | +9.6% | +18.9% | 0.0% | 2.2% |
| +0.10 | Full margin | +1.1% | +13.5% | +26.8% | 0.5% | 7.7% |
| +0.20 | 0.5% risk | +1.2% | +7.0% | +14.1% | 0.0% | 0.0% |
| +0.20 | 1% risk (margin-capped) | +2.0% | +11.5% | +21.0% | 0.1% | 1.3% |
| +0.20 | Full margin | +2.8% | +15.9% | +28.9% | 0.9% | 5.5% |

### E. WTI opening-range breakout (the playbook), its own trade model, about 10 trades left

| Average R per trade | Risk per trade | Median | 1 in 10 best | 1 in 100 best | P(>= +30%) | P(<= -10%) |
| --- | --- | --- | --- | --- | --- | --- |
| +0.00 | 1.5% | -1.0% | +7.3% | +18.0% | 0.1% | 2.0% |
| +0.00 | 3.0% | -2.2% | +14.8% | +38.1% | 2.3% | 20.3% |
| +0.00 | 5.0% | -4.1% | +24.4% | +66.9% | 7.3% | 35.2% |
| +0.15 | 1.5% | +0.2% | +10.7% | +24.6% | 0.4% | 1.8% |
| +0.15 | 3.0% | +0.1% | +21.7% | +53.1% | 5.3% | 17.3% |
| +0.15 | 5.0% | -0.4% | +36.3% | +95.0% | 13.2% | 29.9% |

### F. Best possible odds for ANY strategy (log-normal approximation)

| Finish | Strategy Sharpe | Best daily volatility | Best chance | Chance of losing half |
| --- | --- | --- | --- | --- |
| +30% (2024's 5th place, if it started at $1M) | 0.0 | 18.0% | 23.5% | 27.4% |
| +30% (2024's 5th place, if it started at $1M) | 1.3 | 18.0% | 34.7% | 17.7% |
| +100% | 0.0 | 29.4% | 12.0% | 50.0% |
| +100% | 1.3 | 29.4% | 19.8% | 37.1% |
| +218% (2025's 5th place) | 0.0 | 38.0% | 6.4% | 62.0% |
| +218% (2025's 5th place) | 1.3 | 38.0% | 11.6% | 49.1% |
