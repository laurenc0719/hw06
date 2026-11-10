# Part D Verification — AUM-Weighted Alpha (measure 9)

## Did Claude's measure run as written?
Yes. I added it as "AUM-Weighted Alpha (Claude)" and it ran with no errors. Note: my prompt
included my existing AUM-Weighted Alpha in the measures metadata, so Claude revised my measure
rather than drafting from scratch. Its changes: MAX(snapshot_date) instead of LASTNONBLANK to find
the last date, and an extra NOT ISBLANK(active_alpha_ytd) filter.
Its test query (edited to point at the Claude version) returned Diff = 0 on every year and tier
row. Total = 0.014480, the same as my original measure.

## Reconciliation proof
measure_reconciliation.csv rows for AUM-Weighted Alpha (all match = True):
- Total: 0.014480 | 2020: -0.006802 | 2021: -0.001574 | 2022: 0.028494 | 2023: 0.017689 | 2024: 0.014480
- 2024|Retail: 0.024041 | 2024|HNW: 0.013988 | 2024|UHNW: 0.014097
Claude's version returns the same values on every one of these rows.

## Edge cases
1. Grand total — no date filter, so it uses the single latest snapshot (2024-12-01). It returns
   0.014480 = the 2024 value, as expected for a YTD measure (not an average of the years).
2. dim_date[year] = 2022 — the only year above +2% (0.028494), so Alpha Signal flips to
   "Outperforming". Both versions agree.
3. 2024 tier table — the tier filter flows through dim_client; each tier's last snapshot is still
   2024-12-01. All 148 suspect rows at that date are Retail, so excluding them only changes
   Retail's weighting. Retail = 0.024041 (Outperforming).

## What I changed and why
Nothing in my submitted measure. I kept my original LASTNONBLANK version because it reconciles
83/83 and uses the same last-date logic as Ending AUM. Claude's blank-alpha "fix" changes nothing
here because pandas shows 0 blank active_alpha_ytd values. It's a reasonable robustness guard, and
my pandas twin already only weights non-blank alpha rows. (Earlier, my first draft of this
measure failed because I named a variable LastDate, which collides with the LASTDATE function;
renaming it to LastSnap fixed it.)

## A claim I confirmed / refuted
Refuted: Claude explained the filter context with a "2025" year row, a partial "2026" year, and a
"Platinum" tier. None of these exist: dim_date covers 2020–2024, and client_tier is only Retail,
HNW and UHNW. INFO.VIEW metadata lists columns and types but not their values or date ranges, so
Claude filled in plausible examples instead of real ones.
Confirmed: "if you have no blank alphas, the two versions return the same number" — pandas
finds 0 blank active_alpha_ytd rows, and both measures return 0.014480 at the grand total.