#!/usr/bin/env python3
"""SB-01 paired capital-allocation chain validation v0.

Existing 50-battle artifacts only. No new Battle / Observer.

Pair unit: one seed, using opponent - self differences.
No seed fixed effects are fitted because differencing already absorbs
seed-common conditions.

Chain:
  Day8 allocation difference
  -> Day10/12 productive-State difference
  -> Day14-29 realized non-WHEAT sales difference

Primary outputs are sign consistency, median/IQR, trimmed mean, and
concentration in the largest absolute seed gaps. Correlation/regression are
secondary descriptive checks only.
"""
import json, math, statistics, sys
from pathlib import Path

NONWHEAT=("STRAWBERRY","MELON","MILK","WOOL","FERTILIZER")

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def q(xs,p):
    ys=sorted(xs)
    if not ys: return None
    pos=(len(ys)-1)*p
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return ys[lo]
    return ys[lo]*(hi-pos)+ys[hi]*(pos-lo)
def trimmed_mean(xs, frac=.1):
    ys=sorted(xs); n=len(ys); k=int(n*frac)
    zs=ys[k:n-k] if n-2*k>0 else ys
    return mean(zs)
def summarize(xs):
    return {
      "n":len(xs),
      "mean":mean(xs),
      "median":median(xs),
      "q25":q(xs,.25),
      "q75":q(xs,.75),
      "trimmed_mean_10pct":trimmed_mean(xs,.1),
      "positive":sum(x>0 for x in xs),
      "negative":sum(x<0 for x in xs),
      "zero":sum(x==0 for x in xs),
      "min":min(xs) if xs else None,
      "max":max(xs) if xs else None,
    }
def pearson(x,y):
    if len(x)<2: return None
    mx,my=mean(x),mean(y)
    dx=[a-mx for a in x]; dy=[b-my for b in y]
    den=(sum(a*a for a in dx)*sum(b*b for b in dy))**.5
    if den==0: return None
    return sum(a*b for a,b in zip(dx,dy))/den
def ranks(xs):
    order=sorted(range(len(xs)),key=lambda i:xs[i])
    out=[0.0]*len(xs); i=0
    while i<len(order):
        j=i
        while j+1<len(order) and xs[order[j+1]]==xs[order[i]]: j+=1
        r=(i+j)/2+1
        for k in range(i,j+1): out[order[k]]=r
        i=j+1
    return out
def spearman(x,y): return pearson(ranks(x),ranks(y))
def load_one(root,name):
    hits=list(root.glob(f"**/{name}"))
    if not hits: raise SystemExit(f"Missing {name}")
    return json.loads(hits[0].read_text(encoding="utf-8"))
def idx(payload): return {int(c["seed"]):c for c in payload["cases"]}
def load_cash(root):
    out={}
    for p in root.glob("**/sb01_exact_cash_flow_daily_*.json"):
        if "aggregate" in p.name: continue
        r=json.loads(p.read_text(encoding="utf-8"))
        out[int(r["seed"])]=r
    if len(out)!=50: raise SystemExit(f"Expected 50 cash cases, got {len(out)}")
    return out
def spend_through_day7(r,side):
    # Day8 state is first snapshot of Day8: only Day0..7 realized spend.
    led=r[side].get("daily_ledger",{})
    structural=buy_product=total=0.0
    for d in range(8):
        for k,v0 in (led.get(str(d),{}) or {}).items():
            v=float(v0)
            if v>=0: continue
            cost=-v; total+=cost
            if k.startswith("BUY_PRODUCT:"): buy_product+=cost
            elif k.startswith("BUY_SEED:") or k.startswith("BUY_ANIMAL:") or k=="HIRE" or k=="BUY_LAND":
                structural+=cost
    return structural,buy_product,total
def later_nonwheat_sales(r,side):
    led=r[side].get("daily_ledger",{})
    total=0.0
    by={k:0.0 for k in NONWHEAT}
    for d in range(14,30):
        for item in NONWHEAT:
            v=float((led.get(str(d),{}) or {}).get(f"SELL:{item}",0.0))
            if v>0:
                by[item]+=v; total+=v
    return total,by
def prod_axes(case,day,side):
    x=case["days"][str(day)][side]
    c=x["committed_production"]["crop_count"]
    a=x["committed_production"]["animal_count"]
    return {
      "high_crop":float(c.get("STRAWBERRY",0)+c.get("MELON",0)),
      "high_animal":float(a.get("COW",0)+a.get("SHEEP",0)),
      "committed":float(x["committed_production"]["same_basis_subtotal"]),
      "land":float(x["uncommitted_capacity"]["unlocked_tiles"]),
    }
