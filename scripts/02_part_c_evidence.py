"""HW6 Part C - pandas evidence for design questions (a)-(d). Run from the hw06 folder:
    python scripts/02_part_c_evidence.py
"""
import pandas as pd

s = pd.read_csv("fact_portfolio_snapshot.csv", parse_dates=["snapshot_date"])
f = pd.read_csv("fact_fees.csv", parse_dates=["fee_date"])
t = pd.read_csv("fact_transactions.csv", parse_dates=["txn_date"])
tier = pd.read_csv("dim_client.csv", usecols=["client_id", "client_tier"])
s, f, t = (d.merge(tier, on="client_id") for d in (s, f, t))

def ending(df):
    return df.loc[df.snapshot_date == df.snapshot_date.max(), "aum"].sum()

# (a) Ending AUM vs SUMX over clients
print("=== (a) Ending AUM vs SUMX(VALUES(client_id), [Ending AUM]) ===")
last_by_client = s.groupby("client_id").snapshot_date.transform("max")
per_client = s.loc[s.snapshot_date == last_by_client]
departed = per_client[per_client.snapshot_date < s.snapshot_date.max()]
print(f"Ending AUM (latest snapshot)       : {ending(s):,.2f}")
print(f"SUMX of each client's last balance : {per_client.aum.sum():,.2f}")
print(f"Difference                         : {per_client.aum.sum() - ending(s):,.2f}")
print(f"Clients whose last snapshot < 2024-12-01: {departed.client_id.nunique()}, "
      f"their last balances sum to {departed.aum.sum():,.2f}")
print("Departed clients' last snapshot by year:", departed.snapshot_date.dt.year.value_counts().sort_index().to_dict())

# (b) Fee Yield vs Effective Fee Rate, 2024
print("\n=== (b) 2024 Fee Yield vs Effective Fee Rate ===")
s24, f24 = s[s.snapshot_date.dt.year == 2024], f[f.fee_date.dt.year == 2024]
print(f"Fee Yield (fees / snapshot aum)          : {f24.amount.sum()*12e4 / s24.aum.sum():.4f} bps")
print(f"Effective Fee Rate (fees / aum_basis)    : {f24.amount.sum()*12e4 / f24.aum_basis.sum():.4f} bps")
print("Fee rows per client-month:", f24.groupby(["client_id", "fee_date"]).size().value_counts().to_dict())
k = s24.merge(f24[["client_id", "fee_date", "aum_basis"]], how="left", indicator=True,
              left_on=["client_id", "snapshot_date"], right_on=["client_id", "fee_date"])
print("Snapshot rows with / without a fee row:", k._merge.map({"both": "billed", "left_only": "no fee row"}).value_counts().to_dict())
unb = k[k._merge == "left_only"]
print(f"AUM with no fee row: {unb.aum.sum():,.2f} = {unb.aum.sum()/k.aum.sum():.2%} of 2024 snapshot AUM")
billed = k[k._merge == "both"]
print(f"aum_basis = snapshot aum on billed rows? max abs diff = {(billed.aum - billed.aum_basis).abs().max():.2f}")
print(f"Fee Yield on BILLED AUM only             : {f24.amount.sum()*12e4 / billed.aum.sum():.4f} bps  (= Effective Fee Rate)")
print("No-fee rows by month:", unb.snapshot_date.dt.month.value_counts().sort_index().to_dict())
print("No-fee rows by tier :", unb.client_tier.value_counts().to_dict())

# (c) Weighted alpha at last snapshot
print("\n=== (c) AUM-Weighted Alpha, latest snapshot (2024-12-01) ===")
x = s[s.snapshot_date == s.snapshot_date.max()]
clean = x[x.is_return_suspect == 0]
w = lambda d: (d.aum * d.active_alpha_ytd).sum() / d.aum.sum()
print(f"Rows at last snapshot: {len(x)}, suspect: {int(x.is_return_suspect.sum())}")
print(f"Weighted, suspects excluded : {w(clean):.4%}")
print(f"Simple mean, same rows      : {clean.active_alpha_ytd.mean():.4%}")
print(f"Weighted, suspects included : {w(x):.4%}")
print(f"Simple mean, suspects incl. : {x.active_alpha_ytd.mean():.4%}")
print(f"Suspect rows: mean alpha {x[x.is_return_suspect==1].active_alpha_ytd.mean():.2%}, "
      f"tiers {x[x.is_return_suspect==1].client_tier.value_counts().to_dict()}")
yr = s[s.snapshot_date.dt.year == 2024]
print(f"(Wrong) weighted over ALL 2024 months: {w(yr[yr.is_return_suspect==0]):.4%}")

# (d) Organic growth vs YoY by tier, 2024
print("\n=== (d) 2024 by tier: Organic Growth vs AUM YoY ===")
for tr in ["Retail", "HNW", "UHNW"]:
    a, b = s24[s24.client_tier == tr], s[(s.snapshot_date.dt.year == 2023) & (s.client_tier == tr)]
    tt = t[(t.txn_date.dt.year == 2024) & (t.client_tier == tr)]
    nf = tt.loc[tt.txn_type == "Deposit", "amount"].sum() - tt.loc[tt.txn_type == "Withdrawal", "amount"].sum()
    e, ly = ending(a), ending(b)
    print(f"{tr:7s} ending {e:>17,.2f}  LY {ly:>17,.2f}  growth $ {e-ly:>15,.2f}  net flows $ {nf:>14,.2f}"
          f"  organic {nf/ly:7.2%}  YoY {e/ly-1:7.2%}  non-flow growth {(e-ly-nf)/ly:7.2%}")
