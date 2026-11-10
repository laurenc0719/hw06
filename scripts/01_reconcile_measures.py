"""
HW6 Part B - Reconcile Power BI DAX measures to independent pandas calculations.

Run from the hw06 folder:
    python scripts/01_reconcile_measures.py              # reconcile
    python scripts/01_reconcile_measures.py --print-dax  # regenerate the Power BI export query

Inputs : the Wildcat Capital Clean CSVs (hw06 root) and reports/powerbi_values.csv
Output : reports/measure_reconciliation.csv
pandas never reads anything from Power BI; the two sides only meet in the final merge.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PBI_FILE = REPORTS / "powerbi_values.csv"
OUT_FILE = REPORTS / "measure_reconciliation.csv"

CURRENCY = {"AUM (naive SUM)", "Ending AUM", "Ending AUM LY", "Ending AUM PM",
            "Avg AUM per Client", "Avg Monthly AUM"}
TEXT = {"Alpha Signal"}
BPS = {"Fee Yield (bps)"}
COUNT = {"Ending Clients"}
TOL_CURRENCY, TOL_RATIO, TOL_BPS, TOL_COUNT = 0.01, 0.0001, 0.001, 0.0  # counts must match exactly

# ---------------------------------------------------------------- load data
def load():
    client = pd.read_csv(ROOT / "dim_client.csv", usecols=["client_id", "client_tier"])
    snap = pd.read_csv(ROOT / "fact_portfolio_snapshot.csv", parse_dates=["snapshot_date"])
    fees = pd.read_csv(ROOT / "fact_fees.csv", parse_dates=["fee_date"])
    txns = pd.read_csv(ROOT / "fact_transactions.csv", parse_dates=["txn_date"])
    # tier comes from dim_client, the same way the Power BI relationship filters it
    snap = snap.merge(client, on="client_id", how="left")
    fees = fees.merge(client, on="client_id", how="left")
    txns = txns.merge(client, on="client_id", how="left")
    return snap, fees, txns

# ---------------------------------------------------------------- slices
# A slice = date window + optional tier, mirroring the filter context in Power BI.
def make_slice(start, end, tier=None):
    return {"start": pd.Timestamp(start), "end": pd.Timestamp(end), "tier": tier}

def shift(sl, years=0, months=0):
    off = pd.DateOffset(years=years, months=months)
    # Shift the end, then snap to the last day of that month. Assumes every window ends on a
    # month end (true for all slices here: Dec 31 year-ends and Dec 2024), like DAX's full-month shift.
    end = (sl["end"] - off) + pd.offsets.MonthEnd(0)
    return {"start": sl["start"] - off, "end": end, "tier": sl["tier"]}

def cut(df, col, sl):
    m = (df[col] >= sl["start"]) & (df[col] <= sl["end"])
    if sl["tier"]:
        m &= df["client_tier"] == sl["tier"]
    return df[m]

# ---------------------------------------------------------------- measures
class Pandas:
    def __init__(self, snap, fees, txns):
        self.snap, self.fees, self.txns = snap, fees, txns

    def _s(self, sl):  return cut(self.snap, "snapshot_date", sl)

    def _last(self, sl):
        s = self._s(sl)
        return s[s["snapshot_date"] == s["snapshot_date"].max()] if len(s) else s

    def naive_sum(self, sl):      return self._s(sl)["aum"].sum()
    def ending_aum(self, sl):
        x = self._last(sl);  return x["aum"].sum() if len(x) else np.nan
    def ending_clients(self, sl):
        x = self._last(sl);  return x["client_id"].nunique() if len(x) else np.nan
    def avg_per_client(self, sl): return self.ending_aum(sl) / self.ending_clients(sl)
    def ending_ly(self, sl):      return self.ending_aum(shift(sl, years=1))
    def ending_pm(self, sl):      return self.ending_aum(shift(sl, months=1))
    def yoy(self, sl):
        ly = self.ending_ly(sl);  return (self.ending_aum(sl) - ly) / ly
    def mom(self, sl):
        pm = self.ending_pm(sl);  return (self.ending_aum(sl) - pm) / pm
    def avg_monthly(self, sl):
        s = self._s(sl);  return s["aum"].sum() / s["snapshot_date"].nunique()
    def fee_yield(self, sl):
        fees = cut(self.fees, "fee_date", sl)["amount"].sum()
        return fees * 12 * 10000 / self._s(sl)["aum"].sum()
    def net_flows(self, sl):
        t = cut(self.txns, "txn_date", sl)
        return (t.loc[t["txn_type"] == "Deposit", "amount"].sum()
                - t.loc[t["txn_type"] == "Withdrawal", "amount"].sum())
    def organic(self, sl):        return self.net_flows(sl) / self.ending_ly(sl)
    def w_alpha(self, sl):
        x = self._last(sl)
        x = x[(x["is_return_suspect"] == 0) & x["active_alpha_ytd"].notna()]
        return (x["aum"] * x["active_alpha_ytd"]).sum() / x["aum"].sum() if len(x) else np.nan
    def alpha_signal(self, sl):
        a = self.w_alpha(sl)
        if pd.isna(a):  return ""
        if a >= 0.02:   return "Outperforming"
        if a <= -0.02:  return "Lagging"
        return "In line"
    def top10(self, sl):
        by_client = self._last(sl).groupby("client_id")["aum"].sum()
        return by_client.nlargest(10).sum() / by_client.sum()

MEASURES = {   # Power BI measure name -> pandas method
    "AUM (naive SUM)": "naive_sum", "Ending AUM": "ending_aum", "Ending Clients": "ending_clients",
    "Avg AUM per Client": "avg_per_client", "Ending AUM LY": "ending_ly", "AUM YoY %": "yoy",
    "Ending AUM PM": "ending_pm", "AUM MoM %": "mom", "Avg Monthly AUM": "avg_monthly",
    "Fee Yield (bps)": "fee_yield", "Organic Growth Rate": "organic",
    "AUM-Weighted Alpha": "w_alpha", "Alpha Signal": "alpha_signal",
    "Top 10 Client Share": "top10",
}
BY_YEAR = ["Ending AUM", "Ending AUM LY", "AUM YoY %", "Avg Monthly AUM", "Fee Yield (bps)",
           "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal"]
BY_TIER = ["Ending AUM", "Avg AUM per Client", "Ending AUM LY", "AUM YoY %", "Fee Yield (bps)",
           "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal", "Top 10 Client Share"]
DEC_2024 = ["Ending AUM PM", "AUM MoM %"]
TIERS = ["Retail", "HNW", "UHNW"]

def plan():
    """(measure, slice label, pandas slice, DAX filter args) for every required row."""
    rows = [(m, "Total", make_slice("2020-01-01", "2024-12-31"), "") for m in MEASURES]
    for y in range(2020, 2025):
        for m in BY_YEAR:
            rows.append((m, str(y), make_slice(f"{y}-01-01", f"{y}-12-31"), f"dim_date[year] = {y}"))
    for t in TIERS:
        for m in BY_TIER:
            rows.append((m, f"2024|{t}", make_slice("2024-01-01", "2024-12-31", t),
                         f'dim_date[year] = 2024, dim_client[client_tier] = "{t}"'))
    for m in DEC_2024:
        rows.append((m, "2024-12", make_slice("2024-12-01", "2024-12-31"),
                     "dim_date[year] = 2024, dim_date[month] = 12"))
    return rows

# ---------------------------------------------------------------- DAX export query
def dax_query():
    lines = []
    for m, label, _, filt in plan():
        expr = f"[{m}]" if not filt else f"CALCULATE ( [{m}], {filt} )"
        if m not in TEXT:  # FORMAT = full precision as text, immune to display formatting
            expr = f'FORMAT ( {expr}, "0.000000000000" )'
        lines.append(f'    ROW ( "measure", "{m}", "slice", "{label}", "value", {expr} )')
    return "EVALUATE\nUNION (\n" + ",\n".join(lines) + "\n)\n"

# ---------------------------------------------------------------- reconcile
def read_powerbi():
    pbi = pd.read_csv(PBI_FILE, sep=",", dtype=str, keep_default_na=False)
    pbi.columns = [c.strip().strip("[]").split("[")[-1].lower() for c in pbi.columns]
    if "measure" not in pbi.columns:  # grid was copied without its header row
        pbi = pd.read_csv(PBI_FILE, sep=",", dtype=str, keep_default_na=False,
                          header=None, names=["measure", "slice", "value"])
    for c in ["measure", "slice", "value"]:
        pbi[c] = pbi[c].str.strip()
    dupes = pbi[pbi.duplicated(["measure", "slice"], keep=False)]
    if len(dupes):
        sys.exit(f"Duplicate measure/slice rows in {PBI_FILE}:\n{dupes.to_string(index=False)}")
    return pbi[["measure", "slice", "value"]]

def compare(measure, pbi_raw, pd_val, present):
    if not present:                            # row absent from the export = fail, never a match
        return np.nan, pd_val, np.nan, False
    if measure not in TEXT and np.isinf(pd_val):
        pd_val = np.nan                        # DAX DIVIDE returns BLANK where pandas gives inf
    if measure in TEXT:
        pv = "" if pd.isna(pbi_raw) else str(pbi_raw)
        return pv, pd_val, np.nan, pv == pd_val
    pv = pd.to_numeric(pbi_raw, errors="coerce")
    if pd.isna(pv) and pd.isna(pd_val):        # both blank (e.g. 2020 YoY) = match
        return pv, pd_val, np.nan, True
    diff = abs(pv - pd_val)
    tol = (TOL_CURRENCY if measure in CURRENCY else TOL_BPS if measure in BPS
           else TOL_COUNT if measure in COUNT else TOL_RATIO)
    return pv, pd_val, diff, bool(diff <= tol)

def main():
    if "--print-dax" in sys.argv:
        print(dax_query());  return
    calc = Pandas(*load())
    pandas_rows = [(m, label, getattr(calc, MEASURES[m])(sl)) for m, label, sl, _ in plan()]
    if not PBI_FILE.exists():
        sys.exit(f"Missing {PBI_FILE}. Export it from Power BI first (see walkthrough Phase 4).")
    pbi = read_powerbi().set_index(["measure", "slice"])["value"]
    out = []
    for m, label, pd_val in pandas_rows:
        present = (m, label) in pbi.index
        raw = pbi[(m, label)] if present else np.nan
        pv, pdv, diff, ok = compare(m, raw, pd_val, present)
        out.append({"measure": m, "slice": label, "powerbi_value": pv,
                    "pandas_value": pdv, "abs_diff": diff, "match": ok,
                    "row_present": present})
    res = pd.DataFrame(out)
    REPORTS.mkdir(exist_ok=True)
    res.to_csv(OUT_FILE, index=False)
    print(f"{len(res)} rows, {res['match'].sum()} match, {(~res['match']).sum()} mismatch -> {OUT_FILE}")
    extra = set(pbi.index) - {(m, l) for m, l, _ in pandas_rows}
    if extra:
        print(f"Note: {len(extra)} Power BI row(s) not in the plan (ignored): {sorted(extra)}")
    if (~res["match"]).any():
        print(res[~res["match"]].to_string(index=False))

if __name__ == "__main__":
    main()
