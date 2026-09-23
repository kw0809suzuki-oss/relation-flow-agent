#!/usr/bin/env python3
"""SB-01 Day0-7 BUY_PRODUCT decomposition v0.\n\nRun marker: first paired decomposition.

Existing exact Cash-flow artifacts only.
Pair unit: opponent - self by seed.
No judgment about necessity, excess, or replaceability.
"""
import json, math, statistics, sys
from pathlib import Path

ITEMS=("WHEAT","FERTILIZER")
DAYS=range(0,8)

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def q(xs,p):
    ys=sorted(xs)
    if not ys:return None
    pos=(len(ys)-1)*p
    lo=int(math.floor(pos));hi=int(math.ceil(pos))
    if lo==hi:return ys[lo]
    return ys[lo]*(hi-pos)+ys[hi]*(pos-lo)
def summarize(xs):
    return {
      "n":len(xs),"mean":mean(xs),"median":median(xs),
      "q25":q(xs,.25),"q75":q(xs,.75),
      "positive":sum(x>0 for x in xs),
      "negative":sum(x<0 for x in xs),
      "zero":sum(x==0 for x in xs),
      "min":min(xs) if xs else None,"max":max(xs) if xs else None,
    }
def load(root):
    out={}
    for p in root.glob("**/sb01_exact_cash_flow_daily_*.json"):
        if "aggregate" in p.name: continue
        r=json.loads(p.read_text(encoding="utf-8"))
        out[int(r["seed"])]=r
    if len(out)!=50: raise SystemExit(f"Expected 50, got {len(out)}")
    return out
def item_totals(r,side,item):
    cash=0.0; units=0
    daily=r[side].get("daily_ledger",{})
    du=r[side].get("daily_executed_units",{})
    key=f"BUY_PRODUCT:{item}"
    for d in DAYS:
        cash += -float((daily.get(str(d),{}) or {}).get(key,0.0))
        units += int((du.get(str(d),{}) or {}).get(key,0))
    return cash,units
def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    cases=load(root)
    rows=[]
    for seed in sorted(cases):
        r=cases[seed]
        row={"seed":seed}
        for item in ITEMS:
            sc,su=item_totals(r,"self",item)
            oc,ou=item_totals(r,"opponent",item)
            row[item]={
              "self_cash":sc,"opponent_cash":oc,"cash_gap_opponent_minus_self":oc-sc,
              "self_units":su,"opponent_units":ou,"unit_gap_opponent_minus_self":ou-su,
            }
        rows.append(row)
    out={}
    for item in ITEMS:
        out[item]={
          "self_cash_absolute":summarize([r[item]["self_cash"] for r in rows]),
          "opponent_cash_absolute":summarize([r[item]["opponent_cash"] for r in rows]),
          "cash_gap_opponent_minus_self":summarize([r[item]["cash_gap_opponent_minus_self"] for r in rows]),
          "self_units_absolute":summarize([r[item]["self_units"] for r in rows]),
          "opponent_units_absolute":summarize([r[item]["opponent_units"] for r in rows]),
          "unit_gap_opponent_minus_self":summarize([r[item]["unit_gap_opponent_minus_self"] for r in rows]),
        }
    total_gap=[sum(r[i]["cash_gap_opponent_minus_self"] for i in ITEMS) for r in rows]
    payload={
      "schema":"kaggriculture.sb01.day0-7-buy-product-decomposition.v0",
      "battle_count":50,
      "items":out,
      "total_buy_product_cash_gap":summarize(total_gap),
      "rows":rows,
      "boundary":[
        "Existing exact Cash-flow artifacts only.",
        "Pair unit is seed; all gaps are opponent minus self.",
        "Day0 through Day7 only, aligned to the first Day8 State snapshot.",
        "No claim is made that any BUY_PRODUCT spending is necessary, excessive, harmful, or replaceable."
      ]
    }
    Path("sb01_day0_7_buy_product_decomposition_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SB01_BUY_PRODUCT_DECOMP "+json.dumps({
      "battle_count":50,
      "total_gap":payload["total_buy_product_cash_gap"],
      "WHEAT":out["WHEAT"],
      "FERTILIZER":out["FERTILIZER"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
