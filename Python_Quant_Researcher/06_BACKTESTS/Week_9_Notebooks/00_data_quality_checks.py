"""
Week 9 Data Quality Checks — Altcoin Discovery Pre-Grid
Assets: LINK-USD, BNB-USD, AVAX-USD, DOT-USD, MATIC-USD

Run this before any grid search. Any asset that fails HISTORY or VOLUME must be
flagged for manual deployment decision — it is NOT automatically removed.

MATIC ticker note: MATICUSDT is the correct Binance spot ticker despite the
POL rebrand completed September 13, 2024 (1:1 migration, Binance retained the
original MATIC ticker for the spot pair rather than migrating to POL/USDT as
done on some exchanges). yfinance uses MATIC-USD throughout the full date range.
The POL migration is treated as a continuity check point, not a ticker change.
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
ASSETS = ["LINK-USD", "BNB-USD", "AVAX-USD", "DOT-USD", "MATIC-USD"]
MIN_YEARS = 2
PREF_YEARS = 3
GAP_THRESHOLD_DAYS = 7
SPIKE_PCT = 0.50           # close must be >50% away from BOTH neighbours
VOLUME_USD_MIN = 5_000_000 # $5M average daily USD volume over last 90 days
TODAY = datetime.today()
DOWNLOAD_START = "2018-01-01"  # wide window to capture full history

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_quality_results.csv")


def check_history(df, ticker):
    """Returns (pass, start_date, n_candles, notes)."""
    start = df.index[0].date()
    n = len(df)
    years_available = (TODAY.date() - start).days / 365.25
    passed = years_available >= MIN_YEARS
    preferred = years_available >= PREF_YEARS
    status = "PASS" if passed else "FAIL"
    note = f"{years_available:.1f}yr available"
    if passed and not preferred:
        note += f" (below {PREF_YEARS}yr preferred)"
    return status, str(start), n, note


def check_gaps(df, ticker):
    """
    Find gaps > GAP_THRESHOLD_DAYS in the date index.
    Crypto trades 24/7 so every calendar day should have a candle.
    Returns (pass, gap_count, gap_detail_str).
    """
    dates = pd.Series(df.index.date)
    deltas = dates.diff().dropna()
    long_gaps = deltas[deltas > timedelta(days=GAP_THRESHOLD_DAYS)]

    if long_gaps.empty:
        return "PASS", 0, "None"

    details = []
    for idx in long_gaps.index:
        gap_start = dates.iloc[idx - 1]
        gap_end = dates.iloc[idx]
        days = (gap_end - gap_start).days
        details.append(f"{gap_start}→{gap_end} ({days}d)")

    return "FAIL", len(long_gaps), "; ".join(details)


def check_spikes(df, ticker):
    """
    Flag candles where close is >50% away from BOTH prev_close AND next_close.
    This catches the data-error pattern: price spikes then fully reverses.
    A genuine crash does NOT fully reverse the next day — it will fail the
    next_close test and not be flagged.
    """
    close = df["Close"]
    prev_close = close.shift(1)
    next_close = close.shift(-1)

    # pct deviation from neighbours
    dev_prev = (close - prev_close).abs() / prev_close
    dev_next = (close - next_close).abs() / next_close

    # both neighbours must be far away (spike + full reversal)
    spike_mask = (dev_prev > SPIKE_PCT) & (dev_next > SPIKE_PCT)
    spike_mask = spike_mask.fillna(False)

    flagged = df[spike_mask]
    if flagged.empty:
        return "PASS", 0, "None"

    dates_str = "; ".join([str(d.date()) for d in flagged.index])
    return "WARN", len(flagged), dates_str


def check_volume(df, ticker):
    """
    Average daily USD volume = volume × close, over most recent 90 days.
    Returns (pass, avg_usd_vol, note).
    """
    recent = df.tail(90).copy()
    usd_vol = recent["Volume"] * recent["Close"]
    avg = usd_vol.mean()
    passed = avg >= VOLUME_USD_MIN
    status = "PASS" if passed else "FAIL"
    note = f"${avg:,.0f} avg daily USD vol (90d)"
    return status, f"${avg:,.0f}", note


def check_matic_continuity(df):
    """
    POL migration: September 13, 2024.
    Check for any data anomaly in ±30 days around that date.
    Returns (status, note).
    """
    migration_date = pd.Timestamp("2024-09-13")
    window_start = migration_date - pd.Timedelta(days=30)
    window_end = migration_date + pd.Timedelta(days=30)

    window = df.loc[window_start:window_end]
    if window.empty:
        return "WARN", "No data in migration window"

    # Check candle count — expect ~60 calendar days = ~60 candles
    expected = 61
    actual = len(window)
    if actual < expected * 0.90:  # allow 10% tolerance
        return "WARN", f"Only {actual}/{expected} candles in ±30d window around Sep 2024"

    # Check for gaps in the window
    dates = pd.Series(window.index.date)
    deltas = dates.diff().dropna()
    max_gap = deltas.max().days if not deltas.empty else 0

    if max_gap > 3:
        return "WARN", f"Gap of {max_gap} days found in migration window"

    # Check that migration date itself is present (or close to it)
    close_to_migration = window.loc[
        (window.index >= migration_date - pd.Timedelta(days=1)) &
        (window.index <= migration_date + pd.Timedelta(days=1))
    ]
    if close_to_migration.empty:
        return "WARN", "Migration date Sep 13 2024 missing from data"

    return "PASS", f"Continuous through Sep 2024 ({actual} candles in window, max gap {max_gap}d)"


# ── Main ─────────────────────────────────────────────────────────────────────

print("=" * 70)
print("WEEK 9 DATA QUALITY CHECKS")
print(f"Run date: {TODAY.strftime('%Y-%m-%d')}")
print(f"Assets:   {', '.join(ASSETS)}")
print("=" * 70)

results = []

for ticker in ASSETS:
    print(f"\n{'─'*60}")
    print(f"  {ticker}")
    print(f"{'─'*60}")

    # Download
    try:
        df = yf.download(ticker, start=DOWNLOAD_START, auto_adjust=True, progress=False)
    except Exception as e:
        print(f"  DOWNLOAD ERROR: {e}")
        results.append({
            "Asset": ticker,
            "History": "ERROR",
            "Start Date": "N/A",
            "N Candles": 0,
            "Gaps>7d": "ERROR",
            "Gap Detail": str(e),
            "Spikes": "ERROR",
            "Spike Detail": "",
            "Volume (90d)": "ERROR",
            "Volume Status": "ERROR",
            "MATIC Continuity": "N/A",
            "MATIC Note": "",
            "OVERALL": "ERROR",
        })
        continue

    if df.empty:
        print(f"  No data returned by yfinance.")
        results.append({
            "Asset": ticker,
            "History": "FAIL",
            "Start Date": "N/A",
            "N Candles": 0,
            "Gaps>7d": "N/A",
            "Gap Detail": "No data",
            "Spikes": "N/A",
            "Spike Detail": "",
            "Volume (90d)": "N/A",
            "Volume Status": "FAIL",
            "MATIC Continuity": "N/A",
            "MATIC Note": "",
            "OVERALL": "FAIL — NO DATA",
        })
        continue

    # Flatten MultiIndex columns if present (yfinance sometimes returns them)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Drop rows where Close is NaN
    df = df.dropna(subset=["Close"])

    # ── Check 1: History ──────────────────────────────────────────────────
    hist_status, start_date, n_candles, hist_note = check_history(df, ticker)
    print(f"  [1] History:    {hist_status}  |  Start {start_date}  |  {n_candles} candles  |  {hist_note}")

    # ── Check 2: Gaps ─────────────────────────────────────────────────────
    gap_status, gap_count, gap_detail = check_gaps(df, ticker)
    print(f"  [2] Gaps>7d:    {gap_status}  |  {gap_count} gap(s)  |  {gap_detail}")

    # ── Check 3: Spikes ───────────────────────────────────────────────────
    spike_status, spike_count, spike_detail = check_spikes(df, ticker)
    print(f"  [3] Spikes:     {spike_status}  |  {spike_count} flagged  |  {spike_detail}")

    # ── Check 4: Volume ───────────────────────────────────────────────────
    vol_status, vol_fig, vol_note = check_volume(df, ticker)
    print(f"  [4] Volume:     {vol_status}  |  {vol_note}")

    # ── Check 5: MATIC continuity (MATIC-USD only) ────────────────────────
    if ticker == "MATIC-USD":
        matic_status, matic_note = check_matic_continuity(df)
        print(f"  [5] MATIC/POL:  {matic_status}  |  {matic_note}")
    else:
        matic_status, matic_note = "N/A", ""

    # ── Overall ───────────────────────────────────────────────────────────
    hard_fail = (hist_status == "FAIL") or (vol_status == "FAIL")
    has_warn = (gap_status == "FAIL") or (spike_status == "WARN") or (matic_status == "WARN")
    if hard_fail:
        overall = "FLAG — MANUAL DECISION REQUIRED"
    elif has_warn:
        overall = "PASS WITH WARNINGS"
    else:
        overall = "PASS"
    print(f"  >>> OVERALL:    {overall}")

    results.append({
        "Asset": ticker,
        "History": hist_status,
        "Start Date": start_date,
        "N Candles": n_candles,
        "Gaps>7d": gap_status,
        "Gap Detail": gap_detail,
        "Spikes": spike_status,
        "Spike Detail": spike_detail,
        "Volume (90d)": vol_fig,
        "Volume Status": vol_status,
        "MATIC Continuity": matic_status,
        "MATIC Note": matic_note,
        "OVERALL": overall,
    })


# ── Summary Table ─────────────────────────────────────────────────────────
print("\n")
print("=" * 70)
print("PASS / FAIL SUMMARY")
print("=" * 70)

summary_df = pd.DataFrame(results)

# Compact display
display_cols = ["Asset", "History", "N Candles", "Gaps>7d", "Spikes", "Volume Status", "MATIC Continuity", "OVERALL"]
print(summary_df[display_cols].to_string(index=False))

# Save full results
summary_df.to_csv(OUTPUT_CSV, index=False)
print(f"\nFull results saved to: {OUTPUT_CSV}")

# ── Deployment flag summary ───────────────────────────────────────────────
flagged = summary_df[summary_df["OVERALL"].str.startswith("FLAG")]
if not flagged.empty:
    print("\n*** FLAGGED ASSETS (require manual deployment decision) ***")
    for _, row in flagged.iterrows():
        print(f"  {row['Asset']}: {row['OVERALL']}")
        if row["History"] == "FAIL":
            print(f"    - History: start {row['Start Date']}, {row['N Candles']} candles")
        if row["Volume Status"] == "FAIL":
            print(f"    - Volume: {row['Volume (90d)']} (below ${VOLUME_USD_MIN:,} threshold)")
else:
    print("\nNo assets flagged — all pass hard gates.")

print("\nData quality checks complete. Do not run grid until results reviewed.")
