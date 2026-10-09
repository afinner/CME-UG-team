"""Build playbook/CMES4_v2_trader_sheet.pdf: CMES4 v2 on one A4 page for the person trading it.

Run: python make_trader_sheet.py   (needs reportlab and a TrueType sans such as Carlito)
The rules match playbook/cmes4-v2-rule-card.md and the ticket workbook.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parents[2] / "playbook" / "CMES4_v2_trader_sheet.pdf"

NAVY = colors.HexColor("#1F3A5F")      # Trading Book header navy
BLUE = colors.HexColor("#3B6EA5")
INK = colors.HexColor("#1B2430")
MUTED = colors.HexColor("#5B6778")
RULE = colors.HexColor("#C9D1DC")
SHADE = colors.HexColor("#EEF1F5")     # Trading Book formula grey
YELLOW = colors.HexColor("#FFF7CC")    # Trading Book input yellow
RED = colors.HexColor("#B42318")
GREEN = colors.HexColor("#1E7B34")

FONT_FILES = {
    "Sheet": ["Carlito-Regular.ttf", "LiberationSans-Regular.ttf"],
    "Sheet-Bold": ["Carlito-Bold.ttf", "LiberationSans-Bold.ttf"],
    "Sheet-Italic": ["Carlito-Italic.ttf", "LiberationSans-Italic.ttf"],
    "Sheet-BoldItalic": ["Carlito-BoldItalic.ttf", "LiberationSans-BoldItalic.ttf"],
}
FONT_DIRS = [Path("/usr/share/fonts/truetype/crosextra"), Path("/usr/share/fonts/truetype/liberation"),
             Path.home() / "Library/Fonts", Path("C:/Windows/Fonts")]


def register_fonts() -> None:
    for name, files in FONT_FILES.items():
        path = next((d / f for f in files for d in FONT_DIRS if (d / f).exists()), None)
        if path is None:
            raise SystemExit("Install Carlito or Liberation Sans (TrueType) to build the sheet.")
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily("Sheet", normal="Sheet", bold="Sheet-Bold",
                                  italic="Sheet-Italic", boldItalic="Sheet-BoldItalic")


def styles(size: float) -> dict[str, ParagraphStyle]:
    lead = size * 1.24
    body = ParagraphStyle("body", fontName="Sheet", fontSize=size, leading=lead, textColor=INK)
    return {
        "body": body,
        "small": ParagraphStyle("small", parent=body, fontSize=size - 1, leading=(size - 1) * 1.22, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=body, fontSize=size - 0.6, leading=(size - 0.6) * 1.2),
        "cellb": ParagraphStyle("cellb", parent=body, fontName="Sheet-Bold", fontSize=size - 0.6,
                                leading=(size - 0.6) * 1.2),
        "h": ParagraphStyle("h", parent=body, fontName="Sheet-Bold", fontSize=size + 2.2,
                            leading=(size + 2.2) * 1.2, textColor=NAVY, spaceAfter=2.5),
        "num": ParagraphStyle("num", parent=body, fontName="Sheet-Bold", textColor=BLUE, alignment=2),
    }


def heading(n: int, text: str, s) -> Paragraph:
    return Paragraph(f'<font color="#3B6EA5">{n}</font>&nbsp;&nbsp;{text}', s["h"])


def grid(rows, widths, s, header=True, zebra=False, bold_first_col=False) -> Table:
    data = []
    for i, row in enumerate(rows):
        cells = []
        for j, v in enumerate(row):
            st = s["cellb"] if (header and i == 0) or (bold_first_col and j == 0) else s["cell"]
            cells.append(Paragraph(v, st))
        data.append(cells)
    t = Table(data, colWidths=widths)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), SHADE), ("LINEBELOW", (0, 0), (-1, 0), 0.6, NAVY)]
    if zebra:
        cmds += [("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F7F9FB")) for r in range(2, len(rows), 2)]
    t.setStyle(TableStyle(cmds))
    return t


# --------------------------------------------------------------------------- the pattern sketch

def candle(d: Drawing, x: float, w: float, o, h, l, c, y) -> None:
    up = c >= o
    d.add(Line(x, y(l), x, y(h), strokeColor=INK, strokeWidth=0.7))
    top, bot = y(max(o, c)), y(min(o, c))
    d.add(Rect(x - w / 2, bot, w, max(top - bot, 0.8), fillColor=colors.white if up else colors.HexColor("#4A5568"),
               strokeColor=INK, strokeWidth=0.7))


def sketch(width: float) -> Drawing:
    """Long example, left to right: 15-min trend, then the 5-min dip, confirm, entry, +2R and trail."""
    H = 120
    d = Drawing(width, H)
    d.add(Rect(0, 0, width, H, fillColor=colors.HexColor("#FBFCFD"), strokeColor=RULE, strokeWidth=0.6))
    font, bold, fs = "Sheet", "Sheet-Bold", 7.0

    # panel 1: the trend on the 15-minute chart
    d.add(String(9, H - 13, "Step 1 · 15-min chart", fontName=bold, fontSize=7.6, fillColor=NAVY))
    bars15 = [(100, 104, 98.5, 103.5), (103.5, 107.5, 101.5, 107), (107, 111.5, 104.8, 110.8)]
    ya = lambda p: 33 + (p - 97) * 4.6  # noqa: E731
    xa = [26, 52, 78]
    for x, b in zip(xa, bars15):
        candle(d, x, 11, *b, ya)
    d.add(Line(xa[0], ya(104), xa[2], ya(111.5), strokeColor=BLUE, strokeWidth=0.8, strokeDashArray=[2.2, 1.6]))
    d.add(Line(xa[0], ya(98.5), xa[2], ya(104.8), strokeColor=BLUE, strokeWidth=0.8, strokeDashArray=[2.2, 1.6]))
    d.add(String(9, 21, "Each bar: higher high", fontName=font, fontSize=fs, fillColor=INK))
    d.add(String(9, 12, "and higher low than the last", fontName=font, fontSize=fs, fillColor=INK))
    d.add(String(9, 3.5, "= setup (long)", fontName=bold, fontSize=fs, fillColor=NAVY))
    d.add(Line(112, 8, 112, H - 8, strokeColor=RULE, strokeWidth=0.6))

    # panel 2: the 5-minute chart
    d.add(String(122, H - 13, "Steps 2–7 · 5-min chart", fontName=bold, fontSize=7.6, fillColor=NAVY))
    bars5 = [(100.0, 102.5, 99.5, 102.0), (102.0, 104.75, 101.75, 104.25),
             (104.25, 104.5, 101.0, 101.5),      # dip: low under the previous bar's low
             (101.5, 104.0, 101.25, 103.75),     # confirm: closes above the dip's close
             (103.75, 106.5, 103.5, 106.25),     # entry fills at 104.25
             (106.25, 109.0, 105.75, 108.75),
             (108.75, 111.75, 108.25, 111.5),    # +2R reached: half off
             (111.5, 114.0, 110.75, 113.5),
             (113.5, 115.5, 112.75, 115.0)]
    yb = lambda p: 20 + (p - 99.0) * 5.3  # noqa: E731
    step = 26.0
    xs = [140 + i * step for i in range(len(bars5))]
    d.add(Rect(xs[2] - 9.5, 14, 2 * step, H - 32, fillColor=YELLOW, strokeColor=None))
    entry, stop = 104.25, 100.75
    target = entry + 2 * (entry - stop)
    x_end = xs[-1] + 12
    for p, col in ((entry, NAVY), (stop, RED), (target, GREEN)):
        d.add(Line(xs[3] - 7, yb(p), x_end, yb(p), strokeColor=col, strokeWidth=1.0))
    trail = [(xs[6], entry), (xs[7], 105.5), (xs[8], 108.0)]
    for (x0, p0), (x1, p1) in zip(trail, trail[1:] + [(x_end, 108.0)]):
        d.add(Line(x0 - 6, yb(p0), x1 - 6, yb(p0), strokeColor=BLUE, strokeWidth=0.9, strokeDashArray=[2, 1.5]))
        d.add(Line(x1 - 6, yb(p0), x1 - 6, yb(p1), strokeColor=BLUE, strokeWidth=0.9, strokeDashArray=[2, 1.5]))
    for x, b in zip(xs, bars5):
        candle(d, x, 9, *b, yb)
    d.add(String(xs[2], 5, "dip", fontName=bold, fontSize=fs, fillColor=INK, textAnchor="middle"))
    d.add(String(xs[3], 5, "confirm", fontName=bold, fontSize=fs, fillColor=INK, textAnchor="middle"))
    d.add(String(xs[4], 5, "fill", fontName=font, fontSize=fs, fillColor=MUTED, textAnchor="middle"))
    d.add(String(xs[6], yb(111.75) + 3, "half off", fontName=font, fontSize=fs, fillColor=GREEN, textAnchor="middle"))

    # R brackets
    bx = x_end + 5
    d.add(Line(bx, yb(stop), bx, yb(entry), strokeColor=RED, strokeWidth=1.2))
    d.add(Line(bx, yb(entry), bx, yb(target), strokeColor=GREEN, strokeWidth=1.2))
    d.add(String(bx + 3, (yb(stop) + yb(entry)) / 2 - 2.5, "1R", fontName=bold, fontSize=fs, fillColor=RED))
    d.add(String(bx + 3, (yb(entry) + yb(target)) / 2 - 2.5, "2R", fontName=bold, fontSize=fs, fillColor=GREEN))

    # level labels
    lx = bx + 20
    labels = [(target, GREEN, "+2R: sell half with a limit order", None),
              (108.0, BLUE, "Rest: stop trails 1 tick under", "the lowest of the last 3 lows"),
              (entry, NAVY, "Entry: buy stop 1 tick above", "the confirming bar's high"),
              (stop, RED, "Stop-loss: 1 tick under", "the dip bar's low")]
    for p, col, l1, l2 in labels:
        y = yb(p)
        d.add(String(lx, y + (1.0 if l2 else -2.4), l1, fontName=bold, fontSize=fs, fillColor=col))
        if l2:
            d.add(String(lx, y - 7.6, l2, fontName=font, fontSize=fs, fillColor=col))
    return d


# --------------------------------------------------------------------------- content

def steps_table(items, start: int, w: float, s) -> Table:
    rows = [[Paragraph(str(start + i), s["num"]), Paragraph(f"<b>{name}.</b> {text}", s["body"])]
            for i, (name, text) in enumerate(items)]
    t = Table(rows, colWidths=[11, w - 11])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (0, -1), 4), ("RIGHTPADDING", (1, 0), (1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8)]))
    return t


def blocks(s, W: float, gut: float):
    """Rows of the page: ("split", left, right, left share) or ("full", flowables)."""
    half = (W - gut) / 2
    B = lambda t: Paragraph(t, s["body"])  # noqa: E731

    what = [heading(1, "What it is", s), B(
        "A trend-following day trade in the E-mini S&amp;P 500 (ES). When the 15-minute chart is clearly trending, "
        "wait for a small dip on the 5-minute chart and buy as price turns back up. In a downtrend, wait for a small "
        "bounce and sell as it turns down. The loss is small and set in advance; take half the profit at twice your "
        "risk and let the rest ride until the trend turns.")]
    why = [heading(2, "Why it works", s), B(
        "After three steady 15-minute bars one way, a short pause often resolves in the same direction, so buying the "
        "pause gets you in with a tight stop instead of chasing. Trend-pullback entries are a staple of futures day "
        "trading, and S&amp;P 500 studies find intraday moves tend to carry on, most of all near the open and close "
        "(Gao et al., 2018).")]

    steps = [
        ("Trend", "When a 15-min bar closes, look at the last three. Each must have a <b>higher high and a higher "
                  "low</b> than the bar before. If so, you have a setup."),
        ("Dip", "On the 5-min chart, within the next three bars, wait for a bar whose <b>low goes below the previous "
                "bar's low</b>. Equal doesn't count. No dip in time: the setup is over; go back to step 1."),
        ("Confirm", "The <b>very next</b> 5-min bar must <b>close above the dip bar's close</b>. If not, a new dip "
                    "inside the same 15 minutes still counts; otherwise no trade."),
        ("Ticket", "As soon as the confirming bar closes, type both bars' high, low and close into the ticket. Trade "
                   "only if it says <b>GO</b>."),
        ("Order", "<b>Buy stop 1 tick above the confirming bar's high</b>, with a stop-loss 1 tick under the dip "
                  "bar's low on all contracts and a limit at +2R on half. Not filled in 10 minutes: cancel."),
        ("Manage", "When the +2R half fills, move the other half's stop to your entry price. After each 5-min bar, "
                   "raise it to 1 tick under the lowest low of the last three bars. Never lower it."),
        ("Exit", "If +2R isn't reached within 60 minutes of the fill, close everything at market. Always be flat by "
                 "15:55 New York."),
    ]
    two_col = Table([[steps_table(steps[:4], 1, half, s), steps_table(steps[4:], 5, half, s)]],
                    colWidths=[half + gut, half])
    two_col.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    cw = W / 6
    timing = grid([
        ["Setup", "Dip bar", "Confirming bar", "Ticket and order", "Entry order working", "In the trade"],
        ["A 15-min bar closes: check at :00, :15, :30, :45", "Within the next 15 min (three 5-min bars)",
         "The very next 5-min bar", "About 1 minute", "10 minutes, then cancel",
         "Up to 60 min to reach +2R; the rest can stay until 15:55 NY"],
    ], [cw] * 6, s)
    spot = [
        heading(3, "How to spot it and trade it", s),
        B("<b>Charts:</b> ES (December), a 15-minute and a 5-minute candle chart side by side, no indicators. Long "
          "shown; for a short, flip every high and low and sell instead of buy. 1 tick = 0.25 point. <b>R</b> is "
          "your risk on the trade: entry minus stop."),
        Spacer(1, 4), sketch(W), Spacer(1, 5),
        Paragraph("<b>Time you have</b> (usually 10–20 minutes from setup to order; most trades last under an hour)",
                  s["cellb"]),
        Spacer(1, 2), timing, Spacer(1, 6), two_col,
    ]

    lw = W * 0.45 - gut / 2
    rw = W - lw - gut
    size_tab = grid([
        ["Stop (points)", "2", "3", "4", "5", "6", "8", "10", "12"],
        ["ES contracts", "34*", "32", "24", "19", "16", "12", "9", "8"],
    ], [lw * 0.25] + [lw * 0.75 / 8] * 8, s, header=False, bold_first_col=True)
    size_tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), SHADE), ("ALIGN", (1, 0), (-1, -1), "CENTER")]))
    bullet = ParagraphStyle("bul", parent=s["body"], leftIndent=8, bulletIndent=0, spaceAfter=1.8,
                            bulletFontName="Sheet")
    BL = lambda t: Paragraph(t, bullet, bulletText="•")  # noqa: E731
    size = [
        heading(4, "Size it", s),
        BL("<b>Risk 0.5% of the CQG balance per trade</b>, about $5,000 on $1.0M. Stay at 0.5% until the team "
           "signs off 1%."),
        BL("<b>Contracts = $5,000 ÷ (stop in points × $50 + $5)</b>, rounded down. The ticket does this for you."),
        BL("<b>Never more than margin allows:</b> balance ÷ CQG margin per ES, about 34 at $1.0M and $28,600 a "
           "contract."),
        BL("<b>Split:</b> put half the contracts on the +2R limit and let the rest ride. Odd number: the extra one "
           "rides."),
        Spacer(1, 3), size_tab, Spacer(1, 1.5),
        Paragraph("Contracts at a $1.0M balance and 0.5% risk. *Capped by margin.", s["small"]),
    ]
    risk = [
        Paragraph("Risk rules: if this happens, do this", s["h"]),
        grid([
            ["If", "Do this"],
            ["The stop is under 2 or over 12 points from the entry", "Skip the trade"],
            ["The entry hasn't filled after 10 minutes", "Cancel it. Don't chase."],
            ["Price jumps through your stop", "Close at market now. Never widen a stop or add to a loser."],
            ["2 losing trades today, or 3 trades taken", "Stop trading CMES4 for the day"],
            ["US data (often 10:00 New York) or the Fed is due within 15 min", "Don't enter. Already in: leave the "
                                                                               "stop where it is."],
            ["You can't watch the screen for the next hour", "Don't enter"],
            ["CQG rejects the order for margin", "Cut the size to what margin allows"],
            ["The account is down 3% or more on the week", "Use 0.25% risk the following week"],
        ], [rw * 0.56, rw * 0.44], s, zebra=True),
    ]
    aw = W * 0.47 - gut / 2
    windows = grid([
        ["New setups only", "Morning", "Afternoon", "Flat by"],
        ["Dublin, to Fri 23 Oct", "14:45–16:30", "19:00–20:30", "20:55"],
        ["Dublin, from Mon 26 Oct", "13:45–15:30", "18:00–19:30", "19:55"],
        ["New York, all dates", "09:45–11:30", "14:00–15:30", "15:55"],
    ], [aw * 0.37, aw * 0.21, aw * 0.21, aw * 0.21], s)
    also_left = [
        heading(5, "Also important", s), windows, Spacer(1, 2),
        Paragraph("Wed 28 Oct (Fed at 18:00 Dublin): morning only, flat by 17:55. Fri 30 Oct: morning only, team flat "
                  "by 19:00. Skip the midday lull between the windows: trends stall there.", s["small"]),
    ]
    also_right = [Spacer(1, 15)] + [BL(t) for t in (
        "<b>Expect more losers than winners.</b> About one trade a day. In simulated tests about 1 trade in 4 reached "
        "+2R, and runs of 5 or more losers happened. Keep taking valid setups at the same size.",
        "<b>Daily minimum:</b> one trade of 5 or more ES also covers the 10 contracts.",
        "<b>Log it:</b> every setup in Decisions, taken or skipped, with the bar times; every trade in Trades with "
        "the ticket's numbers.",
        "<b>Not yet proven on real ES prices.</b> Stay at 0.5% until the team's backtest check passes.",
    )]
    return [("split", what, why, 0.5), ("full", spot), ("split", size, risk, 0.45),
            ("split", also_left, also_right, 0.47)]


def height(flowables, w: float) -> float:
    total = 0.0
    for f in flowables:
        _, h = f.wrap(w, 10_000)
        total += h + (f.getSpaceAfter() if hasattr(f, "getSpaceAfter") else 0)
    return total


def row_frames(row, M: float, W: float, gut: float):
    """[(x, width, flowables)] for one row."""
    if row[0] == "full":
        return [(M, W, row[1])]
    _, left, right, share = row
    lw = W * share - gut / 2
    return [(M, lw, left), (M + lw + gut, W - lw - gut, right)]


def build(path: Path) -> float:
    register_fonts()
    PW, PH = A4
    M, TOP, BOT, GUT, ROWGAP = 30, 28, 30, 16, 8
    W = PW - 2 * M
    for size in (9.0, 8.8, 8.6, 8.4, 8.2, 8.0, 7.8):
        s = styles(size)
        rows = blocks(s, W, GUT)
        heights = [max(height(fl, w) for _, w, fl in row_frames(r, M, W, GUT)) for r in rows]
        need = 44 + sum(heights) + ROWGAP * len(rows)
        if need <= PH - TOP - BOT:
            break
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    c.setTitle("CMES4 v2 trader's sheet")
    c.setAuthor("CME UG team")
    c.setSubject("CMES4 v2 rules on one page")
    y = PH - TOP
    c.setFillColor(NAVY)
    c.setFont("Sheet-Bold", 19)
    c.drawString(M, y - 16, "CMES4 v2")
    c.setFont("Sheet", 19)
    c.drawString(M + c.stringWidth("CMES4 v2 ", "Sheet-Bold", 19), y - 16, "trader's sheet")
    c.setFont("Sheet-Bold", 8.8)
    c.drawRightString(M + W, y - 16, "Risk 0.5% a trade · max 3 trades a day · flat by 15:55 New York")
    c.setFillColor(MUTED)
    c.setFont("Sheet", 8.6)
    c.drawString(M, y - 30, "E-mini S&P 500 (ES) day trade · CME University Trading Challenge, October 2026 · "
                            "use with the CMES4 v2 ticket (CMES4_v2_ticket.xlsx)")
    y -= 44
    for row, h in zip(rows, heights):
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(M, y + ROWGAP / 2 + 1, M + W, y + ROWGAP / 2 + 1)
        for x, w, fl in row_frames(row, M, W, GUT):
            fr = Frame(x, y - h - 2, w, h + 2, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            items = list(fl)
            fr.addFromList(items, c)
            if items:
                raise RuntimeError("block did not fit its frame")
        y -= h + ROWGAP
    c.setFont("Sheet", 7.2)
    c.setFillColor(MUTED)
    c.drawString(M, BOT - 16, "Full rules: playbook/cmes4-v2-rule-card.md · the ticket sizes each trade and says GO "
                              "or NO TRADE · prepared 9 Oct 2026")
    c.showPage()
    c.save()
    return size


if __name__ == "__main__":
    used = build(OUT)
    print(f"{OUT} (body {used} pt)")
