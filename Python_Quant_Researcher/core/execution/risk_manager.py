# [FILE] day2_risk_manager.py
# PURPOSE: Production risk management framework for the ADX trading bot
#
# WHY DOES THIS FILE EXIST?
# Trading without risk management is like driving without a seatbelt.
# Most of the time nothing happens. But when something goes wrong,
# the consequences are catastrophic.
#
# The RiskManager is a gatekeeper. Before EVERY trade, the TradingExecutor
# asks the RiskManager "is it safe to trade right now?" If the answer is
# no, the trade doesn't happen — regardless of what the ADX signal says.
#
# PERCENTAGE-BASED DESIGN:
# All limits scale with your account size. This means:
#   - As your account grows, position sizes grow (compounding)
#   - As your account shrinks, position sizes shrink (protection)
#   - A $1,000 account and a $10,000 account follow identical rules
#     — just scaled proportionally
#
# THE THREE SAFETY LAYERS:
#
#   Layer 1 — Per-Trade Stop Loss (5%)
#   "If this specific trade goes against me by 5%, exit immediately"
#   This caps the maximum loss on any single trade.
#   Analogy: A circuit breaker on a single appliance.
#
#   Layer 2 — Daily Loss Limit (2% of account)
#   "If I've lost more than 2% of my account today, stop trading"
#   This prevents a bad day from becoming a catastrophic day.
#   Analogy: A daily spending limit on your credit card.
#
#   Layer 3 — Maximum Drawdown (15% from peak)
#   "If my account has fallen more than 15% from its highest point, stop"
#   This is the ultimate protection — forces a pause to review strategy.
#   Analogy: A smoke detector that shuts down the whole building.

# ── Imports ───────────────────────────────────────────────────────────────────

import logging                           # [LIBRARY] professional logging
from datetime import datetime            # [LIBRARY] timestamps and date tracking
import json                              # [LIBRARY] save/load state to file
import os                                # [LIBRARY] file path operations

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level   = logging.INFO,
    format  = '%(asctime)s | %(levelname)s | %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)     # [OBJECT] our logger instance

# ── Risk Configuration ────────────────────────────────────────────────────────
# All risk parameters in one place.
# Expressed as percentages (0.05 = 5%) so they scale with account size.

RISK_CONFIG = {                          # [VARIABLE - dict] risk parameters

    # Position sizing — Kelly fraction (fraction of capital to RISK per trade)
    # Position size = (position_pct × capital) / stop_loss_pct, capped at balance
    # e.g. Kelly 12.41%, stop 5%: risk=$124, size=$2,482 → capped at $1,000
    'position_pct':      0.1241,

    # Per-trade stop loss
    'stop_loss_pct':     0.08,           # Trailing stop distance 8% (Stage 1b validated, was 5% fixed)

    # Daily loss limit
    'max_daily_loss_pct': 0.02,          # Stop trading if down 2% of account today
                                         # e.g. $1,000 account → stop if down $20

    # Maximum drawdown from peak
    'max_drawdown_pct':  0.15,           # Stop trading if down 15% from peak
                                         # e.g. $1,000 peak → stop if below $850

    # Maximum trades per day (prevents overtrading bugs)
    'max_trades_per_day': 3,             # ADX strategy should trade ~0.06x/day
                                         # 3 is a generous safety ceiling
}


# ── RiskManager Class ─────────────────────────────────────────────────────────

