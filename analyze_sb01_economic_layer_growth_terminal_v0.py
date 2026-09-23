#!/usr/bin/env python3
"""SB-01 Economic Layer Growth -> Terminal validation v0.

Existing 50-battle snapshots only.
Tests interval changes rather than static levels:
Day1->6 and Day6->8 for Cash, Inventory, Production, Land/Empty capacity.
"""
import json,statistics,sys
from pathlib import Path

INTERVALS=((1,6),(6,8))
METRICS=("cash","inventory","production_total","production_crop","production_animal","unlocked_tiles","empty_tiles")

def mean(xs):return sum(xs)/len(xs) if xs else None

def pearson(xs,ys):
    if len(xs)<2:return None
    mx,my=mean(xs),mean(ys)
    dx=[x-mx for x in xs];dy=[y-my for y in ys]
    den=(sum(x*x for x in dx)*sum(y*y for y in dy))**0.5
    return None if den==0 else sum(x*y for x,y in zip(dx,dy))/den

def rank(xs):
    order=sorted(range(len(xs)),key=lambda i:xs[i]);r=[0.0]*len(xs);i=0
    while i<len(order):
        j=i
        while j+1<len(order) and xs[order[j+1]]==xs[order[i]]:j+=1
        rr=(i+j+2)/2
        for k in range(i,j+1):r[order[k]]=rr
        i=j+1
    return r

def spearman(xs,ys):return pearson(rank(xs),rank(ys))

def quartile(xs,ys):
    p=sorted(zip(xs,ys),key=lambda z:z[0]);q=max(1,len(p)//4)
    lo=p[:q];hi=p[-q:]
    return {
      "low_mean_growth":mean([x for x,_ in lo]),
      "high_mean_growth":mean([x for x,_ in hi]),
      "low_mean_terminal":mean([y for _,y in lo]),
      "high_mean_terminal":mean([y for _,y in hi]),
      "terminal_high_minus_low":mean([y for _,y in hi])-mean([y for _,y in lo])
    }

def load(root):
    e=json.loads(next(root.glob("early/**/sb01_early_daily_economic_localization_v0.json")).read_text())
    l=json.loads(next(root.glob("later/**/sb01_economic_layers_v0.json")).read_text())
    out={}
    for c in e["cases"]:
        out[int(c["seed"])]={
          "terminal_self":float(c["terminal"]["self"]),
          "terminal_margin":float(c["terminal"]["margin"]),
          "days":{int(d):row for d,row in c["days"].items()}
        }
    for c in l["cases"]:
        s=int(c["seed"])
        for d,row in c["days"].items():out[s]["days"][int(d)]=row
    return [out[k] for k in sorted(out)]

def val(side,m):
    if m=="cash":return float(side["cash"])
    if m=="inventory":return float(side["liquidatable_inventory"]["display_price_mark"])
    if m=="production_total":return float(side["committed_production"]["same_basis_subtotal"])
    if m=="production_crop":return float(side["committed_production"]["crop_current_price_potential_mark"])
    if m=="production_animal":return float(side["committed_production"]["animal_base_current_price_potential_mark"])
    if m=="unlocked_tiles":return float(side["uncommitted_capacity"]["unlocked_tiles"])
    if m=="empty_tiles":return float(side["uncommitted_capacity"]["empty_unlocked_tiles"])
    raise KeyError(m)

def rel(cases,a,b,m,target):
    xs=[];ys=[]
    for c in cases:
        ra,rb=c["days"][a],c["days"][b]
        if target=="self":
            growth=val(rb["self"],m)-val(ra["self"],m)
            y=c["terminal_self"]
        else:
            ga=val(ra["opponent"],m)-val(ra["self"],m)
            gb=val(rb["opponent"],m)-val(rb["self"],m)
            growth=gb-ga
            y=c["terminal_margin"]
        xs.append(growth);ys.append(y)
    return {
      "pearson":pearson(xs,ys),"spearman":spearman(xs,ys),
      "quartile":quartile(xs,ys),
      "growth_mean":mean(xs),"growth_min":min(xs),"growth_max":max(xs)
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    cases=load(root)
    out={}
    for a,b in INTERVALS:
        key=f"{a}_to_{b}";out[key]={}
        for m in METRICS:
            out[key][m]={
              "self_growth_vs_terminal_self":rel(cases,a,b,m,"self"),
              "gap_growth_vs_terminal_margin":rel(cases,a,b,m,"gap")
            }

    payload={
      "schema":"kaggriculture.sb01.economic-layer-growth-terminal.v0",
      "battle_count":len(cases),"intervals":out,
      "boundary":[
        "Uses changes between existing snapshot valuations; no new Battle or Observer.",
        "Each layer remains separate; no composite score is formed.",
        "Association is descriptive and does not establish causality."
      ]
    }
    Path("sb01_economic_layer_growth_terminal_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    compact={}
    for k,v in out.items():
        compact[k]={}
        for m,r in v.items():
            s=r["self_growth_vs_terminal_self"];g=r["gap_growth_vs_terminal_margin"]
            compact[k][m]={
              "self_growth_pearson":s["pearson"],"self_growth_spearman":s["spearman"],
              "self_growth_quartile_delta":s["quartile"]["terminal_high_minus_low"],
              "gap_growth_pearson":g["pearson"],"gap_growth_spearman":g["spearman"],
              "gap_growth_quartile_delta":g["quartile"]["terminal_high_minus_low"]
            }
    print("SB01_ECONOMIC_LAYER_GROWTH_TERMINAL "+json.dumps({"battle_count":len(cases),"intervals":compact},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