def concentration(rows,key):
    vals=[(r["seed"],r[key]) for r in rows]
    total=sum(abs(v) for _,v in vals)
    ranked=sorted(vals,key=lambda z:abs(z[1]),reverse=True)
    return {
      "abs_total":total,
      "top5_abs_share":sum(abs(v) for _,v in ranked[:5])/total if total else None,
      "top10_abs_share":sum(abs(v) for _,v in ranked[:10])/total if total else None,
      "top5":[{"seed":s,"value":v} for s,v in ranked[:5]]
    }
def same_direction(a,b):
    pairs=[(x,y) for x,y in zip(a,b) if x!=0 and y!=0]
    return {
      "eligible":len(pairs),
      "same_sign":sum((x>0)==(y>0) for x,y in pairs),
      "opposite_sign":sum((x>0)!=(y>0) for x,y in pairs),
      "same_sign_rate":sum((x>0)==(y>0) for x,y in pairs)/len(pairs) if pairs else None,
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    later=idx(load_one(root,"sb01_economic_layers_v0.json"))
    cash=load_cash(root)
    seeds=sorted(set(later)&set(cash))
    if len(seeds)!=50: raise SystemExit(f"Expected 50 common seeds, got {len(seeds)}")

    rows=[]
    for s in seeds:
        cr=cash[s]
        ss,sbp,st=spend_through_day7(cr,"self")
        os,obp,ot=spend_through_day7(cr,"opponent")
        sales_s,by_s=later_nonwheat_sales(cr,"self")
        sales_o,by_o=later_nonwheat_sales(cr,"opponent")
        r={
          "seed":s,
          "day8_structural_spend_gap":os-ss,
          "day8_buy_product_spend_gap":obp-sbp,
          "day8_total_outflow_gap":ot-st,
          "day14_29_nonwheat_sales_gap":sales_o-sales_s,
        }
        for item in NONWHEAT:
            r[f"day14_29_{item.lower()}_sales_gap"]=by_o[item]-by_s[item]
        for d in (10,12):
            sa=prod_axes(later[s],d,"self"); oa=prod_axes(later[s],d,"opponent")
            for k in sa:
                r[f"day{d}_{k}_gap"]=oa[k]-sa[k]
        rows.append(r)

    keys=[
      "day8_structural_spend_gap","day8_buy_product_spend_gap","day8_total_outflow_gap",
      "day10_high_crop_gap","day10_high_animal_gap","day10_committed_gap","day10_land_gap",
      "day12_high_crop_gap","day12_high_animal_gap","day12_committed_gap","day12_land_gap",
      "day14_29_nonwheat_sales_gap",
    ]
    summaries={k:summarize([r[k] for r in rows]) for k in keys}
    conc={k:concentration(rows,k) for k in keys}

    x=[r["day8_structural_spend_gap"] for r in rows]
    relationships={}
    for yk in (
      "day10_high_crop_gap","day10_high_animal_gap","day10_committed_gap",
      "day12_high_crop_gap","day12_high_animal_gap","day12_committed_gap",
      "day14_29_nonwheat_sales_gap",
    ):
        y=[r[yk] for r in rows]
        relationships[yk]={
          "same_direction":same_direction(x,y),
          "pearson":pearson(x,y),
          "spearman":spearman(x,y),
        }

    # Chain-stage pairwise sign consistency.
    chain={}
    for mid in ("day10_high_crop_gap","day10_high_animal_gap","day10_committed_gap",
                "day12_high_crop_gap","day12_high_animal_gap","day12_committed_gap"):
        a=[r[mid] for r in rows]
        b=[r["day14_29_nonwheat_sales_gap"] for r in rows]
        chain[mid]={
          "mid_vs_later_sales_same_direction":same_direction(a,b),
          "pearson":pearson(a,b),
          "spearman":spearman(a,b),
        }

    payload={
      "schema":"kaggriculture.sb01.paired-capital-allocation-chain-validation.v0",
      "battle_count":50,
      "pair_unit":"seed; all metrics are opponent minus self",
      "summaries":summaries,
      "concentration":conc,
      "day8_structural_to_later":relationships,
      "productive_state_to_later_sales":chain,
      "rows":rows,
      "boundary":[
        "No seed fixed effects are fitted; seed-common conditions are already differenced within each paired seed.",
        "Primary evidence is time order, sign consistency, median/IQR, trimmed mean, and concentration across 50 paired seeds.",
        "Pearson/Spearman are secondary descriptive checks only.",
        "No causal claim is made that structural spending increases terminal money.",
        "No intervention or strategy target is selected by this analysis."
      ]
    }
    Path("sb01_paired_capital_allocation_chain_validation_v0.json").write_text(
      json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    compact={
      "battle_count":50,
      "summaries":summaries,
      "top5_abs_share":{k:v["top5_abs_share"] for k,v in conc.items()},
      "day8_structural_to_later":relationships,
      "productive_state_to_later_sales":chain,
    }
    print("SB01_PAIRED_CHAIN "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
