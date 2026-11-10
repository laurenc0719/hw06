---

## Part C — Design Questions
# HW6 — Measure Library: AUM & Performance
All measures live in the `_Measures` table of `powerbi/hw06.pbix`. Every value below is reconciled to an independent pandas calculation in `reports/measure_reconciliation.csv` (83 rows, 83 match).

**Additivity patterns used**
- **SUM (additive):** safe to add across any dimension (fees, flows)
- **Last balance (semi-additive):** a balance taken at the last snapshot date in the filter, never summed across months
- **Recompute-and-weight (non-additive):** ratios rebuilt from additive parts in every filter context, never summed or averaged

## Part A — Measure Library

### Base measures (from the ICEs)
**Total Fees** · Format: Currency
```DAX
Total Fees = SUM ( fact_fees[amount] )
```
- **Pattern:** SUM (additive)
- **Meaning:** Total fee revenue Wildcat billed in the period.

**Net Flows** · Format: Currency
```DAX
Net Flows =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" )
- CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )
```
- **Pattern:** SUM (additive)
- **Meaning:** New money clients brought in minus money they took out.

---

### 0. AUM (naive SUM) — ⚠️ WRONG, kept only to show the trap
**Format:** Currency
```DAX
AUM (naive SUM) = SUM ( fact_portfolio_snapshot[aum] )
```
- **Pattern:** SUM, applied to a balance, which is **incorrect**
- **Meaning:** None. It adds every month's balance together, so the grand total is **$566.7B** when Wildcat actually manages **$12.73B**. It's included only to show the mistake (pandas makes the identical mistake: reconciled row `AUM (naive SUM) | Total`). It is not on the report page.

