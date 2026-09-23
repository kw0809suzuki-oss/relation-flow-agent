#!/usr/bin/env python3
import json,statistics,sys
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("sb01_exact_cash_flow_*.json"))
if not files: files=sorted(root.glob("**/sb01_exact_cash_flow_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not rows: raise SystemExit("No cash flow files")

bad=[r["seed"] for r in rows if r["self"]["error"]!=0 or r["opponent"]["error"]!=0]
if bad: raise SystemExit(f"Non-zero reconstruction error: {bad}")

all_keys=sorted(set().union(*[
    set(r["self"]["ledger"])|set(r["opponent"]["ledger"]) for r in rows
]))

def broad(ledger):
    gross_sell=sum(v for k,v in ledger.items() if k.startswith("SELL:"))
    buy_product=sum(v for k,v in ledger.items() if k.startswith("BUY_PRODUCT:"))
    buy_seed=sum(v for k,v in ledger.items() if k.startswith("BUY_SEED:"))
    buy_animal=sum(v for k,v in ledger.items() if k.startswith("BUY_ANIMAL:"))
    hire=ledger.get("HIRE",0)
    land=ledger.get("BUY_LAND",0)
    total_spend=buy_product+buy_seed+buy_animal+hire+land
    return {
      "gross_sell":gross_sell,
      "buy_product":buy_product,
      "buy_seed":buy_seed,
      "buy_animal":buy_animal,
      "hire":hire,
      "land":land,
      "total_spend":total_spend,
      "net_cash_flow":gross_sell+total_spend
    }

for r in rows:
    r["self_broad"]=broad(r["self"]["ledger"])
    r["opponent_broad"]=broad(r["opponent"]["ledger"])

def summary(vals_self,vals_opp):
    gaps=[o-s for s,o in zip(vals_self,vals_opp)]
    return {
      "self_absolute_mean":mean(vals_self),
      "opponent_absolute_mean":mean(vals_opp),
      "mean_gap_opponent_minus_self":mean(gaps),
      "median_gap_opponent_minus_self":median(gaps),
      "opponent_higher_cases":sum(g>0 for g in gaps),
      "self_higher_cases":sum(g<0 for g in gaps),
      "equal_cases":sum(g==0 for g in gaps),
      "min_gap":min(gaps),"max_gap":max(gaps)
    }

per_key={}
for k in all_keys:
    sv=[r["self"]["ledger"].get(k,0) for r in rows]
    ov=[r["opponent"]["ledger"].get(k,0) for r in rows]
    per_key[k]=summary(sv,ov)

broad_keys=("gross_sell","buy_product","buy_seed","buy_animal","hire","land","total_spend","net_cash_flow")
broad_summary={}
for k in broad_keys:
    broad_summary[k]=summary(
      [r["self_broad"][k] for r in rows],
      [r["opponent_broad"][k] for r in rows]
    )

terminal=summary(
  [r["self"]["actual_terminal"] for r in rows],
  [r["opponent"]["actual_terminal"] for r in rows]
)

# Positive contribution to opponent terminal advantage:
# For revenues, positive diff means opponent earned more.
# For negative-cost ledgers, positive diff means opponent spent less; negative diff means opponent spent more.
contrib=[]
for k,s in per_key.items():
    contrib.append({
      "key":k,
      "mean_gap_opponent_minus_self":s["mean_gap_opponent_minus_self"],
      "self_absolute_mean":s["self_absolute_mean"],
      "opponent_absolute_mean":s["opponent_absolute_mean"]
    })
contrib=sorted(contrib,key=lambda x:abs(x["mean_gap_opponent_minus_self"]),reverse=True)

out={
  "schema":"kaggriculture.sb01.exact-cash-flow-aggregate.v0",
  "battle_count":len(rows),
  "terminal_absolute":terminal,
  "broad":broad_summary,
  "per_key":per_key,
  "largest_absolute_cashflow_differences":contrib,
  "cases":rows,
  "boundary":[
    "Every case passed exact Cash reconstruction with zero error for self and opponent.",
    "Ledger values are realized Cash deltas under public execution rules.",
    "Negative values are expenditures; positive values are sale income.",
    "This is accounting decomposition only, not causal attribution or intervention value."
  ]
}
Path("sb01_exact_cash_flow_aggregate_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("SB01_EXACT_CASH_FLOW_AGG "+json.dumps({
  "battle_count":len(rows),
  "terminal":terminal,
  "broad":broad_summary,
  "top_differences":contrib[:15]
},ensure_ascii=False,separators=(",",":")))
