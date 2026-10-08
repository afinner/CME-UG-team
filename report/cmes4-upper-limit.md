# CMES4 upper limit

8 October 2026 · account $1,001,395 after 7 Oct · 16 sessions left (9–30 Oct)

**CMES4 can't realistically take the team into the top five.** If CQG holds exchange-level margin
(about $28,600 per ES), even a month in which every setup won its full 2R ends at +24% (one setup
a day) to +65% (every setup in the session). With a strong but realistic edge, the best 1 run in 10
ends near +17%. Fifth place took +218% in 2025.

The limit is built into the rules: each trade aims for about 8 ES points, margin stops the
position at about 35 ES, and there are one to two setups a day. CMES4 v2 (below) makes the
strategy cheaper and more disciplined. Raising the ceiling needs a strategy that holds whole trend
days, such as the WTI breakout in the team's playbook.

All tables come from `research/cmes4` (`python upper_limit.py`, `python backtest.py`).

## Where each plan could finish by 30 October

Monte Carlo, 40,000 runs per plan, trades independent, margin $28,600 per ES.

| Plan | Assumes | 1 in 10 worst | Median | 1 in 10 best | 1 in 100 best | ≥ +30% | ≤ −10% |
|---|---|---:|---:|---:|---:|---:|---:|
| CMES4 as traded (5 ES) | 45% hit 2R, every setup (2.3 a day) | −0.4% | +0.9% | +2.3% | +3.5% | 0.0% | 0.0% |
| CMES4 at full margin (35 ES) | 45% hit 2R, every setup (2.3 a day) | −3.1% | +6.2% | +16.8% | +26.8% | 0.5% | 0.8% |
| CMES4 v2 at 1% risk | +0.20R a trade, 1.25 a day | −5.4% | +2.1% | +11.5% | +21.0% | 0.1% | 1.2% |
| WTI breakout at 1.5% risk | playbook model, +0.15R, 0.6 a day | −6.6% | +0.1% | +10.8% | +23.9% | 0.4% | 1.6% |
| WTI breakout at 3% risk | same | −13.2% | −0.2% | +21.9% | +51.8% | 5.3% | 17.7% |
| WTI breakout at 5% risk | same | −21.6% | −0.9% | +36.7% | +93.6% | 13.6% | 30.6% |

## Why the ceiling is low

Contracts × points per trade × trades.

- **Contracts:** ES initial margin was quoted at $28,628.75 on 16 Sep (TradeZero), so $1.0M holds 35 ES.
  At a 4-point stop, 1% risk already needs 48 ES: margin binds before the team's 12% cap.
- **Points:** 2R on a 4-point stop is 8 points. One perfect trade at 35 ES adds 1.4%.
- **Trades:** about 2.3 setups a day over 10:00–15:30 New York; about one a day for one person in a two-hour slot.

| If every setup won 2R (to 30 Oct) | 1 a day (16 trades) | 2.3 a day (37 trades) |
|---|---:|---:|
| 5 ES, as traded on 6 Oct | +3.2% | +7.3% |
| 0.5% risk per trade | +16.3% | +41.7% |
| Full margin, about 35 ES | +24.2% | +65.2% |

**Check CQG's margin first.** At half the margin (70 ES) the perfect-month ceiling is +54% to +173%.
If CQG only charges a day-trading margin, the limit is the risk the team accepts: with a strong edge,
2% risk per trade gives a 25% chance of +30% and a 9% chance of −10%; with no edge the median is −11%.
Reaching +218% would take about 8% risk per trade, and three runs in four would then hit CME's 20%
one-day lockout at least once.

## Without an edge, CMES4 loses about 0.17R a trade

500 simulated sessions of a random walk with ES-like volatility (a market with no edge):

| No-edge test | Trades a day | Median stop | Cost per trade | Average R after costs | 95% range |
|---|---:|---:|---:|---:|---:|
| CMES4 v1, 3-bar trend | 2.3 | 4.0 pts | 0.17R | −0.17R | −0.26 to −0.09 |
| CMES4 v1, 4-bar trend | 1.1 | 4.0 pts | 0.17R | −0.13R | −0.25 to 0.00 |
| CMES4 v2 | 1.2 | 7.0 pts | 0.09R | −0.05R | −0.18 to +0.07 |

The 2R target came first 32% of the time (chance: one in three). Before costs the average is zero,
so the whole loss is commission plus a tick of slippage on entries and stops. To pay its costs,
v1 needs the target first in about 39% of trades. Sixty days of 5-minute data (about 140 trades)
leaves the average uncertain by ±0.25R, so a short backtest checks mechanics, not edge.

## What a top-five finish takes

- **2025:** $1M start; fifth place $3,180,570 (+218%), winner $5,171,285 (+417%).
- **2024:** fifth place $1,296,783, winner $2,056,528 (+30% for fifth if the start was $1M; not confirmed).
- **2021:** winners turned $500,000 into $1.74M trading only crude.

Best possible odds in 16 sessions for any strategy (log-normal approximation, lockout ignored):