class RiskManager:
    """
    [CLASS] Production risk management framework.

    Tracks account state and enforces safety limits before every trade.
    All limits are percentage-based and scale with account size.

    State tracked:
        - Starting balance for the day
        - Peak balance ever achieved
        - P&L for today
        - Number of trades today
        - Date of last reset (for daily counter resets)

    Analogy: The risk manager at a trading firm who sits next to every
    trader and has authority to override any trade decision.
    """

    def __init__(self, config, initial_balance):
        """
        [METHOD] Constructor — initialise risk manager with account state.

        Args:
            config          [dict]  : Risk parameters (use RISK_CONFIG above)
            initial_balance [float] : Starting account value in USDT
        """

        # ── Store configuration ────────────────────────────────────────────
        self.position_pct       = config['position_pct']        # [VARIABLE - float]
        self.stop_loss_pct      = config['stop_loss_pct']        # [VARIABLE - float]
        self.max_daily_loss_pct = config['max_daily_loss_pct']   # [VARIABLE - float]
        self.max_drawdown_pct   = config['max_drawdown_pct']     # [VARIABLE - float]
        self.max_trades_per_day = config['max_trades_per_day']   # [VARIABLE - int]

        # ── Initialise account state ───────────────────────────────────────
        self.initial_balance    = initial_balance                # [VARIABLE - float] starting value
        self.peak_balance       = initial_balance                # [VARIABLE - float] highest ever
        self.session_start      = initial_balance                # [VARIABLE - float] today's start
        self.daily_pnl          = 0.0                            # [VARIABLE - float] today's P&L
        self.trades_today       = 0                              # [VARIABLE - int] trades today
        self.last_reset_date    = datetime.now().date()          # [VARIABLE - date] last reset

        logger.info(f"RiskManager initialised")
        logger.info(f"  Initial balance:    ${initial_balance:,.2f}")
        logger.info(f"  Kelly fraction:     {self.position_pct:.2%} of capital to RISK per trade")
        logger.info(f"  Stop loss:          {self.stop_loss_pct:.0%} per trade")
        logger.info(f"  Max daily loss:     {self.max_daily_loss_pct:.0%} of account")
        logger.info(f"  Max drawdown:       {self.max_drawdown_pct:.0%} from peak")
        logger.info(f"  Max trades/day:     {self.max_trades_per_day}")

    # ── Daily Reset ───────────────────────────────────────────────────────────

    def reset_daily_counters(self, current_balance):
        """
        [METHOD] Reset daily tracking counters at midnight.
        Called automatically at the start of can_trade().

        Args:
            current_balance [float]: Current account value
        """
        today = datetime.now().date()   # [VARIABLE - date] today's date

        if today > self.last_reset_date:
            logger.info(f"Daily reset triggered")
            logger.info(f"  Yesterday P&L:  ${self.daily_pnl:+,.2f}")
            logger.info(f"  Trades made:    {self.trades_today}")

            # Reset daily counters
            self.daily_pnl       = 0.0           # reset P&L tracker
            self.trades_today    = 0             # reset trade counter
            self.session_start   = current_balance  # new day's starting balance
            self.last_reset_date = today         # mark reset complete

    # ── Position Sizing ───────────────────────────────────────────────────────

    def calculate_position_size(self, usdt_balance):
        """
        [METHOD] Calculate how much USDT to deploy in the next trade.

        Kelly fraction is the fraction of capital to RISK per trade, not to deploy.
        Correct formula: position_size = (Kelly% × capital) / stop%
        This ensures maximum possible loss = Kelly% × capital regardless of stop distance.

        The $5 fee buffer ensures the order fits within available balance after fees.
        Update stop_loss_pct when stop type changes (e.g. fixed 5% → trail 8%).

        Example:
            $1,000 account, Kelly=12.41%, stop=5%:
                risk   = 0.1241 × $1,000   = $124.10
                size   = $124.10 / 0.05    = $2,482  → capped at $995 ($1,000 - $5 buffer)
                max loss = $995 × 5%       = $49.75  ≈ 4.975% of capital (unleveraged cap)

        Args:
            usdt_balance [float]: Available USDT balance

        Returns:
            float: USDT amount to use for the trade
        """
        # Kelly fraction is the fraction of capital to RISK, not to deploy.
        # Size = risk / stop_pct, capped at (balance - $5 fee buffer).
        risk_amount   = self.position_pct * usdt_balance
        fee_buffer    = 5.0
        position_size = min(usdt_balance - fee_buffer, risk_amount / self.stop_loss_pct)
        logger.info(f"Position size: ${position_size:,.2f} "
                    f"(Kelly risk ${risk_amount:,.2f} / stop {self.stop_loss_pct:.0%}, "
                    f"cap ${usdt_balance - fee_buffer:.2f})")
        return position_size

    # ── Stop Loss Calculator ──────────────────────────────────────────────────

    def calculate_stop_loss(self, entry_price):
        """
        [METHOD] Calculate stop-loss price for a given entry.

        If ETH drops stop_loss_pct below entry, we exit immediately.
        This caps maximum loss on any single trade.

        Example:
            Entry $2,000, stop_loss_pct=0.05 → stop at $1,900
            Entry $3,000, stop_loss_pct=0.05 → stop at $2,850

        Args:
            entry_price [float]: Price we bought ETH at

        Returns:
            float: Price level at which to trigger stop-loss sell
        """
        stop_price = entry_price * (1 - self.stop_loss_pct)  # [VARIABLE - float]
        logger.info(f"Stop-loss set: ${stop_price:,.2f} "
                    f"({self.stop_loss_pct:.0%} below ${entry_price:,.2f})")
        return stop_price

    # ── Core Safety Gate ──────────────────────────────────────────────────────

    def can_trade(self, current_balance):
        """
        [METHOD] Master safety check — called before every trade.

        Runs through all three safety layers in order.
        Returns False at the FIRST limit that is breached.

        Args:
            current_balance [float]: Current total account value in USDT

        Returns:
            tuple: (bool, str) — (allowed, reason)
                   True  = trade is permitted
                   False = trade is blocked (reason explains why)
        """

        # ── Reset daily counters if new day ───────────────────────────────
        self.reset_daily_counters(current_balance)

        # ── Safety Layer 1: Daily trade limit ─────────────────────────────
        if self.trades_today >= self.max_trades_per_day:
            reason = (f"Max trades reached today "
                      f"({self.trades_today}/{self.max_trades_per_day})")
            logger.warning(f"🛑 TRADE BLOCKED: {reason}")
            return False, reason

        # ── Safety Layer 2: Daily loss limit ──────────────────────────────
        # Calculate today's loss as a percentage of starting balance
        daily_loss_pct = self.daily_pnl / self.session_start  # [VARIABLE - float]
        max_loss_allowed = -self.max_daily_loss_pct            # [VARIABLE - float] negative

        if daily_loss_pct <= max_loss_allowed:
            reason = (f"Daily loss limit reached "
                      f"({daily_loss_pct:.2%} loss vs "
                      f"{self.max_daily_loss_pct:.2%} limit)")
            logger.warning(f"🛑 TRADE BLOCKED: {reason}")
            return False, reason

        # ── Safety Layer 3: Maximum drawdown ──────────────────────────────
        # Update peak balance if we've grown
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
            logger.info(f"New peak balance: ${self.peak_balance:,.2f}")

        # Calculate current drawdown from peak
        drawdown = (current_balance - self.peak_balance) / self.peak_balance
        # [VARIABLE - float] e.g. -0.08 means 8% below peak

        if drawdown <= -self.max_drawdown_pct:
            reason = (f"Max drawdown reached "
                      f"({drawdown:.2%} from peak ${self.peak_balance:,.2f})")
            logger.warning(f"🛑 TRADE BLOCKED: {reason}")
            return False, reason

        # ── All checks passed ──────────────────────────────────────────────
        logger.info(f"✅ Risk checks passed")
        logger.info(f"   Daily P&L:   ${self.daily_pnl:+,.2f} "
                    f"({daily_loss_pct:+.2%})")
        logger.info(f"   Drawdown:    {drawdown:.2%} from peak")
        logger.info(f"   Trades today: {self.trades_today}/{self.max_trades_per_day}")

        return True, "OK"

    # ── Trade Recording ───────────────────────────────────────────────────────

    def record_trade(self, pnl):
        """
        [METHOD] Record a completed trade's P&L.
        Called after every buy/sell pair completes.

        Args:
            pnl [float]: Profit or loss in USDT (negative = loss)
        """
        self.daily_pnl    += pnl         # add to today's running total
        self.trades_today += 1           # increment trade counter

        logger.info(f"Trade recorded: ${pnl:+,.2f}")
        logger.info(f"  Daily P&L:    ${self.daily_pnl:+,.2f}")
        logger.info(f"  Trades today: {self.trades_today}")

    # ── Status Report ─────────────────────────────────────────────────────────

    def get_status(self, current_balance):
        """
        [METHOD] Print full risk status report.

        Args:
            current_balance [float]: Current account value
        """
        drawdown     = (current_balance - self.peak_balance) / self.peak_balance
        daily_loss   = self.daily_pnl / self.session_start if self.session_start else 0

        logger.info(f"{'─' * 50}")
        logger.info(f"RISK MANAGER STATUS")
        logger.info(f"  Current balance:  ${current_balance:,.2f}")
        logger.info(f"  Peak balance:     ${self.peak_balance:,.2f}")
        logger.info(f"  Daily P&L:        ${self.daily_pnl:+,.2f} ({daily_loss:+.2%})")
        logger.info(f"  Drawdown:         {drawdown:.2%}")
        logger.info(f"  Trades today:     {self.trades_today}/{self.max_trades_per_day}")
        logger.info(f"{'─' * 50}")


