# CMES4 v2 rule card

ES (or MES) on 15-minute and 5-minute charts. Times are New York unless marked Dublin.
Use `CMES4_v2_ticket.xlsx` for every order: it applies rules 5–8 and gives a GO / NO TRADE verdict.

| # | Rule | Detail |
|---|------|--------|
| 1 | Windows | New setups only 09:45–11:30 and 14:00–15:30 New York. Dublin: 14:45–16:30 and 19:00–20:30 until Fri 23 Oct; 13:45–15:30 and 18:00–19:30 from Mon 26 Oct. No afternoon window on Wed 28 Oct (Fed 18:00 Dublin) or Fri 30 Oct. |
| 2 | Trend | The last three completed 15-min bars each made a higher high **and** a higher low than the bar before (long). Lower highs and lower lows for a short. Three bars, two comparisons: there is no other wording. |
| 3 | Pullback | Within the next three 5-min bars, a bar's low goes below the previous bar's low (long), or its high above the previous bar's high (short). Equal does not count. |
| 4 | Confirmation | The very next 5-min bar closes above the pullback bar's close (long) or below it (short). |
| 5 | Entry | Stop order 1 tick beyond the confirming bar's high (long) or low (short). Cancel it if it has not filled within 10 minutes. |
| 6 | Stop-loss | 1 tick beyond the pullback bar's low (long) or high (short). Skip the trade if that is under 2 or over 12 ES points from the entry. |
| 7 | Exits | Half the contracts at +2R with a limit order. When it fills, move the stop on the rest to the entry price, then after each 5-min bar raise it to 1 tick under the lowest low of the last three bars (long; mirror for shorts). If +2R is not reached within 60 minutes of the fill, exit everything at market. Flat by 15:55 New York (20:55 Dublin until 23 Oct, 19:55 from 26 Oct; 19:00 on 30 Oct). |
| 8 | Size | Risk 0.5% of the CQG balance per trade; 1% only after the backtest go/no-go passes. Contracts = risk ÷ (stop points × $50 + $5), rounded down, never more than balance ÷ margin per contract. |
| 9 | Daily limits | At most 3 CMES4 trades a day. Stop after 2 losing trades. |
| 10 | Log | Every setup goes in Decisions, taken or not, with its bar times. Each trade goes in Trades with the ticket's numbers (entry, stop, +2R, contracts). |

## Placing the order in CQG

1. Fill the ticket after the confirming bar closes. Continue only on GO.
2. Buy stop (or sell stop) on ESZ6 at the ticket's entry, for the ticket's contracts.
3. Attach a bracket: stop-loss at the ticket's stop for all contracts and a limit at +2R for half. If your bracket takes one target only, send two half-size orders: one with stop and target, one with the stop alone.
4. Cancel the entry if it has not filled within 10 minutes.
5. Manage the runner as in rule 7.

## Go / no-go before raising size to 1%

Run `python backtest.py --source yahoo` in `research/cmes4` (needs internet and `pip install yfinance`). Raise to 1% only if **both** hold for v2:

- `avg_r_net` above 0, and
- the `v2_worst_case_fills` row above −0.10R.

Write the result in the Decisions tab before the next trade.
