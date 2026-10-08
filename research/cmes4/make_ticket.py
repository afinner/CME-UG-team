"""Build playbook/CMES4_v2_ticket.xlsx: the CMES4 v2 order-ticket calculator.

Styled like the team's Trading Book (yellow = you type, grey = formulas) so it can be
imported into the Google Sheet as extra tabs (File > Import > Insert new sheet(s)).
Run: python make_ticket.py, then recalculate with LibreOffice before sharing.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

NAVY, BLUE = "1F3A5F", "3B6EA5"
YELLOW, GREY = "FFF7CC", "EEF1F5"
F = "Arial"
PRICE = "#,##0.00###"
MONEY = '$#,##0;[Red]($#,##0);-'
THIN = Side(style="thin", color="C9D1DC")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def style(c, *, fill=None, bold=False, color=None, size=10, fmt=None, wrap=False, align=None):
    c.font = Font(name=F, size=size, bold=bold, color=color)
    if fill:
        c.fill = PatternFill("solid", fgColor=fill)
        c.border = BOX
    if fmt:
        c.number_format = fmt
    c.alignment = Alignment(wrap_text=wrap, vertical="center", horizontal=align)


def header(ws, row, text, cols=("B", "C")):
    for col in cols:
        style(ws[f"{col}{row}"], fill=NAVY, bold=True, color="FFFFFF")
    ws[f"{cols[0]}{row}"] = text


def inp(ws, ref, value, fmt=None, note=None):
    ws[ref] = value
    style(ws[ref], fill=YELLOW, fmt=fmt)
    if note:
        ws[ref].comment = Comment(note, "CMES4 v2")


def calc(ws, ref, formula, fmt=None, bold=False):
    ws[ref] = formula
    style(ws[ref], fill=GREY, fmt=fmt, bold=bold)


def label(ws, ref, text, bold=False):
    ws[ref] = text
    style(ws[ref], bold=bold, wrap=True)


def build(path: Path) -> None:
    wb = Workbook()
    t = wb.active
    t.title = "CMES4 v2 ticket"
    t.sheet_view.showGridLines = False
    t.column_dimensions["A"].width = 2
    t.column_dimensions["B"].width = 46
    t.column_dimensions["C"].width = 22
    t.column_dimensions["D"].width = 3
    t.column_dimensions["E"].width = 3
    for col, w in zip("FGHIJK", (12, 11, 9, 16, 13, 13)):
        t.column_dimensions[col].width = w

    t["B1"] = "CMES4 v2 order ticket"
    style(t["B1"], bold=True, size=16, color=NAVY)
    t["B2"] = ("Fill the yellow cells once the confirming 5-minute bar has closed. "
               "Grey cells are formulas. Place the order only if the verdict says GO.")
    style(t["B2"], wrap=True)
    t.merge_cells("B2:K2")
    t.row_dimensions[2].height = 28

    # ---- setup inputs
    header(t, 4, "SETUP", ("B", "C"))
    rows = [
        ("Contract", "ES", None, "ES, MES, NQ or MNQ. Point value, tick and margin come from the table on the right."),
        ("Direction", "Long", None, "Long after three rising 15-min bars, Short after three falling ones."),
        ("Date", dt.date(2026, 10, 12), "dd mmm yyyy", None),
        ("Confirming bar closed at (Dublin time)", dt.time(15, 20), "hh:mm", "Close time of the confirming 5-min bar."),
        ("Account balance from CQG ($)", 1_001_395, MONEY, "Net liquidation value in CQG, today."),
        ("Risk per trade (% of balance)", 0.005, "0.0%", "0.5% to start. Raise to 1% only after the backtest go/no-go passes."),
        ("Trades already taken today", 0, "0", "Max 3 CMES4 trades a day."),
        ("Losing trades today", 0, "0", "Stop for the day after 2 losers."),
        ("Scheduled news in the next 15 minutes?", "No", None, "Yes blocks the trade (US data at 15:00 Dublin, FOMC 18:00 on 28 Oct, EIA 15:30 Wednesdays)."),
    ]
    r = 5
    for name, val, fmt, note in rows:
        label(t, f"B{r}", name)
        inp(t, f"C{r}", val, fmt, note)
        r += 1
    # C5 contract, C6 direction, C7 date, C8 time, C9 balance, C10 risk, C11 trades, C12 losses, C13 news

    # ---- bar inputs
    header(t, 15, "BARS (read off the 5-minute chart)", ("B", "C"))
    bars = [("Pullback bar high", 7843.00), ("Pullback bar low", 7838.00), ("Pullback bar close", 7839.50),
            ("Confirming bar high", 7845.50), ("Confirming bar low", 7839.25), ("Confirming bar close", 7844.75)]
    r = 16
    for name, val in bars:
        label(t, f"B{r}", name)
        inp(t, f"C{r}", val, PRICE)
        r += 1
    # C16 pb high, C17 pb low, C18 pb close, C19 conf high, C20 conf low, C21 conf close

    # ---- lookups for the chosen contract
    pv = "INDEX($G$6:$G$9,MATCH($C$5,$F$6:$F$9,0))"
    tick = "INDEX($H$6:$H$9,MATCH($C$5,$F$6:$F$9,0))"
    margin = "INDEX($I$6:$I$9,MATCH($C$5,$F$6:$F$9,0))"
    min_stop = "INDEX($J$6:$J$9,MATCH($C$5,$F$6:$F$9,0))"
    max_stop = "INDEX($K$6:$K$9,MATCH($C$5,$F$6:$F$9,0))"
    comm_rt = "2*$G$11"

    # ---- order
    header(t, 23, "ORDER (bracket: stop entry + stop-loss + half at +2R)", ("B", "C"))
    order = [
        ("Entry: stop order at", f'=IF($C$6="Long",$C$19+{tick},$C$20-{tick})', PRICE, True),
        ("Stop-loss at", f'=IF($C$6="Long",$C$17-{tick},$C$16+{tick})', PRICE, True),
        ("Risk per contract (points)", "=ABS(C24-C25)", "0.00", False),
        ("Target for half the contracts (+2R) at", '=IF($C$6="Long",C24+2*C26,C24-2*C26)', PRICE, True),
        ("Contracts by risk budget", f"=IFERROR(ROUNDDOWN($C$9*$C$10/(C26*{pv}+{comm_rt}),0),0)", "0", False),
        ("Contracts the margin allows", f"=IFERROR(IF({margin}>0,ROUNDDOWN($C$9/{margin},0),C28),0)", "0", False),
        ("CONTRACTS TO TRADE", "=MAX(0,MIN(C28,C29))", "0", True),
        ("   of which: limit at +2R", "=ROUNDDOWN(C30/2,0)", "0", False),
        ("   of which: runner, trailed", "=C30-C31", "0", False),
        ("$ at risk if stopped (incl. commission)", f"=C30*(C26*{pv}+{comm_rt})", MONEY, False),
        ("% of balance at risk", "=IFERROR(C33/$C$9,0)", "0.00%", False),
        ("Cancel the entry if not filled by (Dublin)", "=$C$8+TIME(0,10,0)", "hh:mm", False),
        ("Flat by (Dublin)", '=IF($C$7=DATE(2026,10,28),TIME(17,55,0),IF($C$7=DATE(2026,10,30),TIME(19,0,0),'
                             'IF($C$7>=DATE(2026,10,26),TIME(19,55,0),TIME(20,55,0))))', "hh:mm", False),
    ]
    r = 24
    for name, f, fmt, bold in order:
        label(t, f"B{r}", name, bold=bold)
        calc(t, f"C{r}", f, fmt, bold=bold)
        r += 1
    # C24 entry, C25 stop, C26 risk, C27 target, C28 by risk, C29 margin cap, C30 qty, C31 half,
    # C32 runner, C33 $ risk, C34 % risk, C35 cancel time, C36 flat time

    # ---- checks
    header(t, 38, "CHECKS", ("B", "C"))
    early = "$C$7<DATE(2026,10,26)"
    in_window = (f"OR(AND($C$8>=IF({early},TIME(14,50,0),TIME(13,50,0)),$C$8<=IF({early},TIME(16,50,0),TIME(15,50,0))),"
                 f"AND($C$8>=IF({early},TIME(19,5,0),TIME(18,5,0)),$C$8<=IF({early},TIME(20,50,0),TIME(19,50,0)),"
                 f"$C$7<>DATE(2026,10,28),$C$7<>DATE(2026,10,30)))")
    checks = [
        ("Confirming close beyond the pullback bar's close", '=IF($C$6="Long",$C$21>$C$18,$C$21<$C$18)'),
        ("Prices make sense (stop below the entry for a long)", '=IF($C$6="Long",C25<C24,C25>C24)'),
        ("Stop inside the band for this contract", f"=AND(C26>={min_stop},C26<={max_stop})"),
        ("Inside a trading window (see table)", f"={in_window}"),
        ("Fewer than 3 trades and 2 losers today", "=AND($C$11<3,$C$12<2)"),
        ("No scheduled news in the next 15 minutes", '=$C$13="No"'),
        ("At least 1 contract after sizing", "=C30>=1"),
    ]
    r = 39
    for name, f in checks:
        label(t, f"B{r}", name)
        calc(t, f"C{r}", f)
        r += 1
    # C39..C45
    label(t, "B46", "Also covers the 10-contract daily minimum?")
    calc(t, "C46", "=IF(2*C30>=10,\"Yes\",\"No - add a minimum round-trip\")")
    reasons = ['"no confirming close"', '"check the bar prices"', '"stop outside the band"', '"outside the windows"',
               '"daily limit reached"', '"news due"', '"size rounds to zero"']
    chain = '"GO: place the bracket"'
    for i in reversed(range(7)):
        chain = f'IF(NOT(C{39 + i}),"NO TRADE: "&{reasons[i]},{chain})'
    label(t, "B48", "VERDICT", bold=True)
    calc(t, "C48", "=" + chain, bold=True)
    t["C48"].alignment = Alignment(wrap_text=True, vertical="center")
    t.row_dimensions[48].height = 30
    t.conditional_formatting.add("C48", FormulaRule(formula=['LEFT($C$48,2)="GO"'],
                                                    fill=PatternFill("solid", fgColor="D9EAD3"),
                                                    font=Font(name=F, bold=True, color="1E5631")))
    t.conditional_formatting.add("C48", FormulaRule(formula=['LEFT($C$48,2)="NO"'],
                                                    fill=PatternFill("solid", fgColor="F4CCCC"),
                                                    font=Font(name=F, bold=True, color="8B1A1A")))
    t.conditional_formatting.add("C39:C45", FormulaRule(formula=["C39=FALSE"], fill=PatternFill("solid", fgColor="F4CCCC")))

    # ---- contract table
    for col, text in zip("FGHIJK", ("Contract", "$ per point", "Tick", "Margin ($)", "Min stop (pts)", "Max stop (pts)")):
        style(t[f"{col}5"], fill=NAVY, bold=True, color="FFFFFF", wrap=True)
        t[f"{col}5"] = text
    t.row_dimensions[5].height = 28
    t["F4"] = "CONTRACTS (edit margin to match CQG)"
    style(t["F4"], bold=True, color=NAVY)
    table = [("ES", 50, 0.25, 28_600, 2, 12), ("MES", 5, 0.25, 2_860, 2, 12),
             ("NQ", 20, 0.25, None, 8, 48), ("MNQ", 2, 0.25, None, 8, 48)]
    for i, row in enumerate(table):
        for col, val in zip("FGHIJK", row):
            ref = f"{col}{6 + i}"
            inp(t, ref, val, MONEY if col in "GI" else ("0.00" if col == "H" else None))
    t["I6"].comment = Comment("Initial margin per ES contract, TradeZero support page dated 16 Sep 2026. "
                              "Replace with the figure CQG shows for your account.", "CMES4 v2")
    t["I8"].comment = Comment("Not verified. Enter the margin CQG charges; until then size is set by risk only.", "CMES4 v2")
    t["J8"].comment = Comment("NQ moves roughly 4x as many points as ES; the band is scaled from ES. Adjust after a backtest.", "CMES4 v2")
    label(t, "F11", "Commission per side ($)")
    inp(t, "G11", 2.5, MONEY, "Challenge commission: $2.50 per contract per side (Trading Book Settings).")
    t["G11"].number_format = "$#,##0.00"

    # ---- windows table
    t["F14"] = "TRADING WINDOWS (Dublin time)"
    style(t["F14"], bold=True, color=NAVY)
    for col, text in zip("FGHIJ", ("Dates", "Morning", "Afternoon", "Flat by", "Clock")):
        style(t[f"{col}15"], fill=NAVY, bold=True, color="FFFFFF")
        t[f"{col}15"] = text
    win = [("9-23 Oct", "14:45-16:30", "19:00-20:30", "20:55", "ET + 5h"),
           ("26-30 Oct", "13:45-15:30", "18:00-19:30", "19:55", "ET + 4h"),
           ("Wed 28 Oct", "13:45-15:30", "none (FOMC 18:00)", "17:55", "ET + 4h"),
           ("Fri 30 Oct", "13:45-15:30", "none", "19:00 team cut-off", "ET + 4h")]
    for i, row in enumerate(win):
        for col, val in zip("FGHIJ", row):
            c = t[f"{col}{16 + i}"]
            c.value = val
            style(c, fill=GREY)
    t["F21"] = ("Windows are 09:45-11:30 and 14:00-15:30 New York time. The check above allows the "
                "confirming bar to close up to 20 minutes after a window ends.")
    style(t["F21"], wrap=True)
    t.merge_cells("F21:K23")

    for name, opts in (("C5", '"ES,MES,NQ,MNQ"'), ("C6", '"Long,Short"'), ("C13", '"No,Yes"')):
        dv = DataValidation(type="list", formula1=opts, allow_blank=False)
        t.add_data_validation(dv)
        dv.add(name)
    t.freeze_panes = "A4"

    # ---------------------------------------------------------------- sizing sheet
    s = wb.create_sheet("Sizing table")
    s.sheet_view.showGridLines = False
    s["B1"] = "ES contracts by stop distance"
    style(s["B1"], bold=True, size=16, color=NAVY)
    s["B2"] = ("Uses the balance and ES margin from the ticket tab. Commission is included in the risk per "
               "contract. The margin cap binds first for stops under about 7 points at 1% risk.")
    style(s["B2"], wrap=True)
    s.merge_cells("B2:H2")
    s.row_dimensions[2].height = 30
    heads = ("Stop (ES pts)", "Risk per ES ($)", "ES at 0.5%", "$ at risk", "ES at 1% (capped)", "$ at risk", "MES at 0.5%")
    for col, h in zip("BCDEFGH", heads):
        style(s[f"{col}4"], fill=NAVY, bold=True, color="FFFFFF", wrap=True)
        s[f"{col}4"] = h
    s.row_dimensions[4].height = 30
    bal = "'CMES4 v2 ticket'!$C$9"
    es_m = "'CMES4 v2 ticket'!$I$6"
    mes_m = "'CMES4 v2 ticket'!$I$7"
    comm = "2*'CMES4 v2 ticket'!$G$11"
    cap = f"ROUNDDOWN({bal}/{es_m},0)"
    stops = [x / 2 for x in range(4, 25)]          # 2.0 to 12.0 points
    for i, stop in enumerate(stops):
        r = 5 + i
        inp(s, f"B{r}", stop, "0.00")
        calc(s, f"C{r}", f"=B{r}*50+{comm}", MONEY)
        calc(s, f"D{r}", f"=MIN(ROUNDDOWN({bal}*0.005/C{r},0),{cap})", "0")
        calc(s, f"E{r}", f"=D{r}*C{r}", MONEY)
        calc(s, f"F{r}", f"=MIN(ROUNDDOWN({bal}*0.01/C{r},0),{cap})", "0")
        calc(s, f"G{r}", f"=F{r}*C{r}", MONEY)
        calc(s, f"H{r}", f"=MIN(ROUNDDOWN({bal}*0.005/(B{r}*5+{comm}),0),ROUNDDOWN({bal}/{mes_m},0))", "0")
    for col, w in zip("ABCDEFGH", (2, 13, 15, 12, 13, 16, 13, 13)):
        s.column_dimensions[col].width = w
    s.freeze_panes = "A5"

    # ---------------------------------------------------------------- rules sheet
    h = wb.create_sheet("Rules")
    h.sheet_view.showGridLines = False
    h.column_dimensions["A"].width = 2
    h.column_dimensions["B"].width = 22
    h.column_dimensions["C"].width = 100
    h["B1"] = "CMES4 v2 rules"
    style(h["B1"], bold=True, size=16, color=NAVY)
    rules = [
        ("COLOURS", None),
        ("Yellow cells", "You type here."),
        ("Grey cells", "Formulas. Don't type over them."),
        ("Example", "The ticket opens with a worked example (a long on 12 Oct). Overwrite the yellow cells."),
        ("RULES", None),
        ("1. Windows", "New setups only 09:45-11:30 and 14:00-15:30 New York time (Dublin: see the ticket tab). Flat by 15:55 New York."),
        ("2. Trend", "The last three completed 15-min bars each made a higher high AND a higher low than the bar before (long). "
                     "Lower highs and lower lows for a short. One wording only: three bars, two comparisons."),
        ("3. Pullback", "Within the next three 5-min bars, one bar's low goes below the previous bar's low (long) or its high "
                        "above the previous bar's high (short). Equal does not count."),
        ("4. Confirmation", "The very next 5-min bar closes above the pullback bar's close (long) or below it (short)."),
        ("5. Entry", "Stop order one tick beyond the confirming bar's high (long) or low (short). Cancel if not filled in 10 minutes."),
        ("6. Stop-loss", "One tick beyond the pullback bar's low (long) or high (short). Skip the trade if that is under 2 or "
                         "over 12 ES points from the entry."),
        ("7. Exits", "Half the contracts at +2R with a limit order. When it fills, move the stop on the rest to the entry price, "
                     "then after each 5-min bar raise it to one tick under the lowest low of the last three bars (long). "
                     "If +2R is not reached within 60 minutes of the fill, exit everything at market."),
        ("8. Size", "Risk 0.5% of the balance per trade, 1% after the backtest go/no-go passes. Never more contracts than "
                    "the margin allows. Max 3 trades a day; stop after 2 losers."),
        ("9. Log", "Every setup goes in Decisions, taken or not, with the bar times. Trades go in Trades with the ticket's numbers."),
        ("WHY THESE CHANGES", None),
        ("Small targets", "CMES4 v1's 2R target is about 8 ES points: at most 1.4% of the account per perfect trade, even at the margin limit."),
        ("Costs", "With a 4-point stop, commission and two ticks of slippage cost about 0.12R a trade. v2's median stop is "
                  "about 7 points, which roughly halves that."),
        ("Lunch", "The 6 Oct checks were all 11:15-12:45 New York, the quietest part of the day."),
        ("Ambiguity", "D001: the 3-bar and 4-bar wordings disagreed. v2 keeps one."),
        ("Entry", "T003 was sold before the bounce and confirmation. A stop order placed from this ticket cannot jump the gun."),
    ]
    r = 3
    for k, v in rules:
        if v is None:
            h[f"B{r}"] = k
            style(h[f"B{r}"], bold=True, size=12, color=NAVY)
        else:
            h[f"B{r}"] = k
            style(h[f"B{r}"], bold=True)
            h[f"C{r}"] = v
            style(h[f"C{r}"], wrap=True)
            if k in ("Yellow cells",):
                h[f"B{r}"].fill = PatternFill("solid", fgColor=YELLOW)
            if k in ("Grey cells",):
                h[f"B{r}"].fill = PatternFill("solid", fgColor=GREY)
        r += 1
    wb.move_sheet("Rules", offset=-2)
    wb.active = 1
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "playbook" / "CMES4_v2_ticket.xlsx"
    build(out)
    print(out)
