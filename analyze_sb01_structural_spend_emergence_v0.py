#!/usr/bin/env python3
"""SB-01 structural spend emergence v0.\n\nRun marker: first emergence pass.

Existing exact daily Cash-flow artifacts only.
Observe when the Day8 prior structural-spend gap emerges and which category
contributes. No causal or strategy judgment.
"""
import json, math, statistics, sys
from pathlib import Path

CATS=("seed","animal","hire","land")
DAYS=range(0,8)

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def q(xs,p):
    ys=sorted(xs)
    if not ys:return None
    pos=(len(ys)-1)*p; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return ys[lo]
    return ys[lo]*(hi-pos)+ys[hi]*(pos-lo)
def summ(xs):
    return {"n":len(xs),"mean":mean(xs),"median":median(xs),"q25":q(xs,.25),"q75":q(xs,.75),
            "positive":sum(x>0 for x in xs),"negative":sum(x<0 for x in xs),"zero":sum(x==0 for x in xs),
            "min":min(xs) if xs else None,"max":max(xs) if xs else None}
def load(root):
    out={}
    for p in root.glob("**/sb01_exact_cash_flow_daily_*.json"):
        if "aggregate" in p.name: continue
        r=json.loads(p.read_text(encoding="utf-8"))
        out[int(r["seed"])]=r
    if len(out)!=50: raise SystemExit(f"Expected 50 files, got {len(out)}")
    return out
def classify(k):
    if k.startswith("BUY_SEED:"): return "seed"
    if k.startswith("BUY_ANIMAL:"): return "animal"
    if k=="HIRE": return "hire"
    if k=="BUY_LAND": return "land"
    return None
def side_day_spend(r,side):
    daily=r[side].get("daily_ledger",{})
    out={d:{c:0.0 for c in CATS} for d in DAYS}
    for d in DAYS:
        for k,v0 in (daily.get(str(d),{}) or {}).items():
            c=classify(k)
            if c is None: continue
            v=float(v0)
            if v<0: out[d][c]+=-v
    return out

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    cases=load(root)
    rows=[]
    for seed,r in sorted(cases.items()):
        s=side_day_spend(r,"self"); o=side_day_spend(r,"opponent")
        cum_s={c:0.0 for c in CATS}; cum_o={c:0.0 for c in CATS}
        byday={}
        for d in DAYS:
            for c in CATS:
                cum_s[c]+=s[d][c]; cum_o[c]+=o[d][c]
            byday[str(d)]={
              "self":dict(cum_s),
              "opponent":dict(cum_o),
              "gap_opponent_minus_self":{c:cum_o[c]-cum_s[c] for c in CATS},
              "structural_gap":sum(cum_o.values())-sum(cum_s.values()),
            }
        rows.append({"seed":seed,"days":byday})

    summary={}
    for d in DAYS:
        day={}
        for c in CATS:
            sv=[r["days"][str(d)]["self"][c] for r in rows]
            ov=[r["days"][str(d)]["opponent"][c] for r in rows]
            gv=[r["days"][str(d)]["gap_opponent_minus_self"][c] for r in rows]
            day[c]={"self_absolute":summ(sv),"opponent_absolute":summ(ov),"gap":summ(gv)}
        sg=[r["days"][str(d)]["structural_gap"] for r in rows]
        day["structural_total_gap"]=summ(sg)
        summary[str(d)]=day

    payload={
      "schema":"kaggriculture.sb01.structural-spend-emergence.v0",
      "battle_count":50,
      "days":summary,
      "rows":rows,
      "boundary":[
        "Existing exact realized Cash ledger only.",
        "Day d is cumulative realized structural spend through day d.",
        "Categories are BUY_SEED, BUY_ANIMAL, HIRE, BUY_LAND only.",
        "All gaps are opponent minus self.",
        "No category is labeled good, bad, necessary, excessive, or causal."
      ]
    }
    Path("sb01_structural_spend_emergence_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    compact={}
    for d in DAYS:
        compact[str(d)]={
          "structural_gap_mean":summary[str(d)]["structural_total_gap"]["mean"],
          "structural_gap_median":summary[str(d)]["structural_total_gap"]["median"],
          "positive":summary[str(d)]["structural_total_gap"]["positive"],
          "seed_gap":summary[str(d)]["seed"]["gap"]["mean"],
          "animal_gap":summary[str(d)]["animal"]["gap"]["mean"],
          "hire_gap":summary[str(d)]["hire"]["gap"]["mean"],
          "land_gap":summary[str(d)]["land"]["gap"]["mean"],
        }
    print("SB01_STRUCTURAL_EMERGENCE "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
