# [MODULE] Day 2 - Kelly Recalculation & Portfolio Simulator
# Week 5: Resolves A001 (win rate), A005 (Kelly), A007 (portfolio simulator)
#
# WHAT THIS SCRIPT DOES:
#   Part 1: Recalculate Kelly Criterion using TRUE stop-loss backtest data
#   Part 2: Simulate portfolio growth under 5 different sizing strategies
#
# WHY THIS MATTERS:
#   Week 4 Kelly (12.41%) was calculated without stop-loss data.
#   Now we have real win rate (34.3%) and real avg loss (-3.92%).
#   We need to check if 12.41% is still the right position size.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ---------------------------------------------------------------------------
# PART 1: KELLY RECALCULATION
# ---------------------------------------------------------------------------

def calculate_kelly(win_rate: float, avg_win: float, avg_loss: float) -> dict:
    """
    [FUNCTION] Calculate Kelly Criterion position size.

    The Kelly formula: f* = (p * b - q) / b
    where:
        p = win probability (e.g. 0.343)
        q = loss probability (1 - p)
        b = avg_win / avg_loss ratio (reward:risk)

    Analogy: Kelly answers the question "given the odds of this bet,
    what fraction of your bankroll should you wager to grow fastest
    without risking ruin?" A casino with good odds bets more;
    a casino with bad odds bets less.

    Args:
        win_rate [float] : fraction of trades that are winners (0-1)
        avg_win  [float] : average winning trade return (positive, e.g. 0.24)
        avg_loss [float] : average losing trade return (negative, e.g. -0.039)

    Returns:
        dict with full_kelly, half_kelly, recommended
    """
    p: float = win_rate
    q: float = 1 - win_rate
    b: float = avg_win / abs(avg_loss)   # [VARIABLE - float] reward:risk ratio

    full_kelly: float = (p * b - q) / b
    half_kelly: float = full_kelly * 0.5

    # Safety cap at 25% — never risk more than this regardless of Kelly output
    recommended: float = max(0.0, min(half_kelly, 0.25))

    return {
        'b':           b,
        'full_kelly':  full_kelly,
        'half_kelly':  half_kelly,
        'recommended': recommended,
    }


# ---------------------------------------------------------------------------
# Load trade log from Day 1
# ---------------------------------------------------------------------------

# [VARIABLE - DataFrame] 108 trades with stop-loss data
trades: pd.DataFrame = pd.read_csv('data/trade_log_with_stoploss.csv')

winners = trades[trades['return'] > 0]   # [VARIABLE - DataFrame] winning trades
losers  = trades[trades['return'] <= 0]  # [VARIABLE - DataFrame] losing trades

# Measure inputs from real data
win_rate: float = len(winners) / len(trades)
avg_win:  float = winners['return'].mean()
avg_loss: float = losers['return'].mean()   # negative number

# Calculate Kelly
kelly: dict = calculate_kelly(win_rate, avg_win, avg_loss)

# Week 4 reference values (for comparison)
W4_WIN_RATE: float = 0.375
W4_AVG_WIN:  float = 0.2430
W4_AVG_LOSS: float = -0.0537
W4_KELLY:    float = 0.1241

print(f"\n{'='*70}")
print(f"PART 1: KELLY CRITERION RECALCULATION")
print(f"{'='*70}")
print(f"\n{'Input':<25} {'Week 4 (no stop)':>18} {'Week 5 (with stop)':>18}")
print(f"{'-'*62}")
print(f"{'Win rate':<25} {W4_WIN_RATE:>18.1%} {win_rate:>18.1%}")
print(f"{'Avg win':<25} {W4_AVG_WIN:>18.2%} {avg_win:>18.2%}")
print(f"{'Avg loss':<25} {W4_AVG_LOSS:>18.2%} {avg_loss:>18.2%}")
print(f"{'Reward:risk (b)':<25} {W4_AVG_WIN/abs(W4_AVG_LOSS):>18.2f}x {kelly['b']:>17.2f}x")
print(f"\n{'Kelly Output':<25} {'Week 4':>18} {'Week 5':>18}")
print(f"{'-'*62}")
print(f"{'Full Kelly':<25} {W4_KELLY*2:>18.2%} {kelly['full_kelly']:>18.2%}")
print(f"{'Half Kelly':<25} {W4_KELLY:>18.2%} {kelly['half_kelly']:>18.2%}")
print(f"{'Recommended (capped)':<25} {W4_KELLY:>18.2%} {kelly['recommended']:>18.2%}")
print(f"\n{'Difference':<25} {(kelly['recommended'] - W4_KELLY)*100:>+.2f} percentage points")

# Flag if change is significant
if abs(kelly['recommended'] - W4_KELLY) > 0.02:
    print(f"\n⚠️  SIGNIFICANT CHANGE — Update RiskManager.position_pct")
    print(f"   OLD: position_pct = {W4_KELLY}")
    print(f"   NEW: position_pct = {kelly['recommended']:.4f}")
else:
    print(f"\n✅ Minor difference — current sizing of {W4_KELLY:.1%} remains acceptable")

print(f"\n✅ RESOLVES: A001 (win rate measured), A005 (Kelly recalculated)")


