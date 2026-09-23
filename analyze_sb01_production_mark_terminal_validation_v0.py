#!/usr/bin/env python3
"""SB-01 Production Mark -> Terminal validation v0.

Uses existing 50-battle artifacts only. No new Battle.
Tests whether early committed-production marks actually explain terminal outcome.

Primary questions:
- self Production Mark at Day 1/6/8 vs terminal self
- production gap (opponent-self) at Day 1/6/8 vs terminal margin
- crop vs animal components
- quartile separation as a scale check

This is validation, not causal attribution.
"""
import json, math, statistics, sys
from pathlib import Path

DAYS=(1,6,8)


def mean(xs): return sum(xs)/len(xs) if xs else None


def pearson(xs,ys):
    if len(xs)<2:return None
    mx,my=mean(xs),mean(ys)
    dx=[x-mx for x in xs];dy=[y-my for y in ys]
    den=(sum(a*a for a in dx)*sum(b*b for b in dy))**0.5
    if den==0:return None
    return sum(a*b for a,b in zip(dx,dy))/den


def rankdata(xs):
    order=sorted(range(len(xs)),key=lambda i:xs[i])
    ranks=[0.0]*len(xs)
    i=0
    while i<len(order):
        j=i
        while j+1<len(order) and xs[order[j+1]]==xs[order[i]]:
            j+=1
        r=(i+j+2)/2.0
        for k in range(i,j+1):ranks[order[k]]=r
        i=j+1
    return ranks


def spearman(xs,ys):
    return pearson(rankdata(xs),rankdata(ys))


def quartile_split(xs,ys):
    pairs=sorted(zip(xs,ys),key=lambda p:p[0])
    n=len(pairs)
    q=max(1,n//4)
    low=pairs[:q];high=pairs[-q:]
    return {
        "low_n":len(low),
        "high_n":len(high),
        "low_mean_metric":mean([x for x,_ in low]),
        "high_mean_metric":mean([x for x,_ in high]),
        "low_mean_terminal":mean([y for _,y in low]),
        "high_mean_terminal":mean([y for _,y in high]),
        "terminal_high_minus_low":mean([y for _,y in high])-mean([y for _,y in low]),
    }


def load_early(root):
    p=next(root.glob("early/**/sb01_early_daily_economic_localization_v0.json"))
    return json.loads(p.read_text(encoding="utf-8"))


def load_later(root):
    p=next(root.glob("later/**/sb01_economic_layers_v0.json"))
    return json.loads(p.read_text(encoding="utf-8"))


def index_cases(early,later):
    out={}
    for c in early["cases"]:
        out[int(c["seed"])]={
            "seed":int(c["seed"]),
            "terminal_self":float(c["terminal"]["self"]),
            "terminal_opponent":float(c["terminal"]["opponent"]),
            "terminal_margin":float(c["terminal"]["margin"]),
            "days":{}
        }
        for d in range(0,7):
            row=c["days"][str(d)]
            out[int(c["seed"])]["days"][d]=row
    for c in later["cases"]:
        seed=int(c["seed"])
        if seed not in out:
            out[seed]={
                "seed":seed,
                "terminal_self":float(c["terminal"]["self"]),
                "terminal_opponent":float(c["terminal"]["opponent"]),
                "terminal_margin":float(c["terminal"]["margin"]),
                "days":{}
            }
        for d in (6,8,10,12):
            out[seed]["days"][d]=c["days"][str(d)]
    return [out[k] for k in sorted(out)]


def getmark(side,kind):
    cp=side["committed_production"]
    if kind=="total":return float(cp["same_basis_subtotal"])
    if kind=="crop":return float(cp["crop_current_price_potential_mark"])
    if kind=="animal":return float(cp["animal_base_current_price_potential_mark"])
    raise KeyError(kind)


def relation(cases,day,kind,target):
    xs=[];ys=[]
    for c in cases:
        row=c["days"][day]
        if target=="self_terminal":
            x=getmark(row["self"],kind);y=c["terminal_self"]
        elif target=="gap_margin":
            x=getmark(row["opponent"],kind)-getmark(row["self"],kind)
            y=c["terminal_margin"]
        elif target=="opp_terminal":
            x=getmark(row["opponent"],kind);y=c["terminal_opponent"]
        else: raise KeyError(target)
        xs.append(x);ys.append(y)
    return {
        "n":len(xs),
        "pearson":pearson(xs,ys),
        "spearman":spearman(xs,ys),
        "quartiles":quartile_split(xs,ys),
        "metric_mean":mean(xs),
        "terminal_mean":mean(ys),
        "metric_min":min(xs),"metric_max":max(xs),
        "terminal_min":min(ys),"terminal_max":max(ys),
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    early=load_early(root)
    later=load_later(root)
    cases=index_cases(early,later)

    results={}
    for d in DAYS:
        results[str(d)]={}
        for kind in ("total","crop","animal"):
            results[str(d)][kind]={
                "self_mark_vs_terminal_self":relation(cases,d,kind,"self_terminal"),
                "production_gap_vs_terminal_margin":relation(cases,d,kind,"gap_margin"),
                "opponent_mark_vs_terminal_opponent":relation(cases,d,kind,"opp_terminal"),
            }

    # Direction consistency across days for the primary self relation.
    primary=[]
    for d in DAYS:
        r=results[str(d)]["total"]["self_mark_vs_terminal_self"]
        primary.append({"day":d,"pearson":r["pearson"],"spearman":r["spearman"],"quartile_terminal_delta":r["quartiles"]["terminal_high_minus_low"]})

    payload={
        "schema":"kaggriculture.sb01.production-mark-terminal-validation.v0",
        "battle_count":len(cases),
        "days":results,
        "primary_summary":primary,
        "boundary":[
            "Uses existing SB-01 50-battle artifacts only; no new policy execution.",
            "Production Mark is a valuation proxy, not realized Cash.",
            "Correlation and quartile separation are descriptive association only, not causal proof.",
            "The main decision use is whether Production Mark deserves to remain a main battlefield."
        ]
    }
    Path("sb01_production_mark_terminal_validation_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SB01_PRODUCTION_MARK_TERMINAL "+json.dumps({"battle_count":len(cases),"primary_summary":primary,"days":{
      str(d):{
        "total_self_vs_terminal":results[str(d)]["total"]["self_mark_vs_terminal_self"],
        "total_gap_vs_margin":results[str(d)]["total"]["production_gap_vs_terminal_margin"],
        "crop_self_vs_terminal":results[str(d)]["crop"]["self_mark_vs_terminal_self"],
        "animal_self_vs_terminal":results[str(d)]["animal"]["self_mark_vs_terminal_self"],
      } for d in DAYS
    }},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
