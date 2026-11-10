# HW6 — DAX Measure Library: AUM & Performance
MIS3060 Business Intelligence with AI · Villanova University

A library of 12 DAX measures (plus 2 base measures) over the Wildcat Capital star model, a **Measures** report page, and a full reconciliation of every measure to an independent pandas calculation: **83 rows, 83 match, 0 mismatch.**

## Structure
```
hw06/
├── README.md
├── HW06_DAX_Measure_Library.md        # assignment
├── powerbi_dax_guide.md               # course DAX guide
├── *.csv                              # Wildcat Capital Clean data (8 tables; NOT committed, see How to run)
├── powerbi/
│   ├── hw06.pbix                      # posted model + _Measures table + "Measures" report page (21.9 MB)
│   └── measures.md                    # Part A documentation + Part C answers and evidence
├── scripts/
│   ├── 01_reconcile_measures.py       # Part B: pandas recalculation + reconciliation
│   ├── 02_part_c_evidence.py          # Part C: pandas evidence for (a)–(d)
│   └── export_powerbi_values.dax      # DAX query used to export Power BI values
├── reports/
│   ├── powerbi_values.csv             # Power BI values (measure, slice, value), 83 rows
│   └── measure_reconciliation.csv     # Power BI vs pandas, 83 rows, all match
└── claude/
    ├── model_metadata.md              # INFO.VIEW columns, relationships, measures
    ├── dax_session.md                 # Part D prompt + full Claude Desktop response
    └── verification.md                # Part D verification of AUM-Weighted Alpha
```

## How to run
Requires Python 3 with pandas and numpy (Anaconda base works). The eight Wildcat Capital Clean CSVs are not committed (they're course-provided data, excluded by `.gitignore`); copy them into the `hw06` folder, then run from that folder:
```
python scripts/01_reconcile_measures.py      # writes reports/measure_reconciliation.csv
python scripts/02_part_c_evidence.py         # prints the Part C evidence
python scripts/01_reconcile_measures.py --print-dax   # regenerates the Power BI export query
```
To refresh the Power BI side: open `powerbi/hw06.pbix` → DAX query view → run `scripts/export_powerbi_values.dax` → copy the result grid into `reports/powerbi_values.csv` (columns `measure,slice,value`). The query wraps every numeric measure in `FORMAT(..., "0.000000000000")` so display formatting can't round the exported values.

## Reconciliation coverage (Part B)
| Slice | Measures | Rows |
|---|---|---:|
| Grand total | all 14 (incl. `AUM (naive SUM)`, LY/PM/YoY/MoM) | 14 |
| By year, 2020–2024 | 1, 4 (LY + YoY), 6, 7, 8, 9, 10 | 40 |
| 2024 by client tier (Retail / HNW / UHNW) | 1, 3, 4 (LY + YoY), 7, 8, 9, 10, 11 | 27 |
| December 2024 | 5 (PM + MoM) | 2 |
| **Total** | | **83** |

Tolerances: 0.01 for currency, 0.0001 for ratios, 0.001 for bps, exact for counts (Ending Clients) and text (Alpha Signal). Blank vs blank (e.g. 2020 YoY / Organic Growth, which have no prior year) counts as a match; a row missing from the Power BI export always fails.

`AUM (naive SUM)` is reconciled on purpose: both tools return **$566,681,084,542.48** for the trap measure, which shows that pandas and DAX make the same mistake when a balance is summed across months.

## Workflow
- **Claude Desktop** drafted the reconciliation and evidence scripts and the Part D measure.
- **I** ran the scripts in VS Code (Anaconda terminal) and verified every number against the Measures page.
- **Claude Code** reviewed `01_reconcile_measures.py` before committing (findings below).

## Claude Code review findings
Static review (Claude Code's shell hit the Microsoft Store python stub, so I ran the script myself). Verdict: logic sound, all Part B slices covered, no bug that changes a number.

| Finding | What I did |
|---|---|
| A row missing from the Power BI export could pass as blank = blank | **Fixed:** added `row_present`; a missing row always fails. Tested by deleting the 2020 YoY row → flagged as a mismatch |
| Duplicate rows in `powerbi_values.csv` would crash the script | **Fixed:** the script exits and lists the duplicates (tested) |
| pandas returns `inf` where DAX `DIVIDE` returns blank | **Fixed:** `inf` is converted to blank before comparing |
| Fee Yield (bps) used the 0.0001 ratio tolerance | **Fixed:** separate 0.001 bps tolerance |
| Ending Clients (a count) used the ratio tolerance | **Fixed:** exact match required |
| Rows with a blank alpha would count in the weight denominator | **Fixed:** only non-blank alpha rows are weighted (there are none in this data) |
| Delimiter sniffing is fragile | **Fixed:** plain comma read; kept a fallback for a headerless paste, because that really happened (see below) |
| Excel can turn the slice `2024-12` into `Dec-24` | No code change; the CSVs are never opened or re-saved in Excel |
| The `MonthEnd` shift assumes windows end on a month end | Documented in a code comment (true for every slice used) |
| The DAX query and pandas share slice labels through `plan()` | Kept and documented: only the labels are shared; pandas computes from the CSVs alone and never reads Power BI output. Independent hand check: grouping the raw Dec 2024 rows by client gives **$12,729,572,078.86** = Ending AUM |

## Mismatches and fixes
- **First run failed with `KeyError: 'measure'`.** The DAX query view grid was copied without its header row and as tab-separated text. Fixed by adding the `measure,slice,value` header and converting the file to comma-separated; the script now also accepts a headerless paste. **After the fix: 83 rows, 83 match. There were no value-level mismatches at any point.**
- **DAX errors while building measures (Power BI side):**
  - Pasting two measures into one formula bar gave a syntax error; each measure has to be its own *New measure*.
  - `AUM-Weighted Alpha` first failed because a variable was named `LastDate`, which collides with the DAX `LASTDATE` function (DAX ignores case). Renamed it to `LastSnap` (and `Rows` → `SnapRows`).

## Notes
- `INFO.VIEW.MEASURES` shows a blank `FormatString` even though every measure is formatted (currency / % / bps) in Measure tools; the formats display correctly on the Measures page.
- The metadata export lists 11 star-schema relationships 
11. The model was not changed for this homework, and all 83 reconciliation rows match.
- `hw06.pbix` is 21.9 MB, under GitHub's 100 MB limit, so it is committed here.