# ---------------------------------------------------------------------------
# PART 2: PORTFOLIO SIMULATOR
# ---------------------------------------------------------------------------
# This simulates running all 108 trades in sequence under different
# position sizing rules. After each trade, the account balance updates.
# We track balance after every trade so we can plot the growth path.
#
# KEY CONCEPT — why sizing strategy matters:
#   Fixed $124:    win adds $29, loss costs $5 — regardless of account size
#   Kelly 12.41%:  win adds 12.41% * balance * 24% — grows with the account
#   This is the difference between arithmetic and geometric growth.
#
# THE ALL-IN CURVE:
#   Betting 100% every trade shows why position sizing exists.
#   Even with a positive edge, consecutive losses at 100% sizing
#   compounds losses catastrophically. Kelly exists to prevent this.

def simulate_portfolio(
    trades_df: pd.DataFrame,
    initial_capital: float,
    position_fn,
    label: str
) -> dict:
    """
    [FUNCTION] Simulate portfolio growth trade by trade.

    Args:
        trades_df       : DataFrame of trades with 'return' column
        initial_capital : starting account balance in USD
        position_fn     : function(balance) -> position size in USD
        label           : name for this strategy (used in chart)

    Returns:
        dict with equity history, final value, max drawdown
    """
    capital: float = initial_capital
    history: list  = [capital]   # [VARIABLE - list] balance after each trade

    for _, trade in trades_df.iterrows():
        position_size: float = position_fn(capital)      # how much to bet
        pnl: float           = position_size * trade['return']  # profit or loss
        capital             += pnl
        capital              = max(capital, 0.0)         # floor at zero
        history.append(capital)

    # Calculate max drawdown on equity curve
    equity:   np.ndarray = np.array(history)
    peak:     np.ndarray = np.maximum.accumulate(equity)
    drawdown: np.ndarray = (equity - peak) / peak
    max_dd:   float      = drawdown.min()

    return {
        'label':    label,
        'history':  history,
        'final':    capital,
        'return':   (capital / initial_capital - 1),
        'max_dd':   max_dd,
        'drawdown': drawdown,
    }


# ---------------------------------------------------------------------------
# Define sizing strategies
# ---------------------------------------------------------------------------

INITIAL: float = 1000.0   # [VARIABLE - float] starting capital

# [VARIABLE - function] each lambda takes current balance, returns bet size
fixed_124    = lambda bal: 124.0        # always $124 — no compounding
kelly_1241   = lambda bal: bal * 0.1241 # 12.41% of current balance
conservative = lambda bal: bal * 0.05  # 5% — very cautious
aggressive   = lambda bal: bal * 0.25  # 25% — maximum Kelly cap
all_in       = lambda bal: bal * 1.0   # 100% — entire balance every trade

# Run all five simulations
sims: list = [
    simulate_portfolio(trades, INITIAL, fixed_124,    "Fixed $124"),
    simulate_portfolio(trades, INITIAL, kelly_1241,   "Kelly 12.41%"),
    simulate_portfolio(trades, INITIAL, conservative, "Conservative 5%"),
    simulate_portfolio(trades, INITIAL, aggressive,   "Aggressive 25%"),
    simulate_portfolio(trades, INITIAL, all_in,       "All-in 100%"),
]

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------

print(f"\n\n{'='*70}")
print(f"PART 2: PORTFOLIO SIMULATION RESULTS")
print(f"{'='*70}")
print(f"Initial Capital: ${INITIAL:,.0f} | Trades: {len(trades)}")
print(f"\n{'Strategy':<20} {'Final Value':>12} {'Return':>10} {'Max Drawdown':>14}")
print(f"{'-'*58}")
for s in sims:
    print(f"  {s['label']:<18} ${s['final']:>10,.2f} {s['return']:>10.1%} {s['max_dd']:>13.1%}")

print(f"\nKEY INSIGHT:")
print(f"  Kelly sizing compounds — winners grow the bet size automatically.")
print(f"  Fixed sizing does not compound — every bet is the same dollar amount.")
print(f"  All-in shows why position sizing exists — losses compound just as fast.")
print(f"  Over 108 trades these differences become dramatic.")

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(2, 1, figsize=(14, 10))
fig.suptitle('Portfolio Simulator — Sizing Strategy Comparison (Week 5 Day 2)',
             fontsize=14, fontweight='bold')

colors = ['steelblue', 'green', 'orange', 'crimson', 'purple']

# --- Equity curves ---
for s, color in zip(sims, colors):
    axes[0].plot(s['history'], label=s['label'], linewidth=2, color=color)

axes[0].axhline(INITIAL, color='gray', linestyle='--', alpha=0.5, label='Start ($1,000)')
axes[0].set_title('Portfolio Growth by Sizing Strategy')
axes[0].set_xlabel('Trade Number')
axes[0].set_ylabel('Account Value ($)')
axes[0].legend()
axes[0].grid(alpha=0.3)

# --- Drawdown curves ---
for s, color in zip(sims, colors):
    axes[1].plot(s['drawdown'] * 100, label=s['label'], linewidth=2, color=color)

axes[1].axhline(0, color='gray', linestyle='--', alpha=0.5)
axes[1].set_title('Drawdown by Sizing Strategy')
axes[1].set_xlabel('Trade Number')
axes[1].set_ylabel('Drawdown (%)')
axes[1].legend()
axes[1].grid(alpha=0.3)

plt.tight_layout()
os.makedirs('Week_5_Notebooks/results', exist_ok=True)
chart_path = 'Week_5_Notebooks/results/day2_portfolio_simulator.png'
plt.savefig(chart_path, dpi=150)
print(f"\n✅ Chart saved → {chart_path}")
plt.close()

print(f"\n✅ RESOLVES: A007 (portfolio simulator built)")
print(f"\n{'='*70}")
print(f"DAY 2 COMPLETE")
print(f"RESOLVED: A001, A005, A007")
print(f"{'='*70}\n")