#!/usr/bin/env python3
"""Aggregate LAND Empty Co-location Predictive Audit v0."""
import json, statistics, sys
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def summ(xs):
    xs=[float(x) for x in xs if x is not None]
    return {"n":len(xs),"mean":mean(xs),"median":median(xs),"min":min(xs) if xs else None,"max":max(xs) if xs else None}

def sc(side):
    es=side.get("episodes",[])
    eligible=[e for e in es if not e.get("censored",False)]
    hit=[e for e in eligible if e.get("duplicate_within_2_actions")]
    return {
      "episodes":len(es),
      "eligible":len(eligible),
      "censored":len(es)-len(eligible),
      "hits":len(hit),
      "failed_plants":sum(e["outcome"]["duplicate"]["failed_count"] for e in hit),
      "delay0":sum(e["outcome"]["delay_actions"]==0 for e in hit),
      "delay1":sum(e["outcome"]["delay_actions"]==1 for e in hit),
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/land_empty_colocation_predictive_audit_v0_*.json"))
    if len(files)!=50: raise SystemExit(f"Expected 50 files, got {len(files)}")
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    rows.sort(key=lambda r:int(r["seed"]))
    cases=[]
    for r in rows:
        cases.append({"seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
                      "self":sc(r["self"]),"opponent":sc(r["opponent"])})
    agg={}
    for side in ("self","opponent"):
        ep=sum(c[side]["episodes"] for c in cases)
        eligible=sum(c[side]["eligible"] for c in cases)
        censored=sum(c[side]["censored"] for c in cases)
        hits=sum(c[side]["hits"] for c in cases)
        agg[side]={
          "episodes_total":ep,
          "eligible_episodes_total":eligible,
          "censored_episodes_total":censored,
          "episodes_per_battle":summ([c[side]["episodes"] for c in cases]),
          "hit_episodes_total":hits,
          "hit_episodes_per_battle":summ([c[side]["hits"] for c in cases]),
          "hit_rate":hits/eligible if eligible else None,
          "cases_with_any_episode":sum(c[side]["episodes"]>0 for c in cases),
          "cases_with_any_hit":sum(c[side]["hits"]>0 for c in cases),
          "delay0_total":sum(c[side]["delay0"] for c in cases),
          "delay1_total":sum(c[side]["delay1"] for c in cases),
          "failed_plants_from_hits_total":sum(c[side]["failed_plants"] for c in cases),
        }
    terminal={
      "mean_self":mean([float(r["terminal"]["self"]) for r in rows]),
      "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in rows]),
      "mean_margin":mean([float(r["terminal"]["margin"]) for r in rows]),
      "wins":sum(float(r["terminal"]["margin"])>0 for r in rows),
    }
    payload={
      "schema":"kaggriculture.land-empty-colocation-predictive-audit.aggregate.v0",
      "battle_count":len(rows),"terminal_absolute":terminal,
      "self":agg["self"],"opponent":agg["opponent"],"cases":cases,
      "boundary":[
        "Hit rate is predictive association from empty-tile co-location onset to valid duplicate PLANT within two same-day actions and within the same +72-turn observation window.",
        "Censored episodes with no observable next action inside the window are excluded from the hit-rate denominator.",
        "It is not a causal effect or terminal-value estimate."
      ]
    }
    Path("land_empty_colocation_predictive_audit_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("LAND_EMPTY_COLOCATION_PREDICTIVE_AUDIT_AGG "+json.dumps({
      "battle_count":len(rows),"terminal":terminal,"self":agg["self"],"opponent":agg["opponent"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
