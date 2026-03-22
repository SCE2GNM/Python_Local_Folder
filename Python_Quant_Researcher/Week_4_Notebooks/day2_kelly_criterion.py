# [FILE] day2_kelly_criterion.py
# PURPOSE: Calculate optimal position sizing using the Kelly Criterion
#
# WHAT IS THE KELLY CRITERION?
# Invented by John Kelly at Bell Labs in 1956, originally to solve
# signal noise problems in telephone lines. Gamblers and traders
# quickly realised it solved their problem too:
# "Given my edge, how much should I bet each time?"
#
# The formula finds the position size that MAXIMISES long-run
# account growth while avoiding ruin.
#
# Too small → you grow too slowly, leaving money on the table
# Too large → one bad streak wipes you out (ruin)
# Kelly     → the mathematical sweet spot between the two
#
# ANALOGY:
# Imagine you have a coin that lands heads 60% of the time.
# You can bet any amount per flip.
# - Bet 1% each time → very safe but tiny growth
# - Bet 99% each time → one tail and you're nearly wiped out
# - Kelly formula → bet exactly 20% each time (optimal growth)
#
# THE FORMULA:
# f* = (p × b - q) / b
#
# where:
#   f* = fraction of capital to bet (what we're solving for)
#   p  = probability of winning (win rate)
#   q  = probability of losing (1 - win rate)
#   b  = ratio of average win to average loss

# ── Imports ───────────────────────────────────────────────────────────────────

import json                              # [LIBRARY] load backtest results
import numpy as np                       # [LIBRARY] calculations
import logging                           # [LIBRARY] logging

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level   = logging.INFO,
    format  = '%(asctime)s | %(levelname)s | %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── Step 1: Load Backtest Results ─────────────────────────────────────────────
# We use the real numbers from your ADX 20/10 validation on Day 1.
# This ensures Kelly sizing is based on YOUR actual strategy performance,
# not generic assumptions.

print("=" * 60)
print("KELLY CRITERION POSITION SIZING")
print("=" * 60)

# Load the JSON file saved during Day 1 validation
results_path = 'Week_4_Notebooks/daily_validation_results.json'

try:
    with open(results_path, 'r') as f:
        backtest = json.load(f)          # [VARIABLE - dict] your backtest results
    print(f"\n✅ Loaded backtest results from Day 1")
except FileNotFoundError:
    # Fallback to known values if file not found
    print(f"\n⚠️  Results file not found — using known Week 2 values")
    backtest = {
        'total_return':    40.5415,      # 4,054% total
        'annual_return':   0.5787,       # 57.87% per year
        'sharpe':          1.111,
        'max_drawdown':   -0.4812,
        'total_trades':    193,
        'trades_per_year': 23.5
    }

print(f"\nBacktest statistics:")
print(f"  Total return:    {backtest['total_return']:.2%}")
print(f"  Annual return:   {backtest['annual_return']:.2%}")
print(f"  Sharpe ratio:    {backtest['sharpe']:.3f}")
print(f"  Max drawdown:    {backtest['max_drawdown']:.2%}")
print(f"  Total trades:    {backtest['total_trades']}")
print(f"  Trades/year:     {backtest['trades_per_year']}")

# ── Step 2: Derive Kelly Inputs ───────────────────────────────────────────────
# The Kelly formula needs win rate, avg win, avg loss.
# We derive these from backtest statistics.

print(f"\n{'─' * 60}")
print(f"DERIVING KELLY INPUTS FROM BACKTEST")
print(f"{'─' * 60}")

# Stop loss is fixed at 5% — this IS our average loss per losing trade
# (assuming stop-loss fires on most losing trades, which it should)
AVG_LOSS_PCT = 0.05                      # [VARIABLE - float] 5% per losing trade

# Estimate average win from total return and trade count
# Logic: total_return = (winners × avg_win) - (losers × avg_loss)
# We need to estimate win rate first, then solve for avg_win