### 1. Ending AUM
**Format:** Currency
```DAX
Ending AUM =
CALCULATE (
    SUM ( fact_portfolio_snapshot[aum] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
- **Pattern:** Last balance (semi-additive). LASTNONBLANK is used because snapshots fall on the 1st of the month, so LASTDATE/ENDOFMONTH would land on a date with no data.
- **Meaning:** How much money Wildcat manages at the end of whatever period you're looking at.

### 2. Ending Clients
**Format:** Whole number
```DAX
Ending Clients =
CALCULATE (
    DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
- **Pattern:** Last balance (semi-additive)
- **Meaning:** How many clients Wildcat has on the books at the end of the period.

### 3. Avg AUM per Client
**Format:** Currency
```DAX
Avg AUM per Client = DIVIDE ( [Ending AUM], [Ending Clients] )
```
- **Pattern:** Recompute-and-weight (ratio of two last-balance measures)
- **Meaning:** The size of a typical client relationship at period end, i.e. how "wealthy" the book is.

### 4. Ending AUM LY and AUM YoY %
**Format:** Currency / Percentage
```DAX
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )
```
```DAX
AUM YoY % = DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )
```
- **Pattern:** Last balance (shifted one year) and recompute-and-weight. LASTNONBLANK runs inside the shifted dates. DIVIDE has no 0 fallback, so 2020 shows blank instead of a fake 0%.
- **Meaning:** How much AUM grew versus the same point a year ago.

### 5. Ending AUM PM and AUM MoM %
**Format:** Currency / Percentage
```DAX
Ending AUM PM = CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )
```
```DAX
AUM MoM % = DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )
```
- **Pattern:** Last balance (shifted one month) and recompute-and-weight
- **Meaning:** Month-over-month AUM change. December 2024 grew 4.25% over November.

### 6. Avg Monthly AUM
**Format:** Currency
```DAX
Avg Monthly AUM =
DIVIDE ( SUM ( fact_portfolio_snapshot[aum] ), DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] ) )
```
- **Pattern:** Recompute-and-weight (sum of balances ÷ number of snapshot months)
- **Meaning:** The average balance Wildcat managed across the period. That's the right base for anything earned over time, like fees.

### 7. Fee Yield (bps)
**Format:** Decimal number, 2 decimals
```DAX
Fee Yield (bps) = DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )
```
- **Pattern:** Recompute-and-weight across **two fact tables** (fees ÷ snapshot AUM, annualized)
- **Meaning:** How many basis points of revenue Wildcat earns per dollar it manages each year (43.15 bps in 2024).

### 8. Organic Growth Rate
**Format:** Percentage
```DAX
Organic Growth Rate = DIVIDE ( [Net Flows], [Ending AUM LY] )
```
- **Pattern:** Recompute-and-weight (additive flows ÷ last-year balance)
- **Meaning:** How much the book grew from net new client money alone, with market performance stripped out.

### 9. AUM-Weighted Alpha
**Format:** Percentage · *Part D Claude-assisted measure (see `claude/verification.md`)*
```DAX
AUM-Weighted Alpha =
VAR LastSnap =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
VAR SnapRows =
    CALCULATETABLE (
        fact_portfolio_snapshot,
        LastSnap,
        fact_portfolio_snapshot[is_return_suspect] = 0
    )
RETURN
    DIVIDE (
        SUMX ( SnapRows, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ),
        SUMX ( SnapRows, fact_portfolio_snapshot[aum] )
    )
```
- **Pattern:** Recompute-and-weight (SUMX iterator, weight = `aum`), read at the last snapshot only because alpha is YTD
- **Meaning:** How much Wildcat's money beat its benchmarks, with big accounts counting more and unreliable return rows excluded.

### 10. Alpha Signal
**Format:** Text
```DAX
Alpha Signal =
VAR a = [AUM-Weighted Alpha]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( a ), BLANK (),
        a >= 0.02, "Outperforming",
        a <= -0.02, "Lagging",
        "In line"
    )
```
- **Pattern:** Text classification built on a recompute-and-weight measure (inherits its filter context)
- **Meaning:** A plain-English flag for whether a slice of the business is beating (≥ +2%), trailing (≤ −2%) or tracking its benchmarks.

### 11. Top 10 Client Share
**Format:** Percentage
```DAX
Top 10 Client Share =
DIVIDE (
    SUMX ( TOPN ( 10, VALUES ( dim_client[client_id] ), [Ending AUM] ), [Ending AUM] ),
    [Ending AUM]
)
```
- **Pattern:** Recompute-and-weight. TOPN iterates over `VALUES ( dim_client[client_id] )` so it respects the current filter; `ALL ( dim_client )` would rank all clients firm-wide and push a tier's share over 100%.
- **Meaning:** How concentrated the book is: what share of AUM depends on the 10 biggest relationships (6.16% firm-wide, 8.13% in UHNW).
---

## Part C — Design Questions
### (a) Ending AUM vs SUMX over clients
- Ending AUM (no filters): **$12,729,572,078.86**
- `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )`: **$13,149,297,713.80**
- Difference: **$419,725,634.94**

Power BI (DAX query view):
```DAX
EVALUATE
ROW (
    "Ending AUM", [Ending AUM],
    "SUMX over clients", SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )
)
```
```text
[Ending AUM]	[SUMX over clients]
12729572078.859997	13149297713.800016
```
Both values match pandas to the cent (see the Part C evidence below); the extra digits are floating-point noise.

Without SUMX, `[Ending AUM]` uses one date for the whole filter context: the last snapshot, 2024-12-01. Inside SUMX it is evaluated once per client, so LASTNONBLANK finds each client's **own** last snapshot. For the 175 clients who left before December 2024 (13 last appear in 2022, 162 in 2023), that date is in the past. Their final balances, which pandas sums to exactly **$419,725,634.94**, the full difference, get added back even though Wildcat no longer manages that money. The SUMX total mixes balances from different dates and counts AUM that has already walked out the door.

**"How much do we manage today?" → Ending AUM, $12,729,572,078.86.**

### (b) 2024 Fee Yield (43.15 bps) is lower than Effective Fee Rate (45.53 bps)
Both measures divide the same 2024 fees, so the difference has to come from the denominator:
- **Fee Yield** divides by `SUM ( fact_portfolio_snapshot[aum] )`: every client-month in the snapshot
- **Effective Fee Rate** divides by `SUM ( fact_fees[aum_basis] )`: only client-months that have a fee row

pandas evidence (`scripts/02_part_c_evidence.py`):
- There is exactly **one fee row per billed client-month** (26,216 rows), and `aum_basis` equals snapshot `aum` on every billed row (max difference $0.00). So the two tables agree wherever both have data.
- **1,684 of 27,900** snapshot rows in 2024 have **no fee row**. That's **$7,074,540,256.63**, or **5.22%** of 2024 snapshot AUM.
- Recomputing Fee Yield on billed AUM only gives **45.5323 bps**, exactly the Effective Fee Rate. The entire gap is unbilled AUM.

**Data limitation:** `fact_fees` does not cover every account-month in `fact_portfolio_snapshot`. The unbilled rows are spread across every month (Jan 154 → Dec 91) and every tier (Retail 1,054, HNW 472, UHNW 158), so it is not a year-end timing cutoff. The data can't tell us whether these are genuinely unbilled accounts (fee waivers, new or closing accounts) or missing fee records. For profitability analysis that difference matters: either Wildcat is managing $7B for free, or the fee table is incomplete.

### (c) AUM-Weighted Alpha: why last snapshot only, and why exclude suspects
**Why the last snapshot:** `active_alpha_ytd` is year-to-date, so each month's value already includes all earlier months of the year. Only the December snapshot holds the full-year figure. Weighting across all twelve 2024 snapshots mixes partial-year values and gives **0.3225%** instead of **1.4480%**.

**Why exclude `is_return_suspect = 1`:** the 148 suspect rows at the last snapshot (all Retail) have a mean alpha of **231.55%**, which is clearly bad return data. Even AUM-weighted, they push the result up by about 0.22 points. Unweighted, they wreck it.

At the last snapshot (2024-12-01, 2,325 rows):

| Version | Value |
|---|---|
| **Weighted, suspects excluded (the measure)** | **1.4480%** |
| Simple mean, same rows | 0.8788% |
| Weighted, suspects included | 1.6678% |
| Simple mean, suspects included | 15.5624% |

The weighted value (1.45%) is higher than the simple mean (0.88%), which means larger accounts outperformed smaller ones. Wildcat's dollars did better than its typical client.

### (d) Organic Growth vs AUM YoY by tier, 2024
| Tier | Net flows | Organic Growth | AUM YoY % | Growth not from net flows |
|---|---:|---:|---:|---:|
| Retail | $44,184,047.61 | 9.87% | 19.13% | 9.26% |
| HNW | $25,227,406.26 | 1.18% | 19.64% | 18.46% |
| UHNW | $8,101,601.39 | 0.10% | 19.59% | 19.49% |

Every tier grew about 19–20%, but for HNW and UHNW almost none of it was new money. UHNW grew **$1.58B** with only **$8.1M** of net flows, so its growth came from market and investment returns on existing balances. Retail is the only tier where net new money is a real driver, about half its growth. So most of Wildcat's dollar growth sits in UHNW, the tier that brings in the least new money: the firm's growth story is the market, not client acquisition.

**What it does NOT tell you:**
- **Profitability.** Retail's fee yield is ~83 bps vs ~36 bps for UHNW, so a Retail dollar earns more than twice as much.
- **Where the flows come from.** It can't separate new clients from existing clients adding money, or show how many clients left.
- **Repeatability.** 2024's market-driven growth may not repeat in a down year.
- **Skill.** It's a ratio of flows to last year's balance, not a measure of investment performance or advisor effectiveness.

### Part C evidence (pandas)
Generated by `python scripts/02_part_c_evidence.py`:
```text
=== (a) Ending AUM vs SUMX(VALUES(client_id), [Ending AUM]) ===
Ending AUM (latest snapshot)       : 12,729,572,078.86
SUMX of each client's last balance : 13,149,297,713.80
Difference                         : 419,725,634.94
Clients whose last snapshot < 2024-12-01: 175, their last balances sum to 419,725,634.94
Departed clients' last snapshot by year: {2022: 13, 2023: 162}

=== (b) 2024 Fee Yield vs Effective Fee Rate ===
Fee Yield (fees / snapshot aum)          : 43.1543 bps
Effective Fee Rate (fees / aum_basis)    : 45.5323 bps
Fee rows per client-month: {1: 26216}
Snapshot rows with / without a fee row: {'billed': 26216, 'no fee row': 1684}
AUM with no fee row: 7,074,540,256.63 = 5.22% of 2024 snapshot AUM
aum_basis = snapshot aum on billed rows? max abs diff = 0.00
Fee Yield on BILLED AUM only             : 45.5323 bps  (= Effective Fee Rate)
No-fee rows by month: {1: 154, 2: 172, 3: 147, 4: 155, 5: 151, 6: 162, 7: 150, 8: 131, 9: 119, 10: 138, 11: 114, 12: 91}
No-fee rows by tier : {'Retail': 1054, 'HNW': 472, 'UHNW': 158}

=== (c) AUM-Weighted Alpha, latest snapshot (2024-12-01) ===
Rows at last snapshot: 2325, suspect: 148
Weighted, suspects excluded : 1.4480%
Simple mean, same rows      : 0.8788%
Weighted, suspects included : 1.6678%
Simple mean, suspects incl. : 15.5624%
Suspect rows: mean alpha 231.55%, tiers {'Retail': 148}
(Wrong) weighted over ALL 2024 months: 0.3225%

=== (d) 2024 by tier: Organic Growth vs AUM YoY ===
Retail  ending    533,452,497.89  LY    447,795,648.67  growth $  85,656,849.22  net flows $  44,184,047.61  organic   9.87%  YoY  19.13%  non-flow growth   9.26%
HNW     ending  2,548,521,154.33  LY  2,130,154,150.42  growth $ 418,367,003.91  net flows $  25,227,406.26  organic   1.18%  YoY  19.64%  non-flow growth  18.46%
UHNW    ending  9,647,598,426.64  LY  8,067,021,937.91  growth $1,580,576,488.73  net flows $   8,101,601.39  organic   0.10%  YoY  19.59%  non-flow growth  19.49%
```