| Finish | Best daily volatility | Best chance, no edge | Best chance, Sharpe 1.3 | Lose half (Sharpe 1.3) |
|---|---:|---:|---:|---:|
| +30% | 18% | 24% | 35% | 18% |
| +100% | 29% | 12% | 20% | 37% |
| +218% | 38% | 6% | 12% | 49% |

CMES4 at full margin runs at about 2% a day.

## CMES4 v2

| Rule | v1 as traded | v2 | Why |
|---|---|---|---|
| Trend | "3-bar" and "4-bar" wordings both used | Three 15-min bars, each higher high and higher low | D001 skipped a setup over the wording |
| Entry | Market at the confirming close | Stop 1 tick beyond the confirming bar; cancel after 10 min | T003 sold before the bounce and confirmation |
| Exit | All at 2R or time limit | Half at 2R; rest to breakeven, trailed under the last three 5-min lows; flat 15:55 | 10% of v2 trades beat 2R in the no-edge test; the best made 18R |
| Stop size | Any, median 4 pts | 2–12 pts, else skip | Costs fall from 0.17R to 0.09R a trade |
| Room-to-peak | Room ≥ 1R | Dropped | The runner makes the old peak irrelevant |
| Windows | In practice 11:15–12:45 New York | 09:45–11:30 and 14:00–15:30 New York | Midday is the quietest stretch |
| Size | 5 ES or 10–36 MES (0.02–0.13% risk) | 0.5%, then 1% after the go/no-go | At 0.1% risk a perfect month is worth about 3% |
| Daily limits | None | Max 3 trades, stop after 2 losers | A bad day costs about 1% |

v2 does not lift the ceiling: at +0.20R and 1% risk its best 1 run in 100 is about +21%.
Its job is to stop the leaks. Full rules: `playbook/cmes4-v2-rule-card.md`. Order maths:
`playbook/CMES4_v2_ticket.xlsx`.

## The alternative with a higher ceiling: the WTI breakout

The team's WTI Crude Playbook (3 Oct) trades with the 20-day trend, enters on a break of the
9:00–9:30 New York range and holds to 14:25 with no target. With no profit cap and a wide stop
(about $1,220 a contract in its example, against about $200 for a CMES4 stop), its limit is the
risk the team picks, not margin. See the first table: 1.5% risk as written, 3% and 5% for
comparison. The +0.15R edge is the playbook's assumption, not a measurement.

## Recommendation, in order

1. **Today:** check CQG's ES margin (open a 1-lot ticket, read margin or purchasing power) and
   enter it in the ticket.
2. **From Mon 12 Oct:** trade CMES4 v2, not v1, with the ticket, at 0.5% risk. A trade of 5+ ES
   also covers the 10-contract daily minimum.
3. **Before raising size:** run the backtest on real ES data with the go/no-go fixed in advance
   (v2 average R above 0 and worst-case-fills version above −0.10R).
4. **Make the WTI breakout the core book** at 1.5% as the playbook planned; CMES4 v2 becomes the
   small book and daily-minimum vehicle.
5. **Friday 16 Oct review:** decide the top-five question. Evidence first: stay at 1.5%. A real
   shot: breakout at 3% from 19 Oct with a floor (back to 1.5% below $950,000); expect about a 5%
   chance of +30% and an 18% chance of −10% or worse.

## What this rests on

- CMES4 v1 is reconstructed from the Trading Book (T002–T004, D001–D005). The CME Project chat
  wasn't reachable from this session; check against the original wording.
- No real intraday data: this environment's network policy blocked Yahoo Finance and Dukascopy.
  The no-edge test uses a random walk with ES-like volatility; edge levels are scenarios.
- ES margin $28,600 is a broker's 16 Sep figure; CQG's may differ.
- Monte Carlo trades are independent; real streaks are lumpier.
- Bars hide the order of moves inside them; the backtest uses the open-low-high-close path and
  also reports a worst-case version.

## Sources

- CME Group: [2025 winners](https://www.cmegroup.com/media-room/press-releases/2025/12/11/cme_group_announceswinnersofthe22ndannualuniversitytradingchalle.html),
  [2024 challenge page](https://www.cmegroup.com/events/university-trading-challenge/2024-trading-challenge.html),
  [2025 rules](https://www.cmegroup.com/events/university-trading-challenge/files/2025-university-trading-challenge-rules-regulations.pdf),
  [2026 rules](https://www.cmegroup.com/events/university-trading-challenge/files/2026-university-trading-challenge-rules-regulations.pdf).
  Balances as reported through web search; cmegroup.com was blocked from this session.
- TradeZero, [E-mini S&P 500 contract specifications](https://tradezero.com/en-us/support/questions/what-are-the-contract-specifications-for-the-e-mini-s-and-p-500-tradezero-america) (initial margin $28,628.75, 16 Sep 2026).
- Gao, Han, Li & Zhou (2018), [Market intraday momentum](https://profiles.wustl.edu/en/publications/market-intraday-momentum/), Journal of Financial Economics 129(2).
- The team's WTI Crude Playbook (3 Oct) and Trading Book (as of 8 Oct).