# Historical ADX trend-following strategies typically win 45-55% of trades
# We'll estimate from the backtest: if strategy returned 57.87%/year
# with 23.5 trades/year, average trade return ≈ annual_return / trades_per_year
avg_trade_return = (                     # [VARIABLE - float] avg return per trade
    backtest['annual_return'] / backtest['trades_per_year']
)

print(f"\n  Average trade return: {avg_trade_return:.2%}")
print(f"  (Annual return ÷ trades per year)")

# Estimate win rate
# For ADX trend-following strategies, historical win rate is typically 45-55%
# We'll use a conservative 50% as our estimate
# In Week 5+ we'll calculate this precisely from live trade logs
WIN_RATE = 0.50                          # [VARIABLE - float] estimated win probability
LOSS_RATE = 1 - WIN_RATE                 # [VARIABLE - float] estimated loss probability

# Solve for average win:
# avg_trade_return = (win_rate × avg_win) - (loss_rate × avg_loss)
# avg_win = (avg_trade_return + loss_rate × avg_loss) / win_rate
avg_win_pct = (                          # [VARIABLE - float] avg win per winning trade
    (avg_trade_return + LOSS_RATE * AVG_LOSS_PCT) / WIN_RATE
)

print(f"\n  Estimated inputs:")
print(f"  Win rate:         {WIN_RATE:.0%}")
print(f"  Avg win:          {avg_win_pct:.2%} per winning trade")
print(f"  Avg loss:         {AVG_LOSS_PCT:.2%} per losing trade")
print(f"  Win/loss ratio:   {avg_win_pct/AVG_LOSS_PCT:.2f}x")

# ── Step 3: Apply Kelly Formula ───────────────────────────────────────────────

print(f"\n{'─' * 60}")
print(f"KELLY FORMULA CALCULATION")
print(f"{'─' * 60}")

# Kelly formula: f* = (p × b - q) / b
# where b = avg_win / avg_loss (the reward-to-risk ratio)

b = avg_win_pct / AVG_LOSS_PCT           # [VARIABLE - float] reward:risk ratio
p = WIN_RATE                             # [VARIABLE - float] win probability
q = LOSS_RATE                            # [VARIABLE - float] loss probability

full_kelly = (p * b - q) / b            # [VARIABLE - float] full Kelly fraction

print(f"\n  b (reward:risk ratio): {b:.2f}")
print(f"  p (win probability):   {p:.0%}")
print(f"  q (loss probability):  {q:.0%}")
print(f"\n  Full Kelly: f* = ({p} × {b:.2f} - {q}) / {b:.2f}")
print(f"  Full Kelly: f* = {full_kelly:.2%} of capital per trade")

# ── Step 4: Apply Half-Kelly ──────────────────────────────────────────────────
# Full Kelly is mathematically optimal but dangerously aggressive.
# A string of losses with Full Kelly causes severe account damage.
#
# EXAMPLE of Full Kelly risk:
#   10 losing trades in a row (unlikely but possible):
#   Full Kelly 25%: $1,000 → $56 (94% loss!)
#   Half Kelly 12.5%: $1,000 → $270 (73% loss — bad but survivable)
#
# Professional quants universally use Half-Kelly or less.
# It gives ~75% of Full Kelly's growth with dramatically less risk.

half_kelly = full_kelly * 0.5            # [VARIABLE - float] Half-Kelly fraction

# Apply a maximum cap — never risk more than 25% regardless of Kelly
MAX_KELLY = 0.25                         # [VARIABLE - float] absolute ceiling
safe_kelly = min(half_kelly, MAX_KELLY)  # [VARIABLE - float] our final position size

print(f"\n  Half Kelly:  {half_kelly:.2%} of capital per trade")
print(f"  Maximum cap: {MAX_KELLY:.0%} (absolute ceiling)")
print(f"  Final Kelly: {safe_kelly:.2%} of capital per trade")

# ── Step 5: Translate to Dollar Amounts ───────────────────────────────────────

