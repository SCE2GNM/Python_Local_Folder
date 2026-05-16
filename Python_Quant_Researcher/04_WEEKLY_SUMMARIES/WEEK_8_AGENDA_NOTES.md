# Week 8 Agenda Notes
## DeFi Quant Engineer Curriculum

**Purpose:** Carry-over items and priorities for the Week 8 session. Read this at the start of the Week 8 chat thread before doing anything else. Items are ordered by priority — work through them in sequence.
**Who reads it:** Greg and Claude at the start of Week 8.
**When updated:** Add items during Week 7 close-out. Do not modify once Week 8 begins.
**Related documents:** WEEK_8_THREAD_STARTER.md (when created), WEEK_7_THREAD_STARTER.md.

---

**Student:** Greg (Gmac)
**Week:** 8 of 24
**Prepared:** End of Week 7 (2026-05-15)
**Purpose:** Carry-over items and priorities for Week 8 session start

---

## Week 8 Setup Tasks — Do First

### Task 0 — File System Reorganisation ✅ COMPLETE (done Week 7 close-out, 2026-05-16)

Reorganise the project root into the following folder structure. Do this as the first action of Week 8, before writing any new scripts or notebooks.

**Target structure:**

| Folder | Contents |
|---|---|
| `00_MASTER/` | All living documents: LEARNING_LOG, METHODOLOGY_STANDARDS, STRATEGY_RESEARCH_PIPELINE, STRATEGY_IDEAS_LOG, STRATEGIC_FRAMEWORK, CURRICULUM_OPERATING_MANUAL |
| `01_RISK_REGISTERS/` | All risk register files |
| `02_TEMPLATES/` | STRATEGY_DEPLOYMENT_TEMPLATE, STRATEGY_RISK_REGISTER_TEMPLATE |
| `03_DEPLOYMENT_CARDS/` | All HTML deployment cards and explainers (currently in `Deployment_Documents/Week_6/`) |
| `04_WEEKLY_SUMMARIES/` | All WEEK_N_ files: thread starters, summaries, research briefs, agenda notes |
| `05_BOTS/` | All bot Python files and `core/` directory |
| `06_BACKTESTS/` | All `Week_N_Notebooks/` folders |
| `07_DATA/` | All CSV and results files |
| `PROJECT_REFERENCE.html` | Stays at project root |

**Pre-move checklist (complete before any files are moved):**

1. Update all hardcoded file paths in bot Python files (`day5_production_bot.py`, `rsi_production_bot.py`, any others) to reflect new locations under `05_BOTS/` and `07_DATA/`.
2. Update all hardcoded paths in Jupyter notebooks that reference results CSVs or data files.
3. Update `PROJECT_REFERENCE.html` links to reflect new folder locations.
4. Update Claude Code session re-orientation instructions in this file (WEEK_8_AGENDA_NOTES.md) to reference new canonical paths so future sessions orient correctly.
5. Confirm `07_DATA/` is added to `.gitignore` or explicitly tracked — do not accidentally commit large data files.

**Commit rule:** Reorganisation must be committed as a single clean commit before any Week 8 work begins. Message: `"Week 8: file system reorganisation — new folder structure 00_MASTER through 07_DATA"`. Do not mix reorganisation and new code in the same commit.

**Introduced:** Week 7 (2026-05-16)

---

### Task 1 — EC2 Security and Stability

**Current temporary IP: `3.104.101.30`** (will change again on next restart until Elastic IP is added). SSH key: `~/.ssh/trading-bot-key.pem`. Username: `ubuntu`.

**1. Allocate an Elastic IP**
Prevents the IP changing on every restart. Free while instance is running.
Steps: AWS Console → EC2 → Elastic IPs → Allocate → Associate with instance.

**2. Update IP in all project files once Elastic IP is set**
After allocation, update `3.104.101.30` in:
- `WEEK_8_AGENDA_NOTES.md` (this file)
- `WEEK_8_THREAD_STARTER.md`
- Any other file referencing the current IP

**3. Optionally restrict SSH security group**
After Elastic IP is set, restrict inbound port 22 from `0.0.0.0/0` to a known IP range for better security.

**Introduced:** Week 7 close-out (2026-05-16)

---

## Week 8 Carry-Over Items (from Week 7)

1. **II-001: Telegram message redesign** — implement before leveraged bot deployment. See STRATEGY_IDEAS_LOG.md for full spec. Apply to day5_production_bot.py, rsi_production_bot.py, and any future bots.

2. **Leveraged bot build (day6_leveraged_bot.py)** — Priority 1, deferred from Week 7 pending dynamic leverage framework. Do not build until dynamic leverage framework is designed and backtested.

3. **Dynamic leverage framework** — design and backtest before leveraged bot deployment. Methodology: Kelly-based or volatility-targeted leverage that adjusts position size based on market conditions rather than fixed 1.9×.

4. **BTC SMA Stage C Monte Carlo** — in progress. Win-rate scenario framework is inappropriate for the 23–33% win rate / fat-tail payoff structure of T30% strategies. Resolve scenario design before running Stage C. See session notes for proposed alternatives (return magnitude scaling or bootstrap resampling).

5. **A022: ETH ADX Monte Carlo** — MAJOR priority, Week 8. Risk register item A022 for ETH ADX strategy requires Monte Carlo validation before any leveraged deployment.

6. **ETH RSI stability analysis RR-RSI-006** — outstanding from Week 7 risk register. Required before ETH RSI strategy can be considered for scaling.

7. **Project reference document (PROJECT_REFERENCE.html)** — outstanding from Week 7. Untracked file in repo root. Review whether to commit or archive.

---

*Created: 2026-05-15 — end of Week 7*