# ── Test the RiskManager ──────────────────────────────────────────────────────

if __name__ == '__main__':

    print("\n" + "=" * 60)
    print("RISK MANAGER — SYSTEM TEST")
    print("=" * 60)

    # ── Initialise ────────────────────────────────────────────────────────
    ACCOUNT_SIZE = 1000.00               # [VARIABLE - float] our $1,000 account

    rm = RiskManager(                    # [OBJECT] our risk gatekeeper
        config          = RISK_CONFIG,
        initial_balance = ACCOUNT_SIZE
    )

    # ── Test 1: Normal trade — should pass ────────────────────────────────
    print("\n[TEST 1] Normal conditions — should ALLOW trade")
    allowed, reason = rm.can_trade(current_balance=1000.00)
    print(f"  Result: {'✅ ALLOWED' if allowed else '❌ BLOCKED'} — {reason}")

    # ── Test 2: Position sizing ────────────────────────────────────────────
    print("\n[TEST 2] Position sizing on $1,000 account")
    size = rm.calculate_position_size(usdt_balance=1000.00)
    print(f"  Position size: ${size:,.2f}")

    print("\n[TEST 2b] Position sizing after growth to $1,500")
    size = rm.calculate_position_size(usdt_balance=1500.00)
    print(f"  Position size: ${size:,.2f} (larger — compounding working)")

    print("\n[TEST 2c] Position sizing after loss to $800")
    size = rm.calculate_position_size(usdt_balance=800.00)
    print(f"  Position size: ${size:,.2f} (smaller — protection working)")

    # ── Test 3: Stop loss calculation ─────────────────────────────────────
    print("\n[TEST 3] Stop loss calculation")
    stop = rm.calculate_stop_loss(entry_price=2000.00)
    print(f"  Entry: $2,000.00 → Stop: ${stop:,.2f}")

    # ── Test 4: Daily loss limit ───────────────────────────────────────────
    print("\n[TEST 4] Daily loss limit breach — should BLOCK trade")
    rm.daily_pnl = -25.00                # simulate losing $25 today (2.5% of $1k)
    allowed, reason = rm.can_trade(current_balance=975.00)
    print(f"  Result: {'✅ ALLOWED' if allowed else '🛑 BLOCKED'} — {reason}")
    rm.daily_pnl = 0.0                   # reset for next test

    # ── Test 5: Max drawdown breach ────────────────────────────────────────
    print("\n[TEST 5] Max drawdown breach — should BLOCK trade")
    rm.peak_balance = 1000.00            # peak was $1,000
    allowed, reason = rm.can_trade(current_balance=840.00)  # now at $840 = 16% down
    print(f"  Result: {'✅ ALLOWED' if allowed else '🛑 BLOCKED'} — {reason}")

    # ── Test 6: Trade recording ────────────────────────────────────────────
    print("\n[TEST 6] Recording a winning trade")
    rm.peak_balance = 1000.00
    rm.daily_pnl    = 0.0
    rm.record_trade(pnl=47.50)          # record a $47.50 win
    rm.record_trade(pnl=-18.20)         # record a $18.20 loss

    # ── Final status ───────────────────────────────────────────────────────
    print("\n[FINAL] Risk manager status")
    rm.get_status(current_balance=1029.30)

    print("\n" + "=" * 60)
    print("✅ ALL RISK MANAGER TESTS COMPLETE")
    print("   Percentage-based sizing confirmed — returns will compound")
    print("   All three safety layers operational")
    print("=" * 60 + "\n")