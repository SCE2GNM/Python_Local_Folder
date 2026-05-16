"""
Week 7 Revision Notes — PDF generator
Output: Week_7_Revision_Notes.pdf (same directory as this script)
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable

# ── Paths ────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "Week_7_Revision_Notes.pdf")

# ── Colours ──────────────────────────────────────────────────────────────────
TEAL       = colors.HexColor("#0D7377")   # primary heading colour
TEAL_LIGHT = colors.HexColor("#E8F5F5")   # heading background
DARK       = colors.HexColor("#1A1A2E")   # body dark
MID        = colors.HexColor("#4A4A6A")   # subheading
GREEN      = colors.HexColor("#27AE60")
RED        = colors.HexColor("#C0392B")
AMBER      = colors.HexColor("#E67E22")
BLUE       = colors.HexColor("#2471A3")
ROW_ALT    = colors.HexColor("#F4F9F9")
HEADER_ROW = colors.HexColor("#0D7377")
RULE       = colors.HexColor("#CCCCCC")

PAGE_W, PAGE_H = A4
L_MARGIN = R_MARGIN = 2.0 * cm
T_MARGIN = B_MARGIN = 2.2 * cm

# ── Styles ───────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def style(name, **kwargs):
    s = ParagraphStyle(name, **kwargs)
    return s

TITLE = style("Title",
    fontName="Helvetica-Bold", fontSize=26, textColor=TEAL,
    alignment=TA_CENTER, spaceAfter=6)

SUBTITLE = style("Subtitle",
    fontName="Helvetica", fontSize=13, textColor=MID,
    alignment=TA_CENTER, spaceAfter=4)

META = style("Meta",
    fontName="Helvetica", fontSize=10, textColor=MID,
    alignment=TA_CENTER, spaceAfter=2)

H1 = style("H1",
    fontName="Helvetica-Bold", fontSize=14, textColor=colors.white,
    backColor=TEAL, borderPad=6, spaceBefore=14, spaceAfter=8,
    leftIndent=-8, rightIndent=-8, leading=18)

H2 = style("H2",
    fontName="Helvetica-Bold", fontSize=11, textColor=TEAL,
    spaceBefore=10, spaceAfter=4, leading=15)

H3 = style("H3",
    fontName="Helvetica-Bold", fontSize=10, textColor=DARK,
    spaceBefore=6, spaceAfter=3, leading=14)

BODY = style("Body",
    fontName="Helvetica", fontSize=9.5, textColor=DARK,
    leading=14, spaceAfter=4, alignment=TA_JUSTIFY)

BULLET = style("Bullet",
    fontName="Helvetica", fontSize=9.5, textColor=DARK,
    leading=13, spaceAfter=3, leftIndent=14, firstLineIndent=-10)

BULLET2 = style("Bullet2",
    fontName="Helvetica", fontSize=9, textColor=MID,
    leading=13, spaceAfter=2, leftIndent=26, firstLineIndent=-10)

NOTE = style("Note",
    fontName="Helvetica-Oblique", fontSize=9, textColor=MID,
    leading=13, spaceAfter=4)

VERDICT_GO = style("VerdictGo",
    fontName="Helvetica-Bold", fontSize=11, textColor=GREEN,
    alignment=TA_CENTER, spaceAfter=4)

VERDICT_NOGO = style("VerdictNoGo",
    fontName="Helvetica-Bold", fontSize=11, textColor=RED,
    alignment=TA_CENTER, spaceAfter=4)

TABLE_HDR = dict(fontName="Helvetica-Bold", fontSize=9, textColor=colors.white)
TABLE_BODY= dict(fontName="Helvetica", fontSize=9, textColor=DARK)

# ── Helpers ──────────────────────────────────────────────────────────────────
def rule():
    return HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=6, spaceBefore=2)

def sp(h=6):
    return Spacer(1, h)

def h1(text):
    return Paragraph(f"  {text}", H1)

def h2(text):
    return Paragraph(text, H2)

def h3(text):
    return Paragraph(text, H3)

def body(text):
    return Paragraph(text, BODY)

def bullet(text, level=1):
    s = BULLET if level == 1 else BULLET2
    prefix = "•" if level == 1 else "–"
    return Paragraph(f"{prefix}  {text}", s)

def note(text):
    return Paragraph(f"<i>{text}</i>", NOTE)

def table(data, col_widths, row_colours=None, header=True):
    tbl = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style_cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0),  HEADER_ROW),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUND",(0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ("GRID",        (0, 0), (-1, -1), 0.5, RULE),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
    ]
    if row_colours:
        for (r, c_bg) in row_colours:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), c_bg))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl

# ── Page numbering ────────────────────────────────────────────────────────────
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MID)
    canvas.drawCentredString(PAGE_W / 2, 1.2 * cm,
        f"Week 7 Revision Notes  |  DeFi Quant Engineer Curriculum  |  Page {doc.page}")
    canvas.restoreState()

# ── Content ───────────────────────────────────────────────────────────────────
def build():
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=L_MARGIN, rightMargin=R_MARGIN,
        topMargin=T_MARGIN, bottomMargin=B_MARGIN,
    )
    W = PAGE_W - L_MARGIN - R_MARGIN
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story += [
        sp(60),
        Paragraph("Week 7 Revision Notes", TITLE),
        Paragraph("DeFi Quantitative Trading Engineer Curriculum", SUBTITLE),
        sp(8),
        rule(),
        sp(4),
        Paragraph("Greg (Gmac)  |  Week 7 of 24  |  2026-05-08 → 2026-05-16", META),
        Paragraph("Strategy Validation • Monte Carlo • Methodology Standards • Infrastructure", META),
        sp(4),
        rule(),
        PageBreak(),
    ]

    # ── Section 1: Week 7 Overview ────────────────────────────────────────────
    story += [h1("1.  Week 7 Overview")]

    story += [
        h2("Planned vs. Actual"),
        table(
            [
                ["Area", "Planned", "What Actually Happened"],
                ["BTC ADX", "Full validation pipeline", "Full pipeline completed → NO-GO decision"],
                ["BTC SMA", "Continue Stage B, run Monte Carlo", "Phases 1–4 complete → CONDITIONAL GO"],
                ["Monte Carlo", "Apply standard win-rate scenarios", "Methodology redesign → Option A (magnitude scaling)"],
                ["Leveraged bot", "Build day6_leveraged_bot.py", "Deferred — dynamic leverage framework required first"],
                ["File system", "Not planned", "Reorganised into 8 numbered folders (Week 7 close-out)"],
                ["EC2", "Not planned", "Full migration to new structure, cron paths updated"],
            ],
            [3.5*cm, 5.5*cm, 7.0*cm],
        ),
        sp(8),
    ]

    story += [
        h2("Key Decisions Made This Week"),
        bullet("<b>BTC ADX → NO-GO:</b> Post-2022 performance collapsed, stability FRAGILE — strategy does not hold up in modern market conditions."),
        bullet("<b>BTC SMA → CONDITIONAL GO:</b> SMA110/T30% confirmed as structural optimum. Five deployment conditions set."),
        bullet("<b>Monte Carlo methodology locked:</b> Option A (return magnitude scaling) adopted as standard for low win-rate, fat-tail trend-following strategies."),
        bullet("<b>Quarter-Kelly rejected for sizing:</b> Produces implied leverage at realistic degradation levels. Fixed 5–10% capital-at-risk recommended instead."),
        bullet("<b>First review date set:</b> 2026-07-16 — formal 2-month review of BTC SMA CONDITIONAL GO decision."),
        sp(10),
    ]

    # ── Section 2: Strategy Validation Results ────────────────────────────────
    story += [h1("2.  Strategy Validation Results")]

    # BTC ADX
    story += [
        h2("BTC ADX — NO-GO ✗"),
        Paragraph(
            "Full 4-phase pipeline completed. Strategy showed strong historical performance but failed "
            "on post-2022 stability and regime consistency. Decision: <b>NO-GO</b>.",
            BODY),
        sp(4),
        table(
            [
                ["Metric", "Full Period (2018–2025)", "Post-2022 (2022–2025)", "Threshold"],
                ["Annual Return",      "+28.4%",  "+6.2%",  "≥ +15%/yr"],
                ["Sortino Ratio",      "2.41",    "0.68",   "≥ 1.0"],
                ["Max Drawdown",       "−28.3%",  "−31.2%", "≤ −35%"],
                ["Win Rate",           "37%",     "18%",    "—"],
                ["Stability",          "MODERATE","FRAGILE", "≥ MARGINAL"],
                ["Walk-Forward",       "PASS",    "—",      "PASS"],
                ["Cross-Asset (ETH)",  "—",       "FAIL",   "PARTIAL PASS"],
            ],
            [4.5*cm, 3.5*cm, 3.5*cm, 3.0*cm],
            row_colours=[
                (2,  colors.HexColor("#FDEDEC")),  # post-2022 return row
                (5,  colors.HexColor("#FDEDEC")),  # stability row
                (7,  colors.HexColor("#FDEDEC")),  # cross-asset row
            ],
        ),
        sp(6),
        h3("Why NO-GO?"),
        bullet("Post-2022 annual return +6.2% — far below the +15%/yr deployment threshold."),
        bullet("Win rate halved from 37% (full period) to 18% (post-2022) — edge is disappearing."),
        bullet("Stability rating FRAGILE — Sharpe R² < 0.4, performance not robust across parameter variations."),
        bullet("ADX threshold sensitivity is extreme — tiny changes in ADX cutoff produce large Sharpe swings."),
        bullet("Strategy appears tuned to the 2018–2021 bull market; does not generalise to post-2022 conditions."),
        sp(12),
    ]

    # BTC SMA
    story += [
        h2("BTC SMA — CONDITIONAL GO ✓"),
        Paragraph(
            "Four-phase validation pipeline completed over Weeks 6–7. Primary candidate SMA110/T30% "
            "confirmed as structural optimum, not a boundary artefact (grid extended to T35%). "
            "Decision: <b>CONDITIONAL GO</b> — five deployment conditions must be met.",
            BODY),
        sp(4),
        table(
            [
                ["Metric", "Full Period (2018–2025)", "Post-2022 (2022–2025)", "Threshold"],
                ["Annual Return",      "+42.1%",  "+32.7%",  "≥ +15%/yr ✓"],
                ["Sortino Ratio",      "1.84",    "1.21",    "≥ 1.0 ✓"],
                ["Max Drawdown",       "−34.2%",  "−29.8%",  "≤ −35% ✓"],
                ["Win Rate",           "28%",     "26%",     "—"],
                ["Avg Win / Avg Loss", "4.2×",    "3.9×",    "Fat-tail profile ✓"],
                ["Stability",          "MARGINAL","MARGINAL", "≥ MARGINAL ✓"],
                ["Walk-Forward",       "PASS",    "—",       "PASS ✓"],
                ["Phase 3 Monte Carlo","Viable ≥20% magnitude","—","PASS ✓"],
                ["Phase 4 ETH Cross-Asset","PARTIAL PASS (Sortino 0.701)","—","PARTIAL ✓"],
            ],
            [4.5*cm, 3.5*cm, 3.5*cm, 3.0*cm],
        ),
        sp(6),
        h3("Five Deployment Conditions (must all be met before live deployment):"),
        bullet("Phase 5 leverage analysis completed — confirm 1× before adding leverage."),
        bullet("A021 emergency exit protocol implemented on EC2."),
        bullet("Fixed 5–10% capital-at-risk sizing adopted — Quarter-Kelly explicitly rejected."),
        bullet("Minimum $500 initial capital confirmed."),
        bullet("Full 13-section deployment card completed."),
        sp(6),
        h3("Key Parameters:"),
        table(
            [
                ["Parameter", "Value", "Notes"],
                ["SMA Period",      "110 days",  "Confirmed optimum — not boundary"],
                ["Trail Stop",      "30%",        "T30% — grid extended to T35% to confirm"],
                ["Entry Signal",    "Price > SMA110", "Daily close"],
                ["Exit Signal",     "Trailing stop triggered", "30% from peak"],
                ["Position Sizing", "Fixed 5–10% CAR", "Quarter-Kelly rejected"],
                ["Review Date",     "2026-07-16",  "2-month CONDITIONAL GO review"],
            ],
            [3.5*cm, 4.0*cm, 8.0*cm],
        ),
        sp(6),
        h3("Phase 4 ETH Cross-Asset — PARTIAL PASS:"),
        bullet("ETH Sortino on BTC SMA signals: 0.701 — below 0.8 threshold but above 0.5 floor."),
        bullet("ETH 2022 return: −57.5% vs BTC −6.6% — confirms asset-specificity of the strategy."),
        bullet("Strategy is a BTC momentum strategy. ETH behaves differently in bear markets."),
        bullet("PARTIAL PASS recorded — does not block CONDITIONAL GO but noted in risk register."),
        sp(10),
    ]

    # ── Section 3: Monte Carlo ────────────────────────────────────────────────
    story += [h1("3.  Monte Carlo — What It Is and What We Found"), PageBreak()]

    story += [
        h2("Plain English: What is Monte Carlo Analysis?"),
        body(
            "A Monte Carlo simulation runs a strategy thousands of times, each time with slightly "
            "different assumptions about future trade outcomes. Instead of asking 'what did this strategy "
            "return historically?', it asks: 'across the full range of plausible futures, what is the "
            "distribution of outcomes?' The result is not a single number — it is a fan of equity curves "
            "showing best case, worst case, median, and everything in between."
        ),
        body(
            "The key output is a percentile table: P5 (5th percentile — bad luck scenario), "
            "P25, P50 (median), P75, P95 (good luck scenario). A robust strategy should have "
            "a positive P25 — meaning it makes money in 75% of simulated futures, not just the historical one."
        ),
        sp(8),
        h2("Option A — Return Magnitude Scaling (our chosen method)"),
        body(
            "Standard Monte Carlo applies to strategies with stable win rates (mean-reversion, options). "
            "For BTC SMA, win rate is only 23–33% but average wins are 4–5× average losses — a fat-tail "
            "payoff profile. Standard win-rate scenarios are inappropriate because they assume the shape "
            "of wins and losses stays fixed."
        ),
        body(
            "<b>Option A scales the magnitude of winning trades</b> (positive returns × factor), "
            "leaving losing trades unchanged. This tests whether the strategy's edge — large infrequent "
            "winners — holds at lower magnitudes. If the big wins were 20% smaller in real life, "
            "would the strategy still work?"
        ),
        body(
            "Option B (bootstrap resampling) was also considered but rejected for this strategy: "
            "bootstrapping from a 7-year sample with only ~30 trades introduces significant sampling error. "
            "Option A is more interpretable and directly tests the economic question."
        ),
        sp(8),
        h2("Key Monte Carlo Findings — BTC SMA SMA110/T30%"),
        table(
            [
                ["Magnitude Scale", "P5",    "P25",   "P50 (Median)", "P75",   "P95",   "Verdict"],
                ["100% (baseline)", "+318%", "+680%", "+1,240%",      "+2,100%","+4,800%","—"],
                ["80%",             "+180%", "+420%", "+890%",        "+1,600%","+3,900%","PASS"],
                ["60%",             "+72%",  "+240%", "+580%",        "+1,100%","+2,700%","PASS"],
                ["40%",             "+8%",   "+85%",  "+290%",        "+620%", "+1,500%", "PASS"],
                ["20%",             "−18%",  "+12%",  "+88%",         "+240%", "+680%",   "MARGINAL"],
                ["10%",             "−61%",  "−28%",  "+14%",         "+89%",  "+310%",   "FAIL"],
            ],
            [2.8*cm, 1.8*cm, 1.8*cm, 2.8*cm, 1.8*cm, 2.8*cm, 2.0*cm],
            row_colours=[
                (5, colors.HexColor("#FEF9E7")),
                (6, colors.HexColor("#FDEDEC")),
            ],
        ),
        sp(6),
        h3("Three Critical Findings:"),
        bullet(
            "<b>Viable to 20% magnitude.</b> At 20% scale (P50 still positive), the strategy survives "
            "significant degradation. P10 first turns negative at 20% scale — a meaningful safety margin."
        ),
        bullet(
            "<b>Quarter-Kelly is inappropriate for this strategy.</b> At 100% magnitude, Quarter-Kelly "
            "suggests 47.7% position sizing — which implies leverage. At 40% magnitude, it still suggests "
            "22%. For fat-tail strategies with low win rates, Kelly-based sizing is theoretically invalid "
            "(Kelly assumes log-normal returns). Fixed 5–10% capital-at-risk is the correct approach."
        ),
        bullet(
            "<b>Extreme dispersion — P5/P95 ratio ≈ 100:1.</b> At baseline, P5 is +318% and P95 is +4,800%. "
            "This is expected for a strategy with a handful of massive wins — path dependency is enormous. "
            "Two missed entry signals or one early stop-out can halve the terminal value. This reinforces "
            "the importance of rule-based execution with no discretionary overrides."
        ),
        sp(10),
    ]

    # ── Section 4: Methodology Standards ─────────────────────────────────────
    story += [h1("4.  Methodology Standards Added This Week")]

    story += [
        table(
            [
                ["Standard", "Description", "Trigger"],
                ["MS-001\nFat-Tail Warning",
                 "Power law α < 3 → Sharpe, Sortino, and Kelly all assume normality. "
                 "Always report kurtosis. Flag if excess kurtosis > 5.",
                 "BTC SMA return distribution analysis"],
                ["MS-002\nMonte Carlo Mandatory",
                 "All strategies must complete Monte Carlo before CONDITIONAL GO. "
                 "Trend-following → Option A magnitude scaling. "
                 "Mean reversion → win-rate scenario table.",
                 "BTC SMA Phase 3"],
                ["MS-003\nRegime-Based Review",
                 "Low-frequency strategies (≤ 30 trades/yr) must report pre/post-2022 "
                 "metrics separately. Post-2022 annual return ≥ +15% required for GO.",
                 "BTC ADX post-2022 collapse"],
                ["MS-004\nQuarter-Kelly Sizing",
                 "Quarter-Kelly is the maximum for unvalidated momentum strategies. "
                 "For fat-tail strategies, use fixed 5–10% CAR instead. "
                 "Never use full Kelly on live capital.",
                 "Monte Carlo sizing analysis"],
                ["MS-005\nDynamic Leverage",
                 "Fixed leverage (e.g. 1.9×) is not permitted for deployment. "
                 "Leverage must scale with trend strength or volatility. "
                 "Design required before leveraged bot build.",
                 "Leveraged bot deferral"],
                ["MS-006\nExchange Failure Risk",
                 "All bots must implement A021 emergency exit protocol. "
                 "Reference incidents: Binance October 2025 (withdrawal freeze), "
                 "Binance March 2023 (USDC depeg). Bot must detect and handle gracefully.",
                 "A021 risk register item"],
            ],
            [2.0*cm, 9.5*cm, 4.5*cm],
        ),
        sp(10),
    ]

    # ── Section 5: Key Concepts ───────────────────────────────────────────────
    story += [h1("5.  Key Concepts Learned This Week"), PageBreak()]

    concepts = [
        (
            "ADX — Average Directional Index",
            [
                "Measures trend <i>strength</i>, not direction. Range 0–100. Above 25 = trending.",
                "Derived from +DI and −DI (directional movement indicators).",
                "ADX rising = trend strengthening; ADX falling = trend weakening.",
                "Does not indicate bullish or bearish — only how strong the current move is.",
                "Reference: ETH ADX Deployment Card v1 (03_DEPLOYMENT_CARDS/).",
            ]
        ),
        (
            "ATR — Average True Range",
            [
                "Measures market <i>volatility</i> — the typical daily price range in absolute terms.",
                "True Range = max(High−Low, |High−PrevClose|, |Low−PrevClose|).",
                "ATR = rolling average of True Range (typically 14 days).",
                "Used for stop-loss placement: 'stop at 2× ATR below entry' adapts to current volatility.",
                "Reference: ATR Explainer Card v1 (03_DEPLOYMENT_CARDS/).",
            ]
        ),
        (
            "Kelly Criterion — Corrected Understanding",
            [
                "Kelly fraction = (edge / odds) = fraction of bankroll to risk per bet.",
                "<b>Common misconception:</b> Kelly is a risk fraction, not a capital allocation percentage.",
                "Full Kelly maximises geometric growth but produces catastrophic drawdowns in practice.",
                "Quarter-Kelly (25% of full Kelly) is the practical maximum for unvalidated strategies.",
                "For fat-tail strategies (low win rate, large avg win), Kelly is theoretically invalid — use fixed sizing.",
            ]
        ),
        (
            "Fat Tails and Power Law Distributions",
            [
                "Normal distribution: extreme events are astronomically rare (6σ = once in billions of years).",
                "Power law: extreme events happen regularly — BTC has had 20+ moves > 5σ since 2018.",
                "Power law α < 3 → variance is mathematically infinite; Sharpe ratio is meaningless.",
                "Consequence: Sharpe, Sortino, and Kelly all underestimate risk for crypto strategies.",
                "Always report kurtosis and flag if excess kurtosis > 5 (fat-tail warning).",
            ]
        ),
        (
            "Hurst Exponent",
            [
                "Measures whether a time series is trending, mean-reverting, or random.",
                "H > 0.5 → trending (momentum strategies work); H < 0.5 → mean-reverting; H ≈ 0.5 → random walk.",
                "BTC long-term: H ≈ 0.58–0.62 (mild trending tendency).",
                "Regime-dependent — Hurst changes across market phases (bull, bear, consolidation).",
                "Deferred for deeper study in Week 9 (volatility and regime-switching session).",
            ]
        ),
        (
            "Regime Detection Methods",
            [
                "<b>1. SMA-based:</b> Price above/below SMA200 = bull/bear regime. Simple, lagging.",
                "<b>2. Volatility-based:</b> High ATR or VIX = stressed regime. Fast, noisy.",
                "<b>3. ADX-based:</b> ADX > 25 = trending regime; ADX < 20 = ranging regime.",
                "<b>4. Hidden Markov Model (HMM):</b> Statistical model fitted to returns to infer latent regime states. Most rigorous but complex.",
                "Week 9 will implement and compare at least methods 1 and 3.",
            ]
        ),
        (
            "Confidence Intervals — Standard vs. Monte Carlo",
            [
                "<b>Standard CI:</b> Assumes normality. Computed from historical standard deviation. Unreliable for fat-tail assets.",
                "<b>Monte Carlo CI:</b> No distributional assumption. Runs thousands of simulations. Reports percentile range directly.",
                "For crypto strategies, always prefer Monte Carlo CIs over parametric CIs.",
                "The gap between P5 and P95 reveals the true uncertainty — much wider than a standard 90% CI.",
            ]
        ),
    ]

    for title, points in concepts:
        block = [h2(title)]
        for p in points:
            block.append(bullet(p))
        block.append(sp(8))
        story += block

    # ── Section 6: Live Portfolio Status ─────────────────────────────────────
    story += [h1("6.  Live Portfolio Status"), PageBreak()]

    story += [
        table(
            [
                ["Strategy",       "Status",         "Capital",  "Position", "Notes"],
                ["ETH ADX",        "LIVE",            "$1,000",   "FLAT",     "Trailing stop active. Cron 00:05 UTC daily."],
                ["ETH RSI",        "LIVE (validation)","$150",    "FLAT",     "Validation sizing. Daily 00:06 UTC."],
                ["BTC SMA",        "CONDITIONAL GO",  "$0",       "Not deployed","5 conditions must be met before deployment."],
                ["BTC ADX",        "NO-GO",           "$0",       "Rejected", "Permanently rejected. Do not redeploy."],
                ["Leveraged Bot",  "PAUSED",          "—",        "—",        "Dynamic leverage framework required first."],
                ["Portfolio Mgr",  "LIVE",            "$1,150",   "—",        "Weekly rebalance Monday 01:00 UTC."],
            ],
            [2.8*cm, 3.0*cm, 2.0*cm, 2.5*cm, 6.2*cm],
            row_colours=[
                (3, colors.HexColor("#FDEDEC")),
                (4, colors.HexColor("#FEF9E7")),
            ],
        ),
        sp(8),
        h2("Portfolio Allocation (as at 2026-05-13)"),
        table(
            [
                ["Strategy",  "Allocation", "Reserved Capital", "Status"],
                ["ETH ADX",   "50%",        "$1,000",           "FLAT — awaiting entry signal"],
                ["ETH RSI",   "7.5%",       "$150",             "FLAT — validation mode"],
                ["BTC SMA",   "0%",         "$0",               "Not deployed"],
                ["Cash",      "42.5%",      "$850",             "Available for future strategies"],
            ],
            [3.5*cm, 2.5*cm, 3.5*cm, 6.5*cm],
        ),
        sp(8),
        h2("Bot Infrastructure"),
        table(
            [
                ["Bot File",              "Location",           "Runs",                "Log"],
                ["day5_production_bot.py","05_BOTS/",           "00:05, 06:05, 12:05, 18:05 UTC","adx_strategy.log"],
                ["rsi_production_bot.py", "05_BOTS/",           "00:06 UTC daily",     "rsi_strategy.log"],
                ["portfolio_rebalance.py","Project root",       "Monday 01:00 UTC",    "adx_strategy.log"],
            ],
            [4.5*cm, 3.0*cm, 4.5*cm, 4.0*cm],
        ),
        sp(6),
        note("EC2 connection: ssh -i ~/.ssh/trading-bot-key.pem ubuntu@3.104.101.30  (temporary IP — Elastic IP required)"),
        sp(10),
    ]

    # ── Section 7: Infrastructure Changes ────────────────────────────────────
    story += [h1("7.  Infrastructure Changes")]

    story += [
        h2("File System Reorganisation"),
        body(
            "The project root was reorganised from a flat structure into 8 numbered folders. "
            "All 148 files moved using git mv (preserving history). Completed as a single clean "
            "commit (bd25f40) during Week 7 close-out."
        ),
        sp(4),
        table(
            [
                ["Folder",             "Contents"],
                ["00_MASTER/",         "Living documents: LEARNING_LOG, METHODOLOGY_STANDARDS, STRATEGY_RESEARCH_PIPELINE, STRATEGY_IDEAS_LOG, STRATEGIC_FRAMEWORK, CURRICULUM_OPERATING_MANUAL"],
                ["01_RISK_REGISTERS/", "All risk register files (ETH ADX, ETH RSI, BTC SMA, RISK_AND_ASSUMPTIONS_REGISTER)"],
                ["02_TEMPLATES/",      "STRATEGY_DEPLOYMENT_TEMPLATE, STRATEGY_RISK_REGISTER_TEMPLATE, LIVE_TRADING_CHECKLIST"],
                ["03_DEPLOYMENT_CARDS/","All HTML deployment cards and explainers"],
                ["04_WEEKLY_SUMMARIES/","All WEEK_N_ files: thread starters, summaries, research briefs, agenda notes"],
                ["05_BOTS/",           "day5_production_bot.py, rsi_production_bot.py, portfolio_manager.py, portfolio_rebalance.py, core/"],
                ["06_BACKTESTS/",      "All Week_N_Notebooks/ research folders"],
                ["07_DATA/",           "Runtime state files: bot_state.json, rsi_bot_state.json, portfolio_state.json, performance.json"],
            ],
            [3.5*cm, 12.5*cm],
        ),
        sp(8),
        h2("EC2 Migration"),
        bullet("State files moved from data/ to 07_DATA/ before git pull (preserving live bot state)."),
        bullet("git pull blocked by two conflicts — resolved with git stash and portfolio_state.json backup/restore."),
        bullet("Crontab updated: Week_4_Notebooks/ paths → 05_BOTS/ paths."),
        bullet("portfolio_rebalance.py remains at project root (separate script, not moved)."),
        bullet("EC2 instance received new IP (3.104.101.30) after restart. Elastic IP not yet allocated — Week 8 Task 1."),
        sp(8),
        h2("Deployment Card Template — v2.0 (13 Sections)"),
        table(
            [
                ["Section", "Title", "Key Requirement"],
                ["1",  "Strategy Overview",          "Name, asset, signal, version"],
                ["2",  "Validation Status",          "Phase 1–5 checklist"],
                ["3",  "Performance Summary",        "5 core metrics table"],
                ["4",  "Risk Register",              "Link to register file"],
                ["5",  "Parameter Sensitivity",      "Heatmap + stability rating"],
                ["6",  "Equity Curve",               "Log scale, $1 normalised, vs B&H, drawdown sub-panel"],
                ["7",  "Pre/Post-2022 Regime Split", "Full metrics split table, ≥+15%/yr post-2022"],
                ["8",  "Monte Carlo",                "Option A (trend-following) or win-rate scenarios (mean reversion)"],
                ["9",  "Bot Architecture",           "State machine, file paths, cron schedule"],
                ["10", "Independent Review",         "Peer review checklist"],
                ["11", "Sign-Off",                   "GO/NO-GO decision block, conditions, date"],
                ["12", "Future Improvement Ideas",   "ID, rationale, priority, status table"],
                ["13", "Colour Coding",              "Teal=BTC SMA, Blue=ETH ADX, Orange=ETH RSI, Grey=rejected"],
            ],
            [1.2*cm, 4.5*cm, 10.3*cm],
        ),
        sp(8),
        h2("Versioning — Single Source of Truth"),
        bullet("All living documents consolidated into 00_MASTER/. No more v7 suffixes."),
        bullet("LEARNING_LOG_v7.md → 00_MASTER/LEARNING_LOG.md"),
        bullet("STRATEGY_RESEARCH_PIPELINE_v7.md → 00_MASTER/STRATEGY_RESEARCH_PIPELINE.md"),
        bullet("PROJECT_REFERENCE.html updated: all 120 file:// links updated to new folder paths."),
        sp(10),
    ]

    # ── Section 8: Week 8 Priorities ─────────────────────────────────────────
    story += [h1("8.  Week 8 Priorities")]

    story += [
        table(
            [
                ["Priority", "Task",                               "Notes"],
                ["1",  "Elastic IP — AWS Console",
                       "Prevent IP changing on restart. Cost ~$0.005/hr running, free stopped."],
                ["2",  "BTC SMA Phase 5 — Leverage Analysis",
                       "Confirm 1× is correct before adding leverage. Required for deployment card."],
                ["3",  "BTC SMA Deployment Card",
                       "Full 13-section card. Must complete Phase 5 first."],
                ["4",  "A022: ETH ADX Monte Carlo",
                       "MAJOR priority. Required before any leveraged ETH ADX deployment."],
                ["5",  "ETH RSI Stability (RR-RSI-006)",
                       "Outstanding from Week 7 risk register."],
                ["6",  "Dynamic Leverage Framework",
                       "Design and backtest. Required before leveraged bot build."],
                ["7",  "Donchian Channel Breakout",
                       "Priority 1 momentum strategy. Begin full validation pipeline."],
                ["8",  "II-001: Telegram Message Redesign",
                       "Implement before leveraged bot deployment."],
                ["9",  "Leveraged Bot (day6_leveraged_bot.py)",
                       "Do NOT build until dynamic leverage framework is complete."],
            ],
            [1.5*cm, 5.5*cm, 9.0*cm],
        ),
        sp(8),
        h2("Week 8 Theme"),
        body(
            "Week 8 consolidates the research pipeline established in Weeks 6–7. The primary goal is "
            "to get BTC SMA from CONDITIONAL GO to a fully documented, deployment-ready card with "
            "Phase 5 leverage analysis complete. The secondary goal is Monte Carlo for ETH ADX (A022), "
            "which blocks leveraged deployment. Donchian Channel represents the first new strategy "
            "entering the validation pipeline."
        ),
        sp(8),
        h2("Methodology Standards in Force (as at Week 7)"),
        bullet("MS-001: Fat-tail warning — report kurtosis, flag excess kurtosis > 5."),
        bullet("MS-002: Monte Carlo mandatory before CONDITIONAL GO."),
        bullet("MS-003: Pre/post-2022 regime split required for all strategy reviews."),
        bullet("MS-004: Quarter-Kelly maximum for momentum; fixed 5–10% CAR for fat-tail strategies."),
        bullet("MS-005: Dynamic leverage required — fixed multipliers not permitted."),
        bullet("MS-006: A021 emergency exit protocol required on all live bots."),
        sp(20),
        rule(),
        Paragraph(
            "Week 7 complete — 7 of 24 weeks (29%). 17 weeks remaining.",
            style("Footer2", fontName="Helvetica-Oblique", fontSize=9,
                  textColor=MID, alignment=TA_CENTER)
        ),
        Paragraph(
            "BTC ADX: NO-GO  |  BTC SMA: CONDITIONAL GO  |  ETH ADX: LIVE  |  ETH RSI: LIVE (validation)",
            style("Footer3", fontName="Helvetica-Bold", fontSize=9,
                  textColor=TEAL, alignment=TA_CENTER, spaceBefore=4)
        ),
    ]

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"Saved: {OUT}")

if __name__ == "__main__":
    build()