print(f"\n{'─' * 60}")
print(f"POSITION SIZES AT DIFFERENT ACCOUNT VALUES")
print(f"{'─' * 60}")

account_sizes = [1000, 1500, 2000, 5000, 10000]  # [VARIABLE - list] example sizes

print(f"\n  {'Account':>10}  {'Full Kelly':>12}  {'Half Kelly':>12}  {'Recommended':>12}")
print(f"  {'─'*10}  {'─'*12}  {'─'*12}  {'─'*12}")

for account in account_sizes:
    fk_size   = account * full_kelly     # [VARIABLE - float] full Kelly position
    hk_size   = account * half_kelly     # [VARIABLE - float] half Kelly position
    rec_size  = account * safe_kelly     # [VARIABLE - float] recommended position
    print(f"  ${account:>9,}  ${fk_size:>11,.2f}  ${hk_size:>11,.2f}  ${rec_size:>11,.2f}")

# ── Step 6: Compare to Current Risk Config ────────────────────────────────────

print(f"\n{'─' * 60}")
print(f"COMPARISON TO CURRENT RISK CONFIG")
print(f"{'─' * 60}")

current_pct = 0.95                       # [VARIABLE - float] what day2_risk_manager uses

print(f"\n  Current config:  {current_pct:.0%} of account per trade")
print(f"  Kelly suggests:  {safe_kelly:.2%} of account per trade")
print(f"\n  Verdict:")

if safe_kelly < current_pct:
    print(f"  ⚠️  Current sizing ({current_pct:.0%}) is MORE aggressive than Kelly ({safe_kelly:.2%})")
    print(f"  Kelly recommends reducing position size for optimal growth")
    print(f"  We will update RISK_CONFIG to use {safe_kelly:.2%}")
else:
    print(f"  ✅ Current sizing is within Kelly bounds")

# ── Step 7: Final Recommendation ──────────────────────────────────────────────

print(f"\n{'=' * 60}")
print(f"FINAL POSITION SIZING RECOMMENDATION")
print(f"{'=' * 60}")
print(f"\n  Strategy:        ADX 20/10 on ETHUSDT daily")
print(f"  Win rate:        {WIN_RATE:.0%} (estimated)")
print(f"  Avg win:         {avg_win_pct:.2%}")
print(f"  Avg loss:        {AVG_LOSS_PCT:.2%} (stop-loss)")
print(f"  Full Kelly:      {full_kelly:.2%}")
print(f"  Half Kelly:      {half_kelly:.2%}")
print(f"  RECOMMENDED:     {safe_kelly:.2%} of account per trade")
print(f"\n  For $1,000 account:")
print(f"  → Trade size:    ${1000 * safe_kelly:,.2f} per signal")
print(f"  → Stop-loss:     ${1000 * safe_kelly * 0.05:,.2f} max loss per trade")
print(f"\n  This sizing will:")
print(f"  ✅ Compound returns as account grows")
print(f"  ✅ Reduce exposure as account shrinks")
print(f"  ✅ Survive extended losing streaks")
print(f"  ✅ Maximise long-run growth rate")
print(f"{'=' * 60}\n")

# ── Save Kelly results ────────────────────────────────────────────────────────

kelly_results = {                        # [VARIABLE - dict] Kelly outputs
    'win_rate':       WIN_RATE,
    'avg_win_pct':    round(avg_win_pct, 4),
    'avg_loss_pct':   AVG_LOSS_PCT,
    'full_kelly':     round(full_kelly, 4),
    'half_kelly':     round(half_kelly, 4),
    'recommended':    round(safe_kelly, 4),
    'position_for_1k': round(1000 * safe_kelly, 2)
}

with open('Week_4_Notebooks/kelly_results.json', 'w') as f:
    json.dump(kelly_results, f, indent=2)

print(f"✅ Kelly results saved to kelly_results.json")
print(f"   This will update the RiskManager position sizing")