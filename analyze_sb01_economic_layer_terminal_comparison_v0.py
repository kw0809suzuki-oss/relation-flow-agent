#!/usr/bin/env python3
"""SB-01 Economic Layer -> Terminal comparison v0.

Existing 50-battle data only. Compares broad observable layers on one frame:
Cash, liquidatable inventory, committed production (crop/animal), unlocked land,
empty land. No composite score is formed.
"""
import json, statistics, sys
from pathlib import Path

DAYS=(1,6,8)

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
      "low_mean_metric":mean([x for x,_ in lo]),
      "high_mean_metric":mean([x for x,_ in hi]),
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

def value(side,metric):
    if metric=="cash":return float(side["cash"])
    if metric=="inventory":return float(side["liquidatable_inventory"]["display_price_mark"])
    if metric=="production_total":return float(side["committed_production"]["same_basis_subtotal"])
    if metric=="production_crop":return float(side["committed_production"]["crop_current_price_potential_mark"])
    if metric=="production_animal":return float(side["committed_production"]["animal_base_current_price_potential_mark"])
    if metric=="unlocked_tiles":return float(side["uncommitted_capacity"]["unlocked_tiles"])
    if metric=="empty_tiles":return float(side["uncommitted_capacity"]["empty_unlocked_tiles"])
    raise KeyError(metric)

def relation(cases,day,metric,target):
    xs=[];ys=[]
    for c in cases:
        row=c["days"][day]
        if target=="self":
            xs.append(value(row["self"],metric));ys.append(c["terminal_self"])
        else:
            xs.append(value(row["opponent"],metric)-value(row["self"],metric));ys.append(c["terminal_margin"])
    return {
      "pearson":pearson(xs,ys),
      "spearman":spearman(xs,ys),
      "quartile":quartile(xs,ys),
      "metric_mean":mean(xs),
      "metric_min":min(xs),"metric_max":max(xs)
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    cases=load(root)
    metrics=("cash","inventory","production_total","production_crop","production_animal","unlocked_tiles","empty_tiles")
    days={}
    for d in DAYS:
        days[str(d)]={}
        for m in metrics:
            days[str(d)][m]={
              "self_vs_terminal_self":relation(cases,d,m,"self"),
              "gap_vs_terminal_margin":relation(cases,d,m,"gap")
            }

    payload={
      "schema":"kaggriculture.sb01.economic-layer-terminal-comparison.v0",
      "battle_count":len(cases),"days":days,
      "boundary":[
        "All layers are compared separately; no composite economic score is created.",
        "Correlations and quartile separation are descriptive association only.",
        "The purpose is to identify which broad layer deserves further investigation relative to the remaining terminal residual."
      ]
    }
    Path("sb01_economic_layer_terminal_comparison_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")

    compact={}
    for d in DAYS:
        compact[str(d)]={}
        for m in metrics:
            r=days[str(d)][m]["self_vs_terminal_self"]
            g=days[str(d)][m]["gap_vs_terminal_margin"]
            compact[str(d)][m]={
              "self_terminal_pearson":r["pearson"],
              "self_terminal_spearman":r["spearman"],
              "self_terminal_quartile_delta":r["quartile"]["terminal_high_minus_low"],
              "gap_margin_pearson":g["pearson"],
              "gap_margin_spearman":g["spearman"],
              "gap_margin_quartile_delta":g["quartile"]["terminal_high_minus_low"]
            }
    print("SB01_ECONOMIC_LAYER_TERMINAL "+json.dumps({"battle_count":len(cases),"days":compact},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
